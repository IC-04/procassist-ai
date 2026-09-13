"""Stage E — the evaluation harness (EVALUATION_PROTOCOL.md).

Built BEFORE the first real segmenter (Phase 1) so that no experiment can invent its own
metric. Every later phase reuses this module unchanged, which is what makes the AI arm in
Phase 3 comparable to the Phase 1 baselines.

Two things are scored and **never combined into one number** (`README.md` *Deliverables*):

  (a) boundaries   — boundary F1 @ tolerance, segmental F1 @ IoU, WindowDiff/Pk, count ratio
  (b) label identity — ARI / NMI over matched segments, always with `match_rate`

Both coordinate domains are computed (§2): time (ms) and event index. The event rate is
wildly non-uniform, so a fixed second-tolerance is not a fixed difficulty.

Pure functions. No printing, no conclusions, no mutation of inputs.
"""
from __future__ import annotations
import bisect, collections
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

Interval = Tuple[int, int]          # (start, end), inclusive-exclusive

# Defaults from EVALUATION_PROTOCOL §2. `taus_ms` is CALIBRATED against A's observed
# execution durations in `calibrate_tau`, never assumed.
DEFAULT_TAUS_MS = (1000, 2000, 5000, 10000)
DEFAULT_KAPPAS = (1, 2, 5, 10)
DEFAULT_IOUS = (0.3, 0.5, 0.7)


# ---------------------------------------------------------------- boundaries

def boundary_f1(ref: Sequence[int], hyp: Sequence[int], tol: int) -> Dict[str, Any]:
    """Greedy one-to-one matching of boundary positions within `tol`.

    `ref` and `hyp` are positions in ONE domain (ms or event index). One-to-one matters:
    without it a hypothesis that emits a dense burst of boundaries scores a perfect recall
    by covering every reference with copies of itself.
    """
    ref_s, hyp_s = sorted(ref), sorted(hyp)
    if not ref_s and not hyp_s:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0,
                "n_ref": 0, "n_hyp": 0, "tol": tol}
    # candidate pairs sorted by distance, then greedily consumed one-to-one
    pairs: List[Tuple[int, int, int]] = []
    for i, r in enumerate(ref_s):
        lo = bisect.bisect_left(hyp_s, r - tol)
        hi = bisect.bisect_right(hyp_s, r + tol)
        for j in range(lo, hi):
            pairs.append((abs(hyp_s[j] - r), i, j))
    pairs.sort()
    used_r: set = set()
    used_h: set = set()
    for _d, i, j in pairs:
        if i in used_r or j in used_h:
            continue
        used_r.add(i)
        used_h.add(j)
    tp = len(used_r)
    fp = len(hyp_s) - tp
    fn = len(ref_s) - tp
    precision = tp / len(hyp_s) if hyp_s else 0.0
    recall = tp / len(ref_s) if ref_s else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn, "n_ref": len(ref_s), "n_hyp": len(hyp_s), "tol": tol}


def iou(a: Interval, b: Interval) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def segmental_f1(ref: Sequence[Interval], hyp: Sequence[Interval],
                 iou_thr: float) -> Dict[str, Any]:
    """One-to-one interval matching above an IoU threshold (greedy, best IoU first)."""
    if not ref and not hyp:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "matched": 0,
                "n_ref": 0, "n_hyp": 0, "iou": iou_thr}
    cands: List[Tuple[float, int, int]] = []
    for i, r in enumerate(ref):
        for j, h in enumerate(hyp):
            v = iou(r, h)
            if v >= iou_thr:
                cands.append((-v, i, j))
    cands.sort()
    used_r: set = set()
    used_h: set = set()
    for _v, i, j in cands:
        if i in used_r or j in used_h:
            continue
        used_r.add(i)
        used_h.add(j)
    m = len(used_r)
    precision = m / len(hyp) if hyp else 0.0
    recall = m / len(ref) if ref else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "matched": m, "n_ref": len(ref), "n_hyp": len(hyp), "iou": iou_thr}


def count_ratio(ref: Sequence, hyp: Sequence) -> float:
    """len(hyp)/len(ref). >1 is over-segmentation, <1 under-segmentation."""
    return round(len(hyp) / len(ref), 4) if len(ref) else float("inf")


# ---------------------------------------------------------------- masses / segeval

def masses_from_boundaries(boundaries: Sequence[int], total: int) -> List[int]:
    """Boundary indices -> segment masses over `total` atomic units (EVENT INDEX, §3)."""
    bs = sorted({b for b in boundaries if 0 < b < total})
    out, prev = [], 0
    for b in bs:
        out.append(b - prev)
        prev = b
    out.append(total - prev)
    return [m for m in out if m > 0] or [total]


