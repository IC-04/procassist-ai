"""Stage B — semantic activity blocks.

A *block* is a maximal run of events sharing one context state, after
micro-excursions have been absorbed. Blocks are the unit the AI reasoner
sees; they compress ~20k events into ~10^2-10^3 legible units.

This layer is fully deterministic. It proposes structure; it does NOT
decide execution identity.
"""
from __future__ import annotations
import collections
from typing import Dict, List

from .normalise import USER_LAYERS

# Surfaces that are never business work. Kept as a tiny, auditable seed list;
# the vocabulary compiler (Stage B2) replaces this with typed entries.
# D-2 (STEP1_SPEC §3.1): the bare hint "Untitled" was removed. It was meant to catch a blank
# browser tab, but it is a substring test against the normalised window title, so it also
# matched Notepad's default document name and marked genuine work as noise — 52 blocks
# (14.3%) in the Phase 1 dataset_a sample against 4.0% in dataset_b. After D-1 strips the
# trailing " - Notepad", such a title is exactly "Untitled", so the collision got worse rather
# than better. Removing the hint is the smaller of the two sanctioned fixes; scoping it to
# `web:` surfaces would require changing `_is_noise`, which is outside this change's budget.
# Nothing gates on `is_noise` today — it is descriptive metadata on the block record.
NOISE_TITLE_HINTS = (
    "Turn off extensions", "Restore pages", "New tab",
    "Settings |", "Address and search bar",
)


def surface_key(r: Dict) -> str:
    """Stable identifier for 'where the user is' (DATA_CONTRACT.md §2 grammar).

        web:<origin><route>      an http(s) tab is in context
        app:<app_name>:<title>   otherwise, when a window title is known
        app:<app_name>           otherwise

    The web/app choice is **structural** — it turns on whether a usable origin is in
    context, not on whether the application is on a list of known browser names. An
    allow-list of browser names would be a dataset-specific rule and would silently
    mis-key any browser a future dataset happens to use (ADR-013).
    """
    if r.get("origin"):
        return f"web:{r['origin']}{r['route']}"
    if r.get("title"):
        return f"app:{r['app_name']}:{r['title']}"
    return f"app:{r['app_name']}"


def is_capture_event(r: Dict) -> bool:
    """True for agent/capture plumbing rather than a user operation (ADR-012, R1).

    `DATA_SCHEMA.md` §2 describes `SYSTEM` as "the agent's own activity" and `L1` as
    "screen capture"; only `L2` ("OS-level operations") and `L3` ("in-browser
    operations") are things the user did. A capture event is a passive observation of
    whatever was already on screen, so it must never *define* a surface.
    """
    return r.get("layer") not in USER_LAYERS


def has_discriminator(r: Dict) -> bool:
    """True when the row says anything about *which* surface it is (R2).

    A row with neither a window title nor an origin identifies only an application.
    `DATA_SCHEMA.md` §2 notes context fields are populated with varying frequency, so
    this is missing data rather than a distinct state, and it must not open a block of
    its own inside a run of the same application.
    """
    return bool(r.get("title") or r.get("origin"))


def surface_defining(r: Dict) -> bool:
    """Whether this row may open a new block."""
    return not is_capture_event(r) and has_discriminator(r)


def _is_noise(key: str, title: str) -> bool:
    return any(h in title for h in NOISE_TITLE_HINTS) or key in ("app:", "app:None")


def build_blocks(rows: List[Dict], min_events: int = 3, min_ms: int = 1500) -> List[Dict]:
    """Group events into blocks, then absorb micro-excursions.

    An excursion X between two blocks with the SAME surface is absorbed into
    them when it is short in both events and wall time. This is the
    'suppression policy' -- the real engineering problem at this stage, since
    raw state-change rate is ~1 change per 2.8 events.
    """
    if not rows:
        return []

    # --- pass 1: runs of identical surface, defined only by surface-defining rows
    raw: List[Dict] = []
    pending: List[Dict] = []          # capture events seen before any user operation
    for r in rows:
        if is_capture_event(r):                       # R1: transparent, never opens
            (raw[-1]["rows"] if raw else pending).append(r)
            continue
        app = r.get("app_name") or ""
        # R2: a row with no discriminator is missing data, not a new surface. Attach it
        # to the open block when it cannot contradict that block — same application, or
        # no application recorded at all. A *different* named application is a real
        # change and still opens a block.
        if not has_discriminator(r) and raw and (not app or raw[-1]["app"] == app):
            raw[-1]["rows"].append(r)
            continue
        k = surface_key(r)
        if raw and raw[-1]["surface"] == k:
            raw[-1]["rows"].append(r)
        else:
            raw.append({"surface": k, "app": app, "rows": [r]})
    if pending:
        if raw:
            raw[0]["rows"] = pending + raw[0]["rows"]   # ordered: all precede the first
        else:
            raw.append({"surface": surface_key(pending[0]),
                        "app": pending[0].get("app_name") or "", "rows": pending})

    return _summarise(_absorb(_attach_late_titles(raw), min_events, min_ms))


def _attach_late_titles(raw: List[Dict]) -> List[Dict]:
    """Pass 1b — the forward half of R2.

    Pass 1 can only attach an undiscriminated row to the block already open behind it.
    The common case it cannot see is the mirror image: a window title is not populated
    until the window has finished activating, so switching into an application produces a
    short bare `app:<X>` run immediately *followed* by `app:<X>:<title>`. Those are one
    surface with the title captured late, not two.

    The merge requires the same application on both sides, so an application that never
    reports a title at all (a file-open dialog, say) keeps its own block rather than being
    swallowed by whatever came next. On dataset_b this merges 35 of 59 bare-app runs and
    leaves the other 24 — every one of them an application with no title anywhere — alone.
    """
    out: List[Dict] = []
    i = 0
    while i < len(raw):
        cur = raw[i]
        nxt = raw[i + 1] if i + 1 < len(raw) else None
        if (nxt is not None and cur["app"] and nxt["app"] == cur["app"]
                and cur["surface"] == f"app:{cur['app']}"):
            nxt["rows"] = cur["rows"] + nxt["rows"]
            i += 1
            continue
        out.append(cur)
        i += 1
    return out


