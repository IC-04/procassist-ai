"""The challenger: local, off by default, and never allowed to override the table.

The value of this component is entirely in what it is *not* permitted to do. It is a real
retriever over the real corpus, and the tests below pin the three properties that keep it an
argument about method rather than a RAG demo nobody evaluated.
"""
from __future__ import annotations

import os
import pathlib

import pytest

from procassist.adapters.audit import AuditLog
from procassist.adapters.documents import DocumentIndex
from procassist.challenger import Challenger
from procassist.challenger.retriever import ngrams
from procassist.service import Service

pytestmark = pytest.mark.skipif(
    not os.path.exists("build/dataset_b/evidence/documents.jsonl"),
    reason="Dataset B evidence is not present")


@pytest.fixture(scope="module")
def svc(tmp_path_factory):
    out = tmp_path_factory.mktemp("chal")
    return Service(audit=AuditLog(str(out / "a.sqlite3"), str(out / "a.jsonl")))


def test_it_is_local_with_no_network_no_key_and_no_model_file():
    """Read the source: nothing here reaches outside the process."""
    root = pathlib.Path("procassist/challenger")
    banned = ("requests", "httpx", "urllib", "socket", "openai", "anthropic",
              "sentence_transformers", "transformers", "torch", "faiss", "chromadb",
              "api_key", "API_KEY", "http://", "https://")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path} references {token}"


def test_it_indexes_the_real_clause_corpus(svc):
    c = Challenger.from_documents(DocumentIndex.load().rows)
    assert len(c.docs) > 300
    assert all(d.text_ja for d in c.docs)


def test_character_ngrams_because_japanese_has_no_spaces():
    assert ngrams("接待交際費規程", 3)[:2] == ["接待交", "待交際"]
    assert ngrams("金額：135,181円　差異") == ngrams("金額：135,181円 差異")   # U+3000 dropped
    assert ngrams("") == []


def test_the_endpoint_is_off_unless_explicitly_switched_on():
    """A reviewer must meet this deliberately, not stumble into it."""
    from procassist.api import app as app_module
    assert app_module.CHALLENGER_ENABLED is False or os.environ.get("PROCASSIST_CHALLENGER")


def test_the_retriever_never_changes_the_verdict(svc):
    """Whatever it returns, prepare_record is unaffected."""
    before = svc.prepare_record("P1-07106250-010", log=False, with_population=False)
    svc.challenge("P1-07106250-010")
    after = svc.prepare_record("P1-07106250-010", log=False, with_population=False)
    assert before.status == after.status
    assert before.document == after.document
    assert (before.clause or {}).get("clause_id") == (after.clause or {}).get("clause_id")


def test_the_comparison_declares_itself_unevaluated_and_names_the_bar(svc):
    c = svc.challenge("P1-07106250-010")
    assert c["evaluated"] is False
    assert "71.5%" in c["bar_en"]
    assert "NOT been scored" in c["authority_en"]
    assert "authoritative" in c["authority_en"]
    assert "64.2%" in c["authority_en"] and "n=148" in c["authority_en"]
    assert "評価していません" in c["authority_ja"]


def test_the_retriever_is_allowed_to_lose_in_public(svc):
    """On the FLAG record it disagrees with the table, and the panel shows both.

    This is the finding, not a bug: the query is the record's own surface text, and the
    nearest text in the corpus is the operator's comment and the ledger — not 第２条. Pinning
    it means a future change that quietly hides the disagreement fails here.
    """
    c = svc.challenge("P1-07106250-010")
    assert c["lookup"]["clause_id"] == "c002"
    assert c["lookup"]["heading_ja"] == "第２条（承認権限）"
    assert c["retrieved"], "the retriever must actually return candidates"
    assert c["agrees"] is False
    assert c["retrieved"][0]["clause_id"] != "c002"


def test_scores_are_labelled_scores_and_never_leak_into_the_four_statuses(svc):
    c = svc.challenge("P1-07106250-010")
    assert all("score" in r for r in c["retrieved"])
    assert c["status"] in ("OK", "FLAG", "REQUIRES_REVIEW", "MISS")
    # a retrieval score must never appear on a PrepareResult
    result = svc.prepare_record("P1-07106250-010", log=False, with_population=False)
    assert "score" not in str(result.model_dump()).lower()
