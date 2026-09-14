"""Stages 4, 5 and 7 — scoring, the ambiguity gate, and the constrained decoder.

The decoder's hard constraints are rejections, not penalties, so each is asserted separately:
a constraint enforced only by construction is one that will eventually not be.
"""
from __future__ import annotations
import ast, json, os
import pytest

from procmine import score as SC, gate as GA, decoder as DE, candidates as CA
from procmine import normalise as N, blocks as B
from conftest import needs_b, DATASET_B


def cand(seq, ms, kind="intra_block", sc=None, **feats):
    f = {"events_in_window": 10, "keystroke_w_n": 0, "mouse_click_w_n": 0,
         "browser_click_w_n": 0, "mouse_scroll_w_n": 0, "shortcut_w_n": 0,
         "clipboard_change_w_n": 0, "browser_form_input_w_n": 0,
         "app_switch_w_n": 0, "browser_navigation_w_n": 0, "window_title_change_w_n": 0}
    f.update(feats)
    d = {"cand_id": f"s#c{seq:05d}", "session_id": "s", "at_seq": seq, "at_ms": ms,
         "block_id": "s#b0000", "kind": kind, "features": f}
    if sc is not None:
        d["score"] = sc
    return d


# ---------------------------------------------------------------- score: composition

def test_composition_ratios_are_derived_not_flags():
    """S-E3: boundaries are navigation-heavy and work-light. A presence flag cannot say that."""
    c = cand(1, 1000, events_in_window=10, keystroke_w_n=8, app_switch_w_n=2)
    comp = SC.composition(c["features"])
    assert comp["transactional_ratio"] == pytest.approx(0.8)
    assert comp["navigational_ratio"] == pytest.approx(0.2)
    assert comp["transactional_per_sec"] == pytest.approx(2.0)   # 8 events / 4 s window


def test_composition_handles_an_empty_window():
    comp = SC.composition({"events_in_window": 0})
    assert comp["transactional_ratio"] == 0.0 and comp["navigational_ratio"] == 0.0


def test_vectorise_is_numeric_only_and_ordered():
    v = SC.vectorise(cand(1, 1000, is_web_surface=True, shortcut_w=False))
    assert set(v) == set(SC.FEATURE_ORDER)
    assert all(isinstance(x, float) for x in v.values())
    assert v["is_web_surface"] == 1.0 and v["shortcut_w"] == 0.0


def test_vectorise_can_drop_a_feature_for_the_ablation():
    v = SC.vectorise(cand(1, 1000), drop=("is_web_surface",))
    assert "is_web_surface" not in v


def test_scorer_is_explainable_and_deterministic():
    s = SC.Scorer(["is_web_surface", "shortcut_w"], [1.0, -2.0], 0.0, [0.0, 0.0], [1.0, 1.0])
    c = cand(1, 1000, is_web_surface=True, shortcut_w=True)
    assert 0.0 <= s.score(c) <= 1.0
    assert s.score(c) == s.score(c)
    tf = s.top_features(c)
    assert len(tf) == 2 and any("shortcut_w-" in t for t in tf)


def test_scorer_round_trips_through_json():
    s = SC.Scorer(["is_web_surface"], [1.5], -0.2, [0.1], [2.0], {"n_train": 3})
    r = SC.Scorer.from_dict(json.loads(json.dumps(s.to_dict())))
    c = cand(1, 1000, is_web_surface=True)
    assert r.score(c) == s.score(c)


def test_negative_evidence_lowers_the_score():
    """S-E3's dominant signal: transactional activity in the window argues AGAINST a boundary."""
    s = SC.Scorer(["transactional_ratio"], [-3.0], 1.0, [0.0], [1.0])
    quiet = cand(1, 1000, events_in_window=10)
    busy = cand(2, 2000, events_in_window=10, keystroke_w_n=10)
    assert s.score(quiet) > s.score(busy)


# ---------------------------------------------------------------- gate

def test_gate_bands_and_ambiguity():
    scored = [cand(1, 1000, sc=0.05), cand(2, 2000, sc=0.50), cand(3, 3000, sc=0.95)]
    r = GA.route(scored)
    assert [x["route"] for x in r] == ["rule", "llm", "rule"]
    assert r[1]["ambiguity"] == pytest.approx(1.0)      # dead centre
    assert r[0]["ambiguity"] == 0.0 and r[2]["ambiguity"] == 0.0


def test_every_routed_candidate_still_carries_a_rule_decision():
    """--no-llm is a complete mode, not a degraded one: the fallback must exist before the
    adjudicator does (ADR-018)."""
    r = GA.route([cand(i, i * 1000, sc=s) for i, s in enumerate([0.4, 0.5, 0.6, 0.9])])
    for x in r:
        assert isinstance(x["rule_decision"], bool)
    routed = [x for x in r if x["route"] == "llm"]
    assert routed and all("rule_decision" in x for x in routed)


def test_routing_report_computes_the_fraction_and_population():
    scored = [cand(i, i * 1000, sc=s) for i, s in enumerate([0.1, 0.5, 0.55, 0.9])]
    labels = [0, 1, 0, 1]
    rep = GA.routing_report(GA.route(scored), labels)
    assert rep["n_candidates"] == 4 and rep["n_routed"] == 2
    assert rep["routing_fraction"] == 0.5
    assert rep["true_boundaries_total"] == 2
    assert rep["true_boundaries_in_routed"] == 1
    assert "rule_only_precision_on_routed" in rep


def test_gate_handles_an_empty_input():
    assert GA.route([]) == []
    assert GA.routing_report([])["n_candidates"] == 0


