"""Stage 8 — process-identity labelling (STEP1_SPEC §3.7).

Label TEXT is not scored; consistency is. So the tests are about stability and determinism,
and about the module never seeing ground truth.
"""
from __future__ import annotations
import ast
import pytest

from procmine import label as LB
from conftest import ev, flat


def seg(sid, a, b):
    return {"session_id": sid, "start_ms": a, "end_ms": b}


def rows_for(app, title, route, n=6, t0=0):
    out = []
    for i in range(n):
        out.append(ev(t0 + i * 1000, app=app, title=title,
                      url=f"http://h{route}" if route else "",
                      et="keystroke" if i % 2 else "mouse_click"))
    return flat(*out)


def blocks_for(surface, route, origin, app, title, a, b):
    return [{"surface": surface, "route": route, "origin": origin, "app": app,
             "title": title, "start_ms": a, "end_ms": b}]


# ---------------------------------------------------------------- signature

def test_signature_is_structural_and_collapses_repeats():
    rows = rows_for("Edge", "T", "/payroll")
    blks = (blocks_for("web:http://h/payroll", "/payroll", "http://h", "Edge", "T", 0, 5000)
            + blocks_for("web:http://h/payroll", "/payroll", "http://h", "Edge", "T", 5000, 9000))
    s = LB.signature(seg("s1", 0, 9000), rows, blks)
    assert s["surface_shape"] == ["web:http://h/payroll"], "immediate repeats must collapse"
    assert s["routes"] == ["/payroll"]
    assert abs(sum(s["profile"].values()) - 1.0) < 0.5


def test_collapse_keeps_a_genuine_return():
    assert LB._collapse(["A", "A", "B", "B", "A"]) == ["A", "B", "A"]


def test_profile_is_proportions_not_counts():
    """Long and short executions of the same process must look alike."""
    short = LB._profile(flat(*[ev(i * 100, et="keystroke") for i in range(4)]))
    long = LB._profile(flat(*[ev(i * 100, et="keystroke") for i in range(40)]))
    assert short == long


# ---------------------------------------------------------------- distance

def test_identical_signatures_have_zero_distance():
    rows = rows_for("Edge", "T", "/payroll")
    blks = blocks_for("web:http://h/payroll", "/payroll", "http://h", "Edge", "T", 0, 9000)
    a = LB.signature(seg("s1", 0, 9000), rows, blks)
    b = LB.signature(seg("s2", 0, 9000), rows, blks)
    assert LB.distance(a, b) == 0.0


def test_different_processes_are_far_apart():
    ra = rows_for("Edge", "HR", "/payroll")
    rb = rows_for("Word", "doc", "")
    a = LB.signature(seg("s1", 0, 9000), ra,
                     blocks_for("web:http://h/payroll", "/payroll", "http://h", "Edge", "HR", 0, 9000))
    b = LB.signature(seg("s1", 0, 9000), rb,
                     blocks_for("app:Word:doc", "", "", "Word", "doc", 0, 9000))
    assert LB.distance(a, b) > 0.5


def test_distance_is_symmetric_and_bounded():
    ra = rows_for("Edge", "HR", "/payroll")
    rb = rows_for("Edge", "HR", "/leave")
    a = LB.signature(seg("s1", 0, 9000), ra,
                     blocks_for("web:http://h/payroll", "/payroll", "http://h", "Edge", "HR", 0, 9000))
    b = LB.signature(seg("s1", 0, 9000), rb,
                     blocks_for("web:http://h/leave", "/leave", "http://h", "Edge", "HR", 0, 9000))
    assert LB.distance(a, b) == LB.distance(b, a)
    assert 0.0 <= LB.distance(a, b) <= 1.0


# ---------------------------------------------------------------- stability across sessions

