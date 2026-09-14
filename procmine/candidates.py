"""Stage 3 — deterministic event-level boundary candidate generation (STEP1_SPEC §3.2).

A block is a **container**, not a boundary unit (ADR-015). This module produces a candidate
space strictly finer than block edges, able to place a boundary **between two events inside a
block**.

It **emits**; it does not decide. Scoring is stage 4, the gate stage 5, the decoder stage 7.

Four properties this module guarantees, each covered by a test:

  * **Superset.** Every block edge is emitted as `kind="block_edge"`, so the old candidate
    space is a strict subset of the new one.
  * **No ground truth.** This module imports no GT module and reads no `build/*/gt_*`,
    `executions*` or `expected_boundaries` artifact. It cannot, even accidentally, be fitted
    to the answer. S-E2's category assignments are GT-derived and are used only in the
    experiment's *evaluation* code, never here.
  * **Determinism.** No randomness, no wall-clock, no set iteration order in the output.
  * **No chunk-derived candidates.** No trigger references `chunk_id` (ADR-001). A candidate
    may coincide with a chunk edge, but never *because* of it; `feat_at_chunk_edge` records
    the coincidence for audit only and is not a trigger.

**Generation is recall-oriented.** S-E2 measured every strongly discriminating signal to be
*inverse* — `shortcut` 1.6% at missed boundaries vs 44.0% at controls, `clipboard_change`
0.6% vs 26.5%. Those are real evidence, but they are evidence for a **scorer**, which can
weigh them and still be overruled. A generator that used them to suppress candidates would
destroy boundaries irrecoverably, because nothing downstream can re-nominate what was never
emitted. So the inverse signals are **featurised and never used to prune**.
"""
from __future__ import annotations
import bisect, collections
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

Candidate = Dict[str, Any]

# Triggers. Each is a HYPOTHESIS about where a boundary might sit, not a rule that one does.
# None of them is permitted to suppress a candidate, only to propose one.
TRIGGER_EVENT_TYPES = frozenset({
    "app_switch", "browser_navigation", "window_title_change",
    "dialog_opened", "dialog_closed", "browser_tab_event",
})

# Windowed-context signals: featurised for the scorer, never used to gate generation.
CONTEXT_EVENT_TYPES = frozenset({
    "browser_navigation", "app_switch", "clipboard_change", "shortcut",
    "browser_form_input", "browser_click", "keystroke", "mouse_click",
    "mouse_scroll", "window_title_change",
})

# Interaction modes, for the typing -> navigating -> copying transition feature.
_MODE = {
    "keystroke": "typing", "text_input_complete": "typing", "browser_form_input": "typing",
    "browser_navigation": "navigating", "app_switch": "navigating",
    "browser_tab_event": "navigating", "window_title_change": "navigating",
    "clipboard_change": "copying",
    "mouse_click": "pointing", "browser_click": "pointing", "mouse_scroll": "pointing",
    "mouse_double_click": "pointing", "mouse_drag_drop": "pointing",
}

# Which triggers may PROPOSE a candidate. Every signal in §3.2.1 is featurised regardless;
# this set decides only which ones nominate a position.
#
# `mode_transition` is featurised but does NOT trigger. It fires on 77.7% of intra-block
# candidates — typing -> pointing happens constantly — and measured on both datasets it is
# what makes generation indiscriminate: with it, density is 0.272/event on dataset_a and
# 0.330/event on dataset_b, the latter over the 0.30 gate. Without it, density is 0.165 and
# 0.127. The cost is 1.9 points of reachability at tau=2s (89.9% -> 88.0%, i.e. 99.9% -> 97.8%
# of the achievable ceiling). S-E3 measures both arms; this is the shipped default because a
# trigger that nominates on three quarters of all intra-block positions is not discriminating
# a boundary hypothesis, it is nominating indiscriminately. It remains available via cfg.
ENABLED_TRIGGERS = frozenset({
    "app_switch", "app_switch_self", "browser_navigation", "window_title_change",
    "dialog_opened", "dialog_closed", "browser_tab_event",
    "title_change", "route_change", "origin_change", "app_change",
    "field_key_change", "large_relative_gap",
})

DEFAULT_CFG = {
    "enabled_triggers": ENABLED_TRIGGERS,
    # Redundancy control, NOT pruning. Self-referential app_switch events arrive in bursts
    # with a p50 inter-arrival of 55 ms on dataset_a; nominating each one separately proposes
    # the same boundary hypothesis dozens of times and costs 0.27 candidates/event on its own.
    # Collapsing a burst to its first member costs at most `dedup_ms` of positional accuracy,
    # far inside the tightest tolerance in the grid (tau = 1000 ms). Set to 0 to emit one
    # candidate at every trigger, which STEP1_SPEC §3.2's literal reading asks for; S-E3
    # measures both arms.
    "dedup_ms": 250,
    "gap_percentile": 0.95,     # per-session, never an absolute threshold (ADR-003)
    "window_ms": 2000,          # context window for featurisation
    "window_events": 3,         # +/- n events for local structure
}


