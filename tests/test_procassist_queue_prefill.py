"""Agent prefill over a whole queue: the counts, and the thing it must never do.

`prepare_queue` is the demo's centrepiece and also its biggest risk: it touches every record
on a screen at once. The tests below assert that what it touches is never a host field, never
a judgement, and never a disposition.
"""
from __future__ import annotations

import os
import re

import pytest

from procassist.adapters.audit import AuditLog
from procassist.service import Service

pytestmark = pytest.mark.skipif(
    not os.path.exists("build/dataset_b/evidence/records.jsonl"),
    reason="Dataset B evidence is not present")

QUEUE_JS = os.path.join("procassist", "panel", "queue.js")
FORBIDDEN = (".click(", "dispatchEvent", ".submit(", "requestSubmit", "new Event(",
             "new MouseEvent", "pi-note", "la-note", "btn-pi-ok", "btn-la-ok")


@pytest.fixture(scope="module")
def batch(tmp_path_factory):
    out = tmp_path_factory.mktemp("batch")
    svc = Service(audit=AuditLog(str(out / "a.sqlite3"), str(out / "a.jsonl")))
    return svc, svc.prepare_queue("hr_expense_settlement")


def test_every_record_on_the_queue_is_prepared(batch):
    svc, b = batch
    assert b["summary"]["n_records"] == 120
    assert len(b["rows"]) == 120
    assert {r["record_id"] for r in b["rows"]} == {
        r["record_id"] for r in svc.queue("hr_expense_settlement")}


def test_the_counts_add_up_to_the_queue(batch):
    _, b = batch
    counts = b["summary"]["counts"]
    assert sum(counts.values()) == b["summary"]["n_records"]
    assert counts["OK"] and counts["FLAG"] and counts["MISS"]
    from_rows = {}
    for row in b["rows"]:
        from_rows[row["status"]] = from_rows.get(row["status"], 0) + 1
    assert from_rows == {k: v for k, v in counts.items() if v}


def test_the_batch_agrees_with_preparing_each_record_singly(batch):
    """The surface must not have its own semantics."""
    svc, b = batch
    for row in b["rows"][:25]:
        single = svc.prepare_record(row["record_id"], log=False, with_population=False)
        assert single.status.value == row["status"]
        assert (single.draft is not None) == row["draft_ready"]


def test_no_disposition_is_taken_by_the_batch(batch):
    """The number that matters most in the demo."""
    _, b = batch
    assert b["summary"]["before"]["dispositions_taken"] == 0
    assert b["summary"]["after"]["dispositions_taken"] == 0


def test_every_staged_draft_has_the_judgement_slot_empty(batch):
    _, b = batch
    staged = [r for r in b["rows"] if r["draft_ready"]]
    assert len(staged) == b["summary"]["after"]["drafts_staged"] > 0
    for row in staged:
        # the HR template ends 「…。{judgement}。」, so an unfilled slot leaves 。。
        assert row["draft_preview"].endswith("。。"), row["draft_preview"]
        assert "規程内であることを確認した" not in row["draft_preview"]


def test_the_batch_resolves_a_document_only_where_one_governs(batch):
    _, b = batch
    with_doc = [r for r in b["rows"] if r["document_heading"]]
    assert len(with_doc) == b["summary"]["after"]["documents_resolved"]
    for row in b["rows"]:
        if row["status"] == "MISS":
            assert row["document_heading"] is None and row["clause_heading"] is None


def test_the_invoice_queue_prepares_and_still_refuses_every_record(batch):
    svc, _ = batch
    b = svc.prepare_queue("fi_invoice_approval")
    assert b["summary"]["counts"] == {"OK": 0, "FLAG": 0, "REQUIRES_REVIEW": 0, "MISS": 108}
    assert b["summary"]["after"]["documents_resolved"] == 0
    assert b["summary"]["after"]["drafts_staged"] == 108      # the comment is still evidenced
    assert all(r["draft_preview"].endswith("。差異。") for r in b["rows"])


def test_the_action_budget_is_a_range_and_names_its_module_key(batch):
    _, b = batch
    avoided = b["rows"][0]["actions_avoided"]
    assert avoided["module_key"] == "http://127.0.0.1:5132/#/payroll-items"
    lo, hi = avoided["app_switches"]["range"]
    assert 0 <= lo < hi                                   # a range, never a point estimate
    assert "Wilson" in avoided["app_switches"]["basis_en"]
    total = b["summary"]["after"]["actions_avoided_range"]
    assert total[0] < total[1]


def test_the_impact_strip_claims_no_time_no_money_no_headcount(batch):
    """Every quantity in the strip is a count of actions. Nothing is a duration or a cost."""
    _, b = batch
    after = b["summary"]["after"]
    assert set(after) == {"documents_resolved", "drafts_staged", "actions_avoided_range",
                          "keystrokes_total", "lookups_total", "dispositions_taken"}
    for key in after:
        for unit in ("hour", "minute", "second", "yen", "jpy", "usd", "cost", "fte", "saving"):
            assert unit not in key
    assert "no seconds, no yen, no fte" in b["summary"]["caveat_en"].lower()
    # and the per-record budget reports units of action, nothing else
    avoided = b["rows"][0]["actions_avoided"]
    assert set(avoided) == {"module_key", "app_switches", "keystrokes", "lookups", "caveat_en"}


def test_the_batch_is_audited_with_its_zero(batch):
    svc, b = batch
    rows = [r for r in svc.audit.tail(200) if r["event_type"] == "prepare_queue"]
    assert rows, "the batch itself must be audited, not only its records"
    import json
    assert json.loads(rows[-1]["detail_json"])["dispositions_taken"] == 0


@pytest.mark.parametrize("api", FORBIDDEN)
def test_the_prefill_script_touches_no_host_control(api):
    """queue.js must not know the name of a host field, let alone write to one."""
    with open(QUEUE_JS, encoding="utf-8") as fh:
        source = fh.read()
    assert api not in source, f"queue.js references {api!r}"


def _strip_comments(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(l for l in js.splitlines() if not l.strip().startswith("//"))


def test_the_prefill_script_assigns_no_value_and_no_judgement():
    """Read the code, not the comments: the comments are allowed to name the invariant."""
    with open(QUEUE_JS, encoding="utf-8") as fh:
        code = _strip_comments(fh.read())
    assert not re.search(r"\.value\s*=[^=]", code)
    assert "judgement" not in code.lower()
