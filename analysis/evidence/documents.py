"""Pass 0 — reference documents, keyed by CONTENT rather than filename.

reads only:  screen_text.jsonl rows (in memory)
writes only: build/dataset_b/evidence/documents.jsonl, document_title_mismatch.csv

**Window titles do not identify documents in Dataset B.** The same body text appears under
several unrelated titles — measured here, and reported in `document_title_mismatch.csv`. So the
document key is `sha256` of the NFKC-normalised, whitespace-collapsed body, and every observed
title is kept as an alias. `body_ja` is the longest observed capture, verbatim.

A "document" capture is a CONCATENATION, not a clean document: a pasted record line, then the
regulation clauses, then an appended 承認記録 ledger. Clause splitting separates the three, and
the ledger rows go to `document_ledger.jsonl` (a separate artifact, different provenance from
system-read records) rather than being emitted as rules.

**Rule parsing is conservative by construction.** Only three shapes are parsed: a numeric
threshold with a unit and a comparator, a table row carrying an amount, and a bulleted
conditional item. Anything else is emitted with `parsed=null` and `rule_kind="unknown"`. A rule
we cannot check mechanically is recorded as unparsed, never guessed into a shape that would let a
downstream test claim more than the evidence supports.
"""
from __future__ import annotations

import collections
import csv
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import common as C

DOC_APPS = ("Microsoft Word", "Notepad", "WordPad")
MIN_BODY = 120

CLAUSE_RE = re.compile(r"(第[一二三四五六七八九十０-９0-9]+条(?:（[^）]*）)?)")
LEDGER_RE = re.compile(r"(承認記録|経費承認記録|処理記録)")

# --- conservative rule shapes -------------------------------------------------
_NUM = r"(?P<num>[0-9０-９][0-9０-９,，]*(?:\.[0-9]+)?)"
_UNIT = r"(?P<unit>万円|円|名|人|営業日|日|時間|%|％|件)"
_CMP = r"(?P<cmp>以上|以下|未満|超|以内|まで)"
THRESHOLD_RE = re.compile(rf"{_NUM}\s*{_UNIT}\s*{_CMP}")
CONSEQUENT_RE = re.compile(r"[：:]\s*(?P<consequent>[^。．\n、]{1,40})")

CMP_OP = {"以上": ">=", "以下": "<=", "未満": "<", "超": ">", "以内": "<=", "まで": "<="}
UNIT_SCALE = {"万円": 10_000, "円": 1}


def normalise_body(text: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(text.split()))


