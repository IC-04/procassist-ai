"""Evaluation harness — every expected value below is computed by hand.

A harness that is only checked against its own output cannot detect a systematic error,
so each case states the arithmetic in the docstring or comment.
"""
from __future__ import annotations
import pytest

from procmine import evaluate as E


# ---------------------------------------------------------------- boundary_f1

def test_boundary_f1_hand_computed():
    """ref 0,10,20 vs hyp 0,11,30 at tol=2.
    0<->0 (d=0) and 10<->11 (d=1) match; 20 vs 30 is d=10 > 2.
    tp=2 fp=1 fn=1 -> P=R=2/3, F1=2/3."""
    m = E.boundary_f1([0, 10, 20], [0, 11, 30], tol=2)
    assert (m["tp"], m["fp"], m["fn"]) == (2, 1, 1)
    assert m["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["f1"] == pytest.approx(2 / 3, abs=1e-4)


def test_boundary_f1_perfect_and_empty():
    m = E.boundary_f1([0, 5, 9], [0, 5, 9], tol=0)
    assert m["f1"] == 1.0 and m["fp"] == 0 and m["fn"] == 0
    e = E.boundary_f1([], [], tol=5)
    assert e["f1"] == 1.0 and e["n_ref"] == 0


def test_boundary_f1_matching_is_one_to_one():
    """One reference must not be matched by three hypotheses.
    ref=[10], hyp=[9,10,11], tol=2 -> tp=1 fp=2 fn=0, P=1/3, R=1, F1=0.5.
    Without one-to-one matching this would report P=1, R=1."""
    m = E.boundary_f1([10], [9, 10, 11], tol=2)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 2, 0)
    assert m["precision"] == pytest.approx(1 / 3, abs=1e-4)
    assert m["recall"] == 1.0
    assert m["f1"] == 0.5


def test_boundary_f1_tolerance_is_inclusive():
    assert E.boundary_f1([10], [12], tol=2)["tp"] == 1
    assert E.boundary_f1([10], [13], tol=2)["tp"] == 0


def test_boundary_f1_no_hypothesis_gives_zero_recall():
    m = E.boundary_f1([1, 2, 3], [], tol=1)
    assert m["f1"] == 0.0 and m["fn"] == 3


# ---------------------------------------------------------------- iou / segmental

def test_iou_hand_computed():
    """(0,10) vs (5,15): intersection 5, union 15 -> 1/3."""
    assert E.iou((0, 10), (5, 15)) == pytest.approx(1 / 3, abs=1e-6)
    assert E.iou((0, 10), (0, 10)) == 1.0
    assert E.iou((0, 10), (10, 20)) == 0.0          # touching, not overlapping
    assert E.iou((0, 10), (20, 30)) == 0.0


def test_segmental_f1_threshold_behaviour():
    """(0,10) vs (0,6): IoU = 6/10 = 0.6, so it matches at 0.5 but not at 0.7."""
    assert E.segmental_f1([(0, 10)], [(0, 6)], 0.5)["matched"] == 1
    assert E.segmental_f1([(0, 10)], [(0, 6)], 0.7)["matched"] == 0
    # (0,10) vs (0,4): IoU = 0.4 -> no match at 0.5
    assert E.segmental_f1([(0, 10)], [(0, 4)], 0.5)["matched"] == 0


def test_segmental_f1_is_one_to_one():
    """Two identical hypotheses cannot both claim one reference."""
    m = E.segmental_f1([(0, 10)], [(0, 10), (0, 10)], 0.5)
    assert m["matched"] == 1
    assert m["precision"] == 0.5 and m["recall"] == 1.0


def test_count_ratio():
    assert E.count_ratio([1, 2], [1, 2, 3]) == 1.5
    assert E.count_ratio([1, 2], [1, 2]) == 1.0
    assert E.count_ratio([], [1]) == float("inf")


# ---------------------------------------------------------------- masses

def test_masses_from_boundaries_hand_computed():
    """Boundaries at 3 and 7 over 10 units -> segments of 3, 4, 3."""
    assert E.masses_from_boundaries([3, 7], 10) == [3, 4, 3]
    assert E.masses_from_boundaries([], 10) == [10]
    # boundaries at the extremes are not interior and are ignored
    assert E.masses_from_boundaries([0, 10], 10) == [10]
    assert sum(E.masses_from_boundaries([2, 5, 9], 12)) == 12


def test_windowdiff_and_pk_perfect_and_worst():
    ref = [5, 5]
    assert E.windowdiff(ref, [5, 5]) == 0.0      # identical segmentation
    assert E.pk(ref, [5, 5]) == 0.0
    # differing total mass is undefined, not an exception
    assert E.windowdiff([5, 5], [3, 3]) is None
    assert E.pk([5, 5], [3, 3]) is None


def test_windowdiff_penalises_a_wrong_segmentation():
    good = E.windowdiff([10, 10], [10, 10])
    bad = E.windowdiff([10, 10], [2, 2, 2, 2, 2, 2, 2, 2, 2, 2])
    assert good == 0.0
    assert bad is not None and bad > good


# ---------------------------------------------------------------- identity

def test_identity_scores_perfect_and_permuted():
    """ARI is invariant to label renaming: a consistent relabel scores 1.0."""
    assert E.identity_scores(["a", "a", "b"], ["a", "a", "b"])["ari"] == 1.0
    assert E.identity_scores(["a", "a", "b"], ["x", "x", "y"])["ari"] == 1.0
    # everything collapsed into one label carries no information
    assert E.identity_scores(["a", "b", "c"], ["z", "z", "z"])["ari"] == 0.0


