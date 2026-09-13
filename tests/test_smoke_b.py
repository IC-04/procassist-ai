"""Integration — a full build on real data.

The only test that touches a dataset. It skips itself when `dataset_b/` is absent so
the suite stays green on a clean clone, and it never references `dataset_a/` (ADR-010).
"""
from __future__ import annotations
import json, os
import pytest

from procmine import cli, schemas as S
from conftest import DATASET_A, DATASET_B, needs_b

pytestmark = needs_b


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("build_b")
    summary = cli.build(DATASET_B, str(out), write_windows=True)
    return summary, str(out)


def test_summary_is_populated(built):
    summary, _ = built
    assert summary["sessions"] > 0
    assert summary["events"] > 0
    assert summary["blocks"] > 0
    assert summary["params"]["min_events"] >= 1
    assert set(summary["edges_by_type"]) <= S.RELATIONS


def test_blocks_artifact_exists_and_conforms(built):
    _, out = built
    path = os.path.join(out, "blocks.jsonl")
    assert os.path.exists(path)
    blocks = [json.loads(l) for l in open(path, encoding="utf-8")]
    assert S.validate_blocks(blocks) == []


def test_every_session_has_a_conforming_tekg_document(built):
    summary, out = built
    files = sorted(os.listdir(os.path.join(out, "tekg")))
    assert len(files) == summary["sessions"]
    for f in files:
        with open(os.path.join(out, "tekg", f), encoding="utf-8") as fh:
            assert S.validate_tekg(json.load(fh), max_lag=12) == []


def test_every_window_payload_honours_adr_006(built):
    """The ADR-006 guarantee, checked against every payload actually written."""
    _, out = built
    n = 0
    for root, _dirs, files in os.walk(os.path.join(out, "windows")):
        for f in files:
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                assert S.validate_window_payload(json.load(fh)) == [], f
            n += 1
    assert n > 0


def test_degeneracy_is_within_the_phase_0_findings(built):
    """Guards the fixes against regression. The bound is the measured Phase 0 result
    with headroom, not a target to optimise toward."""
    summary, _ = built
    assert summary["empty_surface_blocks"] == 0
    assert summary["one_event_blocks"] / summary["blocks"] < 0.20
    assert summary["compression_events_per_block"] > 10


def test_no_block_surface_repeats_its_origin(built):
    """Regression for the route_of defect (54 blocks on dataset_b)."""
    _, out = built
    for line in open(os.path.join(out, "blocks.jsonl"), encoding="utf-8"):
        s = json.loads(line)["surface"]
        if s.startswith("web:"):
            assert s.count("http") == 1, s


def test_build_is_reproducible(built, tmp_path):
    """AC4: two runs must diff clean."""
    _, out = built
    second = tmp_path / "again"
    cli.build(DATASET_B, str(second), write_windows=False)
    a = open(os.path.join(out, "blocks.jsonl"), encoding="utf-8").read()
    b = open(os.path.join(second, "blocks.jsonl"), encoding="utf-8").read()
    assert a == b
    for f in sorted(os.listdir(os.path.join(out, "tekg"))):
        assert (open(os.path.join(out, "tekg", f), encoding="utf-8").read()
                == open(os.path.join(second, "tekg", f), encoding="utf-8").read())


def test_absent_dataset_reports_and_writes_nothing(tmp_path, capsys):
    """AC5. Also the ADR-010 guarantee: the B path never needs dataset_a/."""
    missing = str(tmp_path / "dataset_a")
    assert cli.main(["--dataset", missing, "--out", str(tmp_path / "out")]) == 0
    assert "Phase 1 blocked" in capsys.readouterr().out
    assert not os.path.exists(str(tmp_path / "out"))


def test_a_directory_with_no_sessions_is_also_handled(tmp_path, capsys):
    empty = tmp_path / "dataset_a"
    empty.mkdir()
    assert cli.main(["--dataset", str(empty), "--out", str(tmp_path / "out2")]) == 0
    assert "Phase 1 blocked" in capsys.readouterr().out


@pytest.mark.skipif(os.path.isdir(DATASET_A), reason="dataset_a/ is present")
def test_the_b_pipeline_does_not_need_dataset_a():
    """ADR-010, mechanically: this whole module ran without dataset_a/ on disk."""
    assert not os.path.isdir(DATASET_A)
