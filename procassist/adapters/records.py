"""Read `build/dataset_b/evidence/records.jsonl`. Read-only: this layer never writes.

Keyed on `record_prefix`, never on `module_id`. ADR-022 measured `module_id` — which is derived
from the URL in the address bar — to be wrong about the screen in 21% of captures, while the
`P<n>` prefix agrees with the screen at purity 1.00 for the prefixes this demo uses. The
`module_id` is still carried through so a disagreement stays visible rather than being resolved.

The file holds 3,011 rows for 898 distinct records: the same queue was captured repeatedly, so
each record recurs. `queue` deduplicates on `record_id`, keeping the first occurrence in
(timestamp, sequence, row) order, and records how many captures the row was seen in.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from ..core.rules import parse_amount_jpy
from .paths import RECORDS


class RecordStore:
    """The 898 distinct business records, grouped by `record_prefix`."""

    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self.rows = rows
        order = sorted(
            rows,
            key=lambda r: (r.get("timestamp_ms") or 0, r.get("sequence_number") or 0,
                           r.get("row_index") or 0),
        )
        self._first: Dict[str, Dict[str, Any]] = {}
        self._seen: Dict[str, int] = {}
        self._captures: Dict[str, List[str]] = {}
        self._sessions: Dict[str, List[str]] = {}
        self._statuses: Dict[str, List[str]] = {}
        for row in order:
            rid = row["record_id"]
            self._first.setdefault(rid, row)
            self._seen[rid] = self._seen.get(rid, 0) + 1
            cap, ses = row.get("capture_id"), row.get("session_id")
            if cap and cap not in self._captures.setdefault(rid, []):
                self._captures[rid].append(cap)
            if ses and ses not in self._sessions.setdefault(rid, []):
                self._sessions[rid].append(ses)
            st = row.get("status_ja")
            if st and st not in self._statuses.setdefault(rid, []):
                self._statuses[rid].append(st)

    @classmethod
    def load(cls, path: str = RECORDS) -> "RecordStore":
        with open(path, encoding="utf-8") as fh:
            return cls([json.loads(line) for line in fh if line.strip()])

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        row = self._first.get(record_id)
        return None if row is None else self._decorate(row)

    def queue(self, record_prefix: str, column_headers_ja: Optional[List[str]] = None,
              limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Distinct records for one prefix, in capture order.

        `column_headers_ja` is a cross-check, not a filter shaped by us: a row whose captured
        headers disagree with the definition's is kept and marked, because a silently dropped
        row would hide a real inconsistency in the corpus.
        """
        out = []
        for rid, row in self._first.items():
            if row.get("record_prefix") != record_prefix:
                continue
            item = self._decorate(row)
            if column_headers_ja is not None:
                item["headers_agree"] = (row.get("column_headers") == column_headers_ja)
            out.append(item)
        out.sort(key=lambda r: r["record_id"])
        return out[:limit] if limit else out

    def _decorate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        rid = row["record_id"]
        fields = dict(row.get("fields") or {})
        return {
            "record_id": rid,
            "record_prefix": row.get("record_prefix"),
            "module_id": row.get("module_id"),
            "prefix_modal_module_id": row.get("prefix_modal_module_id"),
            "module_id_agrees_with_prefix": row.get("module_id_agrees_with_prefix"),
            "column_headers": list(row.get("column_headers") or []),
            "fields": fields,
            "amount_jpy": parse_amount_jpy(fields.get("金額")),
            "status_ja": row.get("status_ja"),
            # 324 of the 898 records were captured in more than one ステータス — the queue was
            # recorded before and after the work was done. We show the first and disclose the
            # rest rather than picking one and calling it the record's state.
            "statuses_observed_ja": self._statuses.get(rid, []),
            "source_view": row.get("source_view"),
            "evidence_type": row.get("evidence_type", "OBSERVED"),
            "capture_ids": self._captures.get(rid, []),
            "session_ids": self._sessions.get(rid, []),
            "n_captures": self._seen.get(rid, 1),
            "first_seen_ms": row.get("timestamp_ms"),
        }


@lru_cache(maxsize=1)
def store() -> RecordStore:
    return RecordStore.load()
