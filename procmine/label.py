"""Stage 8 — process-identity labelling (STEP1_SPEC §3.7).

The label names an inferred **business process**, not the current app, window or route. Two
executions of the same process must receive the same string in every session — that is half of
what the assignment scores (`README.md` *Deliverables* §1), and the half a location-derived
label cannot deliver.

Method, deliberately the lightest thing that can work:

  1. **Structural signature** per segment — the ordered surface-key shape, the route and origin
     sets, the interaction profile (typing / navigation / clipboard / form-input mix), and
     window-title evidence. Structure, never content: no A vocabulary reaches this.
  2. **Agglomerative clustering** of signatures under a `rapidfuzz` sequence distance over the
     surface-key shape, combined with set overlap and profile distance.
  3. `k` is chosen by **stability on the dataset being processed**. A's `k` never transfers to
     B (ADR-010); it is re-derived from whatever data is in front of the module.

**No ground truth, ever.** `process_code`, `case_id`, `variant`, `family_name`, `split_id`,
`phase`, `task_id` and `expected_boundaries` are evaluation-only. This module imports no GT
module and reads no GT artifact; an AST test in `tests/` enforces it.
"""
from __future__ import annotations
import collections, hashlib, math, re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

TRANSACTIONAL = ("keystroke", "mouse_click", "browser_click", "mouse_scroll")
NAVIGATIONAL = ("app_switch", "browser_navigation", "window_title_change", "browser_tab_event")
CLIPBOARD = ("clipboard_change",)
FORM = ("browser_form_input", "shortcut")

DEFAULT_CFG = {
    # Grouping method. "graph" is the shipped default from S-E6 (ADR-021): the three-view
    # representation of `identity.py`, a weighted similarity, a kNN graph and Louvain, with
    # the weighting and graph `k` selected unsupervised by stability x cross-session reuse.
    # "structural" is the Phase E single-pass medoid labeller, kept as the control arm the
    # decision was measured against and as the fallback when the optional numeric stack is
    # absent. Measured on dataset_a over the frozen S-E4 segmentation, at identical boundary
    # F1 (0.6904 at tau=2 s) and identical match_rate (0.760):
    #
    #     arm          ARI     NMI     hom     cmp     labels   interruption_recall
    #     structural   0.4307  0.5625  0.6215  0.5137  51       0.1224
    #     graph        0.5831  0.6880  0.6788  0.6975  15       0.3367
    #
    # The interruption figure must be read with the label count: 15 labels raise it partly by
    # being coarser. Homogeneity and completeness are reported because ARI alone cannot tell
    # over-merging from over-splitting, and here both rise.
    "method": "graph",
    # The view weighting is fixed rather than swept: S-E6b measured the unsupervised sweep
    # selecting `how_heavy` on Dataset B's 183 executions — the view the supervised probe scored
    # at 0.256 accuracy — producing 6 clusters whose members mostly do not share the cluster's
    # own modal surface. Constrained to `where_heavy`, B yields 8 clusters at a modal-surface
    # share of 0.77 against 0.32-0.52. Declared as an A->B transfer under the ADR-019 conditions:
    # structural and domain-neutral, no A surface, route, process name or cluster count crosses.
    # Set to None to sweep every weighting (the S-E6 behaviour).
    "weightings": ("where_heavy",),
    # Distance below which two signatures are the same process, "structural" method only.
    # Structural: a similarity on shapes, not a value fitted to A's content.
    "merge_distance": 0.42,
    "min_cluster": 2,            # a singleton is still labelled, just not merged
    "k_stability_trials": 5,     # perturbation trials when selecting k
    "seed": 7,
}


def _profile(rows: Sequence[Dict]) -> Dict[str, float]:
    """Interaction mix as proportions. Shape, not volume, so long and short executions of the
    same process look alike."""
    n = max(1, len(rows))
    c = collections.Counter(r.get("event_type") for r in rows)
    return {
        "transactional": sum(c.get(t, 0) for t in TRANSACTIONAL) / n,
        "navigational": sum(c.get(t, 0) for t in NAVIGATIONAL) / n,
        "clipboard": sum(c.get(t, 0) for t in CLIPBOARD) / n,
        "form": sum(c.get(t, 0) for t in FORM) / n,
    }


def _collapse(seq: Sequence[str]) -> List[str]:
    """Collapse immediate repeats: A A A B A -> A B A. The SHAPE of the visit sequence."""
    out: List[str] = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def signature(segment: Dict, rows: Sequence[Dict], blocks: Sequence[Dict]) -> Dict[str, Any]:
    """Structural signature of one segment. Deterministic; no GT field is read."""
    a, b = segment["start_ms"], segment["end_ms"]
    win = [r for r in rows if a <= (r.get("ts_ms") or 0) <= b]
    blks = [x for x in blocks if x["start_ms"] <= b and x["end_ms"] >= a]
    surfaces = _collapse([x.get("surface", "") for x in blks])
    routes = sorted({x.get("route") or "" for x in blks if x.get("route")})
    origins = sorted({x.get("origin") or "" for x in blks if x.get("origin")})
    apps = sorted({x.get("app") or "" for x in blks if x.get("app")})
    titles = sorted({x.get("title") or "" for x in blks if x.get("title")})
    return {
        "surface_shape": surfaces,
        "surface_set": sorted(set(surfaces)),
        "routes": routes, "origins": origins, "apps": apps, "titles": titles,
        "profile": _profile(win),
        "n_blocks": len(blks), "n_events": len(win),
    }


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / max(1, len(sa | sb))