def _three_sessions():
    """The same two processes, executed in three different sessions."""
    segs, rows_by, blocks_by = [], {}, {}
    for si, sid in enumerate(("ses_a", "ses_b", "ses_c")):
        rows = rows_for("Edge", "HR", "/payroll") + rows_for("Word", "contract", "", t0=20_000)
        rows_by[sid] = rows
        blocks_by[sid] = (
            blocks_for("web:http://h/payroll", "/payroll", "http://h", "Edge", "HR", 0, 9_000)
            + blocks_for("app:Word:contract", "", "", "Word", "contract", 20_000, 29_000))
        segs.append(seg(sid, 0, 9_000))
        segs.append(seg(sid, 20_000, 29_000))
    return segs, rows_by, blocks_by


def test_the_same_process_gets_the_same_label_in_every_session():
    """This is half of what the assignment scores."""
    segs, rows_by, blocks_by = _three_sessions()
    out = LB.label_segments(segs, rows_by, blocks_by)
    payroll = {s["label"] for s in out if s["start_ms"] == 0}
    contract = {s["label"] for s in out if s["start_ms"] == 20_000}
    assert len(payroll) == 1, f"one process split across labels: {payroll}"
    assert len(contract) == 1, f"one process split across labels: {contract}"
    assert payroll != contract, "two different processes collapsed into one label"


def test_label_report_measures_cross_session_reuse():
    segs, rows_by, blocks_by = _three_sessions()
    rep = LB.label_report(LB.label_segments(segs, rows_by, blocks_by))
    assert rep["n_sessions"] == 3
    assert rep["cross_session_label_rate"] == 1.0
    assert rep["mean_sessions_per_label"] == 3.0


def test_labelling_is_deterministic():
    segs, rows_by, blocks_by = _three_sessions()
    a = LB.label_segments(segs, rows_by, blocks_by)
    b = LB.label_segments(segs, rows_by, blocks_by)
    assert [x["label"] for x in a] == [x["label"] for x in b]


def test_labelling_handles_empty_input():
    assert LB.label_segments([], {}, {}) == []
    assert LB.label_report([])["n_labels"] == 0


# ---------------------------------------------------------------- k selection

def test_choose_k_is_not_maximised_by_the_finest_clustering():
    """Stability ALONE is degenerate — on dataset_a it selected k=849 at 2 segments per label
    and 27% cross-session reuse. The objective must have an interior optimum."""
    segs, rows_by, blocks_by = _three_sessions()
    sigs = [LB.signature(s, rows_by[s["session_id"]], blocks_by[s["session_id"]]) for s in segs]
    sessions = [s["session_id"] for s in segs]
    sel = LB.choose_k(sigs, sessions)
    assert sel["k"] < len(sigs), "every segment became its own cluster"
    assert sel.get("cross_session_rate") is not None


def test_choose_k_reports_both_halves_of_its_objective():
    segs, rows_by, blocks_by = _three_sessions()
    sigs = [LB.signature(s, rows_by[s["session_id"]], blocks_by[s["session_id"]]) for s in segs]
    sel = LB.choose_k(sigs, [s["session_id"] for s in segs])
    assert "stability" in sel and "cross_session_rate" in sel and "objective" in sel


# ---------------------------------------------------------------- GT leakage (AST)

def test_label_py_reads_no_ground_truth():
    """Parsed with ast, not grepped — the Phase C test flagged a docstring that merely
    EXPLAINED it reads no GT."""
    tree = ast.parse(open(LB.__file__, encoding="utf-8").read())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
            modules.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any(m.rsplit(".", 1)[-1] == "gt" or m.endswith(".gt") for m in modules)

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    forbidden = ("process_code", "case_id", "family_name", "split_id",
                 "task_id", "expected_boundaries", "executions_canonical", "gt_manifest")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            for f in forbidden:
                assert f not in node.value, f"label.py names a GT field in code: {f!r}"
    # and no GT field is ever read as an attribute/subscript key in code
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            assert node.slice.value not in ("process_code", "case_id", "variant",
                                            "family_name", "split_id", "phase", "task_id")
