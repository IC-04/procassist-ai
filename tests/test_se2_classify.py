"""S-E2 miss-attribution classifier — one synthetic case per category rule.

The classifier decides what the whole GATE-1 decision rests on, so each rule is exercised in
isolation on data where the right answer is known by construction, and the precedence between
rules is tested explicitly.
"""
from __future__ import annotations
import os, sys
import pytest

SE2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "experiments", "SE2-miss-attribution")
sys.path.insert(0, SE2)

classify = pytest.importorskip("classify", reason="experiments/SE2-miss-attribution absent")

from procmine import blocks as B                                    # noqa: E402
from conftest import ev, flat                                       # noqa: E402


def row(ts, et="mouse_click", app="Word", title="doc", url="", ms_since_last=50, field=""):
    r = flat(ev(ts, et=et, app=app, title=title, url=url, field=field))[0]
    r["ms_since_last"] = ms_since_last
    return r


def sess(rows, *, blocks=None, edges=None, edges_no_absorb=None, raw=None,
         normalised=None, span=None, gap=100000):
    ts = [r["ts_ms"] for r in rows]
    blocks = blocks if blocks is not None else B.build_blocks(rows, min_events=1, min_ms=0)
    return {
        "rows": rows, "ts": ts, "blocks": blocks,
        "edges": edges if edges is not None else [],
        "edges_no_absorb": edges_no_absorb if edges_no_absorb is not None else [],
        "raw_ids_sorted": raw if raw is not None else sorted((r["ts_ms"], r["event_id"])
                                                             for r in rows),
        "normalised_ids": normalised if normalised is not None else {r["event_id"] for r in rows},
        "telemetry_span": span if span is not None else (ts[0], ts[-1]),
        "gap_threshold_ms": gap,
    }


LEAD = 176
TAU = 2000


# ---------------------------------------------------------------- (e)

def test_e_boundary_outside_the_telemetry_span():
    rows = [row(1000), row(2000)]
    s = sess(rows, edges=[1000, 2000])
    out = classify.classify_boundary(999_000, s, TAU, LEAD)
    assert out["category"] == "e_gt_telemetry_mismatch"
    assert out["sub"] == "outside_telemetry"


def test_e_explained_by_the_measured_annotation_lead():
    """A boundary unreachable as annotated but reachable once the measured GT lead is
    removed is an annotation offset, not a miss — and must not leak into (d)."""
    rows = [row(0), row(10_000)]
    # edge at 7000; boundary at 9000 is 2000 away (not <= TAU strictly? it is equal) ->
    # place the boundary so only the lead correction brings it inside
    s = sess(rows, edges=[6800], span=(0, 10_000))
    out = classify.classify_boundary(6800 + LEAD + 1500, s, TAU, LEAD)
    assert out["category"] == "e_gt_telemetry_mismatch"
    assert out["sub"] == "annotation_lead"


def test_e_no_telemetry_within_tolerance_is_a_recording_gap():
    rows = [row(0), row(60_000)]
    s = sess(rows, edges=[0, 60_000])
    out = classify.classify_boundary(30_000, s, TAU, LEAD)
    assert out["category"] == "e_gt_telemetry_mismatch"
    assert out["sub"] == "telemetry_gap"


# ---------------------------------------------------------------- (a)

def test_a_requires_a_raw_event_that_does_not_survive_normalisation():
    """The claim is only made when a raw event in the window is absent from the normalised
    stream. An assertion without that trace is not category (a)."""
    rows = [row(1000), row(1500), row(2000)]
    s = sess(rows, edges=[9_000_000],
             raw=sorted([(r["ts_ms"], r["event_id"]) for r in rows] + [(1600, "evt_lost")]),
             normalised={r["event_id"] for r in rows}, span=(0, 10_000))
    out = classify.classify_boundary(1500, s, TAU, LEAD)
    assert out["category"] == "a_information_destroyed"
    assert out["raw_events_missing_from_normalised"] == 1
    assert "evt_lost" in out["missing_event_ids"]


def test_a_not_claimed_when_every_raw_event_survives():
    rows = [row(1000), row(1500), row(2000)]
    s = sess(rows, edges=[9_000_000], span=(0, 10_000))
    out = classify.classify_boundary(1500, s, TAU, LEAD)
    assert out["category"] != "a_information_destroyed"


# ---------------------------------------------------------------- (c)

