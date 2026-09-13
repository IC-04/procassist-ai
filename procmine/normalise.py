"""Stage A — deterministic normalisation.

events.jsonl (many chunks) -> one flat, time-ordered table per session.

Contract notes (DATA_SCHEMA.md):
  * chunk boundaries are recording artifacts and are DISSOLVED here;
    `correlation.sequence_number` restarts per chunk so global order is
    rebuilt from `timestamp_ms`.
  * every `context.*` and `extensions.*` field is OPTIONAL. Nothing below
    may raise if a field is absent.
  * `text_input_complete` is unreliable -> flagged, never used as a feature.
"""
from __future__ import annotations
import json, re, glob, os
from typing import Any, Dict, Iterator, List

# ---------------------------------------------------------------- helpers

def _g(d: Any, *path, default=None):
    """Safe nested get. Returns `default` on any missing/None link."""
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


# Window-title noise that carries no business meaning.
_TITLE_STRIP = [
    (re.compile(r"\s*-\s*Profile \d+\s*-\s*Microsoft.?\s*Edge\s*$"), ""),
    (re.compile(r"\s+and \d+ more pages?\b"), ""),
    (re.compile(r"\s*-\s*Compatibility Mode\s*"), " "),
    (re.compile(r"\s*-\s*(Word|Excel|PowerPoint)\s*$"), ""),
    (re.compile(r"^\*"), ""),            # unsaved-document marker
    (re.compile(r"\s{2,}"), " "),
]

def normalise_title(t: str | None) -> str:
    if not t:
        return ""
    s = t
    for pat, rep in _TITLE_STRIP:
        s = pat.sub(rep, s)
    return s.strip()


def route_of(url: str | None) -> str:
    """SPA hash route, or the origin when there is no route."""
    if not url:
        return ""
    if "#" in url:
        frag = url.split("#", 1)[1]
        return frag if frag.startswith("/") else "/" + frag
    m = re.match(r"^(https?://[^/]+)", url)
    return m.group(1) if m else url


def origin_of(url: str | None) -> str:
    if not url:
        return ""
    m = re.match(r"^(https?://[^/]+)", url)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- core

def flatten_event(e: Dict) -> Dict:
    """One raw event -> one flat record. Never raises on missing fields."""
    app = _g(e, "context", "active_app", default={}) or {}
    tab = _g(e, "context", "active_browser_tab", default={}) or {}
    ext = e.get("extensions") or {}
    corr = e.get("correlation") or {}
    pay = e.get("payload") or {}

    url = tab.get("url") or ""
    title_raw = app.get("window_title") or ""
    df = ext.get("dataflow_v2") or {}
    fid = ext.get("field_identity_v1") or {}

    # element identity (browser events)
    el = _g(pay, "element", "attributes", default={}) or {}
    fld = pay.get("field") or {}
    element_id = el.get("id") or fld.get("id") or fld.get("css_selector") or ""
    element_label = el.get("placeholder") or el.get("aria-label") or fld.get("label") or ""

    return {
        "event_id": e.get("event_id"),
        "session_id": e.get("session_id"),
        "chunk_id": corr.get("chunk_id"),
        "ts_ms": e.get("timestamp_ms"),
        "ts_iso": e.get("timestamp_iso"),
        "layer": e.get("layer"),
        "event_type": e.get("event_type"),
        "app_name": app.get("app_name") or "",
        "process_name": app.get("process_name") or "",
        "title_raw": title_raw,
        "title": normalise_title(title_raw),
        "url": url,
        "origin": origin_of(url),
        "route": route_of(url),
        "element_id": element_id,
        "element_label": element_label,
        "ms_since_last": corr.get("ms_since_last_event"),
        "seq_in_chunk": corr.get("sequence_number"),
        "triggered_by": corr.get("triggered_by"),
        "operator": _g(e, "source", "username_hash", default="") or "",
        "machine": _g(e, "source", "machine_id", default="") or "",
        # --- optional extension signals (absent-tolerant) ---
        "field_key": fid.get("stable_key") or "",
        "dataflow_op": df.get("operation") or "",
        "dataflow_src": df.get("source_event_id") or "",
        "dataflow_hashes": ",".join(
            h.get("hash", "") for h in (df.get("normalized_value_hashes") or []) if isinstance(h, dict)
        ),
        "capture_quality": _g(ext, "capture_quality_v1", "quality_class", default="") or "",
        "screenshot": _g(pay, "file_reference", "filename", default="") or "",
        "unreliable": e.get("event_type") == "text_input_complete",  # README caveat
    }


def iter_session_dirs(dataset_root: str) -> Iterator[str]:
    for p in sorted(glob.glob(os.path.join(dataset_root, "ses_*"))):
        if os.path.isdir(p):
            yield p


def load_session(session_dir: str) -> List[Dict]:
    """All chunks of one session, chunk boundaries dissolved, globally ordered."""
    rows: List[Dict] = []
    for f in sorted(glob.glob(os.path.join(session_dir, "chunk_*", "events.jsonl"))):
        chunk_dir = os.path.dirname(f)
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = flatten_event(json.loads(line))
                except json.JSONDecodeError:
                    continue          # malformed line: skip, do not crash
                r["chunk_dir"] = chunk_dir
                rows.append(r)
    rows.sort(key=lambda r: (r["ts_ms"] if r["ts_ms"] is not None else 0))
    for i, r in enumerate(rows):
        r["seq"] = i                  # global, chunk-free ordering
    return rows