def windowdiff(ref_masses: Sequence[int], hyp_masses: Sequence[int],
               k: Optional[int] = None) -> Optional[float]:
    """Thin wrapper over `segeval`. Lower is better; 0 is perfect."""
    try:
        import segeval
    except ImportError:
        return None
    if sum(ref_masses) != sum(hyp_masses) or not ref_masses or not hyp_masses:
        return None
    try:
        v = (segeval.window_diff(tuple(hyp_masses), tuple(ref_masses)) if k is None
             else segeval.window_diff(tuple(hyp_masses), tuple(ref_masses), window_size=k))
        return round(float(v), 4)
    except Exception:
        return None


def pk(ref_masses: Sequence[int], hyp_masses: Sequence[int],
       k: Optional[int] = None) -> Optional[float]:
    """Thin wrapper over `segeval.pk`. Lower is better."""
    try:
        import segeval
    except ImportError:
        return None
    if sum(ref_masses) != sum(hyp_masses) or not ref_masses or not hyp_masses:
        return None
    try:
        v = (segeval.pk(tuple(hyp_masses), tuple(ref_masses)) if k is None
             else segeval.pk(tuple(hyp_masses), tuple(ref_masses), window_size=k))
        return round(float(v), 4)
    except Exception:
        return None


# ---------------------------------------------------------------- identity

def identity_scores(ref_labels: Sequence, hyp_labels: Sequence) -> Dict[str, Any]:
    """ARI / NMI / homogeneity / completeness over paired label sequences."""
    if len(ref_labels) != len(hyp_labels) or not ref_labels:
        return {"ari": None, "nmi": None, "homogeneity": None, "completeness": None, "n": 0}
    try:
        from sklearn import metrics as skm
    except ImportError:
        return {"ari": None, "nmi": None, "homogeneity": None, "completeness": None,
                "n": len(ref_labels)}
    r = [str(x) for x in ref_labels]
    h = [str(x) for x in hyp_labels]
    return {"ari": round(float(skm.adjusted_rand_score(r, h)), 4),
            "nmi": round(float(skm.normalized_mutual_info_score(r, h)), 4),
            "homogeneity": round(float(skm.homogeneity_score(r, h)), 4),
            "completeness": round(float(skm.completeness_score(r, h)), 4),
            "n": len(r)}


def matched_identity(ref: Sequence[Interval], ref_labels: Sequence,
                     hyp: Sequence[Interval], hyp_labels: Sequence,
                     iou_thr: float = 0.5) -> Dict[str, Any]:
    """Match intervals at IoU, then score identity over matched pairs ONLY.

    `match_rate` is returned alongside and is not optional: ARI computed over a handful of
    easy matches is meaningless without knowing how much of the reference was matched at all
    (EVALUATION_PROTOCOL §3).
    """
    cands: List[Tuple[float, int, int]] = []
    for i, r in enumerate(ref):
        for j, h in enumerate(hyp):
            v = iou(r, h)
            if v >= iou_thr:
                cands.append((-v, i, j))
    cands.sort()
    used_r: set = set()
    used_h: set = set()
    pairs: List[Tuple[int, int]] = []
    for _v, i, j in cands:
        if i in used_r or j in used_h:
            continue
        used_r.add(i)
        used_h.add(j)
        pairs.append((i, j))
    rl = [ref_labels[i] for i, _ in pairs]
    hl = [hyp_labels[j] for _, j in pairs]
    scores = identity_scores(rl, hl)
    scores["match_rate"] = round(len(pairs) / len(ref), 4) if ref else 0.0
    scores["n_matched"] = len(pairs)
    scores["n_ref"] = len(ref)
    scores["iou"] = iou_thr
    return scores


def interruption_recall(canonical: Sequence[Dict], hyp: Sequence[Interval],
                        hyp_labels: Sequence) -> Dict[str, Any]:
    """The only metric that measures M2b (stitching interrupted executions).

    For each canonical execution with n_fragments > 1: find the hypothesis segment covering
    each fragment (largest temporal overlap) and ask whether ALL fragments were assigned the
    same hypothesis label.
    """
    multi = [c for c in canonical if c.get("n_fragments", 1) > 1]
    if not multi:
        return {"n_interrupted": 0, "stitched": 0, "recall": None,
                "n_fragments_total": 0, "fragments_covered": 0}
    stitched = 0
    frag_total = frag_cov = 0
    for c in multi:
        labels: List[Any] = []
        for a, b in c.get("interval_ms", []):
            frag_total += 1
            best, best_ov = None, 0
            for j, (hs, he) in enumerate(hyp):
                ov = max(0, min(b, he) - max(a, hs))
                if ov > best_ov:
                    best, best_ov = j, ov
            if best is not None:
                frag_cov += 1
                labels.append(hyp_labels[best])
            else:
                labels.append(None)
        if labels and all(x is not None and x == labels[0] for x in labels):
            stitched += 1
    return {"n_interrupted": len(multi), "stitched": stitched,
            "recall": round(stitched / len(multi), 4),
            "n_fragments_total": frag_total, "fragments_covered": frag_cov}


