"""Provisional segments emission and the DATA_CONTRACT §6 validator.

The validator tests are the important ones: a contract checker that cannot reject a bad file
is decoration, so each of the five constraints gets a case that must FAIL.
"""
from __future__ import annotations
import json, os
import pytest

from procmine import emit_segments as ES, validate_segments as V
from conftest import needs_b, DATASET_B


SES = "ses_20260701-183232-LAPTOP-76QMG9DE"


def seg(session=SES, start="2026-07-01T18:32:32Z", end="2026-07-01T18:35:41Z",
        label="payroll-items", **extra):
    d = {"session_id": session, "start": start, "end": end, "label": label}
    d.update(extra)
    return d


def test_a_conforming_file_passes_every_check():
    segs = [seg(), seg(start="2026-07-01T18:36:00Z", end="2026-07-01T18:37:00Z",
                       label="onboarding")]
    assert V.validate(segs, session_ids={SES}) == []


# ---------------------------------------------------------------- the five violations

def test_1_rejects_a_session_id_that_is_not_a_session_directory():
    """§6.1 — session_id must be the EXACT session directory name."""
    bad = [seg(session="ses_does_not_exist")]
    assert V.check_session_ids(bad, session_ids={SES}) != []
    # and the same row passes once the id is real
    assert V.check_session_ids([seg()], session_ids={SES}) == []


def test_2_rejects_bad_timestamps_and_non_increasing_intervals():
    """§6.2 — ISO-8601 UTC ending in Z, second precision, start < end."""
    assert V.check_timestamps([seg(start="2026-07-01 18:32:32")]) != []      # no T/Z
    assert V.check_timestamps([seg(start="2026-07-01T18:32:32+00:00")]) != []  # not Z
    assert V.check_timestamps([seg(start="2026-07-01T18:32:32.500Z")]) != []   # sub-second
    assert V.check_timestamps([seg(start="2026-07-01T18:35:41Z",
                                   end="2026-07-01T18:32:32Z")]) != []         # reversed
    assert V.check_timestamps([seg(start="2026-07-01T18:32:32Z",
                                   end="2026-07-01T18:32:32Z")]) != []         # zero length
    assert V.check_timestamps([seg()]) == []


def test_3_rejects_extra_or_missing_keys():
    """§6.3 — exactly four keys, no extras."""
    assert V.check_keys([seg(confidence=0.9)]) != []
    missing = seg()
    del missing["label"]
    assert V.check_keys([missing]) != []
    assert V.check_keys([seg()]) == []


def test_4_rejects_out_of_order_and_overlapping_segments():
    """§6.4 — ordered by start and non-overlapping within a session."""
    out_of_order = [seg(start="2026-07-01T18:36:00Z", end="2026-07-01T18:37:00Z"),
                    seg(start="2026-07-01T18:32:32Z", end="2026-07-01T18:33:00Z")]
    assert any("out of order" in p for p in V.check_ordering(out_of_order))

    overlapping = [seg(start="2026-07-01T18:32:00Z", end="2026-07-01T18:35:00Z"),
                   seg(start="2026-07-01T18:34:00Z", end="2026-07-01T18:36:00Z")]
    assert any("overlap" in p for p in V.check_ordering(overlapping))

    # touching intervals are NOT overlapping
    touching = [seg(start="2026-07-01T18:32:00Z", end="2026-07-01T18:34:00Z"),
                seg(start="2026-07-01T18:34:00Z", end="2026-07-01T18:36:00Z")]
    assert V.check_ordering(touching) == []

    # two sessions interleaved in the file are independent
    other = [seg(start="2026-07-01T18:36:00Z", end="2026-07-01T18:37:00Z"),
             seg(session="ses_other", start="2026-07-01T18:00:00Z",
                 end="2026-07-01T18:01:00Z")]
    assert V.check_ordering(other) == []