def _seq_distance(a: Sequence[str], b: Sequence[str]) -> float:
    """Normalised sequence distance over the surface shape, via `rapidfuzz` when available.

    `rapidfuzz` is an approved dependency (ARCHITECTURE §6). The fallback is a plain
    normalised Levenshtein over tokens, so the module never hard-depends on it.
    """
    if not a and not b:
        return 0.0
    try:
        from rapidfuzz.distance import Levenshtein
        d = Levenshtein.distance(list(a), list(b))
    except ImportError:
        prev = list(range(len(b) + 1))
        for i, x in enumerate(a, 1):
            cur = [i]
            for j, y in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
            prev = cur
        d = prev[-1]
    return d / max(1, max(len(a), len(b)))


def distance(s1: Dict, s2: Dict) -> float:
    """Composite structural distance in [0,1]. Ordered shape dominates; sets and interaction
    profile refine it."""
    seq = _seq_distance(s1["surface_shape"], s2["surface_shape"])
    surf = 1.0 - _jaccard(s1["surface_set"], s2["surface_set"])
    route = 1.0 - _jaccard(s1["routes"], s2["routes"])
    prof = sum(abs(s1["profile"][k] - s2["profile"][k]) for k in s1["profile"]) / 2.0
    return round(0.45 * seq + 0.25 * surf + 0.20 * route + 0.10 * prof, 6)


def _cluster(sigs: Sequence[Dict], merge_distance: float) -> List[int]:
    """Single-pass agglomerative assignment against cluster medoids. Deterministic: segments
    are visited in a fixed order and the first cluster within `merge_distance` wins."""
    assign: List[int] = []
    medoids: List[Dict] = []
    for s in sigs:
        best, bd = -1, 10.0
        for i, m in enumerate(medoids):
            d = distance(s, m)
            if d < bd:
                best, bd = i, d
        if best >= 0 and bd <= merge_distance:
            assign.append(best)
        else:
            medoids.append(s)
            assign.append(len(medoids) - 1)
    return assign


def _name(sig: Dict, idx: int) -> str:
    """A stable, readable name derived from structure. The text is not scored; consistency is."""
    basis = (sig["routes"][:2] or sig["titles"][:1] or sig["apps"][:1] or ["process"])
    slug = "-".join(re.sub(r"[^\w]+", "-", str(b)).strip("-").lower() for b in basis)[:40]
    slug = slug.strip("-") or "process"
    return f"{slug}__p{idx:02d}"


