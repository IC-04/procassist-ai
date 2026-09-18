"""Pass 1 (screenshot indexing) and Phase 3 (hypothesis harness) contract tests."""
from __future__ import annotations

import glob
import json
import os

import pytest

from analysis.evidence import common as C
from analysis.evidence import hypotheses as H
from analysis.evidence import pass1_states as P1

ROOT = C.ROOT
DATASET_B = os.path.join(ROOT, "dataset_b")
EV = C.evidence_dir("dataset_b")
needs_b = pytest.mark.skipif(not os.path.isdir(DATASET_B), reason="dataset_b not present")
needs_pass1 = pytest.mark.skipif(not os.path.exists(os.path.join(EV, "states.jsonl")),
                                 reason="pass 1 not run")
needs_pass3 = pytest.mark.skipif(
    not os.path.exists(os.path.join(EV, "hypothesis_tests.json")), reason="pass 3 not run")


# ---------------------------------------------------------------- pHash

@needs_b
def test_phash_is_deterministic():
    p = sorted(glob.glob(os.path.join(DATASET_B, "*", "*", "screenshots", "*.jpg")))[:3]
    for path in p:
        assert P1.phash(path) == P1.phash(path)


@needs_b
def test_phash_is_stable_under_re_encoding(tmp_path):
    """A re-encoded copy of the same image must land on the same state, or the index would
    fragment on compression noise rather than on visual change."""
    from PIL import Image
    src = sorted(glob.glob(os.path.join(DATASET_B, "*", "*", "screenshots", "*.jpg")))[0]
    dst = tmp_path / "copy.jpg"
    with Image.open(src) as im:
        im.save(dst, quality=88)
    a, b = P1.phash(src), P1.phash(str(dst))
    hamming = bin(a ^ b).count("1")
    assert hamming <= 4, f"pHash moved {hamming} bits under re-encoding"


def test_phash_differs_for_visually_different_images(tmp_path):
    from PIL import Image
    import numpy as np
    rng = np.random.default_rng(0)
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(a)
    Image.fromarray((rng.random((64, 64)) * 255).astype(np.uint8)).save(b)
    assert P1.phash(str(a)) != P1.phash(str(b))


@needs_b
@needs_pass1
def test_states_partition_all_screenshots():
    states = [json.loads(l) for l in open(os.path.join(EV, "states.jsonl"), encoding="utf-8")]
    members = [m for s in states for m in s["member_screenshot_paths"]]
    assert len(members) == len(set(members)), "a screenshot belongs to two states"
    on_disk = {os.path.relpath(p, ROOT) for p in
               glob.glob(os.path.join(DATASET_B, "*", "*", "screenshots", "*.jpg"))}
    assert set(members) == on_disk
    for s in states:
        assert s["representative_screenshot_path"] in s["member_screenshot_paths"]
        assert s["n_members"] == len(s["member_screenshot_paths"])


@needs_b
@needs_pass1
def test_coverage_reports_all_three_window_definitions():
    rows = [json.loads(l) for l in
            open(os.path.join(EV, "coverage_gaps.jsonl"), encoding="utf-8")]
    assert rows
    for r in rows[:50]:
        for N in P1.WINDOWS:
            for kind in ("symmetric", "before_only", "normalised"):
                assert f"has_text_{kind}_{N}" in r
                assert f"dist_{kind}_{N}" in r
        assert "queue_table_captured" in r and "detail_pane_captured" in r
        # a before-only hit is by construction also a symmetric hit
        for N in P1.WINDOWS:
            if r[f"has_text_before_only_{N}"]:
                assert r[f"has_text_symmetric_{N}"]


# ---------------------------------------------------------------- hypotheses

def test_zero_variance_outcome_yields_untestable():
    ctx = {"outcomes": [{"module_id": "M01", "source": "toast", "outcome_polarity": "positive",
                         "outcome_id": f"o{i}"} for i in range(20)]}
    v = [t for t in H.h1(ctx) if t["module_id"] == "M01"][0]
    assert v["result"] == H.UNTESTABLE
    assert "constant" in v["reason"]
    assert v["n"] == 20


def test_insufficient_evidence_below_declared_floor_carries_its_n():
    ctx = {"outcomes": [{"module_id": "M01", "source": "toast", "outcome_polarity": "positive",
                         "outcome_id": f"o{i}"} for i in range(H.EVIDENCE_FLOOR - 1)]}
    v = [t for t in H.h1(ctx) if t["module_id"] == "M01"][0]
    assert v["result"] == H.INSUFFICIENT
    assert v["n"] == H.EVIDENCE_FLOOR - 1
    assert str(H.EVIDENCE_FLOOR) in v["reason"]


def test_all_eleven_modules_are_always_reported():
    ctx = {"outcomes": []}
    assert {t["module_id"] for t in H.h1(ctx)} == set(H.M.ALL_MODULE_IDS)


def test_permutation_is_seeded_and_reproducible():
    x = [float(i) for i in range(20)]
    y = [float((i * 7) % 20) for i in range(20)]
    rho = H._spearman(x, y)
    assert H._permutation_p(x, y, rho) == H._permutation_p(x, y, rho)


def test_spearman_returns_none_on_a_constant_variable():
    assert H._spearman([1.0] * 10, list(map(float, range(10)))) is None


@needs_pass3
def test_no_verdict_is_forced():
    doc = json.load(open(os.path.join(EV, "hypothesis_tests.json"), encoding="utf-8"))
    allowed = {H.SUPPORTED, H.REFUTED, H.UNTESTABLE, H.INSUFFICIENT}
    for t in doc["tests"]:
        assert t["result"] in allowed
        assert t["reason"]
        assert t["null_model"]
        if t["result"] in (H.UNTESTABLE, H.INSUFFICIENT):
            assert t["statistic"] is None or "p_value" not in (t["statistic"] or {})
    assert {t["module_id"] for t in doc["tests"]} == set(H.M.ALL_MODULE_IDS)