def test_5_rejects_a_boundary_derived_from_a_recording_chunk_edge():
    """§6.7 — a boundary must not exist BECAUSE of a chunk edge (DATA_SCHEMA §1, ADR-001)."""
    edge_ms = V.to_ms("2026-07-01T18:35:41Z")
    edges = {SES: {edge_ms // 1000}}

    # the boundary sits on a chunk edge and nothing else explains it -> violation
    assert V.check_no_chunk_boundaries([seg()], chunk_edges=edges, justified={SES: set()}) != []

    # the same boundary is fine when independently justified (a real surface change that
    # happens to coincide) -- 4 of 1,781 dataset_b block boundaries do exactly this
    assert V.check_no_chunk_boundaries([seg()], chunk_edges=edges,
                                       justified={SES: {edge_ms // 1000}}) == []

    # away from any chunk edge -> fine
    assert V.check_no_chunk_boundaries([seg(end="2026-07-01T18:40:00Z")],
                                       chunk_edges=edges, justified={SES: set()}) == []

    # no chunk information supplied -> the check cannot fire
    assert V.check_no_chunk_boundaries([seg()]) == []


def test_validate_aggregates_all_five():
    """One row violating several constraints at once is fully reported."""
    bad = [{"session_id": "nope", "start": "x", "end": "y", "label": "l", "extra": 1}]
    problems = V.validate(bad, session_ids={SES})
    assert len(problems) >= 3


# ---------------------------------------------------------------- slug / label stability

def test_labels_are_stable_and_deterministic():
    """§6.6 — the same surface must yield the same label in every session."""
    blk = {"surface": "web:http://127.0.0.1:5132/payroll-items",
           "route": "/payroll-items", "origin": "http://127.0.0.1:5132",
           "app": "Microsoft Edge", "title": "HR"}
    assert ES.label_for(blk) == "payroll-items"
    assert ES.label_for(dict(blk)) == ES.label_for(dict(blk))
    # a different origin serving the same route collapses under the default scheme...
    other = dict(blk, origin="http://127.0.0.1:5134",
                 surface="web:http://127.0.0.1:5134/payroll-items")
    assert ES.label_for(other) == "payroll-items"
    # ...and is kept apart under the `surface` scheme
    assert ES.label_for(blk, "surface") != ES.label_for(other, "surface")


def test_slugify_is_deterministic_and_safe():
    assert ES.slugify("Payroll Items") == "payroll-items"
    assert ES.slugify("  a/b  ") == "a-b"
    assert ES.slugify("") == ""
    assert ES.slugify("財務会計システム") == "財務会計システム"
    assert ES.slugify("x") == ES.slugify("X")


def test_app_surface_without_a_title_falls_back_to_the_app_name():
    assert ES.label_for({"surface": "app:Notepad", "app": "Notepad", "title": ""}) == "notepad"


def test_root_route_becomes_home():
    assert ES.label_for({"surface": "web:http://h/", "route": "/", "origin": "http://h"}) == "home"


# ---------------------------------------------------------------- merging / absorption

def test_adjacent_segments_with_the_same_label_are_merged():
    segs = [[0, 1000, "a", 1], [1000, 2000, "a", 1], [2000, 3000, "b", 1]]
    out = ES._merge_same_label(segs)
    assert [s[2] for s in out] == ["a", "b"]
    assert out[0][0] == 0 and out[0][1] == 2000


def test_subsecond_segments_are_absorbed_not_dropped():
    """A segment inside one second cannot satisfy start < end; it joins its neighbour."""
    segs = [[0, 5000, "a", 1], [5000, 5100, "b", 1]]
    out, absorbed = ES._absorb_subsecond([list(s) for s in segs])
    assert absorbed == 1
    assert len(out) == 1 and out[0][1] == 5100


def test_absorption_keeps_a_lone_subsecond_session_rather_than_looping():
    out, absorbed = ES._absorb_subsecond([[0, 100, "a", 1]])
    assert len(out) == 1 and absorbed == 0


def test_segments_for_session_on_empty_input():
    segs, stats = ES.segments_for_session([])
    assert segs == [] and stats["blocks"] == 0


# ---------------------------------------------------------------- integration

@needs_b
def test_emitter_runs_on_dataset_b_without_raising(tmp_path):
    out = tmp_path / "segments.jsonl"
    summary = ES.emit(DATASET_B, str(out))
    assert summary["segments"] > 0
    assert summary["sessions"] > 0
    assert summary["provisional"] is True
    assert summary["accuracy_validated"] is False
    assert out.exists()


@needs_b
def test_emitted_file_satisfies_the_contract(tmp_path):
    out = tmp_path / "segments.jsonl"
    ES.emit(DATASET_B, str(out))
    assert V.validate_file(str(out), dataset_root=DATASET_B) == []


@needs_b
def test_emission_is_deterministic(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    ES.emit(DATASET_B, str(a))
    ES.emit(DATASET_B, str(b))
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


def test_emitter_reports_an_absent_dataset_without_writing(tmp_path, capsys):
    out = tmp_path / "segments.jsonl"
    assert ES.main(["--dataset", str(tmp_path / "dataset_zz"), "--out", str(out)]) == 0
    assert "not present" in capsys.readouterr().out
    assert not out.exists()


def test_validator_reports_a_missing_file():
    assert V.validate_file("does_not_exist.jsonl") != []


# ---------------------------------------------------------------- the clobbering trap
#
# `make run-b` was `build-b` + this emitter, and this emitter defaulted to "segments.jsonl".
# So running the ADR-010 leakage check silently replaced a Phase D/E deliverable with
# block-edge-only segments. It happened during the S-E7 freeze and was caught only because a
# downstream experiment reported a segment count that could not be right.
#
# Three things now prevent it, and each has a test: the emitter does not default to the
# deliverable path, it refuses that path when asked explicitly, and exactly one code path in
# the package writes the deliverable.

def test_provisional_emitter_does_not_default_to_the_deliverable():
    from procmine import emit_segments as ES
    assert ES.default_out("dataset_b") != ES.DELIVERABLE
    assert os.path.basename(ES.default_out("dataset_b")) == "segments_provisional.jsonl"
    assert "build" in ES.default_out("dataset_b")
    assert ES.default_out("dataset_b") != ES.default_out("dataset_a")


def test_provisional_emitter_refuses_the_deliverable_path_without_force():
    """argparse errors exit 2; the point is that it does not silently write."""
    from procmine import emit_segments as ES
    with pytest.raises(SystemExit) as e:
        ES.main(["--dataset", "dataset_b", "--out", "segments.jsonl"])
    assert e.value.code != 0


def test_exactly_one_module_writes_the_deliverable():
    """A grep would be the wrong test — the string appears in docstrings explaining the rule.
    This walks the AST and looks for an actual open() of the deliverable path."""
    import ast
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pkg = os.path.join(root, "procmine")
    writers = set()
    for fn in sorted(os.listdir(pkg)):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(pkg, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open"):
                continue
            mode = ""
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            if "w" not in (mode or ""):
                continue
            target = node.args[0] if node.args else None
            named = (isinstance(target, ast.Name) and target.id == "deliverable") or (
                isinstance(target, ast.Constant) and target.value == "segments.jsonl")
            if named:
                writers.add(fn)
    assert writers == {"cli.py"}, f"deliverable writers: {sorted(writers)}"
