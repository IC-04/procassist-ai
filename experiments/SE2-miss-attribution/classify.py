"""S-E2 miss attribution — the classifier, importable so it can be unit-tested.

Every rule below is mechanical and computed from the data. None is inferred.

Precedence is fixed and total: a boundary is tested against (e), (a), (c), (b) in that
order and falls through to (d). Exactly one category is assigned, so the counts sum to the
number of missed boundaries.

Why this order:

  (e) first  — a GT/telemetry mismatch is a property of the annotation, not of our
               representation. Testing it first stops the +820 ms annotation lead leaking
               into (d) and inflating the "genuinely ambiguous" residue, which is exactly
               the failure mode S-E2 exists to prevent.
  (a) second — representation loss outranks every explanation that assumes the events are
               present, because if the events are gone the later rules are meaningless.
  (c) third  — absorption is a specific, provable act of the block builder. It is checked
               before the generic "signal is present" rule so that an absorbed excursion is
               never merely reported as (b).
  (b) fourth — the events are there and carry a discriminating signal.
  (d) last   — the residue, by construction.
"""
from __future__ import annotations
import bisect
from typing import Dict, List, Optional, Sequence, Tuple

CATEGORIES = ("a_information_destroyed", "b_preserved_inside_block",
              "c_absorbed_micro_excursion", "d_ambiguous_no_evidence",
              "e_gt_telemetry_mismatch")

# Event types that, on their own, discriminate a change of activity. Each is a documented
# DATA_SCHEMA §2 event_type that marks a transition rather than continuation of typing or
# pointing. `keystroke`, `mouse_click`, `mouse_scroll` and `screenshot_smart` are deliberately
# NOT here: they are the background hum of any activity and would make every window "signalled".
DISCRIMINATING_TYPES = frozenset({
    "browser_navigation", "app_switch", "browser_form_input", "clipboard_change",
    "shortcut", "mouse_drag_drop", "dialog_opened", "dialog_closed",
    "browser_tab_event", "window_title_change",
})

# Non-event-type signals, derived by comparing consecutive retained rows in the window.
STATE_SIGNALS = ("route_change", "origin_change", "app_change", "field_key_change",
                 "large_relative_gap")


def window_rows(rows: Sequence[Dict], ts: Sequence[int], centre: int,
                half_ms: int) -> List[Dict]:
    """Retained rows within +/- half_ms of `centre`."""
    lo = bisect.bisect_left(ts, centre - half_ms)
    hi = bisect.bisect_right(ts, centre + half_ms)
    return list(rows[lo:hi])


def signals_in_window(win: Sequence[Dict], gap_threshold_ms: Optional[int]) -> Dict[str, bool]:
    """Which discriminating signals are present among the retained rows of a window.

    Returns one boolean per signal name, so the same function drives both the classifier
    and the contingency table and the two can never disagree.
    """
    out = {t: False for t in DISCRIMINATING_TYPES}
    out.update({s: False for s in STATE_SIGNALS})
    for r in win:
        et = r.get("event_type")
        if et in out:
            out[et] = True
        if gap_threshold_ms is not None:
            ms = r.get("ms_since_last")
            if isinstance(ms, (int, float)) and ms >= gap_threshold_ms:
                out["large_relative_gap"] = True
    for x, y in zip(win, win[1:]):
        if (x.get("route") or "") != (y.get("route") or ""):
            out["route_change"] = True
        if (x.get("origin") or "") != (y.get("origin") or ""):
            out["origin_change"] = True
        if (x.get("app_name") or "") != (y.get("app_name") or ""):
            out["app_change"] = True
        fx, fy = x.get("field_key") or "", y.get("field_key") or ""
        if fx and fy and fx != fy:
            out["field_key_change"] = True
    return out


def any_signal(sig: Dict[str, bool]) -> bool:
    return any(sig.values())


