"""Pass 0 — telemetry text harvest.

reads only:  dataset_b/*/*/events.jsonl
writes only: build/dataset_b/evidence/screen_text.jsonl

`context.extracted_text` is supplied by the recorder itself. Measured over Dataset B: 939 of
20,477 events (4.59%) carry a non-empty `text`, on `app_switch` (583), `mouse_click` (279) and
`text_input_complete` (77). Nothing here runs OCR — `tesseract` is not installed on this machine,
and ADR-007's rejection of global OCR pipelines stands regardless.

`text_ja` is copied VERBATIM. No normalisation, no translation, no trimming: a test asserts it is
byte-identical to the source value, because every downstream claim about what a screen said rests
on this field not having been quietly rewritten.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, Iterator, List, Optional

from . import common as C
from . import modules as M


def iter_raw_events(dataset_root: str) -> Iterator[Dict]:
    """Every raw event, in (session, chunk, file order). Chunks are recording artifacts and are
    NOT boundaries (ADR-001); they are carried only as provenance."""
    for path in sorted(glob.glob(os.path.join(dataset_root, "*", "*", "events.jsonl"))):
        parts = os.path.abspath(path).split(os.sep)
        session_id, chunk_dir = parts[-3], parts[-2]
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                e["_session_id"] = session_id
                e["_chunk_dir"] = chunk_dir
                yield e


def _g(d: Any, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def capture_row(e: Dict) -> Optional[Dict]:
    """One `screen_text.jsonl` row, or None when the event carries no text."""
    xt = _g(e, "context", "extracted_text", default={}) or {}
    if not isinstance(xt, dict):
        return None
    text = xt.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    url = _g(e, "context", "active_browser_tab", "url", default="") or ""
    origin, route = M.split_url(url)
    text_sha = C.sha256_text(text)
    session_id = e["_session_id"]
    seq = _g(e, "correlation", "sequence_number")
    capture_id = C.sha256_text(f"{session_id}|{seq}|{text_sha}")[:16]

    return {
        "capture_id": capture_id,
        "session_id": session_id,
        "chunk_id": _g(e, "correlation", "chunk_id") or e["_chunk_dir"],
        "source_event_id": e.get("event_id"),
        "sequence_number": seq,
        "timestamp_ms": e.get("timestamp_ms"),
        "event_type": e.get("event_type"),
        "active_app": _g(e, "context", "active_app", "app_name", default="") or "",
        "window_title": _g(e, "context", "active_app", "window_title", default="") or "",
        "browser_origin": origin,
        "browser_route": route,
        "module_id": M.module_id_of_url(url),
        "text_ja": text,                       # VERBATIM — never normalised, never translated
        "text_len": len(text),
        "text_sha256": text_sha,
        "char_count_reported": xt.get("char_count"),
        "truncated": bool(xt.get("truncated")),
        "capture_source": xt.get("source"),
        "extraction_method": "telemetry_text",
        "evidence_type": "OBSERVED",
    }


REQUIRED = ("capture_id", "session_id", "chunk_id", "source_event_id", "sequence_number",
            "timestamp_ms", "active_app", "window_title", "browser_origin", "browser_route",
            "text_ja", "text_len", "text_sha256")


def harvest(dataset_root: str) -> List[Dict]:
    rows = [r for r in (capture_row(e) for e in iter_raw_events(dataset_root)) if r]
    rows.sort(key=lambda r: (r["session_id"], r["sequence_number"] or 0, r["capture_id"]))
    return rows


def run(dataset: str, dataset_root: str) -> Dict[str, Any]:
    rows = harvest(dataset_root)
    art = C.write_jsonl(rows, os.path.join(C.evidence_dir(dataset), "screen_text.jsonl"),
                        dataset, sort_key=lambda r: (r["session_id"],
                                                     r["sequence_number"] or 0,
                                                     r["capture_id"]),
                        required=REQUIRED)
    return {"artifact": art, "rows": rows}