def _absorb(raw: List[Dict], min_events: int, min_ms: int) -> List[Dict]:
    """Pass 2 — absorb micro-excursions (A | x | A -> A).

    Only a run bracketed by the SAME surface on both sides is absorbed. Absorbing a
    short run into an unrelated neighbour would merge genuinely distinct work, which is
    the failure mode Phase 0 is explicitly warned against; brief-but-distinct activity
    is left alone and reported instead.
    """
    merged: List[Dict] = []
    i = 0
    while i < len(raw):
        cur = raw[i]
        if (
            merged
            and i + 1 < len(raw)
            and merged[-1]["surface"] == raw[i + 1]["surface"]
            and len(cur["rows"]) < min_events
            and (cur["rows"][-1]["ts_ms"] - cur["rows"][0]["ts_ms"]) < min_ms
        ):
            merged[-1]["rows"].extend(cur["rows"])          # absorb excursion
            merged[-1]["rows"].extend(raw[i + 1]["rows"])   # and its return
            merged[-1]["absorbed"] = merged[-1].get("absorbed", 0) + 1
            i += 2
            continue
        merged.append(cur)
        i += 1
    return merged


def _summarise(merged: List[Dict]) -> List[Dict]:
    """Pass 3 — runs of rows -> the DATA_CONTRACT.md §1 block records."""
    out: List[Dict] = []
    for bi, b in enumerate(merged):
        rs = b["rows"]
        first, last = rs[0], rs[-1]
        # Identity attributes come from the rows that actually DEFINE the surface: a
        # leading capture event carries no app, route or origin, and letting rows[0]
        # speak for the block would blank them out.
        drs = [r for r in rs if surface_defining(r)] or rs
        head = drs[0]
        etypes = collections.Counter(r["event_type"] for r in rs)
        fields = sorted({r["field_key"] for r in rs if r["field_key"]})
        elements = sorted({r["element_id"] for r in rs if r["element_id"]})
        labels = sorted({r["element_label"] for r in rs if r["element_label"]})
        hashes = sorted({h for r in rs for h in r["dataflow_hashes"].split(",") if h})
        shots = [r["screenshot"] for r in rs if r["screenshot"]]
        titles = collections.Counter(r["title"] for r in drs if r["title"])

        out.append({
            "block_id": f"{head['session_id']}#b{bi:04d}",
            "session_id": head["session_id"],
            "idx": bi,
            "surface": b["surface"],
            "app": head["app_name"],
            "title": titles.most_common(1)[0][0] if titles else "",
            "route": head["route"],
            "origin": head["origin"],
            "start_ms": first["ts_ms"],
            "end_ms": last["ts_ms"],
            "dur_ms": last["ts_ms"] - first["ts_ms"],
            "n_events": len(rs),
            "event_mix": dict(etypes.most_common(6)),
            "n_keystrokes": etypes.get("keystroke", 0),
            "n_clicks": etypes.get("mouse_click", 0) + etypes.get("browser_click", 0),
            "n_form_inputs": etypes.get("browser_form_input", 0),
            "n_nav": etypes.get("browser_navigation", 0),
            "n_clipboard": etypes.get("clipboard_change", 0),
            "field_keys": fields,
            "element_ids": elements[:8],
            "element_labels": labels[:5],
            "value_hashes": hashes,
            "screenshots": shots[:3],
            "absorbed_excursions": b.get("absorbed", 0),
            "is_noise": _is_noise(b["surface"], head["title"]),
            "operator": head["operator"],
            "machine": head["machine"],
            "start_iso": first["ts_iso"],
            "end_iso": last["ts_iso"],
            # DATA_CONTRACT §10.1 / ADR-015: a block is a CONTAINER, so a boundary may be
            # placed between two events inside it. These expose the block's own rows as a
            # span into the normalised event stream, which `candidates.py` recovers
            # deterministically from the same session load.
            "first_seq": first.get("seq"),
            "last_seq": last.get("seq"),
        })
    return out


def block_stats(blocks: List[Dict]) -> Dict:
    """Block-quality metrics. The degeneracy counters are the Phase 0 acceptance measures."""
    if not blocks:
        return {}
    durs = sorted(b["dur_ms"] for b in blocks)
    ns = sorted(b["n_events"] for b in blocks)
    q = lambda a, p: a[min(len(a) - 1, int(len(a) * p))]
    return {
        "n_blocks": len(blocks),
        "n_noise_blocks": sum(1 for b in blocks if b["is_noise"]),
        "median_dur_ms": q(durs, .5), "p90_dur_ms": q(durs, .9),
        "median_events": q(ns, .5), "p90_events": q(ns, .9),
        "mean_events": round(sum(ns) / len(ns), 2),
        "absorbed_total": sum(b["absorbed_excursions"] for b in blocks),
        # --- degeneracy (Phase 0 Task 0.3) ---
        "n_one_event": sum(1 for b in blocks if b["n_events"] == 1),
        "n_zero_duration": sum(1 for b in blocks if b["dur_ms"] == 0),
        "n_empty_surface": sum(1 for b in blocks if b["surface"] in ("app:", "app:None")),
    }