def classify_boundary(g: int, sess: Dict, tau_ms: int, lead_ms: int) -> Dict:
    """Classify ONE unreachable GT boundary. Returns the category plus its evidence.

    `sess` carries the precomputed per-session world:
      rows, ts, blocks, edges, edges_no_absorb, raw_ids_sorted, normalised_ids,
      telemetry_span, gap_threshold_ms
    """
    ev: Dict = {"ts_ms": g}

    # ---- (e) GT / telemetry mismatch -------------------------------------------------
    t0, t1 = sess["telemetry_span"]
    if g < t0 or g > t1:
        ev["reason"] = "boundary lies outside the session's telemetry span"
        return {"category": "e_gt_telemetry_mismatch", "sub": "outside_telemetry", **ev}

    # the measured annotation lead: does correcting it make the boundary reachable?
    edges = sess["edges"]
    if edges and min(abs((g - lead_ms) - e) for e in edges) <= tau_ms:
        ev["reason"] = (f"reachable once the measured +{lead_ms} ms GT annotation lead is "
                        f"removed; the boundary is an annotation offset, not a miss")
        return {"category": "e_gt_telemetry_mismatch", "sub": "annotation_lead", **ev}

    # no telemetry at all within tolerance -> the recorder, not the representation
    ts = sess["ts"]
    i = bisect.bisect_left(ts, g)
    near = [abs(ts[j] - g) for j in (i - 1, i) if 0 <= j < len(ts)]
    if not near or min(near) > tau_ms:
        ev["reason"] = "no telemetry event within tolerance — a recording gap"
        return {"category": "e_gt_telemetry_mismatch", "sub": "telemetry_gap", **ev}

    # ---- (a) information destroyed by preprocessing ----------------------------------
    # The claim requires a trace: a raw event exists in the source chunk file inside the
    # window and does NOT survive into the normalised stream. Asserting loss without that
    # trace is not category (a).
    raw = sess["raw_ids_sorted"]
    lo = bisect.bisect_left(raw, (g - tau_ms,))
    hi = bisect.bisect_right(raw, (g + tau_ms, chr(0x10FFFF)))
    missing = [eid for _t, eid in raw[lo:hi] if eid not in sess["normalised_ids"]]
    if missing:
        ev["reason"] = "raw events in the window do not survive normalisation"
        ev["raw_events_in_window"] = hi - lo
        ev["raw_events_missing_from_normalised"] = len(missing)
        ev["missing_event_ids"] = missing[:5]
        return {"category": "a_information_destroyed", "sub": "dropped_by_normalise", **ev}

    # ---- (c) absorbed micro-excursion ------------------------------------------------
    # Provable: unreachable against the default blocks, reachable against blocks rebuilt
    # with absorption disabled. Default behaviour is untouched — min_events=0 makes the
    # `len(rows) < min_events` guard in blocks._absorb unsatisfiable.
    na = sess["edges_no_absorb"]
    if na and min(abs(g - e) for e in na) <= tau_ms:
        ev["reason"] = ("reachable against blocks built with absorption disabled, so the "
                        "boundary sat inside an excursion that blocks._absorb merged "
                        "under the A|x|A -> A rule")
        ev["distance_to_nearest_default_edge_ms"] = min(abs(g - e) for e in edges)
        ev["distance_to_nearest_unabsorbed_edge_ms"] = min(abs(g - e) for e in na)
        return {"category": "c_absorbed_micro_excursion", "sub": "absorb_a_x_a", **ev}

    # ---- (b) information preserved inside a block ------------------------------------
    inside = any(b["start_ms"] < g < b["end_ms"] for b in sess["blocks"])
    win = window_rows(sess["rows"], ts, g, tau_ms)
    sig = signals_in_window(win, sess["gap_threshold_ms"])
    fired = sorted(k for k, v in sig.items() if v)
    ev["events_in_window"] = len(win)
    ev["signals"] = fired
    ev["strictly_inside_a_block"] = inside
    if inside and fired:
        ev["reason"] = ("boundary falls strictly inside a block and the retained events in "
                        "the window carry at least one discriminating signal")
        return {"category": "b_preserved_inside_block", "sub": "signal_present", **ev}

    # ---- (d) ambiguous ----------------------------------------------------------------
    ev["reason"] = ("no discriminating signal among the retained events in the window"
                    + ("" if inside else "; boundary sits in an inter-block gap"))
    return {"category": "d_ambiguous_no_evidence",
            "sub": "inside_block" if inside else "inter_block_gap", **ev}
