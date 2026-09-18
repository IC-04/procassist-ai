"""Pass 0 contract tests.

The provenance and verbatim-text tests are the load-bearing ones: every downstream claim about
what a screen said rests on `text_ja` not having been quietly normalised, and on each row naming
where it came from.
"""
from __future__ import annotations

import glob
import json
import os
import shutil

import pytest

from analysis.evidence import common as C
from analysis.evidence import documents as DOCS
from analysis.evidence import ledger as LEDGER
from analysis.evidence import outcomes as OUT
from analysis.evidence import pass0_text as P0
from analysis.evidence import records as REC

ROOT = C.ROOT
DATASET_B = os.path.join(ROOT, "dataset_b")
needs_b = pytest.mark.skipif(not os.path.isdir(DATASET_B), reason="dataset_b not present")


@pytest.fixture(scope="module")
def caps():
    if not os.path.isdir(DATASET_B):
        pytest.skip("dataset_b not present")
    return P0.harvest(DATASET_B)


# ---------------------------------------------------------------- provenance

@needs_b
def test_every_row_has_full_provenance(caps):
    for r in caps:
        for k in P0.REQUIRED + C.PROVENANCE_FIELDS:
            assert k in r and r[k] is not None or k in ("browser_origin", "browser_route"), \
                f"{k} missing/None on {r.get('capture_id')}"
        assert r["extraction_method"] == "telemetry_text"
        assert r["evidence_type"] in C.EVIDENCE_TYPES


@needs_b
def test_text_ja_is_byte_identical_to_source(caps):
    """No normalisation, no translation, no trimming — asserted against the raw file."""
    want = {}
    for path in sorted(glob.glob(os.path.join(DATASET_B, "*", "*", "events.jsonl"))):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            xt = ((e.get("context") or {}).get("extracted_text") or {})
            t = xt.get("text") if isinstance(xt, dict) else None
            if isinstance(t, str) and t.strip():
                want[e.get("event_id")] = t
    assert want
    for r in caps:
        src = want.get(r["source_event_id"])
        assert src is not None
        assert r["text_ja"] == src, f"text mutated for {r['capture_id']}"
        assert r["text_sha256"] == C.sha256_text(src)
        assert r["text_len"] == len(src)


@needs_b
def test_capture_id_and_document_id_are_stable_across_runs(caps):
    again = P0.harvest(DATASET_B)
    assert [r["capture_id"] for r in caps] == [r["capture_id"] for r in again]
    a = [d["document_id"] for d in DOCS.build(caps)["documents"]]
    b = [d["document_id"] for d in DOCS.build(again)["documents"]]
    assert a == b and a


# ---------------------------------------------------------------- determinism

@needs_b
def test_rerun_produces_byte_identical_output(caps):
    """Determinism is asserted on the serialised bytes rather than on files: `guard_path`
    refuses to write outside the evidence directory, including a pytest tmp_path, and relaxing
    it for a test would defeat the guard it exists to enforce."""
    def payloads(captures):
        docs = DOCS.build(captures)["documents"]
        rec = REC.build(captures)["rows"]
        return (
            C.serialise_jsonl(captures, lambda r: (r["session_id"], r["sequence_number"] or 0,
                                                   r["capture_id"]), P0.REQUIRED),
            C.serialise_jsonl(docs, lambda x: (-x["n_captures"], x["document_id"]),
                              DOCS.REQUIRED),
            C.serialise_jsonl(LEDGER.build(docs), lambda r: r["ledger_row_id"],
                              LEDGER.REQUIRED),
            C.serialise_jsonl(rec, lambda r: (r["session_id"], r["sequence_number"] or 0,
                                              r["row_index"], r["record_id"]), REC.REQUIRED),
        )

    a = payloads(caps)
    b = payloads(P0.harvest(DATASET_B))
    for i, (x, y) in enumerate(zip(a, b)):
        assert x == y, f"artifact {i} is not byte-identical across runs"


# ---------------------------------------------------------------- write scope

