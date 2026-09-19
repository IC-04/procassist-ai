"""Read `build/dataset_b/evidence/documents.jsonl`. Read-only: this layer never writes.

Two things a caller needs and one thing it must not be allowed to assume:

  * the exact clause excerpt, by `(document_id, clause_id)`, with its `char_span` into the
    captured body, so `View source` can show the surrounding text rather than the excerpt alone;
  * the parsed rule payload for a `rule_id`, which is what the engine evaluates;
  * and it must not assume `document_id` is a document identity. It is a sha256 of the captured
    body text. Fifteen distinct ids in Dataset B carry the same 接待交際費規程 第2条 under five
    different Word window titles, so `siblings_by_rule_text` is provided to show how many
    captures agree, and `doc_type_ja` is deliberately not surfaced — on these rows it is screen
    text scraped from the top of the window, not a document type.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from .paths import DOCUMENTS


def _load(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class DocumentIndex:
    """An in-memory index of the 112 captured documents."""

    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self.rows = rows
        self.by_id: Dict[str, Dict[str, Any]] = {r["document_id"]: r for r in rows}
        self._clauses: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._rules: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
        for row in rows:
            for clause in row.get("clauses") or []:
                self._clauses[(row["document_id"], clause["clause_id"])] = clause
            for rule in row.get("extracted_rules") or []:
                self._rules[rule["rule_id"]] = (row, rule)

    @classmethod
    def load(cls, path: str = DOCUMENTS) -> "DocumentIndex":
        return cls(_load(path))

    def clause(self, document_id: str, clause_id: str) -> Optional[Dict[str, Any]]:
        return self._clauses.get((document_id, clause_id))

    def rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        found = self._rules.get(rule_id)
        return found[1] if found else None

    def parsed_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        rule = self.rule(rule_id)
        return (rule or {}).get("parsed")

    def siblings_by_rule_text(self, raw_text_ja: str) -> List[str]:
        """Every `document_id` whose extracted rules contain this exact clause text.

        This is the measurement behind "`document_id` is a capture-window hash": the answer for
        接待交際費規程 第2条 is fifteen ids, not one.
        """
        out = []
        for row in self.rows:
            for rule in row.get("extracted_rules") or []:
                if rule.get("raw_text_ja") == raw_text_ja:
                    out.append(row["document_id"])
                    break
        return sorted(out)

    def excerpt(self, document_id: str, clause_id: str,
                context_chars: int = 0) -> Optional[Dict[str, Any]]:
        """The clause's verbatim text plus everything needed to open its source.

        `context_chars` widens the returned `context_ja` around `char_span` without altering
        `text_ja`, which stays byte-identical to the captured clause.
        """
        row = self.by_id.get(document_id)
        clause = self.clause(document_id, clause_id)
        if row is None or clause is None:
            return None
        body = row.get("body_ja") or ""
        start, end = clause.get("char_span") or (0, 0)
        lo = max(0, int(start) - context_chars)
        hi = min(len(body), int(end) + context_chars)
        return {
            "document_id": document_id,
            "clause_id": clause_id,
            "heading_ja": clause.get("heading_ja"),
            "text_ja": clause.get("text_ja"),
            "section": clause.get("section"),
            "char_span": [int(start), int(end)],
            "context_ja": body[lo:hi],
            "body_len": row.get("body_len"),
            "title_aliases": row.get("title_aliases") or [],
            "capture_ids": row.get("capture_ids") or [],
            "session_ids": row.get("session_ids") or [],
            "n_captures": row.get("n_captures"),
            "first_seen_ms": row.get("first_seen_ms"),
            "last_seen_ms": row.get("last_seen_ms"),
            "evidence_type": row.get("evidence_type", "OBSERVED"),
        }


@lru_cache(maxsize=1)
def index() -> DocumentIndex:
    return DocumentIndex.load()
