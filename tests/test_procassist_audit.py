"""The audit log is append-only and tamper-evident.

It is the instrument behind the question Step 3 exists to inform — whether a model is warranted
here at all — so a row that can be quietly edited later is worthless.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from procassist.adapters.audit import EVENT_TYPES, AuditLog, new_trace_id


@pytest.fixture
def log(tmp_path):
    return AuditLog(str(tmp_path / "a.sqlite3"), str(tmp_path / "a.jsonl"))


def test_rows_append_and_the_hash_chain_verifies(log):
    trace = new_trace_id()
    for event in ("prepare", "draft_used", "judgement_chosen", "host_submitted"):
        log.append(trace, event, record_id="P1-07106250-010", suggested="FLAG:社長承認",
                   human_action=event)
    assert log.count() == 4
    assert log.verify_chain()
    assert [r["seq"] for r in log.tail(4)] == [1, 2, 3, 4]


def test_the_module_contains_no_update_and_no_delete():
    import pathlib
    source = pathlib.Path("procassist/adapters/audit.py").read_text(encoding="utf-8").upper()
    for statement in ("UPDATE AUDIT", "DELETE FROM", "DROP TABLE", "TRUNCATE"):
        assert statement not in source


def test_an_edited_row_breaks_the_chain(log):
    trace = new_trace_id()
    log.append(trace, "prepare", record_id="P1-07106250-010", suggested="FLAG:社長承認")
    log.append(trace, "host_submitted", record_id="P1-07106250-010", human_action="clicked")
    assert log.verify_chain()
    with sqlite3.connect(log.db_path) as conn:      # tamper, out of band
        conn.execute("UPDATE audit SET suggested = 'OK' WHERE seq = 1")
    assert not log.verify_chain()


def test_an_unknown_event_type_is_refused(log):
    with pytest.raises(ValueError):
        log.append(new_trace_id(), "auto_submitted")


def test_there_is_no_event_type_for_the_tool_acting_on_its_own():
    """The vocabulary itself encodes the boundary: every verb is something a human did."""
    assert "host_submitted" in EVENT_TYPES
    for banned in ("auto_approve", "auto_submit", "tool_submitted", "auto_dispositioned"):
        assert banned not in EVENT_TYPES


def test_the_jsonl_mirror_matches_the_database(log):
    trace = new_trace_id()
    log.append(trace, "prepare", record_id="P6-07010448-004", suggested="MISS",
               detail={"note": "請求書には費目がありません"})
    with open(log.jsonl_path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    assert len(rows) == log.count()
    assert rows[-1]["suggested"] == "MISS"
    assert rows[-1]["detail"]["note"] == "請求書には費目がありません"   # not escaped to \u
