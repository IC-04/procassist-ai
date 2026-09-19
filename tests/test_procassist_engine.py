"""The four demo cases, end to end through the engine, on real Dataset B records.

Every record id below exists in build/dataset_b/evidence/records.jsonl. Nothing is
constructed for the test: if the corpus changes, these fail, which is the point.
"""
from __future__ import annotations

import os

import pytest

from procassist.adapters.audit import AuditLog
from procassist.core.comment import complete
from procassist.core.definitions import Status
from procassist.service import Service

pytestmark = pytest.mark.skipif(
    not os.path.exists("build/dataset_b/evidence/records.jsonl"),
    reason="Dataset B evidence is not present")


@pytest.fixture(scope="module")
def svc(tmp_path_factory):
    out = tmp_path_factory.mktemp("audit")
    return Service(audit=AuditLog(str(out / "a.sqlite3"), str(out / "a.jsonl")))


# ── the four cases ─────────────────────────────────────────────────────────────────────────

def test_case_1_ok(svc):
    """P1-07089771-005, 接待交際費 60,936円 -> one tier matches -> OK, 役員承認."""
    r = svc.prepare_record("P1-07089771-005", log=False)
    assert r.status is Status.OK
    threshold = _threshold(r)
    assert threshold.status is Status.OK
    assert threshold.expected_ja == "役員承認"
    assert r.clause["text_ja"] == "1回あたり5万円未満：部門長承認。5万円以上：役員承認。10万円以上：社長承認。"
    assert r.document["regulation_name_ja"] == "接待交際費規程"


def test_case_2_flag(svc):
    """P1-07106250-010, 接待交際費 135,181円 -> two tiers match -> FLAG, strictest 社長承認."""
    r = svc.prepare_record("P1-07106250-010", log=False)
    assert r.status is Status.FLAG
    threshold = _threshold(r)
    assert threshold.status is Status.FLAG
    assert threshold.expected_ja == "社長承認"
    assert "135,181円" in threshold.why_ja and "10万円以上" in threshold.why_ja
    # the denominator is measured, not asserted: a lone FLAG would read as an anecdote
    assert r.population["n_same_status"] > 1
    assert r.population["n_queue"] == 120


def test_case_3_miss_guesses_no_document(svc):
    """Any P6 invoice: no document, no clause, no ranked fallback."""
    r = svc.prepare_record("P6-07010448-004", log=False)
    assert r.status is Status.MISS
    assert r.document is None and r.clause is None
    miss = [c for c in r.checks if c.kind == "lookup"]
    assert len(miss) == 1 and miss[0].status is Status.MISS
    assert "請求書" in miss[0].why_ja
    # every invoice in the queue reaches the same verdict; that is the honest headline
    assert r.population["n_same_status"] == r.population["n_queue"]


def test_case_4_requires_review_when_the_amount_is_not_on_screen(svc):
    """P9-07084298-006: 接待交際費 is governed, but this screen has no 金額 column."""
    r = svc.prepare_record("P9-07084298-006", log=False)
    assert r.status is Status.REQUIRES_REVIEW
    threshold = _threshold(r)
    assert threshold.status is Status.REQUIRES_REVIEW
    assert "金額" in (threshold.why_ja or "")
    assert "金額" not in svc.defs.by_id["fi_managerial_expense_approval"].column_headers_ja
    # no draft is offered rather than one with a hole in it
    assert r.draft is None


# ── invariants ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("record_id", ["P1-07089771-005", "P1-07106250-010",
                                       "P6-07010448-004", "P9-07084298-006"])
def test_judgement_is_never_decided_by_the_engine(svc, record_id):
    r = svc.prepare_record(record_id, log=False)
    if r.draft is not None:
        assert r.draft.judgement is None
        assert r.draft.text_ja == r.draft.template_ja.format(
            **r.draft.filled_slots, **{r.draft.judgement_slot: ""})


def test_every_record_in_every_queue_keeps_the_judgement_empty(svc):
    """Not a sample: all 252 records across the three queues."""
    n = 0
    for definition in svc.definitions():
        for row in svc.queue(definition.definition_id):
            r = svc.prepare_record(row["record_id"], log=False, with_population=False)
            assert r.draft is None or r.draft.judgement is None
            assert r.status in set(Status)
            n += 1
    assert n > 200


def test_no_confidence_score_anywhere(svc):
    dumped = str(svc.prepare_record("P1-07106250-010", log=False).model_dump())
    for word in ("confidence", "score", "probability", "likelihood"):
        assert word not in dumped.lower()


@pytest.mark.parametrize(
    "record_id,judgement,expected",
    [
        ("P6-07010448-004", "なし承認",
         "請求書照合完了。INV-2026-7347　金額：1,832,962円。差異なし承認。"),
        ("P6-07010448-008", "あり要確認",
         "請求書照合完了。INV-2026-7351　金額：1,218,687円。差異あり要確認。"),
        ("P1-07106250-010", "規程内であることを確認した",
         "経費精算確認済み。費目：接待交際費　金額：135,181円。規程内であることを確認した。"),
    ],
)
def test_comment_renders_byte_identical_to_the_observed_string(svc, record_id, judgement,
                                                               expected):
    """These strings were typed by operators in Dataset B; we reproduce them exactly.

    Including the ideographic space U+3000 before 金額 and 円 as a suffix.
    """
    r = svc.prepare_record(record_id, log=False)
    got = complete(r.draft, judgement)
    assert got == expected
    assert got.encode("utf-8") == expected.encode("utf-8")
    assert "　" in got and "¥" not in got


def test_a_judgement_that_was_never_observed_is_refused(svc):
    r = svc.prepare_record("P6-07010448-004", log=False)
    with pytest.raises(ValueError):
        complete(r.draft, "差戻し")


def test_no_procassist_module_reads_ground_truth():
    """CLAUDE.md hard rule 3, applied to this package too."""
    import pathlib
    forbidden = ("procmine.gt", "from .gt", "gt_manifest", "expected_boundaries",
                 "build/dataset_a")
    for path in pathlib.Path("procassist").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} references {token}"


def test_nothing_in_procassist_writes_to_the_step_1_or_step_2_outputs():
    """build/dataset_b is read-only to this package."""
    import pathlib
    import re
    opens = re.compile(r"open\([^)]*['\"][wa]")
    for path in pathlib.Path("procassist").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if opens.search(line):
                assert "dataset_b" not in line and "segments" not in line, line


def _threshold(result):
    found = [c for c in result.checks if c.kind == "threshold"]
    assert len(found) == 1, f"expected one threshold check, got {len(found)}"
    return found[0]
