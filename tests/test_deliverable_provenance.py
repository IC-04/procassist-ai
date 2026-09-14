"""The deliverable must be reproducible AND produced by the method that was validated.

These are two different assertions and both are needed, which is the whole lesson of the S-E9
incident:

  (a) **the bytes reproduce.** Regenerating `segments.jsonl` must yield the sha256 of the
      committed file. This is the reproducibility claim a reviewer cares about.
  (b) **the method is the validated one.** `run_manifest.json` must report
      `method_used == "graph"`.

(a) alone is not sufficient, and believing it was is what let the defect through. The previous
check was "two consecutive runs agree" — two runs in one environment agree even when both are
wrong. On a host without networkx and rapidfuzz the labeller fell back to the structural method
and produced a file with byte-identical SPANS and different LABELS, exit code 0, no warning;
both runs on that host would have agreed with each other perfectly. (b) is what makes the
environment itself part of the assertion, and it is recorded in an artifact so the mismatch is
visible rather than only inferable by hashing the file on two machines.
"""
from __future__ import annotations
import hashlib, json, os
import pytest

from procmine import label as LB
from conftest import needs_b, DATASET_B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELIVERABLE = os.path.join(ROOT, "segments.jsonl")
MANIFEST = os.path.join(ROOT, "build", "dataset_b", "run_manifest.json")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_the_graph_identity_stack_is_present():
    """A hard requirement, asserted first so the failure names the cause rather than surfacing
    as a mysterious label-count mismatch three tests later."""
    assert LB.missing_graph_dependencies() == [], (
        "the shipped identity method cannot run in this environment; run `make setup`")


@pytest.mark.skipif(not os.path.exists(MANIFEST), reason="no run yet — run `make run-b`")
def test_manifest_reports_the_validated_method():
    """(b). The environment is part of the assertion."""
    m = json.load(open(MANIFEST, encoding="utf-8"))
    assert m["method_used"] == m["expected_method"] == "graph", (
        f"deliverable was produced by {m['method_used']!r}, not the validated graph method; "
        f"missing dependencies: {m.get('missing_graph_dependencies')}")
    assert m["missing_graph_dependencies"] == []
    assert m["n_labels"] and m["n_segments"]


@pytest.mark.skipif(not os.path.exists(MANIFEST) or not os.path.exists(DELIVERABLE),
                    reason="no run yet — run `make run-b`")
def test_manifest_hash_matches_the_deliverable_on_disk():
    """Cheap continuous version of (a): the manifest describes THIS file, not a previous one."""
    m = json.load(open(MANIFEST, encoding="utf-8"))
    assert m["segments_sha256"] == _sha(DELIVERABLE)
    assert sum(1 for _ in open(DELIVERABLE, encoding="utf-8")) == m["n_segments"]
    labels = {json.loads(l)["label"] for l in open(DELIVERABLE, encoding="utf-8")}
    assert len(labels) == m["n_labels"]


@needs_b
@pytest.mark.slow
def test_regenerating_reproduces_the_committed_deliverable(tmp_path):
    """(a) in full: run the chain and compare against the COMMITTED bytes.

    Slow (it runs the whole Step 1 chain over dataset_b), so it carries the `slow` marker; it is
    the assertion that actually proves the submitted file is reproducible, so it is not
    conditional on anything else.
    """
    import subprocess, sys
    committed = subprocess.run(["git", "show", "HEAD:segments.jsonl"], cwd=ROOT,
                               capture_output=True, timeout=60)
    if committed.returncode != 0:
        pytest.skip("segments.jsonl is not committed at HEAD")
    expected = hashlib.sha256(committed.stdout).hexdigest()

    out = tmp_path / "out"
    from procmine import cli
    target = tmp_path / "segments.jsonl"
    cli.segment(DATASET_B, str(out), deliverable=str(target))
    assert _sha(str(target)) == expected, (
        "regenerating the deliverable did not reproduce the committed bytes — the submission's "
        "provenance is broken")
    m = json.load(open(out / "run_manifest.json", encoding="utf-8"))
    assert m["method_used"] == "graph"


def test_degraded_identity_raises_rather_than_shipping_a_different_method(monkeypatch):
    """The fix itself. With the stack unavailable and no explicit opt-in, labelling must raise;
    with the opt-in it may fall back, loudly."""
    monkeypatch.setattr(LB, "missing_graph_dependencies", lambda: ["networkx", "rapidfuzz"])
    segs = [{"session_id": "s", "start_ms": i * 1000, "end_ms": i * 1000 + 900}
            for i in range(8)]
    with pytest.raises(LB.DegradedIdentityError) as e:
        LB.label_segments(segs, {"s": []}, {"s": []})
    assert "networkx" in str(e.value) and "rapidfuzz" in str(e.value)
    assert "make setup" in str(e.value)
    out = LB.label_segments(segs, {"s": []}, {"s": []}, {"allow_degraded": True})
    assert len(out) == len(segs)
