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

BROWSERS = {"Microsoft Edge", "Google Chrome", "Chrome", "Firefox", "msedge"}

# Surfaces that are never business work. Kept as a tiny, auditable seed list;
# the vocabulary compiler (Stage B2) replaces this with typed entries.
NOISE_TITLE_HINTS = (
    "Turn off extensions", "Restore pages", "New tab", "Untitled",
    "Settings |", "Address and search bar",
)


def surface_key(r: Dict) -> str:
    """Stable identifier for 'where the user is'.

    Browser  -> origin + hash route   (business function, per DATA_SCHEMA §2)
    Otherwise-> app + normalised window title
    """
    if r["app_name"] in BROWSERS and r["url"]:
        return f"web:{r['origin']}{r['route']}"
    if r["title"]:
        return f"app:{r['app_name']}:{r['title']}"
    return f"app:{r['app_name']}"


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

    # --- pass 1: raw runs of identical surface
    raw: List[Dict] = []
    for r in rows:
        k = surface_key(r)
        if raw and raw[-1]["surface"] == k:
            raw[-1]["rows"].append(r)
        else:
            raw.append({"surface": k, "rows": [r]})

    # --- pass 2: absorb micro-excursions (A | x | A  ->  A)
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

    # --- pass 3: summarise
    out: List[Dict] = []
    for bi, b in enumerate(merged):
        rs = b["rows"]
        first, last = rs[0], rs[-1]
        etypes = collections.Counter(r["event_type"] for r in rs)
        fields = sorted({r["field_key"] for r in rs if r["field_key"]})
        elements = sorted({r["element_id"] for r in rs if r["element_id"]})
        labels = sorted({r["element_label"] for r in rs if r["element_label"]})
        hashes = sorted({h for r in rs for h in r["dataflow_hashes"].split(",") if h})
        shots = [r["screenshot"] for r in rs if r["screenshot"]]
        titles = collections.Counter(r["title"] for r in rs if r["title"])

        out.append({
            "block_id": f"{first['session_id']}#b{bi:04d}",
            "session_id": first["session_id"],
            "idx": bi,
            "surface": b["surface"],
            "app": first["app_name"],
            "title": titles.most_common(1)[0][0] if titles else "",
            "route": first["route"],
            "origin": first["origin"],
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
            "is_noise": _is_noise(b["surface"], first["title"]),
            "operator": first["operator"],
            "machine": first["machine"],
            "start_iso": first["ts_iso"],
            "end_iso": last["ts_iso"],
        })
    return out


def block_stats(blocks: List[Dict]) -> Dict:
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
        "absorbed_total": sum(b["absorbed_excursions"] for b in blocks),
    }
