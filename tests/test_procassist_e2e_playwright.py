"""End-to-end through a real browser. Skipped cleanly when Playwright or Chromium is absent.

Checked on this machine at the time of writing: `playwright` is NOT installed and there is no
browser at `/opt/pw-browsers`, so this file skips. It is committed anyway, because the twelve
assertions below are the ones a hand click-through cannot be trusted to make, and because
installing Playwright is a one-line change that must not also require writing the tests.

    .venv/bin/pip install playwright && .venv/bin/playwright install chromium
    .venv/bin/python -m pytest tests/test_procassist_e2e_playwright.py -q

Nothing else in the suite depends on this file, and CI stays green without it.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from typing import Any, Iterator

import pytest

playwright_api = pytest.importorskip(
    "playwright.sync_api",
    reason="playwright is not installed; install it and chromium to run the e2e suite")

HR_PORT_ENV = "PROCASSIST_E2E_PORT"
FLAG_RECORD = "P1-07106250-010"
MISS_RECORD = "P6-07010448-004"
EXPECTED_DRAFT_EMPTY = "経費精算確認済み。費目：接待交際費　金額：135,181円。。"
EXPECTED_DRAFT_DONE = "経費精算確認済み。費目：接待交際費　金額：135,181円。規程内であることを確認した。"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """Serve the real app on one ephemeral port. Host header selection still applies."""
    import uvicorn

    from procassist.adapters.audit import AuditLog
    from procassist.api.app import create_app
    from procassist.service import Service

    tmp = os.path.join("build", "procassist", "e2e")
    os.makedirs(tmp, exist_ok=True)
    svc = Service(audit=AuditLog(os.path.join(tmp, "audit.sqlite3"),
                                 os.path.join(tmp, "audit.jsonl")))
    port = int(os.environ.get(HR_PORT_ENV) or _free_port())
    config = uvicorn.Config(create_app(svc), host="127.0.0.1", port=port, log_level="error")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    assert srv.started, "the app did not start"
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with playwright_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:                       # no chromium downloaded
            pytest.skip(f"chromium is not available: {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    """A page whose Host header selects the HR portal, which is where the demo opens."""
    ctx = browser.new_context(viewport={"width": 1400, "height": 1000},
                              extra_http_headers={"Host": "127.0.0.1:5132"})
    pg = ctx.new_page()
    pg.goto(server + "/", wait_until="networkidle")
    yield pg
    ctx.close()


# 1
def test_portal_loads_and_the_hr_queue_is_first(page):
    first = page.locator(".modulelist li").first
    assert "経費精算・給与変更" in first.inner_text()
    assert "M01" in first.inner_text()


# 2
def test_queue_renders_the_verbatim_headers(page, server):
    page.goto(server + "/payroll-items", wait_until="networkidle")
    headers = [h.strip() for h in page.locator("table.queue thead th").all_inner_texts()]
    assert headers[:7] == ["ID", "社員ID", "氏名", "区分", "金額", "種別", "ステータス"]


# 3
def test_prepare_all_resolves_every_row_and_the_counts_match_the_json(page, server):
    page.goto(server + "/payroll-items", wait_until="networkidle")
    batch = page.request.post(server + "/v1/prepare_queue",
                              data=json.dumps({"definition_id": "hr_expense_settlement"}),
                              headers={"Content-Type": "application/json"}).json()
    page.click("#prepare-all")
    page.wait_for_selector("#beforeafter:not([hidden])", timeout=15000)
    pills = page.locator("td.col-agent .q-pill")
    assert pills.count() == batch["summary"]["n_records"]
    rendered: dict = {}
    for text in pills.all_inner_texts():
        key = text.split()[-1].strip()
        rendered[key] = rendered.get(key, 0) + 1
    assert rendered == {k: v for k, v in batch["summary"]["counts"].items() if v}
    strip = page.inner_text("#beforeafter")
    assert "0 dispositions taken" in strip or "処分は 0 件" in strip


# 4
def test_the_flag_record_shows_the_clause_and_the_expected_authority(page, server):
    page.goto(f"{server}/payroll-items/{FLAG_RECORD}", wait_until="networkidle")
    page.wait_for_selector("#procassist-panel .pa-status", timeout=10000)
    panel = page.inner_text("#procassist-panel")
    assert "FLAG" in panel and "社長承認" in panel
    assert "第２条（承認権限）" in panel
    assert page.inner_text("#pa-clausetext").startswith("1回あたり5万円未満")


# 5
def test_a_miss_record_names_no_document(page, server, browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 1000},
                              extra_http_headers={"Host": "127.0.0.1:5133"})
    pg = ctx.new_page()
    pg.goto(f"{server}/payroll-items/{MISS_RECORD}", wait_until="networkidle")
    pg.wait_for_selector("#procassist-panel .pa-status", timeout=10000)
    panel = pg.inner_text("#procassist-panel")
    assert "MISS" in panel
    assert pg.locator("#pa-sec-clause").count() == 0
    assert pg.locator(".pa-docname").count() == 0
    assert "接待交際費規程" not in panel
    ctx.close()


# 6 + 7 + 8 + 9
def test_the_whole_human_loop(page, server):
    page.goto(f"{server}/payroll-items/{FLAG_RECORD}", wait_until="networkidle")
    page.wait_for_selector("#pa-usedraft", timeout=10000)

    # 7 — nothing is preselected before a human clicks
    assert page.locator(".pa-chip.pa-judgement.chosen").count() == 0

    # 6 — the draft lands with the judgement slot empty
    page.click("#pa-usedraft")
    page.wait_for_function(
        "() => document.getElementById('pi-note').value.endsWith('。。')", timeout=5000)
    assert page.input_value("#pi-note") == EXPECTED_DRAFT_EMPTY

    # 8 — a chip completes it byte-identically to the observed operator string
    page.click(".pa-chip.pa-judgement")
    page.wait_for_function(
        "() => document.getElementById('pi-note').value.includes('規程内')", timeout=5000)
    assert page.input_value("#pi-note") == EXPECTED_DRAFT_DONE

    # 9 — the toast appears only after the human clicks the host's own control
    assert page.locator("#toast").is_hidden()
    page.click("#btn-pi-ok")
    page.wait_for_selector("#toast:not([hidden])", timeout=5000)
    assert page.inner_text("#toast").strip() == "登録確定しました"


# 10
def test_the_audit_chain_verifies_and_relinks(page, server):
    page.goto(f"{server}/payroll-items/{FLAG_RECORD}", wait_until="networkidle")
    page.wait_for_selector("#procassist-panel .pa-status", timeout=10000)
    tail = page.request.get(server + "/v1/audit/tail?n=25").json()
    assert tail["chain_ok"] is True
    rows = tail["rows"]
    for earlier, later in zip(rows, rows[1:]):
        assert later["prev_hash"] == earlier["row_hash"]


# 11
def test_the_language_toggle_shows_english_and_keeps_the_clause_japanese(page, server):
    page.goto(f"{server}/payroll-items/{FLAG_RECORD}", wait_until="networkidle")
    page.wait_for_selector("#pa-clausetext", timeout=10000)
    page.click('.langtoggle button[data-lang="en"]')
    page.wait_for_function("() => document.documentElement.dataset.lang === 'en'")
    panel = page.inner_text("#procassist-panel")
    assert "approval authority by amount" in panel          # an *_en string is visible
    # and the regulation text itself is still Japanese, never machine-translated
    assert page.inner_text("#pa-clausetext").startswith("1回あたり5万円未満")
    assert page.locator("#pa-clausetext").is_visible()
    assert "not authoritative" in panel                     # the gloss is labelled as such


# 12
def test_the_evidence_page_matches_its_artifacts(page, server):
    path = "build/dataset_b/evidence/retrieval_feasibility.json"
    if not os.path.exists(path):
        pytest.skip("Dataset B evidence is not present")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)["baselines_by_document_heading"]
    page.goto(server + "/_evidence", wait_until="networkidle")
    text = page.inner_text(".ev")
    for value in (raw["B0_random"], raw["B1_most_frequent_overall"],
                  raw["B2_most_frequent_per_module"],
                  raw["B3_module_and_record_type_lookup"], raw["B3_wilson_95ci"][1]):
        assert f"{round(value * 100, 1)}%" in text, value
    assert "the table won" in text
