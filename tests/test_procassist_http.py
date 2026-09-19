"""HTTP round trips: one per demo case, plus the audit trail they leave behind.

Exercised with an explicit `Host` header, because host resolution is real logic here —
`(origin, route)` is the module key — and a test that did not set it would be testing
something the demo does not do. The caller is `tests/asgi_client.py` rather than
`fastapi.testclient`, which would have required httpx, a fifth dependency.
"""
from __future__ import annotations

import os

import pytest
from procassist.adapters.audit import AuditLog
from procassist.api.app import create_app
from procassist.service import Service

from asgi_client import ASGIClient

pytestmark = pytest.mark.skipif(
    not os.path.exists("build/dataset_b/evidence/records.jsonl"),
    reason="Dataset B evidence is not present")

HR = "127.0.0.1:5132"
FI = "127.0.0.1:5133"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("http-audit")
    svc = Service(audit=AuditLog(str(out / "a.sqlite3"), str(out / "a.jsonl")))
    return ASGIClient(create_app(svc))


def _get(client, host, path):
    return client.get(path, headers={"Host": host})


# ── the replica ────────────────────────────────────────────────────────────────────────────

def test_the_fi_queue_renders_the_verbatim_headers_and_the_badges(client):
    r = _get(client, FI, "/payroll-items")
    assert r.status_code == 200
    for header in ("ID", "社員ID", "氏名", "区分", "金額", "種別", "ステータス"):
        assert header in r.text
    for badge in ("SYNTHETIC", "REPLICA", "PRODUCTION-UNVERIFIED"):
        assert badge in r.text
    assert "P6-07010448-001" in r.text and "716,232円" in r.text


def test_the_same_route_on_a_different_origin_is_a_different_module(client):
    """:5132/payroll-items and :5133/payroll-items are M01 and M05, not one screen."""
    hr = _get(client, HR, "/payroll-items").text
    fi = _get(client, FI, "/payroll-items").text
    assert "M01" in hr and "経費精算・給与変更" in hr and "P1-" in hr
    assert "M05" in fi and "請求書承認・経費精算" in fi and "P6-" in fi


def test_an_undefined_host_route_is_a_404_not_a_guess(client):
    assert _get(client, HR, "/resident-tax").status_code == 404
    assert _get(client, "127.0.0.1:5199", "/payroll-items").status_code == 404


def test_a_record_from_another_queue_is_refused(client):
    assert _get(client, FI, "/payroll-items/P1-07106250-010").status_code == 404


def test_the_detail_page_carries_the_host_field_and_its_verbatim_placeholder(client):
    r = _get(client, FI, "/payroll-items/P6-07010448-004")
    assert r.status_code == 200
    assert 'id="pi-note"' in r.text
    assert "処理内容・確認コメントを入力してください…" in r.text
    assert 'id="btn-pi-ok"' in r.text
    assert "登録確定しました" in r.text
    assert 'id="procassist-panel"' in r.text          # the panel is on this page, not another


def test_the_managerial_queue_uses_its_own_element_ids_and_placeholder(client):
    r = _get(client, FI, "/leave-applications/P9-07084298-006")
    assert 'id="la-note"' in r.text and 'id="btn-la-ok"' in r.text
    assert "承認コメントまたは差戻し理由を入力してください…" in r.text


# ── POST /v1/prepare, one per case ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "record_id,status,authority",
    [
        ("P1-07089771-005", "OK", "役員承認"),
        ("P1-07106250-010", "FLAG", "社長承認"),
        ("P6-07010448-004", "MISS", None),
        ("P9-07084298-006", "REQUIRES_REVIEW", "金額（数値）"),
    ],
)
def test_prepare_returns_the_expected_verdict(client, record_id, status, authority):
    r = client.post("/v1/prepare", json={"record_id": record_id})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == status
    assert body["draft"] is None or body["draft"]["judgement"] is None
    thresholds = [c for c in body["checks"] if c["kind"] == "threshold"]
    if authority is None:
        assert thresholds == []
        assert body["document"] is None and body["clause"] is None
    else:
        assert thresholds[0]["expected_ja"] == authority


def test_prepare_on_an_unknown_record_is_a_404(client):
    assert client.post("/v1/prepare", json={"record_id": "P6-99999999-999"}).status_code == 404


def test_view_source_returns_the_capture_provenance(client):
    body = client.post("/v1/prepare", json={"record_id": "P1-07106250-010"}).json()
    doc = body["document"]
    r = client.get(f"/v1/source/{doc['document_id']}/{body['clause']['clause_id']}")
    assert r.status_code == 200
    src = r.json()
    assert src["text_ja"] == body["clause"]["text_ja"]
    assert src["capture_ids"] and src["session_ids"] and src["title_aliases"]
    # document_id is a capture-window hash: many captures carry the same clause
    assert len(doc["sibling_document_ids"]) > 1


# ── the audit trail ────────────────────────────────────────────────────────────────────────

def test_every_interaction_is_recorded_and_the_chain_holds(client):
    svc = client.app.state.service
    before = svc.audit.count()
    body = client.post("/v1/prepare", json={"record_id": "P1-07106250-010"}).json()
    trace = body["trace_id"]
    for event, action in (("draft_used", "pasted the draft into #pi-note"),
                          ("judgement_chosen", "規程内であることを確認した"),
                          ("host_submitted", "clicked #btn-pi-ok")):
        r = client.post("/v1/event", json={
            "trace_id": trace, "event_type": event, "record_id": "P1-07106250-010",
            "definition_id": "hr_expense_settlement", "module_id": "M01",
            "suggested": "FLAG:社長承認", "human_action": action, "detail": {}})
        assert r.status_code == 200
    assert svc.audit.count() == before + 4
    assert svc.audit.verify_chain()

    rows = svc.audit.tail(4)
    assert [r["event_type"] for r in rows] == [
        "prepare", "draft_used", "judgement_chosen", "host_submitted"]
    # the pairing that matters: what the tool suggested, and what the human then did
    assert all(r["suggested"] == "FLAG:社長承認" for r in rows)
    assert rows[-1]["human_action"] == "clicked #btn-pi-ok"


def test_an_unaudited_event_type_is_refused(client):
    r = client.post("/v1/event", json={"trace_id": "tr_x", "event_type": "auto_approved"})
    assert r.status_code == 400
