"""Ground-truth canonicaliser (EVALUATION_PROTOCOL §4, DATA_CONTRACT §5).

Synthetic fixtures: the repair rules are frozen (ADR-011) and must behave identically
whether or not dataset_a is on disk.
"""
from __future__ import annotations
import json
import pytest

from procmine import gt as GT


def ev(ts, event, **kw):
    d = {"ts_utc": ts, "event": event}
    d.update(kw)
    return d


T = "2026-06-30T12:{:02d}:{:02d}.000000+00:00".format


# ---------------------------------------------------------------- parse_ts

def test_parse_ts_and_absent_values():
    assert GT.parse_ts("2026-06-30T12:00:00.000000+00:00") == 1782820800000
    assert GT.parse_ts("2026-06-30T12:00:00Z") == 1782820800000
    assert GT.parse_ts(None) is None
    assert GT.parse_ts("") is None
    assert GT.parse_ts("not a timestamp") is None
    assert GT.parse_ts(12345) is None


def test_parse_ts_is_ordering_preserving():
    assert GT.parse_ts(T(0, 0)) < GT.parse_ts(T(0, 1)) < GT.parse_ts(T(1, 0))


# ---------------------------------------------------------------- stream intervals

def test_switch_out_closes_the_open_execution():
    evs = [ev(T(0, 0), "process_started", process_code="A", case_id="c1"),
           ev(T(0, 30), "process_switched_out", **{"from": "A", "to": "B"})]
    iv, an = GT.stream_intervals(evs)
    assert len(iv) == 1 and an == []
    assert iv[0]["process_code"] == "A" and iv[0]["closed_by"] == "process_switched_out"


def test_duplicate_process_started_is_collapsed_and_flagged():
    """DATA_SCHEMA §3 names this defect explicitly."""
    evs = [ev(T(0, 0), "process_started", process_code="A", case_id="c1"),
           ev(T(0, 1), "process_started", process_code="A", case_id="c1"),
           ev(T(0, 30), "process_switched_out", **{"from": "A", "to": "B"})]
    iv, an = GT.stream_intervals(evs)
    assert len(iv) == 1, "the duplicate must not open a second execution"
    assert [a["kind"] for a in an] == [GT.DUPLICATE_START]


def test_a_different_start_is_not_a_duplicate():
    evs = [ev(T(0, 0), "process_started", process_code="A", case_id="c1"),
           ev(T(0, 5), "process_started", process_code="A", case_id="c2")]
    iv, an = GT.stream_intervals(evs)
    assert len(iv) == 2 and an == []


def test_unpaired_switch_out_is_flagged_not_repaired():
    evs = [ev(T(0, 10), "process_switched_out", **{"from": "A", "to": "B"})]
    iv, an = GT.stream_intervals(evs)
    assert iv == []
    assert [a["kind"] for a in an] == [GT.UNPAIRED_SWITCH]


def test_suspend_resume_carries_split_id_on_the_suspended_side():
    """The manifest records split_id only on the phase-2 fragment; the stream is the ONLY
    source that names it for the suspended phase-1 fragment."""
    evs = [ev(T(0, 0), "process_started", process_code="B", case_id="c1"),
           ev(T(0, 20), "process_suspended", split_id="S1", **{"from": "B", "to": "H"}),
           ev(T(1, 0), "process_resumed", process_code="B", case_id="c2",
              split_id="S1", phase=2),
           ev(T(1, 30), "process_switched_out", **{"from": "B", "to": "A"})]
    iv, an = GT.stream_intervals(evs)
    assert an == []
    assert len(iv) == 2
    assert iv[0]["split_id"] == "S1", "phase-1 fragment must pick up split_id from the stream"
    assert iv[1]["split_id"] == "S1" and iv[1]["phase"] == 2


def test_task_started_is_counted_against_the_open_execution():
    evs = [ev(T(0, 0), "process_started", process_code="A", case_id="c1"),
           ev(T(0, 1), "task_started", task_id="t1"),
           ev(T(0, 2), "task_started", task_id="t2"),
           ev(T(0, 30), "process_switched_out", **{"from": "A", "to": "B"})]
    iv, _ = GT.stream_intervals(evs)
    assert iv[0]["n_tasks"] == 2


def test_session_ended_closes_the_last_execution():
    evs = [ev(T(0, 0), "process_started", process_code="A", case_id="c1"),
           ev(T(0, 50), "session_ended")]
    iv, _ = GT.stream_intervals(evs)
    assert iv[0]["closed_by"] == "session_ended"


def test_empty_stream():
    assert GT.stream_intervals([]) == ([], [])


# ---------------------------------------------------------------- reconcile

def _man(**kw):
    d = {"session_id": "s1", "process_code": "A", "family_name": "F", "domain": "hr",
         "case_id": "c1", "variant": "std", "seq": 1, "phase": 1, "split_id": None,
         "exec_id": "X-1", "start_ts": T(0, 0), "end_ts": T(0, 30),
         "start_ms": GT.parse_ts(T(0, 0)), "end_ms": GT.parse_ts(T(0, 30)),
         "apps": [], "continues_from_prev": False, "continues_to_next": False}
    d.update(kw)
    return d


