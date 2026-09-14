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
from urllib.parse import urlsplit
from typing import Any, Dict, Iterator, List

# Layers that record operations the USER performed. DATA_SCHEMA.md §2 `layer`:
#   SYSTEM = "the agent's own activity"   (recording start/stop, uploads, extension state)
#   L1     = "screen capture"
#   L2     = "OS-level operations"        <- user
#   L3     = "in-browser operations"      <- user
# Nothing dataset-specific: this is a property of the recording format (ADR-012).
USER_LAYERS = frozenset({"L2", "L3"})

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
# A window title is "<document or page> - <chrome the application appended>". The trailing
# chrome is not part of the surface, and when it is stripped for one browser but not another
# the SAME page keys as two different surfaces (defect D-1, STEP1_SPEC §3.1).
#
# The rule is STRUCTURAL — the shape of an appended application suffix — not an allow-list of
# browser names. ADR-013 deleted the BROWSERS allow-list deliberately and that decision stands.
# Measured across dataset_a + dataset_b, the trailing " - X" segment IS the application's own
# name in 92.8% (A) / 74.0% (B) of titles that have one, which is what makes the shape reliable:
#
#     A: 'Google Chrome' x118,102 · 'Notepad' x29,506 · 'Word' · 'PowerPoint' · 'File Explorer'
#     B: 'Microsoft Edge' x13,200 · 'Word' · 'Excel' · 'Notepad'
#
# _APP_SUFFIX therefore matches a trailing separator followed by an optional "Profile N"
# segment and one to three Capitalised tokens. It deliberately does NOT match a tail containing
# punctuation or lower-case words, so a real title such as
# "Mixed Multi-Domain (HR / Finance / Ops)" survives intact.
#
# `Microsoft\u200bEdge` really does carry a zero-width space, so it is allowed inside a token.
_APP_TOKEN = r"[A-Z][\w.\u200b]*"
_APP_SUFFIX = re.compile(
    r"\s*[-–—]\s*"                                    # " - " / en / em dash
    r"(?:Profile\s+\d+\s*[-–—]\s*)?"                # optional "Profile 1 - "
    rf"(?:{_APP_TOKEN}(?:\s+{_APP_TOKEN}){{0,2}})"          # 1-3 Capitalised tokens
    r"\s*$"
)

_TITLE_STRIP = [
    (re.compile(r"\s+and \d+ more pages?\b"), ""),
    (re.compile(r"\s*-\s*Compatibility Mode\s*"), " "),
    (_APP_SUFFIX, ""),                   # D-1: trailing application/browser chrome
    (re.compile(r"^\*"), ""),            # unsaved-document marker
    (re.compile(r"\s*[-–—]\s*$"), ""),                # separator left behind
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
    """The path within a system: SPA hash route when present, else the URL path.

    DATA_CONTRACT.md §2 defines the surface grammar as `web:<origin><route>`, so the
    route must be a path *relative to the origin*. Returning the origin here (the
    previous behaviour) produced keys such as
    `web:http://127.0.0.1:5132http://127.0.0.1:5132`.

    Returns "" when there is no usable http(s) URL.
    """
    if not url:
        return ""
    parts = urlsplit(url)
    if not (parts.scheme in ("http", "https") and parts.netloc):
        return ""
    if parts.fragment:
        frag = parts.fragment
        return frag if frag.startswith("/") else "/" + frag
    return parts.path or "/"


def origin_of(url: str | None) -> str:
    """Scheme + authority, or "" when the URL is absent or not http(s)."""
    if not url:
        return ""
    parts = urlsplit(url)
    if not (parts.scheme in ("http", "https") and parts.netloc):
        return ""
    return f"{parts.scheme}://{parts.netloc}"


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

    # app_switch payload (DATA_SCHEMA.md §2): `new_app` / `previous_app`. Either may be a
    # bare string or an object carrying `app_name`; normalise both to a plain name.
    def _app_name(v: Any) -> str:
        if isinstance(v, dict):
            return v.get("app_name") or ""
        return v or ""

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
        "url_observed": bool(url),     # False once carry-forward fills it in (R3)
        "new_app": _app_name(pay.get("new_app")),
        "prev_app": _app_name(pay.get("previous_app")),
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


def carry_forward_tab_state(rows: List[Dict]) -> List[Dict]:
    """Fill in `active_browser_tab` where the recorder did not repeat it (ADR-013).

    `context` is a snapshot of "the situation when the event occurred", and
    `DATA_SCHEMA.md` §2 states plainly that "how often each field is populated varies".
    The browser tab is therefore **state**, not a per-event fact: its absence is missing
    data, not evidence that the user left the page.

    **Measured effect on dataset_b (E01): this changes no block boundary.** It fills
    3,058 rows, every one of them an L1 `screenshot_smart`, which `blocks.is_capture_event`
    already treats as surface-transparent. The 562 L2 user operations that carry no tab
    URL turn out to sit at the *entry* to a browser visit, before any tab has been
    observed, so there is no prior state to carry and the rule correctly declines to
    invent one. It is kept because it is the correct reading of the schema, because it
    gives capture rows a resolved surface for later phases (ADR-009 vision gating,
    prototype screenshot attachment), and because L2/L3 coverage differs per dataset —
    not because it is load-bearing on B. Re-measure on dataset_a in Phase 2.

    Two guards keep this from inventing state:

    * **Scope.** It is reset the moment `app_name` changes, so a stale URL can never leak
      across an application boundary.
    * **Seeding layer.** Only an `L2` event may seed it. L2 is the OS-level view, the one
      that populates `active_app` and `active_browser_tab` from the same vantage point.
      L3 events come from the browser extension, a separate capture mechanism whose
      `active_app` can lag the OS foreground: measured on `dataset_b`, 42 L3
      `browser_navigation` / `browser_error` events report a tab URL while `active_app`
      says Notepad, Word or WindowsTerminal. Seeding from those propagated a browser URL
      onto 87 non-browser events. An L3 event still keeps its own observed URL; it simply
      does not define the surrounding application's tab state.

    Rows whose URL was inherited rather than observed are marked `url_observed=False`.

    Pure: returns a new list of new dicts; `rows` is not modified. Expects `rows` already
    ordered (`load_session` sorts before calling).
    """
    out: List[Dict] = []
    last_app: str | None = None
    last_url = ""
    for r in rows:
        r = dict(r)
        app = r.get("app_name") or ""
        if app != last_app:
            last_app, last_url = app, ""      # app changed -> tab state is unknown again
        if r.get("url"):
            if r.get("layer") == "L2":
                last_url = r["url"]
        elif last_url:
            r["url"] = last_url
            r["origin"] = origin_of(last_url)
            r["route"] = route_of(last_url)
            r["url_observed"] = False
        out.append(r)
    return out


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
    rows = carry_forward_tab_state(rows)          # ADR-013
    for i, r in enumerate(rows):
        r["seq"] = i                  # global, chunk-free ordering
    return rows
