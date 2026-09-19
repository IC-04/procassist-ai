"""Append-only audit log: SQLite at `build/procassist/audit.sqlite3` + a JSONL mirror.

This is the instrument, and it is the part of the demo with the longest half-life. The open
question behind Step 3 is whether a *model* is warranted here at all, and that question is
answered by data of exactly this shape: for every suggestion the deterministic engine made,
what did the human then do? Accept the draft unchanged, edit it, dismiss the check, override
the suggested authority, choose which disposition?

Append-only in the strict sense: there is no UPDATE and no DELETE anywhere in this module, and
`row_hash` chains each row to the one before it, so a later edit to the file is detectable.
The JSONL mirror exists because a graded deliverable should be readable with `cat`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from analysis.evidence.common import sha256_text

from .paths import AUDIT_DB, AUDIT_JSONL, OUT

#: The interactions worth recording. Anything not in this set is a programming error, not a
#: new category to be invented at the call site.
EVENT_TYPES = (
    "prepare",              # the engine produced a PrepareResult
    "prepare_queue",        # the engine was run over a whole queue at once
    "draft_used",           # the human pasted the draft into the host field
    "draft_edited",         # the human changed the draft text before/after pasting
    "judgement_chosen",     # the human picked a disposition chip
    "check_agreed",         # the human agreed with a check
    "check_dismissed",      # the human dismissed a check
    "suggestion_overridden",# the human recorded a different authority than the one suggested
    "host_submitted",       # the human clicked the host's own submit control
    "source_viewed",        # the human opened the document provenance
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms          INTEGER NOT NULL,
    ts_iso         TEXT    NOT NULL,
    trace_id       TEXT    NOT NULL,
    event_type     TEXT    NOT NULL,
    definition_id  TEXT,
    module_id      TEXT,
    record_id      TEXT,
    suggested      TEXT,
    human_action   TEXT,
    detail_json    TEXT    NOT NULL,
    prev_hash      TEXT,
    row_hash       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_trace ON audit(trace_id);
CREATE INDEX IF NOT EXISTS audit_record ON audit(record_id);
"""

_LOCK = threading.Lock()


def new_trace_id() -> str:
    return "tr_" + uuid.uuid4().hex[:16]


class AuditLog:
    """Append-only. No method on this class updates or deletes a row."""

    def __init__(self, db_path: str = AUDIT_DB, jsonl_path: str = AUDIT_JSONL) -> None:
        os.makedirs(OUT, exist_ok=True)
        self.db_path = db_path
        self.jsonl_path = jsonl_path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def append(
        self,
        trace_id: str,
        event_type: str,
        *,
        definition_id: Optional[str] = None,
        module_id: Optional[str] = None,
        record_id: Optional[str] = None,
        suggested: Optional[str] = None,
        human_action: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write one row. `suggested` is what the tool proposed; `human_action` is what happened."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type!r} is not one of {EVENT_TYPES}")
        ts_ms = int(time.time() * 1000)
        ts_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts_ms / 1000)) + \
            f".{ts_ms % 1000:03d}Z"
        detail_json = json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)
        with _LOCK, self._connect() as conn:
            prev = conn.execute("SELECT row_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = prev["row_hash"] if prev else None
            payload = "|".join([
                str(prev_hash), str(ts_ms), trace_id, event_type, str(definition_id),
                str(module_id), str(record_id), str(suggested), str(human_action), detail_json,
            ])
            row_hash = sha256_text(payload)
            cur = conn.execute(
                "INSERT INTO audit (ts_ms, ts_iso, trace_id, event_type, definition_id, "
                "module_id, record_id, suggested, human_action, detail_json, prev_hash, "
                "row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts_ms, ts_iso, trace_id, event_type, definition_id, module_id, record_id,
                 suggested, human_action, detail_json, prev_hash, row_hash),
            )
            seq = cur.lastrowid
        row = {
            "seq": seq, "ts_ms": ts_ms, "ts_iso": ts_iso, "trace_id": trace_id,
            "event_type": event_type, "definition_id": definition_id, "module_id": module_id,
            "record_id": record_id, "suggested": suggested, "human_action": human_action,
            "detail": detail or {}, "prev_hash": prev_hash, "row_hash": row_hash,
        }
        with open(self.jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def tail(self, n: int = 3) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit ORDER BY seq DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM audit").fetchone()["n"])

    def verify_chain(self) -> bool:
        """True when every row's hash still matches its contents and its predecessor."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit ORDER BY seq ASC").fetchall()
        prev_hash = None
        for r in rows:
            payload = "|".join([
                str(prev_hash), str(r["ts_ms"]), r["trace_id"], r["event_type"],
                str(r["definition_id"]), str(r["module_id"]), str(r["record_id"]),
                str(r["suggested"]), str(r["human_action"]), r["detail_json"],
            ])
            if sha256_text(payload) != r["row_hash"]:
                return False
            prev_hash = r["row_hash"]
        return True
