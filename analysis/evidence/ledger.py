"""Pass 0 — 承認記録 ledger rows embedded in reference documents.

reads only:  documents.jsonl rows (in memory)
writes only: build/dataset_b/evidence/document_ledger.jsonl

These rows are record-like — `申請者 / 費目 / 金額 / 承認日 / 承認者` — but their PROVENANCE differs
from `records.jsonl`: those were read off the system's own queue, these off a Word document
someone pasted them into. Keeping them in a separate artifact prevents double-counting a record
that appears in both places, and lets H4 state WHICH source supplied a variable rather than
silently crediting the system for a value that only exists in a document.

They are joinable to `records.jsonl` on field values; they are never merged into it.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence

from . import common as C

LEDGER_BLOCK = re.compile(r"(承認記録|経費承認記録|処理記録)")
PAIR = re.compile(r"([^\s:：\r\n　]{1,14})\s*[:：]\s*([^\r\n　]{1,40})")
AMOUNT = re.compile(r"([0-9][0-9,]*)\s*円")


def parse_block(text: str) -> List[Dict[str, str]]:
    """Split a ledger section into one dict per record.

    A new record starts at each `申請者` key, which is how the rendered document delimits them —
    there is no blank line or bullet to split on.
    """
    pairs = [(m.group(1).strip(), m.group(2).strip()) for m in PAIR.finditer(text)]
    out: List[Dict[str, str]] = []
    cur: Dict[str, str] = {}
    for k, v in pairs:
        if k.startswith("申請者") and cur:
            out.append(cur)
            cur = {}
        cur[k] = v
    if cur:
        out.append(cur)
    return [r for r in out if len(r) >= 2]


def build(documents: Sequence[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    for d in documents:
        for cl in d.get("clauses", []):
            if cl.get("section") != "ledger":
                continue
            for i, fields in enumerate(parse_block(cl["text_ja"])):
                amt = None
                for k, v in fields.items():
                    m = AMOUNT.search(v)
                    if m and ("金額" in k or amt is None):
                        amt = float(m.group(1).replace(",", ""))
                        if "金額" in k:
                            break
                rows.append({
                    "ledger_row_id": f"{d['document_id'][:12]}:{cl['clause_id']}:{i:03d}",
                    "document_id": d["document_id"],
                    "clause_id": cl["clause_id"],
                    "row_index": i,
                    "fields": dict(fields),
                    "amount_jpy": amt,
                    "session_ids": list(d.get("session_ids") or []),
                    "first_seen_ms": d.get("first_seen_ms"),
                    "source": "document_ledger",
                    "extraction_method": "telemetry_text",
                    "evidence_type": "OBSERVED",
                })
    rows.sort(key=lambda r: r["ledger_row_id"])
    return rows


REQUIRED = ("ledger_row_id", "document_id", "clause_id", "row_index", "fields", "source")


def run(dataset: str, documents: Sequence[Dict]) -> Dict[str, Any]:
    rows = build(documents)
    art = C.write_jsonl(rows, os.path.join(C.evidence_dir(dataset), "document_ledger.jsonl"),
                        dataset, sort_key=lambda r: r["ledger_row_id"], required=REQUIRED)
    return {"artifact": art, "rows": rows}