def test_matched_identity_always_reports_match_rate():
    """ARI without match_rate is meaningless (EVALUATION_PROTOCOL §3)."""
    ref = [(0, 10), (20, 30), (40, 50)]
    hyp = [(0, 10), (20, 30)]
    m = E.matched_identity(ref, ["a", "b", "c"], hyp, ["a", "b"], iou_thr=0.5)
    assert "match_rate" in m
    assert m["n_matched"] == 2 and m["n_ref"] == 3
    assert m["match_rate"] == pytest.approx(2 / 3, abs=1e-4)


def test_matched_identity_with_no_matches():
    m = E.matched_identity([(0, 10)], ["a"], [(100, 110)], ["b"], iou_thr=0.5)
    assert m["n_matched"] == 0 and m["match_rate"] == 0.0


# ---------------------------------------------------------------- interruption

def test_interruption_recall_counts_only_stitched_executions():
    """Two fragments of one execution, both covered by the SAME hypothesis label -> stitched."""
    canonical = [{"n_fragments": 2, "interval_ms": [(0, 10), (100, 110)]}]
    hyp = [(0, 200)]
    assert E.interruption_recall(canonical, hyp, ["X"])["recall"] == 1.0
    # split across two differently-labelled segments -> not stitched
    hyp2 = [(0, 50), (60, 200)]
    assert E.interruption_recall(canonical, hyp2, ["X", "Y"])["recall"] == 0.0
    # same label on both segments -> stitched again
    assert E.interruption_recall(canonical, hyp2, ["X", "X"])["recall"] == 1.0


def test_interruption_recall_ignores_uninterrupted_executions():
    r = E.interruption_recall([{"n_fragments": 1, "interval_ms": [(0, 10)]}], [(0, 10)], ["X"])
    assert r["n_interrupted"] == 0 and r["recall"] is None


# ---------------------------------------------------------------- index mapping

def test_ms_to_index_and_intervals():
    timeline = [100, 200, 300, 400, 500]
    assert E.ms_to_index(timeline, 100) == 0
    assert E.ms_to_index(timeline, 350) == 3
    assert E.ms_to_index(timeline, 500) == 4
    assert E.intervals_to_index(timeline, [(100, 300)]) == [(0, 2)]


def test_boundaries_of_uses_both_endpoints():
    assert E.boundaries_of([(0, 10), (10, 20)]) == [0, 10, 20]


# ---------------------------------------------------------------- calibration

def test_calibrate_tau_is_derived_from_the_data_not_hard_coded():
    """A 100 s median must not produce the same grid as a 10 s median."""
    slow = E.calibrate_tau([{"total_duration_s": 100.0} for _ in range(50)])
    fast = E.calibrate_tau([{"total_duration_s": 10.0} for _ in range(50)])
    assert slow["grid_ms"] != fast["grid_ms"]
    assert max(slow["grid_ms"]) > max(fast["grid_ms"])
    assert slow["median_duration_s"] == 100.0


def test_calibrate_tau_handles_no_durations():
    r = E.calibrate_tau([])
    assert r["grid_ms"] == list(E.DEFAULT_TAUS_MS)


# ---------------------------------------------------------------- evaluate_all

def _bundle(intervals, labels=None):
    return {"intervals": intervals, "labels": labels or []}


def test_evaluate_all_perfect_reconstruction():
    ref = {"s1": {"intervals": [(0, 1000), (1000, 2000)], "labels": ["A", "B"]}}
    hyp = {"s1": _bundle([(0, 1000), (1000, 2000)], ["A", "B"])}
    cfg = {"taus_ms": [1000], "kappas": [1], "ious": [0.5],
           "timelines": {"s1": list(range(0, 2000, 100))}}
    out = E.evaluate_all(ref, hyp, cfg)
    o = out["overall"]
    assert o["boundary_time"]["1000"]["f1"] == 1.0
    assert o["segmental"]["0.5"]["f1"] == 1.0
    assert o["count_ratio"] == 1.0
    assert o["identity_pooled"]["ari"] == 1.0


def test_evaluate_all_shape_is_stable():
    ref = {"s1": {"intervals": [(0, 100)], "labels": ["A"]}}
    hyp = {"s1": _bundle([(0, 50), (50, 100)], ["A", "B"])}
    out = E.evaluate_all(ref, hyp, {"taus_ms": [1, 2], "kappas": [1], "ious": [0.5],
                                    "timelines": {"s1": [0, 25, 50, 75]}})
    assert set(out) == {"config", "overall", "per_session"}
    assert set(out["overall"]["boundary_time"]) == {"1", "2"}
    assert out["overall"]["count_ratio"] == 2.0
    assert "s1" in out["per_session"]


def test_evaluate_all_does_not_mutate_inputs():
    ref = {"s1": {"intervals": [(0, 100)], "labels": ["A"]}}
    hyp = {"s1": _bundle([(0, 100)], ["A"])}
    import copy
    r0, h0 = copy.deepcopy(ref), copy.deepcopy(hyp)
    E.evaluate_all(ref, hyp, {"taus_ms": [1], "kappas": [1], "ious": [0.5],
                              "timelines": {"s1": [0, 50]}})
    assert ref == r0 and hyp == h0


def test_evaluate_all_handles_an_empty_hypothesis():
    ref = {"s1": {"intervals": [(0, 100)], "labels": ["A"]}}
    out = E.evaluate_all(ref, {"s1": _bundle([], [])},
                         {"taus_ms": [1], "kappas": [1], "ious": [0.5],
                          "timelines": {"s1": [0, 50]}})
    assert out["overall"]["boundary_time"]["1"]["f1"] == 0.0
    assert out["overall"]["count_ratio"] == 0.0
