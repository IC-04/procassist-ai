"""Stage 7 — constrained global segmentation (STEP1_SPEC §3.6).

A dynamic-programming pass that chooses the globally best set of segments from scored
candidates, subject to **hard constraints that reject rather than penalise**.

Shape of the output, and why it matters: Dataset A's ground truth does **not** tile the session.
Median GT time coverage is 0.81 with 12% of the span falling in inter-fragment gaps, so
executions are disjoint intervals with idle space between them. A decoder that partitioned the
session would emit `N+1` boundary points where the reference has `2N`, capping boundary recall
near 52% by construction however good its ranking. This decoder therefore selects **disjoint
segments**, each contributing its own start and end.

Not in scope, deliberately: a process-mining engine, `pm4py`, step discovery. ADR-008's
precondition is unmet — A's `task_started` is 1:1 with executions, so there is no internal step
structure to mine.
"""
from __future__ import annotations
import collections
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Recomputed on the CORRECTED scoreable canonical population (S-E1), fragment convention:
#   p01 19.0 s · p05 21.8 s · p10 23.2 s · p50 31.7 s · p90 66.4 s · p99 144.2 s · max 1144.8 s
# Phase 1's "median 34.8 s / p10 23.9 s" was the EXECUTION-ACTIVE duration, a different
# quantity; it is not reused here.
DEFAULT_CFG = {
    # A hard floor at the 1st percentile rejects only what the reference distribution says
    # cannot happen. A floor at the median would be a shaping penalty wearing a constraint's
    # clothes.
    "min_duration_ms": 19_000,
    # No upper bound. A's fragments run to 1144.8 s with p99 at 144.2 s, so any ceiling that
    # bit at all would reject genuine executions. STEP1_SPEC §3.6 permits one "only where A's
    # distribution justifies one" — it does not.
    "max_duration_ms": None,
    # Cost of opening a segment; the operating point. Operates on PERCENTILE-CALIBRATED
    # scores (score.calibrate), so it selects a FRACTION of each dataset's own distribution
    # rather than clearing an absolute bar fitted on A. Chosen for count ratio ~= 1.0 on
    # dataset_a (0.98 at this value), NOT for maximum F1 — 1.5 scores F1 0.717 at ratio 0.87,
    # which is a bet on under-segmenting; a ratio near 1.0 makes no such bet.
    "lambda_per_segment": 1.40,
    "nms_window_ms": 0,           # extra suppression; 0 = rely on the duration floor
    "min_score": 0.0,
}


def _nms(cands: Sequence[Dict], window_ms: int) -> List[Dict]:
    """Score-ranked non-maximum suppression within a time window.

    S-E3 measured ~2 candidates per true boundary, so clusters must collapse or the count
    ratio inflates on that alone. The duration floor already suppresses most clusters; this
    exists so its contribution can be measured separately (`nms_window_ms=0` disables it).
    """
    if window_ms <= 0:
        return list(cands)
    keep: List[Dict] = []
    for c in sorted(cands, key=lambda x: (-float(x.get("score") or 0), x["at_seq"])):
        t = c.get("at_ms")
        if t is None:
            continue
        if any(abs(t - k["at_ms"]) < window_ms for k in keep):
            continue
        keep.append(c)
    return sorted(keep, key=lambda x: x["at_seq"])


def decode_session(cands: Sequence[Dict], cfg: Optional[Dict] = None) -> List[Dict]:
    """Scored candidates for ONE session -> chosen disjoint segments.

    Maximises `sum over chosen segments of (score(start) + score(end) - lambda)` subject to the
    hard constraints. O(n^2) in the number of candidates per session (~426 on A).
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    pool = [x for x in cands
            if x.get("at_ms") is not None and float(x.get("score") or 0) >= c["min_score"]]
    pool = _nms(pool, int(c["nms_window_ms"]))
    pool.sort(key=lambda x: (x["at_ms"], x["at_seq"]))
    n = len(pool)
    if n < 2:
        return []

    floor = int(c["min_duration_ms"])
    ceil_ms = c["max_duration_ms"]
    lam = float(c["lambda_per_segment"])
    s = [float(x.get("score") or 0.0) for x in pool]
    t = [int(x["at_ms"]) for x in pool]

    NEG = float("-inf")
    # best[k] = best achievable value using pool[:k] with no segment left open
    best = [0.0] * (n + 1)
    take: List[Optional[Tuple[int, int]]] = [None] * (n + 1)
    for k in range(1, n + 1):
        best[k] = best[k - 1]
        take[k] = None
        j = k - 1                      # candidate index of a potential segment END
        bv = NEG
        bi = -1
        for i in range(j - 1, -1, -1):  # potential segment START
            dur = t[j] - t[i]
            if dur < floor:
                continue
            if ceil_ms is not None and dur > ceil_ms:
                break                   # earlier i only makes it longer
            v = best[i] + s[i] + s[j] - lam
            if v > bv:
                bv, bi = v, i
        if bi >= 0 and bv > best[k]:
            best[k] = bv
            take[k] = (bi, j)

    # backtrack
    segs: List[Dict] = []
    k = n
    while k > 0:
        if take[k] is None:
            k -= 1
            continue
        i, j = take[k]
        segs.append({
            "start_ms": t[i], "end_ms": t[j],
            "start_seq": pool[i]["at_seq"], "end_seq": pool[j]["at_seq"],
            "session_id": pool[i].get("session_id"),
            "start_cand_id": pool[i].get("cand_id"), "end_cand_id": pool[j].get("cand_id"),
            "start_score": s[i], "end_score": s[j],
            "score": round((s[i] + s[j]) / 2, 6),
            "evidence": sorted(set((pool[i].get("top_features") or [])
                                   + (pool[j].get("top_features") or []))),
        })
        k = i
    segs.reverse()
    return segs


def decode(scored_by_session: Dict[str, Sequence[Dict]],
           cfg: Optional[Dict] = None) -> Dict[str, List[Dict]]:
    return {sid: decode_session(cands, cfg) for sid, cands in sorted(scored_by_session.items())}


# ---------------------------------------------------------------- constraint audit

def violations(segments: Sequence[Dict], cfg: Optional[Dict] = None) -> List[str]:
    """Every hard constraint, checked on the decoder's own output.

    A constraint that is only enforced by construction is a constraint that will one day not be.
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    out: List[str] = []
    by_session: Dict[str, List[Dict]] = collections.defaultdict(list)
    for s in segments:
        by_session[s.get("session_id")].append(s)
    for sid, segs in by_session.items():
        segs = sorted(segs, key=lambda x: x["start_ms"])
        for s in segs:
            if s["end_ms"] <= s["start_ms"]:
                out.append(f"{sid}: zero-length or reversed segment {s['start_ms']}-{s['end_ms']}")
            dur = s["end_ms"] - s["start_ms"]
            if dur < int(c["min_duration_ms"]):
                out.append(f"{sid}: segment {dur} ms is below the duration floor "
                           f"{c['min_duration_ms']} ms")
            if c["max_duration_ms"] is not None and dur > int(c["max_duration_ms"]):
                out.append(f"{sid}: segment {dur} ms exceeds the upper bound")
        for a, b in zip(segs, segs[1:]):
            if b["start_ms"] < a["end_ms"]:
                out.append(f"{sid}: segments overlap at {a['end_ms']} / {b['start_ms']}")
            if b["start_ms"] < a["start_ms"]:
                out.append(f"{sid}: segments out of chronological order")
    return out