def choose_k(sigs: Sequence[Dict], sessions: Optional[Sequence[str]] = None,
             cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Select the merge threshold on the dataset in front of us. A's `k` never transfers to B
    (ADR-010), so `k` is never a parameter — the threshold is swept and selected per dataset.

    The criterion is **stability x cross-session reuse**, and it needs both halves:

      * Stability alone is degenerate at this granularity. Fine clusters survive subsampling
        trivially — measured on dataset_a, stability alone selects merge_distance 0.22 and
        k=849, which is 2 segments per label with only 27% of labels reused across sessions.
        That is the opposite of a process identity.
      * Cross-session reuse alone is degenerate in the other direction: it is maximised by
        collapsing everything into one cluster (k=10 at 100% reuse on dataset_a).

    Their product has an interior optimum. A label is a process identity only if it both
    survives resampling AND recurs in more than one session — the second being half of what
    the assignment scores. `session_id` is a directory name, not ground truth; nothing here
    reads a GT field.
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    import random
    rng = random.Random(c["seed"])
    best = None
    for thr in [round(x * 0.02 + 0.20, 2) for x in range(26)]:
        base = _cluster(sigs, thr)
        k = len(set(base))
        if k < 2 or k > max(2, len(sigs) // 2):
            continue
        agrees = []
        for _ in range(int(c["k_stability_trials"])):
            idx = sorted(rng.sample(range(len(sigs)), max(2, int(len(sigs) * 0.8))))
            sub = _cluster([sigs[i] for i in idx], thr)
            # Pairwise JACCARD over CO-CLUSTERED pairs, not plain agreement.
            #
            # Plain agreement is degenerate: with k -> n almost every pair is "different in
            # both", so the metric is trivially maximised by the finest possible clustering.
            # Measured on dataset_a it selected merge_distance 0.22 and k=849 at "stability"
            # 0.9999 — 2 segments per label and only 27% of labels reused across sessions,
            # which is the opposite of a process identity. Jaccard takes no credit for pairs
            # that are apart in both clusterings, so it cannot be gamed that way.
            both = either = 0
            for x in range(len(idx)):
                for y in range(x + 1, len(idx)):
                    p = sub[x] == sub[y]
                    q = base[idx[x]] == base[idx[y]]
                    if p or q:
                        either += 1
                        if p and q:
                            both += 1
            agrees.append(both / either if either else 0.0)
        stab = sum(agrees) / len(agrees)
        if sessions is not None and len(sessions) == len(sigs):
            groups: Dict[int, set] = collections.defaultdict(set)
            for lab, sid in zip(base, sessions):
                groups[lab].add(sid)
            reuse = sum(1 for v in groups.values() if len(v) > 1) / max(1, k)
        else:
            reuse = 1.0
        objective = stab * reuse
        if best is None or objective > best["objective"]:
            best = {"merge_distance": thr, "k": k, "stability": round(stab, 4),
                    "cross_session_rate": round(reuse, 4), "objective": round(objective, 4)}
    return best or {"merge_distance": c["merge_distance"], "k": 1, "stability": None,
                    "cross_session_rate": None, "objective": None}


def _graph_assign(segs: Sequence[Dict], rows_by_session: Dict[str, Sequence[Dict]],
                  blocks_by_session: Dict[str, Sequence[Dict]],
                  cfg: Dict) -> Optional[List[int]]:
    """The S-E6 grouping (ADR-021): three-view representation -> similarity -> kNN graph ->
    Louvain, with the configuration selected unsupervised on THIS dataset.

    Returns `None` — and the caller falls back to the structural labeller — if the optional
    numeric stack is unavailable. Nothing here reads a ground-truth field, and `k` is never a
    parameter: Louvain selects the community count itself, which is what makes the same code
    run on Dataset B without A's `k` transferring (ADR-010).
    """
    try:
        from . import identity as ID
    except ImportError:
        return None
    try:
        reps = [ID.represent(s, rows_by_session.get(s.get("session_id"), []),
                             blocks_by_session.get(s.get("session_id"), [])) for s in segs]
        sel = ID.select_config(reps, [s.get("session_id") for s in segs],
                               seed=int(cfg.get("seed", 7)),
                               weightings=cfg.get("weightings"))
        S = ID.combine(sel.pop("_views"), ID.WEIGHT_GRID[sel["weights"]],
                       mode=sel.get("mode", "linear"))
        return ID.louvain(ID.knn_graph(S, k=sel["k_nn"]), seed=int(cfg.get("seed", 7)))
    except ImportError:
        return None


def label_segments(segments: Sequence[Dict], rows_by_session: Dict[str, Sequence[Dict]],
                   blocks_by_session: Dict[str, Sequence[Dict]],
                   cfg: Optional[Dict] = None) -> List[Dict]:
    """Assign a stable process label to every segment, ACROSS sessions.

    Clustering is global over the whole dataset, not per session — that is what makes the same
    process receive the same string in every session.
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    segs = sorted(segments, key=lambda s: (s.get("session_id") or "", s["start_ms"]))
    if not segs:
        return []
    sigs = [signature(s, rows_by_session.get(s.get("session_id"), []),
                      blocks_by_session.get(s.get("session_id"), [])) for s in segs]
    assign = None
    if c.get("method") == "graph" and len(segs) > 3:
        assign = _graph_assign(segs, rows_by_session, blocks_by_session, c)
    if assign is None:
        sel = (choose_k(sigs, [s.get("session_id") for s in segs], c) if len(sigs) > 3
               else {"merge_distance": c["merge_distance"]})
        assign = _cluster(sigs, sel["merge_distance"])

    # name each cluster from its FIRST member, so names are stable under re-runs
    first: Dict[int, int] = {}
    for i, a in enumerate(assign):
        first.setdefault(a, i)
    names = {a: _name(sigs[i], a) for a, i in sorted(first.items())}

    out: List[Dict] = []
    for s, sig, a in zip(segs, sigs, assign):
        d = dict(s)
        d["label"] = names[a]
        d["cluster"] = a
        d["signature"] = {"surface_shape": sig["surface_shape"][:6], "routes": sig["routes"][:4],
                          "profile": {k: round(v, 3) for k, v in sig["profile"].items()}}
        out.append(d)
    return out


def label_report(labelled: Sequence[Dict]) -> Dict[str, Any]:
    """Stability evidence: a label used in one session only is not a process identity."""
    by_label = collections.defaultdict(set)
    counts = collections.Counter()
    for s in labelled:
        by_label[s["label"]].add(s.get("session_id"))
        counts[s["label"]] += 1
    n_sessions = len({s.get("session_id") for s in labelled})
    multi = sum(1 for v in by_label.values() if len(v) > 1)
    return {
        "n_segments": len(labelled), "n_labels": len(by_label), "n_sessions": n_sessions,
        "labels_in_more_than_one_session": multi,
        "cross_session_label_rate": round(multi / len(by_label), 4) if by_label else None,
        "segments_under_a_cross_session_label": sum(
            counts[l] for l, v in by_label.items() if len(v) > 1),
        "most_common": counts.most_common(10),
        "mean_sessions_per_label": round(
            sum(len(v) for v in by_label.values()) / len(by_label), 2) if by_label else None,
    }