def test_writes_nothing_outside_the_evidence_directory(tmp_path):
    for bad in (os.path.join(ROOT, "build", "dataset_b", "blocks.jsonl"),
                os.path.join(ROOT, "segments.jsonl"),
                os.path.join(ROOT, "dataset_b", "x.jsonl"),
                os.path.join(ROOT, "build", "dataset_b", "evidence", "..", "blocks.jsonl")):
        with pytest.raises(C.ArtifactInvalid):
            C.guard_path(bad, "dataset_b")
    ok = os.path.join(C.evidence_dir("dataset_b"), "sub", "x.jsonl")
    assert C.guard_path(ok, "dataset_b").endswith(os.path.join("evidence", "sub", "x.jsonl"))


def test_invalid_row_is_a_hard_failure_not_a_warning(tmp_path):
    d = str(tmp_path)
    with pytest.raises(C.ArtifactInvalid):
        C.write_jsonl([{"a": 1}], os.path.join(d, "x.jsonl"), d, required=("a",))
    with pytest.raises(C.ArtifactInvalid):
        C.write_jsonl([{"a": 1, "extraction_method": "m", "evidence_type": "NOPE"}],
                      os.path.join(d, "x.jsonl"), d, required=("a",))


# ---------------------------------------------------------------- rules

def test_unparseable_clause_is_null_not_guessed():
    kind, parsed = DOCS.parse_rule("取引先接待に関する費用の承認・計上基準を定める。")
    assert kind == "unknown" and parsed is None


def test_threshold_rule_parses_with_units_and_consequents():
    kind, parsed = DOCS.parse_rule("1回あたり5万円未満：部門長承認。5万円以上：役員承認。10万円以上：社長承認。")
    assert kind == "threshold"
    tiers = parsed["tiers"]
    assert [t["value_jpy"] for t in tiers] == [50000.0, 50000.0, 100000.0]
    assert [t["operator"] for t in tiers] == ["<", ">=", ">="]
    assert tiers[-1]["consequent"] == "社長承認"


def test_ledger_is_split_out_of_the_regulation():
    body = "第１条（目的）定める。第２条（記録）提出すること。経費承認記録 申請者: 山田 太郎　金額: 1,000円"
    sections = [c["section"] for c in DOCS.split_clauses(body)]
    assert "ledger" in sections and "clause" in sections


# ---------------------------------------------------------------- records

@needs_b
def test_record_headers_stored_verbatim_with_positional_index(caps):
    rows = REC.build(caps)["rows"]
    q = [r for r in rows if r["source_view"] == "queue_table"]
    assert q
    for r in q[:200]:
        assert r["column_headers"], r["record_id"]
        assert list(r["fields"].keys()) == list(r["column_headers"])
        assert len(r["fields_by_index"]) == len(r["column_headers"])
        assert r["fields_by_index"]["0"] == r["record_id"]


@needs_b
def test_module_disagreement_is_recorded_not_resolved(caps):
    built = REC.build(caps)
    rows = built["rows"]
    assert any(r["module_id_agrees_with_prefix"] is False for r in rows), \
        "the URL and prefix keys agreed everywhere; the cross-check would be vacuous"
    for r in rows:
        assert "prefix_modal_module_id" in r and "module_id_agrees_with_prefix" in r
        # the URL-derived value is never overwritten by the prefix
        if r["module_id_agrees_with_prefix"] is False:
            assert r["module_id"] != r["prefix_modal_module_id"]


# ---------------------------------------------------------------- outcomes

@needs_b
def test_outcome_polarity_distribution_is_reported(caps):
    rows = REC.build(caps)["rows"]
    built = OUT.build(caps, rows)
    rep = built["report"]
    assert rep["n_outcomes"] == len(built["rows"])
    assert "toast" in rep["by_source"] and rep["_finding"]
    assert sum(rep["by_source"]["toast"].values()) > 0


def test_negative_polarity_is_checked_before_positive():
    assert OUT.polarity("申請を却下しました") == "negative"
    assert OUT.polarity("登録確定しました") == "positive"
    assert OUT.polarity("なにか") == "unknown"


@needs_b
def test_document_ledger_is_a_separate_artifact_not_merged_into_records(caps):
    docs = DOCS.build(caps)["documents"]
    led = LEDGER.build(docs)
    rec = REC.build(caps)["rows"]
    assert led
    assert all(r["source"] == "document_ledger" for r in led)
    assert all("ledger_row_id" in r for r in led)
    # no ledger row leaked into records.jsonl
    assert not any(r.get("source") == "document_ledger" for r in rec)