# ---------------------------------------------------------------- calibration

def calibrate_tau(canonical: Sequence[Dict],
                  fractions: Sequence[float] = (0.03, 0.06, 0.15, 0.30)) -> Dict[str, Any]:
    """Derive the τ grid from A's OBSERVED execution durations (Task 1.5).

    A tolerance is only interpretable relative to how long an execution actually lasts, so
    the grid is expressed as a fraction of the median canonical duration rather than
    hard-coded seconds. The returned `grid_ms` is what `evaluate_all` should be given.
    """
    durs = sorted(c["total_duration_s"] for c in canonical
                  if c.get("total_duration_s", 0) > 0)
    if not durs:
        return {"median_duration_s": None, "grid_ms": list(DEFAULT_TAUS_MS),
                "source": "default (no durations available)"}
    def q(p: float) -> float:
        return durs[min(len(durs) - 1, int(len(durs) * p))]
    med = q(0.5)
    grid = sorted({max(250, int(round(med * f * 1000 / 250)) * 250) for f in fractions})
    return {"n": len(durs), "p10_s": round(q(.1), 1), "median_duration_s": round(med, 1),
            "p90_s": round(q(.9), 1),
            "fractions_of_median": list(fractions),
            "grid_ms": grid,
            "grid_as_pct_of_median": [round(100 * g / (med * 1000), 1) for g in grid],
            "source": "calibrated from canonical execution durations"}


# ---------------------------------------------------------------- index mapping

def ms_to_index(timeline: Sequence[int], ts: int) -> int:
    """Map a timestamp to its global event index within a session (`normalise` seq)."""
    return bisect.bisect_left(timeline, ts)


def intervals_to_index(timeline: Sequence[int],
                       intervals: Sequence[Interval]) -> List[Interval]:
    return [(ms_to_index(timeline, a), ms_to_index(timeline, b)) for a, b in intervals]


def boundaries_of(intervals: Sequence[Interval]) -> List[int]:
    """Interval endpoints -> the boundary set. Starts and ends both count."""
    return sorted({x for a, b in intervals for x in (a, b)})


# ---------------------------------------------------------------- entry point