def _mode(et: Optional[str]) -> str:
    return _MODE.get(et or "", "other")


def _session_gap_stats(rows: Sequence[Dict], pct: float) -> Tuple[Optional[float], float]:
    """Per-session gap percentile and median. ADR-003 keeps RELATIVE gap as a feature; an
    absolute millisecond threshold would be a dataset-specific rule."""
    gaps = sorted(r["ms_since_last"] for r in rows
                  if isinstance(r.get("ms_since_last"), (int, float)))
    if not gaps:
        return None, 1.0
    p = gaps[min(len(gaps) - 1, int(len(gaps) * pct))]
    med = gaps[len(gaps) // 2] or 1.0
    return p, float(med or 1.0)


def _is_self_switch(r: Dict) -> bool:
    """`payload.new_app == payload.previous_app` — the application did not change.

    S-E2 measured these at 71.0% of missed boundaries while `app_change` was 0.6%, i.e. they
    are almost the only high-mass signal available inside a block, and they create no block
    edge. ADR-014 declined to suppress them precisely because 176 of 738 on dataset_b carried
    a different, meaningful window title. They are the largest recoverable mass this generator
    targets.
    """
    na, pa = r.get("new_app") or "", r.get("prev_app") or ""
    return bool(na) and na == pa


def _triggers(rows: Sequence[Dict], i: int, p95: Optional[float]) -> List[str]:
    """Why position `i` is proposed. Empty list means it is not proposed."""
    r = rows[i]
    prev = rows[i - 1] if i > 0 else None
    out: List[str] = []
    et = r.get("event_type")
    if et in TRIGGER_EVENT_TYPES:
        out.append(et)
        if et == "app_switch" and _is_self_switch(r):
            out.append("app_switch_self")
    if prev is not None:
        if (prev.get("title") or "") != (r.get("title") or ""):
            out.append("title_change")
        if (prev.get("route") or "") != (r.get("route") or ""):
            out.append("route_change")
        if (prev.get("origin") or "") != (r.get("origin") or ""):
            out.append("origin_change")
        if (prev.get("app_name") or "") != (r.get("app_name") or ""):
            out.append("app_change")
        fp, fr = prev.get("field_key") or "", r.get("field_key") or ""
        if fp and fr and fp != fr:                      # optional extension, degrades to absent
            out.append("field_key_change")
        if _mode(prev.get("event_type")) != _mode(et):
            out.append("mode_transition")
    ms = r.get("ms_since_last")
    if p95 is not None and isinstance(ms, (int, float)) and ms >= p95:
        out.append("large_relative_gap")
    return out


def _features(rows: Sequence[Dict], i: int, blk: Dict, p95: Optional[float],
              med_gap: float, cfg: Dict, timeline: Sequence[int]) -> Dict[str, Any]:
    """Deterministic, numeric or boolean only. Hypotheses — never boundary rules.

    `timeline` is precomputed once per session; rebuilding it per candidate made generation
    quadratic and unusable on dataset_a's 162k events.
    """
    r = rows[i]
    prev = rows[i - 1] if i > 0 else None
    ts = r.get("ts_ms") or 0
    win_ms = cfg["window_ms"]
    lo = bisect.bisect_left(timeline, ts - win_ms)
    hi = bisect.bisect_right(timeline, ts + win_ms)
    win = rows[lo:hi]
    k = cfg["window_events"]
    near = rows[max(0, i - k):min(len(rows), i + k + 1)]

    ms = r.get("ms_since_last")
    ms = float(ms) if isinstance(ms, (int, float)) else 0.0
    span = max(1, (blk.get("last_seq") or 0) - (blk.get("first_seq") or 0))
    pos = (i - (blk.get("first_seq") or 0)) / span

    f: Dict[str, Any] = {
        # --- position within the enclosing block
        "pos_in_block": round(pos, 4),
        "events_from_block_start": i - (blk.get("first_seq") or 0),
        "events_to_block_end": (blk.get("last_seq") or 0) - i,
        "block_n_events": blk.get("n_events", 0),
        # --- timing
        "ms_since_last": ms,
        "rel_gap": round(ms / med_gap, 4) if med_gap else 0.0,
        "large_relative_gap": bool(p95 is not None and ms >= p95),
        "local_density_w": len(win) / (2 * win_ms / 1000.0),
        "lull_ratio": round((ms / med_gap) / max(1.0, len(near)), 4) if med_gap else 0.0,
        # --- identity / surface change across the candidate
        "app_switch_at": r.get("event_type") == "app_switch",
        "app_switch_self_at": _is_self_switch(r) and r.get("event_type") == "app_switch",
        "app_change": bool(prev is not None
                           and (prev.get("app_name") or "") != (r.get("app_name") or "")),
        "title_change": bool(prev is not None
                             and (prev.get("title") or "") != (r.get("title") or "")),
        "route_change": bool(prev is not None
                             and (prev.get("route") or "") != (r.get("route") or "")),
        "origin_change": bool(prev is not None
                              and (prev.get("origin") or "") != (r.get("origin") or "")),
        "field_key_change": bool(prev is not None and (prev.get("field_key") or "")
                                 and (r.get("field_key") or "")
                                 and prev["field_key"] != r["field_key"]),
        "mode_transition": bool(prev is not None
                                and _mode(prev.get("event_type")) != _mode(r.get("event_type"))),
        "is_web_surface": bool(r.get("origin")),
        # audit only — never a trigger (ADR-001)
        "at_chunk_edge": bool(prev is not None
                              and prev.get("chunk_id") != r.get("chunk_id")),
    }
    # --- windowed event-type presence and counts. The inverse signals S-E2 found live here:
    #     featurised for the scorer, never used to suppress a candidate.
    counts = collections.Counter(x.get("event_type") for x in win)
    for et in sorted(CONTEXT_EVENT_TYPES):
        f[f"{et}_w"] = bool(counts.get(et))
        f[f"{et}_w_n"] = counts.get(et, 0)
    f["events_in_window"] = len(win)
    return f


def generate(rows: Sequence[Dict], blocks: Sequence[Dict],
             cfg: Optional[Dict] = None) -> List[Candidate]:
    """Rows + blocks -> boundary candidates, ordered by `at_seq` (DATA_CONTRACT §10.2).

    `at_seq` is the index of the event the boundary sits BEFORE. Block edges are emitted for
    every block; intra-block candidates come from event-level structure, never a fixed stride
    or time grid.
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    if not rows or not blocks:
        return []
    sid = rows[0].get("session_id") or blocks[0].get("session_id")
    p95, med_gap = _session_gap_stats(rows, c["gap_percentile"])
    timeline = [r.get("ts_ms") or 0 for r in rows]

    # block index -> enclosing block for any event position
    starts = [b.get("first_seq") or 0 for b in blocks]
    def enclosing(i: int) -> Dict:
        j = bisect.bisect_right(starts, i) - 1
        return blocks[max(0, min(j, len(blocks) - 1))]

    # ---- 1. every block edge (contract 1: the old space is a strict subset)
    proposed: Dict[int, Dict[str, Any]] = {}
    for b in blocks:
        fs = b.get("first_seq")
        if fs is None or not (0 <= fs < len(rows)):
            continue
        proposed[fs] = {"kind": "block_edge", "block": b, "triggers": ["block_edge"]}

    # ---- 2. intra-block candidates from event-level structure
    for i in range(1, len(rows)):
        if i in proposed:
            continue
        trg = [t for t in _triggers(rows, i, p95) if t in c["enabled_triggers"]]
        if trg:
            proposed[i] = {"kind": "intra_block", "block": enclosing(i), "triggers": trg}

    # ---- 3. redundancy control (NOT pruning): collapse a burst of intra-block candidates
    #         to its first member. A block edge is never dropped.
    keep: List[int] = []
    last_ms: Optional[int] = None
    for i in sorted(proposed):
        ts = rows[i].get("ts_ms") or 0
        if proposed[i]["kind"] == "block_edge":
            keep.append(i)
            last_ms = ts
            continue
        if c["dedup_ms"] and last_ms is not None and (ts - last_ms) < c["dedup_ms"]:
            continue
        keep.append(i)
        last_ms = ts

    out: List[Candidate] = []
    for n, i in enumerate(keep):
        p = proposed[i]
        b = p["block"]
        out.append({
            "cand_id": f"{sid}#c{n:05d}",
            "session_id": sid,
            "at_seq": i,
            "at_ms": rows[i].get("ts_ms"),
            "block_id": b.get("block_id"),
            "kind": p["kind"],
            "triggers": sorted(p["triggers"]),
            "features": _features(rows, i, b, p95, med_gap, c, timeline),
        })
    return out


def density(candidates: Sequence[Candidate], rows: Sequence[Dict],
            blocks: Sequence[Dict]) -> Dict[str, Any]:
    """Mandatory alongside any reachability figure (STEP1_SPEC §3.2 contract 5)."""
    n = len(candidates)
    return {
        "candidates": n, "events": len(rows), "blocks": len(blocks),
        "per_event": round(n / len(rows), 4) if rows else None,
        "per_block": round(n / len(blocks), 3) if blocks else None,
        "block_edge": sum(1 for x in candidates if x["kind"] == "block_edge"),
        "intra_block": sum(1 for x in candidates if x["kind"] == "intra_block"),
    }