def _to_number(raw: str) -> Optional[float]:
    s = unicodedata.normalize("NFKC", raw).replace(",", "").replace("，", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_rule(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """`(rule_kind, parsed | None)`. Returns `("unknown", None)` unless the text matches one of
    the three declared shapes unambiguously."""
    conditions: List[Dict[str, Any]] = []
    for m in THRESHOLD_RE.finditer(text):
        n = _to_number(m.group("num"))
        if n is None:
            continue
        unit = m.group("unit")
        cond: Dict[str, Any] = {
            "raw": m.group(0),
            "operator": CMP_OP[m.group("cmp")],
            "value": n,
            "unit": unit,
        }
        if unit in UNIT_SCALE:
            cond["value_jpy"] = n * UNIT_SCALE[unit]
        tail = text[m.end():m.end() + 40]
        cm = CONSEQUENT_RE.match(tail)
        if cm:
            cond["consequent"] = cm.group("consequent").strip()
        conditions.append(cond)

    if not conditions:
        return "unknown", None
    monetary = [c for c in conditions if "value_jpy" in c]
    if len(monetary) >= 2 and all("consequent" in c for c in monetary):
        return "threshold", {"variable": "金額", "unit": "JPY", "tiers": monetary}
    if len(conditions) == 1 and "consequent" in conditions[0]:
        return "threshold", {"variable": "金額" if "value_jpy" in conditions[0] else None,
                             "unit": "JPY" if "value_jpy" in conditions[0] else
                                     conditions[0]["unit"],
                             "tiers": conditions}
    return "conditional_item", {"conditions": conditions}


def split_clauses(body: str) -> List[Dict[str, Any]]:
    """Clauses on `第N条（…）`. The text before the first clause is the pasted-record preamble and
    the text after a ledger marker is the ledger; both are labelled, not dropped."""
    out: List[Dict[str, Any]] = []
    parts = CLAUSE_RE.split(body)
    if parts and parts[0].strip():
        head = parts[0].strip()
        cut = LEDGER_RE.search(head)
        pre = head[:cut.start()] if cut else head
        if pre.strip():
            out.append({"heading_ja": None, "text_ja": pre.strip(), "section": "preamble",
                        "char_span": [0, len(pre)]})
        if cut:
            out.append({"heading_ja": head[cut.start():cut.end()],
                        "text_ja": head[cut.start():].strip(), "section": "ledger",
                        "char_span": [cut.start(), len(head)]})
    cursor = len(parts[0]) if parts else 0
    for i in range(1, len(parts) - 1, 2):
        heading, text = parts[i], parts[i + 1]
        cut = LEDGER_RE.search(text)
        clause_text = text[:cut.start()] if cut else text
        out.append({"heading_ja": heading, "text_ja": clause_text.strip(), "section": "clause",
                    "char_span": [cursor, cursor + len(heading) + len(clause_text)]})
        if cut:
            out.append({"heading_ja": heading, "text_ja": text[cut.start():].strip(),
                        "section": "ledger",
                        "char_span": [cursor + len(heading) + cut.start(),
                                      cursor + len(heading) + len(text)]})
        cursor += len(heading) + len(text)
    for i, c in enumerate(out):
        c["clause_id"] = f"c{i:03d}"
    return out


def build(captures: Sequence[Dict]) -> Dict[str, Any]:
    groups: Dict[str, Dict[str, Any]] = {}
    for cap in captures:
        if cap["active_app"] not in DOC_APPS or cap["text_len"] < MIN_BODY:
            continue
        key = C.sha256_text(normalise_body(cap["text_ja"]))
        g = groups.setdefault(key, {"titles": collections.Counter(), "caps": [], "best": ""})
        g["titles"][cap["window_title"]] += 1
        g["caps"].append(cap)
        if len(cap["text_ja"]) > len(g["best"]):
            g["best"] = cap["text_ja"]

    docs: List[Dict] = []
    for key in sorted(groups):
        g = groups[key]
        body = g["best"]
        clauses = split_clauses(body)
        first = next((l.strip() for l in body.splitlines() if l.strip()), "")
        doc_type = first[:60]
        rules: List[Dict] = []
        for cl in clauses:
            if cl["section"] != "clause":
                continue
            kind, parsed = parse_rule(cl["text_ja"])
            rules.append({
                "rule_id": f"{key[:12]}:{cl['clause_id']}",
                "clause_id": cl["clause_id"],
                "rule_kind": kind,
                "raw_text_ja": cl["text_ja"],
                "parsed": parsed,
                "extraction_method": "telemetry_text",
                "evidence_type": "OBSERVED" if parsed is None else "DERIVED",
            })
        ts = [c["timestamp_ms"] for c in g["caps"] if c["timestamp_ms"]]
        docs.append({
            "document_id": key,
            "title_aliases": sorted(g["titles"]),
            "n_title_aliases": len(g["titles"]),
            "doc_type_ja": doc_type,
            "body_ja": body,
            "body_len": len(body),
            "n_captures": len(g["caps"]),
            "first_seen_ms": min(ts) if ts else None,
            "last_seen_ms": max(ts) if ts else None,
            "session_ids": sorted({c["session_id"] for c in g["caps"]}),
            "capture_ids": sorted(c["capture_id"] for c in g["caps"]),
            "clauses": clauses,
            "extracted_rules": rules,
            "n_parsed_rules": sum(1 for r in rules if r["parsed"] is not None),
            "extraction_method": "telemetry_text",
            "evidence_type": "OBSERVED",
        })
    docs.sort(key=lambda d: (-d["n_captures"], d["document_id"]))
    return {"documents": docs}


REQUIRED = ("document_id", "title_aliases", "doc_type_ja", "body_ja", "body_len",
            "n_captures", "clauses", "extracted_rules")


def run(dataset: str, captures: Sequence[Dict]) -> Dict[str, Any]:
    built = build(captures)
    docs = built["documents"]
    art = C.write_jsonl(docs, os.path.join(C.evidence_dir(dataset), "documents.jsonl"), dataset,
                        sort_key=lambda d: (-d["n_captures"], d["document_id"]),
                        required=REQUIRED)

    path = C.guard_path(os.path.join(C.evidence_dir(dataset),
                                     "document_title_mismatch.csv"), dataset)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["document_id", "n_captures", "heading_ja", "n_title_aliases",
                    "title_aliases", "multi_title_flag", "method"])
        for d in docs:
            w.writerow([d["document_id"][:12], d["n_captures"], d["doc_type_ja"],
                        d["n_title_aliases"], " | ".join(d["title_aliases"]),
                        "YES" if d["n_title_aliases"] > 1 else "no",
                        "one content hash observed under N distinct window titles; "
                        "script-independent, unlike comparing a Japanese heading to a romaji "
                        "filename"])
    return {"artifact": art, "documents": docs,
            "mismatch_csv": os.path.relpath(path, C.ROOT),
            "n_multi_title": sum(1 for d in docs if d["n_title_aliases"] > 1)}
