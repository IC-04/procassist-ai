"""Stage B0-B5 — the baseline segmenters (EVALUATION_PROTOCOL.md §6).

These exist to answer a question the final report must answer: **what does a trivial method
already achieve, and where exactly does it fail?** `README.md`'s FAQ says deciding what counts
as "good enough" is part of the task, so this scorecard is a graded deliverable, not
scaffolding. They are implemented in Phase 1 and kept forever.

Every baseline returns `(intervals, labels)` in the same shape, so the harness scores all of
them identically and the Phase 3 AI arm is comparable to them without re-implementation.

Two of them are deliberately **generous**, and that is the point:

  * `B2-gap` receives k = the true execution count (oracle cardinality)
  * `B3-random` is count-matched to the truth

Neither could know k in production. They are floors: a real method that cannot beat a method
handed the answer's cardinality has not earned its complexity.
"""
from __future__ import annotations
import collections, random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Interval = Tuple[int, int]

# The label a boundary-only baseline attaches to a segment. None of these baselines models
# process identity, so identity is assigned deterministically from the modal surface key.
# This is a documented floor for label consistency, not a labelling method.
LABEL_FROM = "modal_surface"


def _span(rows: Sequence[Dict]) -> Interval:
    return (rows[0]["ts_ms"], rows[-1]["ts_ms"])


def _label_for(rows: Sequence[Dict], surface_of) -> str:
    c = collections.Counter(surface_of(r) for r in rows)
    return c.most_common(1)[0][0] if c else "unknown"


def _intervals_from_cuts(rows: Sequence[Dict], cuts: Sequence[int],
                         surface_of) -> Tuple[List[Interval], List[str]]:
    """`cuts` are row indices where a new segment STARTS."""
    n = len(rows)
    idx = sorted({0} | {c for c in cuts if 0 < c < n})
    out_i: List[Interval] = []
    out_l: List[str] = []
    for a, b in zip(idx, list(idx[1:]) + [n]):
        chunk = rows[a:b]
        if not chunk:
            continue
        out_i.append((chunk[0]["ts_ms"], chunk[-1]["ts_ms"]))
        out_l.append(_label_for(chunk, surface_of))
    return out_i, out_l


# ---------------------------------------------------------------- the six

def b0_single(rows, blocks, **kw):
    """One segment per session. The absolute floor."""
    from .blocks import surface_key
    if not rows:
        return [], []
    return [_span(rows)], [_label_for(rows, surface_key)]


def b1_chunk(rows, blocks, **kw):
    """One segment per chunk. Exists to PROVE chunks are meaningless (DATA_SCHEMA §1).

    Chunks are fixed recording-time buckets. ADR-001 dissolves them precisely because they
    carry no business meaning; this baseline is the measurement that justifies that.
    """
    from .blocks import surface_key
    if not rows:
        return [], []
    cuts = [i for i in range(1, len(rows))
            if rows[i].get("chunk_id") != rows[i - 1].get("chunk_id")]
    return _intervals_from_cuts(rows, cuts, surface_key)


def b2_gap(rows, blocks, k: Optional[int] = None, **kw):
    """Top-k largest inter-event gaps, with k = the TRUE execution count (oracle).

    ADR-003 already established on B that no gap-threshold segmenter is a candidate method;
    this is kept permanently as a published floor rather than re-litigated.
    """
    from .blocks import surface_key
    if not rows:
        return [], []
    k = max(1, int(k or 1))
    gaps = sorted(((rows[i]["ts_ms"] - rows[i - 1]["ts_ms"], i)
                   for i in range(1, len(rows))), reverse=True)
    cuts = sorted(i for _g, i in gaps[:max(0, k - 1)])
    return _intervals_from_cuts(rows, cuts, surface_key)


def b3_random(rows, blocks, k: Optional[int] = None, seed: int = 0, **kw):
    """Count-matched random boundaries. Chance level; reported as mean +/- sd over seeds."""
    from .blocks import surface_key
    if not rows:
        return [], []
    k = max(1, int(k or 1))
    rng = random.Random(seed)
    n = len(rows)
    cuts = sorted(rng.sample(range(1, n), min(max(0, k - 1), max(0, n - 1)))) if n > 1 else []
    return _intervals_from_cuts(rows, cuts, surface_key)


def b4_surface(rows, blocks, **kw):
    """A boundary at EVERY context-state change. The over-segmentation ceiling.

    This is the perception layer with no absorption at all — the thing Phase 0's block
    builder exists to improve on.
    """
    from .blocks import surface_key
    if not rows:
        return [], []
    cuts = [i for i in range(1, len(rows))
            if surface_key(rows[i]) != surface_key(rows[i - 1])]
    return _intervals_from_cuts(rows, cuts, surface_key)


def b5_dwell(rows, blocks, **kw):
    """Activity blocks after micro-excursion absorption — the deterministic candidate.

    This is what Phase 0 actually produces, and the number every later method must beat.
    """
    if not blocks:
        return [], []
    return ([(b["start_ms"], b["end_ms"]) for b in blocks],
            [b["surface"] for b in blocks])


REGISTRY = {
    "B0-single": b0_single,
    "B1-chunk": b1_chunk,
    "B2-gap": b2_gap,
    "B3-random": b3_random,
    "B4-surface": b4_surface,
    "B5-dwell": b5_dwell,
}

ORACLE_K = frozenset({"B2-gap", "B3-random"})     # receive the true segment count
N_RANDOM_SEEDS = 20                                # EVALUATION_PROTOCOL §6


def run_baseline(name: str, rows, blocks, k: Optional[int] = None,
                 seed: int = 0) -> Tuple[List[Interval], List[str]]:
    fn = REGISTRY[name]
    return fn(rows, blocks, k=k, seed=seed)


def to_segments(session_id: str, intervals: Sequence[Interval],
                labels: Sequence[str]) -> List[Dict]:
    """`segments.jsonl`-shaped rows (DATA_CONTRACT §6) so the harness scores every arm alike.

    Emitted for inspection only in Phase 1; the contractual deliverable is produced by the
    decoder in Phase 4.
    """
    from datetime import datetime, timezone
    def iso(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [{"session_id": session_id, "start": iso(a), "end": iso(b), "label": str(l)}
            for (a, b), l in zip(intervals, labels)]