def test_c_absorbed_micro_excursion_is_provable_by_the_absorption_diff():
    """Unreachable against default blocks, reachable against blocks built with absorption
    disabled -> the boundary sat inside an excursion blocks._absorb merged."""
    rows = [row(1000), row(5000)]
    s = sess(rows, edges=[9_000_000], edges_no_absorb=[5000], span=(0, 10_000))
    out = classify.classify_boundary(4500, s, TAU, LEAD)
    assert out["category"] == "c_absorbed_micro_excursion"
    assert out["distance_to_nearest_unabsorbed_edge_ms"] <= TAU
    assert out["distance_to_nearest_default_edge_ms"] > TAU


def test_c_outranks_b_so_an_absorbed_excursion_is_never_merely_signalled():
    rows = [row(4400, et="app_switch"), row(4500), row(4600)]
    s = sess(rows, edges=[9_000_000], edges_no_absorb=[4500], span=(0, 10_000))
    assert classify.classify_boundary(4500, s, TAU, LEAD)["category"] == \
        "c_absorbed_micro_excursion"


# ---------------------------------------------------------------- (b)

def test_b_preserved_inside_a_block_with_a_discriminating_signal():
    rows = [row(3000), row(4000, et="app_switch"), row(5000)]
    blocks = [{"start_ms": 0, "end_ms": 10_000}]
    s = sess(rows, blocks=blocks, edges=[0, 10_000], span=(0, 10_000))
    out = classify.classify_boundary(4000, s, TAU, LEAD)
    assert out["category"] == "b_preserved_inside_block"
    assert "app_switch" in out["signals"]
    assert out["strictly_inside_a_block"] is True


def test_b_fires_on_a_state_signal_not_only_an_event_type():
    rows = [row(3500, url="http://h/#/a", app="Edge", title="T"),
            row(4500, url="http://h/#/b", app="Edge", title="T")]
    blocks = [{"start_ms": 0, "end_ms": 10_000}]
    s = sess(rows, blocks=blocks, edges=[0, 10_000], span=(0, 10_000))
    out = classify.classify_boundary(4000, s, TAU, LEAD)
    assert out["category"] == "b_preserved_inside_block"
    assert "route_change" in out["signals"]


# ---------------------------------------------------------------- (d)

def test_d_is_the_residue_when_no_signal_is_present():
    rows = [row(3500, et="keystroke"), row(4500, et="keystroke")]
    blocks = [{"start_ms": 0, "end_ms": 10_000}]
    s = sess(rows, blocks=blocks, edges=[0, 10_000], span=(0, 10_000))
    out = classify.classify_boundary(4000, s, TAU, LEAD)
    assert out["category"] == "d_ambiguous_no_evidence"
    assert out["signals"] == []


def test_keystrokes_and_clicks_are_not_discriminating():
    """Background activity must not make every window look signalled."""
    sig = classify.signals_in_window(
        [row(1, et="keystroke"), row(2, et="mouse_click"),
         row(3, et="mouse_scroll"), row(4, et="screenshot_smart")], None)
    assert not classify.any_signal(sig)


# ---------------------------------------------------------------- totality

def test_every_boundary_receives_exactly_one_category():
    rows = [row(3500), row(4500)]
    blocks = [{"start_ms": 0, "end_ms": 10_000}]
    s = sess(rows, blocks=blocks, edges=[0, 10_000], span=(0, 10_000))
    seen = set()
    for g in (-5000, 4000, 4200, 50_000):
        out = classify.classify_boundary(g, s, TAU, LEAD)
        assert out["category"] in classify.CATEGORIES
        seen.add(out["category"])
    assert seen, "classifier returned nothing"


def test_classifier_is_deterministic():
    rows = [row(3500, et="app_switch"), row(4500)]
    blocks = [{"start_ms": 0, "end_ms": 10_000}]
    s = sess(rows, blocks=blocks, edges=[0, 10_000], span=(0, 10_000))
    a = classify.classify_boundary(4000, s, TAU, LEAD)
    b = classify.classify_boundary(4000, s, TAU, LEAD)
    assert a == b


def test_absorption_is_disabled_by_min_events_zero_without_touching_blocks():
    """Category (c) depends on this identity; blocks.py default behaviour is unchanged."""
    rows = flat(ev(0, app="W", title="a"), ev(100, app="E", title="b"),
                ev(200, app="W", title="a"))
    default = B.build_blocks(rows, min_events=3, min_ms=1500)
    disabled = B.build_blocks(rows, min_events=0, min_ms=0)
    assert len(default) == 1, "the excursion is absorbed by default"
    assert len(disabled) == 3, "min_events=0 disables absorption"
    assert sum(b["absorbed_excursions"] for b in disabled) == 0