# ---------------------------------------------------------------- decoder: HARD CONSTRAINTS

def _segments(scores_ms, **cfg):
    cands = [cand(i, ms, sc=s) for i, (ms, s) in enumerate(scores_ms)]
    segs = DE.decode_session(cands, cfg)
    for x in segs:
        x["session_id"] = "s"
    return segs


def test_constraint_no_zero_length_segment():
    segs = _segments([(0, 0.9), (0, 0.9)])
    assert all(x["end_ms"] > x["start_ms"] for x in segs)
    assert DE.violations(segs) == []


def test_constraint_duration_floor_is_a_rejection_not_a_penalty():
    """Two very high-scoring candidates 5 s apart must NOT produce a segment when the floor
    is 19 s, however attractive their scores."""
    segs = _segments([(0, 0.99), (5_000, 0.99)], min_duration_ms=19_000)
    assert segs == []
    ok = _segments([(0, 0.99), (25_000, 0.99)], min_duration_ms=19_000)
    assert len(ok) == 1 and ok[0]["end_ms"] - ok[0]["start_ms"] >= 19_000


def test_constraint_segments_are_non_overlapping_and_ordered():
    segs = _segments([(0, .9), (25_000, .9), (50_000, .9), (75_000, .9)],
                     min_duration_ms=19_000, lambda_per_segment=0.1)
    for a, b in zip(segs, segs[1:]):
        assert b["start_ms"] >= a["end_ms"], "segments overlap"
        assert b["start_ms"] >= a["start_ms"], "segments out of order"
    assert DE.violations(segs, {"min_duration_ms": 19_000}) == []


def test_constraint_upper_bound_is_enforced_when_configured():
    segs = _segments([(0, .99), (500_000, .99)], min_duration_ms=1000,
                     max_duration_ms=100_000)
    assert segs == []
    assert DE.violations([{"session_id": "s", "start_ms": 0, "end_ms": 500_000}],
                         {"min_duration_ms": 1000, "max_duration_ms": 100_000}) != []


def test_violations_detects_each_constraint_separately():
    assert any("zero-length" in v for v in DE.violations(
        [{"session_id": "s", "start_ms": 10, "end_ms": 10}]))
    assert any("below the duration floor" in v for v in DE.violations(
        [{"session_id": "s", "start_ms": 0, "end_ms": 1000}], {"min_duration_ms": 19_000}))
    assert any("overlap" in v for v in DE.violations(
        [{"session_id": "s", "start_ms": 0, "end_ms": 40_000},
         {"session_id": "s", "start_ms": 20_000, "end_ms": 60_000}],
        {"min_duration_ms": 1000}))


def test_decoder_emits_disjoint_segments_not_a_partition():
    """A's GT does not tile the session (coverage 0.81); a partitioning decoder would cap
    boundary recall near 52% by construction."""
    segs = _segments([(0, .9), (25_000, .9), (200_000, .9), (225_000, .9)],
                     min_duration_ms=19_000, lambda_per_segment=0.1)
    assert len(segs) >= 2
    assert segs[1]["start_ms"] > segs[0]["end_ms"], "a gap between segments must be possible"


def test_decoder_is_deterministic():
    pts = [(0, .9), (25_000, .8), (60_000, .95), (90_000, .7)]
    assert _segments(pts, min_duration_ms=19_000) == _segments(pts, min_duration_ms=19_000)


def test_decoder_handles_degenerate_input():
    assert DE.decode_session([]) == []
    assert DE.decode_session([cand(0, 0, sc=0.9)]) == []
    assert DE.decode({}) == {}


def test_nms_collapses_a_cluster_and_keeps_the_best():
    cl = [cand(0, 1000, sc=0.5), cand(1, 1200, sc=0.9), cand(2, 1400, sc=0.6)]
    kept = DE._nms(cl, 2000)
    assert len(kept) == 1 and kept[0]["score"] == 0.9
    assert len(DE._nms(cl, 0)) == 3


# ---------------------------------------------------------------- GT leakage (AST)

@pytest.mark.parametrize("mod", [CA, SC, GA, DE])
def test_no_stage_imports_a_ground_truth_module(mod):
    """Parsed with ast, not grepped: a module's prose explaining that it reads no GT must not
    fail its own test (the Phase C test flagged exactly that)."""
    tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
            modules.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any(m.rsplit(".", 1)[-1] == "gt" or m.endswith(".gt") for m in modules), \
        f"{mod.__name__} imports a ground-truth module: {sorted(modules)}"

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            for f in ("executions_canonical", "expected_boundaries", "gt_events",
                      "gt.jsonl", "gt_manifest", "executions.jsonl"):
                assert f not in node.value, f"{mod.__name__} names a GT artifact in code: {f!r}"


# ---------------------------------------------------------------- end to end

@needs_b
def test_full_deterministic_chain_runs_on_dataset_b_without_raising():
    """--no-llm end to end: candidates -> score -> gate -> decode, with every routed candidate
    falling back to its rule_decision."""
    sd = os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE")
    rows = N.load_session(sd)
    blks = B.build_blocks(rows)
    cands = CA.generate(rows, blks)
    scorer = SC.Scorer(["is_web_surface", "transactional_ratio"], [1.0, -2.0], 0.0,
                       [0.0, 0.0], [1.0, 1.0])
    scored = scorer.apply(cands)
    routed = GA.route(scored)
    assert all("rule_decision" in x for x in routed)
    segs = DE.decode_session(routed, {"min_duration_ms": 19_000})
    for s in segs:
        s["session_id"] = "x"
    assert DE.violations(segs, {"min_duration_ms": 19_000}) == []