def test_agreeing_sources_are_clean():
    stream = [{"process_code": "A", "case_id": "c1", "start_ms": GT.parse_ts(T(0, 0)),
               "end_ms": GT.parse_ts(T(0, 30)), "start_ts": T(0, 0), "split_id": None,
               "phase": None, "closed_by": "process_switched_out", "n_tasks": 1}]
    out = GT.reconcile([_man()], stream, tau_ms=2000)
    assert len(out) == 1
    assert out[0]["confidence"] == "clean" and out[0]["repair_flags"] == []
    assert out[0]["source"] == "both"
    assert out[0]["delta_start_ms"] == 0


def test_disagreement_beyond_tau_is_disputed_and_both_values_kept():
    stream = [{"process_code": "A", "case_id": "c1",
               "start_ms": GT.parse_ts(T(0, 0)) + 9000, "end_ms": GT.parse_ts(T(0, 30)),
               "start_ts": T(0, 9), "split_id": None, "phase": None,
               "closed_by": "process_switched_out", "n_tasks": 1}]
    out = GT.reconcile([_man()], stream, tau_ms=2000)
    assert GT.MANIFEST_STREAM in out[0]["repair_flags"]
    assert out[0]["confidence"] == "disputed"
    assert out[0]["manifest_value"] is not None and out[0]["stream_value"] is not None


def test_chunk_continuation_is_a_deterministic_repair():
    out = GT.reconcile([_man(continues_to_next=True)], [], tau_ms=2000)
    assert out[0]["repair_flags"] == [GT.CHUNK_MERGE]
    assert out[0]["confidence"] == "repaired"


def test_zero_duration_is_disputed():
    out = GT.reconcile([_man(end_ms=GT.parse_ts(T(0, 0)))], [], tau_ms=2000)
    assert GT.ZERO_DURATION in out[0]["repair_flags"]
    assert out[0]["confidence"] == "disputed"


def test_split_id_is_backfilled_from_the_stream():
    stream = [{"process_code": "A", "case_id": "c1", "start_ms": GT.parse_ts(T(0, 0)),
               "end_ms": GT.parse_ts(T(0, 30)), "start_ts": T(0, 0), "split_id": "S9",
               "phase": None, "closed_by": "process_suspended", "n_tasks": 0}]
    out = GT.reconcile([_man(split_id=None)], stream, tau_ms=2000)
    assert out[0]["split_id"] == "S9"
    assert out[0]["split_id_source"] == "stream"


def test_stream_only_execution_is_retained_not_dropped():
    stream = [{"process_code": "Z", "case_id": "zz", "start_ms": 1, "end_ms": 2,
               "start_ts": T(0, 0), "split_id": None, "phase": None,
               "closed_by": "x", "n_tasks": 0, "session_id": "s1"}]
    out = GT.reconcile([], stream, tau_ms=2000)
    assert len(out) == 1 and out[0]["source"] == "stream"


# ---------------------------------------------------------------- canonicalise

def _exe(case, split=None, a=0, b=10, conf="clean"):
    return {"session_id": "s1", "process_code": "A", "case_id": case, "split_id": split,
            "variant": "std", "family_name": "F", "domain": "hr",
            "start_ts": T(0, a), "end_ts": T(0, b),
            "start_ms": GT.parse_ts(T(0, a)), "end_ms": GT.parse_ts(T(0, b)),
            "confidence": conf, "repair_flags": []}


def test_fragments_group_by_split_id_across_different_case_ids():
    """The decisive case: A's two fragments carry DIFFERENT case_ids and are linked only
    by split_id. Grouping on case_id reports an interruption rate of exactly zero."""
    out = GT.canonicalise([_exe("c1", "S1", 0, 10), _exe("c2", "S1", 40, 50)])
    assert len(out) == 1
    assert out[0]["n_fragments"] == 2
    assert sorted(out[0]["case_ids"]) == ["c1", "c2"]


def test_unsplit_executions_stay_separate():
    out = GT.canonicalise([_exe("c1", None, 0, 10), _exe("c2", None, 40, 50)])
    assert len(out) == 2 and all(c["n_fragments"] == 1 for c in out)


def test_canonical_durations_hand_computed():
    """Fragments 0-10 s and 40-50 s: active 20 s, wall span 50 s."""
    out = GT.canonicalise([_exe("c1", "S1", 0, 10), _exe("c2", "S1", 40, 50)])
    assert out[0]["total_duration_s"] == pytest.approx(20.0, abs=1e-3)
    assert out[0]["wall_span_s"] == pytest.approx(50.0, abs=1e-3)


def test_confidence_is_the_worst_of_the_fragments():
    out = GT.canonicalise([_exe("c1", "S1", 0, 10, "clean"),
                           _exe("c2", "S1", 40, 50, "disputed")])
    assert out[0]["confidence"] == "disputed"
    out2 = GT.canonicalise([_exe("c1", "S1", 0, 10, "clean"),
                            _exe("c2", "S1", 40, 50, "repaired")])
    assert out2["0" if False else 0]["confidence"] == "repaired"


def test_canonicalise_empty():
    assert GT.canonicalise([]) == []