def evaluate_all(ref_bundle: Dict[str, Any], hyp_bundle: Dict[str, Any],
                 config: Dict[str, Any]) -> Dict[str, Any]:
    """The one entry point. Returns the nested dict written verbatim to `metrics.json`.

    `ref_bundle` / `hyp_bundle` are `{session_id: {"intervals": [(ms,ms)], "labels": [...]}}`;
    `ref_bundle` may also carry `"canonical"` per session for `interruption_recall`.
    `config` carries `taus_ms`, `kappas`, `ious`, and `timelines` (session -> sorted ts_ms).
    """
    taus = list(config.get("taus_ms", DEFAULT_TAUS_MS))
    kappas = list(config.get("kappas", DEFAULT_KAPPAS))
    ious = list(config.get("ious", DEFAULT_IOUS))
    timelines: Dict[str, Sequence[int]] = config.get("timelines", {})
    sessions = sorted(set(ref_bundle) | set(hyp_bundle))

    # --- pooled accumulators
    agg_time: Dict[int, Dict[str, int]] = {t: collections.Counter() for t in taus}
    agg_idx: Dict[int, Dict[str, int]] = {k: collections.Counter() for k in kappas}
    agg_seg: Dict[float, Dict[str, int]] = {i: collections.Counter() for i in ious}
    wd_vals: List[float] = []
    pk_vals: List[float] = []
    all_ref_lab: List[Any] = []
    all_hyp_lab: List[Any] = []
    per_session: Dict[str, Any] = {}
    n_ref_total = n_hyp_total = 0
    canon_all: List[Dict] = []
    hyp_all: List[Interval] = []
    hyp_lab_all: List[Any] = []

    for sid in sessions:
        r = ref_bundle.get(sid, {})
        h = hyp_bundle.get(sid, {})
        ri: List[Interval] = list(r.get("intervals", []))
        hi: List[Interval] = list(h.get("intervals", []))
        rl = list(r.get("labels", []))
        hl = list(h.get("labels", []))
        tl = list(timelines.get(sid, []))
        n_ref_total += len(ri)
        n_hyp_total += len(hi)

        rb, hb = boundaries_of(ri), boundaries_of(hi)
        s_entry: Dict[str, Any] = {"n_ref": len(ri), "n_hyp": len(hi),
                                   "count_ratio": count_ratio(ri, hi)}

        # (a) boundaries — time domain
        s_entry["boundary_time"] = {}
        for t in taus:
            m = boundary_f1(rb, hb, t)
            s_entry["boundary_time"][str(t)] = m
            for k in ("tp", "fp", "fn"):
                agg_time[t][k] += m[k]

        # (a) boundaries — event-index domain
        s_entry["boundary_index"] = {}
        if tl:
            rbi = [ms_to_index(tl, x) for x in rb]
            hbi = [ms_to_index(tl, x) for x in hb]
            for k in kappas:
                m = boundary_f1(rbi, hbi, k)
                s_entry["boundary_index"][str(k)] = m
                for kk in ("tp", "fp", "fn"):
                    agg_idx[k][kk] += m[kk]
            # WindowDiff / Pk over EVENT INDEX masses
            total = len(tl)
            rm = masses_from_boundaries([x for x in rbi if 0 < x < total], total)
            hm = masses_from_boundaries([x for x in hbi if 0 < x < total], total)
            wd, p = windowdiff(rm, hm), pk(rm, hm)
            s_entry["windowdiff"], s_entry["pk"] = wd, p
            if wd is not None:
                wd_vals.append(wd)
            if p is not None:
                pk_vals.append(p)

        # (a) segmental
        s_entry["segmental"] = {}
        for i in ious:
            m = segmental_f1(ri, hi, i)
            s_entry["segmental"][str(i)] = m
            agg_seg[i]["matched"] += m["matched"]
            agg_seg[i]["n_ref"] += m["n_ref"]
            agg_seg[i]["n_hyp"] += m["n_hyp"]

        # (b) identity
        if rl and hl:
            s_entry["identity"] = matched_identity(ri, rl, hi, hl, iou_thr=0.5)
            for i, j in _pairs_at(ri, hi, 0.5):
                all_ref_lab.append(rl[i])
                all_hyp_lab.append(hl[j])

        can = r.get("canonical") or []
        canon_all.extend(can)
        hyp_all.extend(hi)
        hyp_lab_all.extend(hl if hl else [None] * len(hi))
        if can:
            s_entry["interruption"] = interruption_recall(can, hi, hl or [None] * len(hi))
        per_session[sid] = s_entry

    def prf(c: Dict[str, int]) -> Dict[str, Any]:
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        rr = tp / (tp + fn) if (tp + fn) else 0.0
        return {"precision": round(p, 4), "recall": round(rr, 4),
                "f1": round(2 * p * rr / (p + rr), 4) if (p + rr) else 0.0,
                "tp": tp, "fp": fp, "fn": fn}

    overall: Dict[str, Any] = {
        "n_sessions": len(sessions),
        "n_ref_segments": n_ref_total,
        "n_hyp_segments": n_hyp_total,
        "count_ratio": round(n_hyp_total / n_ref_total, 4) if n_ref_total else None,
        "boundary_time": {str(t): prf(agg_time[t]) for t in taus},
        "boundary_index": {str(k): prf(agg_idx[k]) for k in kappas},
        "segmental": {},
        "windowdiff_mean": round(sum(wd_vals) / len(wd_vals), 4) if wd_vals else None,
        "pk_mean": round(sum(pk_vals) / len(pk_vals), 4) if pk_vals else None,
    }
    for i in ious:
        c = agg_seg[i]
        p = c["matched"] / c["n_hyp"] if c["n_hyp"] else 0.0
        rr = c["matched"] / c["n_ref"] if c["n_ref"] else 0.0
        overall["segmental"][str(i)] = {
            "precision": round(p, 4), "recall": round(rr, 4),
            "f1": round(2 * p * rr / (p + rr), 4) if (p + rr) else 0.0,
            "matched": c["matched"], "n_ref": c["n_ref"], "n_hyp": c["n_hyp"]}
    if all_ref_lab:
        sc = identity_scores(all_ref_lab, all_hyp_lab)
        sc["match_rate"] = round(len(all_ref_lab) / n_ref_total, 4) if n_ref_total else 0.0
        sc["n_matched"] = len(all_ref_lab)
        overall["identity_pooled"] = sc
    if canon_all:
        overall["interruption"] = interruption_recall(canon_all, hyp_all, hyp_lab_all)

    return {"config": {"taus_ms": taus, "kappas": kappas, "ious": ious,
                       "tier": config.get("tier"), "arm": config.get("arm")},
            "overall": overall, "per_session": per_session}


def _pairs_at(ref: Sequence[Interval], hyp: Sequence[Interval],
              thr: float) -> List[Tuple[int, int]]:
    cands: List[Tuple[float, int, int]] = []
    for i, r in enumerate(ref):
        for j, h in enumerate(hyp):
            v = iou(r, h)
            if v >= thr:
                cands.append((-v, i, j))
    cands.sort()
    ur: set = set()
    uh: set = set()
    out: List[Tuple[int, int]] = []
    for _v, i, j in cands:
        if i in ur or j in uh:
            continue
        ur.add(i)
        uh.add(j)
        out.append((i, j))
    return out
