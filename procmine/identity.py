"""Stage 8a — execution **representation, similarity and grouping** for process identity.

STEP1_SPEC §3.7 asks for a label that names an inferred business process rather than the
current app or window. S-E4 measured the structural labeller at ARI 0.431 / NMI 0.5625 at
match_rate 0.760 against 15 reference process codes, and diagnosed the weakness as a
*representation* one: nothing in the signature captured "same business purpose, different
route". This module treats identity as

    REPRESENTATION -> SIMILARITY -> GROUPING -> IDENTITY

and nothing else. It does not move a boundary, does not see a score, and does not touch the
decoder; the segmentation it is handed is frozen.

**Three named views**, because the hypothesis under test is that the old signature overweights
WHERE:

  WHERE  the surface/app/route/origin footprint and the shape of the visit sequence
  HOW    the interaction profile — typing / navigating / pointing / clipboard / form mix,
         transition rate and relative timing, normalised per event so a long execution does
         not dominate a short one of the same process
  WHAT   evidence about the business object — window titles, element labels, element ids and
         field keys, as **character 2-3-gram TF-IDF**. Character n-grams are used rather than
         words because Dataset A's titles are Japanese (財務会計システム) and Dataset B's are
         romanised; a word tokeniser would work on one and not the other, and neither is
         available without a new dependency.

  `context.extracted_text` is named in the spec but is **not exposed** by the frozen flat
  record `normalise.flatten_event` produces, and `normalise.py` is not modifiable here. It is
  therefore absent from the WHAT view, and this is recorded rather than worked around.

**No ground truth, ever.** `process_code`, `case_id`, `variant`, `family_name`, `split_id`,
`phase`, `task_id` and `expected_boundaries` are evaluation-only. This module imports no GT
module and reads no GT artifact; an AST test in `tests/` enforces it. `session_id` is a
directory name and is used only for reuse statistics, never as a grouping target.
"""
from __future__ import annotations
import collections, math
from typing import Any, Dict, List, Optional, Sequence, Tuple

TRANSACTIONAL = ("keystroke", "mouse_click", "browser_click", "mouse_scroll")
NAVIGATIONAL = ("app_switch", "browser_navigation", "window_title_change", "browser_tab_event")
CLIPBOARD = ("clipboard_change",)
FORM = ("browser_form_input", "shortcut")
POINTING = ("mouse_click", "browser_click", "mouse_scroll", "mouse_double_click",
            "mouse_drag_drop")
TYPING = ("keystroke", "text_input_complete", "browser_form_input")

# HOW is a fixed-length vector; the order is the contract.
HOW_KEYS = (
    "p_typing", "p_pointing", "p_navigating", "p_clipboard", "p_form", "p_shortcut",
    "p_dialog", "p_scroll", "p_drag", "p_title_change",
    "rate_events_per_min", "rate_app_switch_per_min", "rate_nav_per_min",
    "blocks_per_min", "surface_switch_rate", "revisit_ratio",
    "log_gap_p50", "log_gap_p90", "burstiness", "log_duration",
)

DEFAULT_WEIGHTS = {"where": 0.30, "how": 0.20, "what": 0.30, "seq": 0.20}

WEIGHT_GRID = {
    "uniform":    {"where": 0.25, "how": 0.25, "what": 0.25, "seq": 0.25},
    "where_heavy": {"where": 0.50, "how": 0.10, "what": 0.20, "seq": 0.20},
    "what_heavy": {"where": 0.15, "how": 0.15, "what": 0.55, "seq": 0.15},
    "how_heavy":  {"where": 0.15, "how": 0.55, "what": 0.15, "seq": 0.15},
    "balanced":   dict(DEFAULT_WEIGHTS),
}


# ------------------------------------------------------------------ representation

def _collapse(seq: Sequence[str]) -> List[str]:
    out: List[str] = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def _quantile(v: Sequence[float], q: float) -> float:
    if not v:
        return 0.0
    s = sorted(v)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return float(s[i])


def _text_bag(rows: Sequence[Dict], blks: Sequence[Dict]) -> str:
    """WHAT evidence, as one string. Titles carry the business object; element labels, element
    ids and field keys carry the form being filled. Absent fields contribute nothing — absence
    is normal (ADR-018: `extracted_text` covers ~4% of events) and is never a feature value."""
    parts: List[str] = []
    for b in blks:
        t = b.get("title") or ""
        if t:
            parts.append(t)
        for k in ("element_labels", "element_ids", "field_keys"):
            v = b.get(k) or []
            if isinstance(v, (list, tuple)):
                parts.extend(str(x) for x in v if x)
    for r in rows:
        for k in ("element_label", "element_id", "field_key"):
            x = r.get(k)
            if x:
                parts.append(str(x))
    # de-duplicate while preserving order: a title repeated 300 times is one piece of evidence
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return " ".join(out)


def represent(segment: Dict, rows: Sequence[Dict], blocks: Sequence[Dict]) -> Dict[str, Any]:
    """The three-view representation of one execution. Deterministic; reads no GT field."""
    a, b = segment["start_ms"], segment["end_ms"]
    win = [r for r in rows if a <= (r.get("ts_ms") or 0) <= b]
    blks = [x for x in blocks if x["start_ms"] <= b and x["end_ms"] >= a]
    dur_min = max(1e-3, (b - a) / 60000.0)
    n = max(1, len(win))

    surfaces = _collapse([x.get("surface", "") for x in blks])
    et = collections.Counter(r.get("event_type") for r in win)
    gaps = [float(r.get("ms_since_last") or 0) for r in win if r.get("ms_since_last")]
    g50, g90 = _quantile(gaps, 0.5), _quantile(gaps, 0.9)
    mean_gap = (sum(gaps) / len(gaps)) if gaps else 0.0
    var = (sum((x - mean_gap) ** 2 for x in gaps) / len(gaps)) if gaps else 0.0
    burst = (math.sqrt(var) / mean_gap) if mean_gap > 0 else 0.0

    where = {
        "surface_shape": surfaces,
        "surface_set": sorted(set(surfaces)),
        "bigrams": sorted({f"{x}>{y}" for x, y in zip(surfaces, surfaces[1:])}),
        "routes": sorted({x.get("route") or "" for x in blks if x.get("route")}),
        "origins": sorted({x.get("origin") or "" for x in blks if x.get("origin")}),
        "apps": sorted({x.get("app") or "" for x in blks if x.get("app")}),
    }
    how = {
        "p_typing": sum(et.get(t, 0) for t in TYPING) / n,
        "p_pointing": sum(et.get(t, 0) for t in POINTING) / n,
        "p_navigating": sum(et.get(t, 0) for t in NAVIGATIONAL) / n,
        "p_clipboard": sum(et.get(t, 0) for t in CLIPBOARD) / n,
        "p_form": et.get("browser_form_input", 0) / n,
        "p_shortcut": et.get("shortcut", 0) / n,
        "p_dialog": (et.get("dialog_opened", 0) + et.get("dialog_closed", 0)) / n,
        "p_scroll": et.get("mouse_scroll", 0) / n,
        "p_drag": et.get("mouse_drag_drop", 0) / n,
        "p_title_change": et.get("window_title_change", 0) / n,
        "rate_events_per_min": len(win) / dur_min,
        "rate_app_switch_per_min": et.get("app_switch", 0) / dur_min,
        "rate_nav_per_min": et.get("browser_navigation", 0) / dur_min,
        "blocks_per_min": len(blks) / dur_min,
        "surface_switch_rate": (len(surfaces) - 1) / max(1, len(blks)),
        "revisit_ratio": 1.0 - len(set(surfaces)) / max(1, len(surfaces)),
        "log_gap_p50": math.log1p(g50),
        "log_gap_p90": math.log1p(g90),
        "burstiness": burst,
        "log_duration": math.log1p((b - a) / 1000.0),
    }
    return {"where": where, "how": how, "what": _text_bag(win, blks),
            "n_blocks": len(blks), "n_events": len(win),
            "session_id": segment.get("session_id"), "start_ms": a, "end_ms": b}


def audit(reps: Sequence[Dict]) -> Dict[str, Any]:
    """Per-view dimensionality, sparsity and coverage. Coverage = the fraction of executions
    with *any* signal in the view; a view that is empty for half the data cannot carry
    identity however good its similarity is."""
    n = max(1, len(reps))
    surf_v = {s for r in reps for s in r["where"]["surface_set"]}
    route_v = {s for r in reps for s in r["where"]["routes"]}
    big_v = {s for r in reps for s in r["where"]["bigrams"]}
    nz = [sum(1 for k in HOW_KEYS if abs(r["how"][k]) > 1e-9) for r in reps]
    return {
        "n_executions": len(reps),
        "where": {"dim_surfaces": len(surf_v), "dim_routes": len(route_v),
                  "dim_bigrams": len(big_v),
                  "mean_surfaces_per_exec": round(sum(len(r["where"]["surface_set"])
                                                      for r in reps) / n, 2),
                  "sparsity": round(1 - sum(len(r["where"]["surface_set"]) for r in reps)
                                    / (n * max(1, len(surf_v))), 4),
                  "coverage": round(sum(1 for r in reps if r["where"]["surface_set"]) / n, 4)},
        "how": {"dim": len(HOW_KEYS),
                "mean_nonzero": round(sum(nz) / n, 2),
                "sparsity": round(1 - sum(nz) / (n * len(HOW_KEYS)), 4),
                "coverage": round(sum(1 for r in reps if r["n_events"] > 0) / n, 4)},
        "what": {"mean_chars": round(sum(len(r["what"]) for r in reps) / n, 1),
                 "coverage": round(sum(1 for r in reps if r["what"].strip()) / n, 4),
                 "note": "char 2-3-gram TF-IDF; extracted_text not exposed by the frozen "
                         "normalise record and therefore absent"},
    }


# ------------------------------------------------------------------ similarity

def _binary_jaccard(sets: Sequence[Sequence[str]]):
    """Dense pairwise Jaccard over set-valued features. Both-empty is defined as 1.0."""
    import numpy as np
    vocab = {v: i for i, v in enumerate(sorted({x for s in sets for x in s}))}
    X = np.zeros((len(sets), max(1, len(vocab))), dtype=np.float32)
    for i, s in enumerate(sets):
        for x in s:
            X[i, vocab[x]] = 1.0
    inter = X @ X.T
    size = X.sum(1)
    union = size[:, None] + size[None, :] - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        J = np.where(union > 0, inter / np.maximum(union, 1e-9), 1.0)
    return J.astype(np.float32)


def _seq_similarity(shapes: Sequence[Sequence[str]]):
    """Normalised Levenshtein similarity over the surface-visit shape.

    Each distinct surface is mapped to one code point so the sequence becomes a string and
    `rapidfuzz.process.cdist` can do all 2.9M pairs in C. The fallback is an O(n^2 * L^2)
    Python implementation, correct but slow; it exists so the module never hard-depends on
    an optional import.
    """
    import numpy as np
    vocab = {v: i for i, v in enumerate(sorted({x for s in shapes for x in s}))}
    strs = ["".join(chr(0x4E00 + vocab[x]) for x in s) for s in shapes]
    try:
        from rapidfuzz import process as rf_process
        from rapidfuzz.distance import Levenshtein
        return rf_process.cdist(strs, strs, scorer=Levenshtein.normalized_similarity,
                                workers=-1, dtype=np.float32)
    except ImportError:
        n = len(strs)
        S = np.ones((n, n), dtype=np.float32)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = strs[i], strs[j]
                prev = list(range(len(b) + 1))
                for x_i, x in enumerate(a, 1):
                    cur = [x_i]
                    for y_i, y in enumerate(b, 1):
                        cur.append(min(prev[y_i] + 1, cur[y_i - 1] + 1,
                                       prev[y_i - 1] + (x != y)))
                    prev = cur
                d = prev[-1] / max(1, max(len(a), len(b)))
                S[i, j] = S[j, i] = 1.0 - d
        return S


def _cosine(M):
    import numpy as np
    norm = np.linalg.norm(M, axis=1, keepdims=True)
    Z = M / np.maximum(norm, 1e-9)
    return np.clip(Z @ Z.T, 0.0, 1.0).astype(np.float32)


def how_matrix(reps: Sequence[Dict]):
    """Z-scored HOW vectors. Standardising is what makes a rate comparable to a proportion;
    without it `rate_events_per_min` alone decides every cosine."""
    import numpy as np
    M = np.array([[r["how"][k] for k in HOW_KEYS] for r in reps], dtype=np.float32)
    mu, sd = M.mean(0), M.std(0)
    return (M - mu) / np.maximum(sd, 1e-6)


def what_matrix(reps: Sequence[Dict]):
    """Character 2-3-gram TF-IDF over the WHAT bag, L2-normalised by the vectoriser."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=2,
                          sublinear_tf=True, lowercase=True)
    texts = [r["what"] if r["what"].strip() else " " for r in reps]
    return vec.fit_transform(texts), vec


def similarity_views(reps: Sequence[Dict]) -> Dict[str, Any]:
    """The four per-view similarity matrices. Computed ONCE; every graph below is a slice."""
    import numpy as np
    w = reps[0]["where"]  # noqa: F841 — shape documentation only
    s_surface = _binary_jaccard([r["where"]["surface_set"] for r in reps])
    s_route = _binary_jaccard([r["where"]["routes"] for r in reps])
    s_origin = _binary_jaccard([r["where"]["origins"] for r in reps])
    s_bigram = _binary_jaccard([r["where"]["bigrams"] for r in reps])
    sim_where = (0.40 * s_surface + 0.25 * s_route + 0.15 * s_origin + 0.20 * s_bigram)
    sim_how = _cosine(how_matrix(reps))
    Xw, _ = what_matrix(reps)
    sim_what = np.clip(np.asarray((Xw @ Xw.T).todense(), dtype=np.float32), 0.0, 1.0)
    sim_seq = _seq_similarity([r["where"]["surface_shape"] for r in reps])
    return {"where": sim_where, "how": sim_how, "what": sim_what, "seq": sim_seq}


def combine(views: Dict[str, Any], weights: Optional[Dict[str, float]] = None):
    """S = w_where*sim_where + w_how*sim_how + w_what*sim_what + w_seq*sim_sequence.

    Weights are experimental configuration, not fitted parameters: they are chosen from a
    small declared grid on unsupervised criteria. No reference process code enters here.
    """
    import numpy as np
    w = dict(DEFAULT_WEIGHTS)
    w.update(weights or {})
    tot = sum(w.values()) or 1.0
    S = sum((w[k] / tot) * views[k] for k in ("where", "how", "what", "seq"))
    S = np.clip(S, 0.0, 1.0).astype(np.float32)
    np.fill_diagonal(S, 1.0)
    return S


# ------------------------------------------------------------------ grouping

def knn_graph(S, k: int = 10, mutual: bool = False):
    """kNN (or mutual-kNN) graph over the dense similarity matrix.

    Self-selecting community count is the property that matters for transfer: a `k`-selection
    rule has to run unsupervised on Dataset B, and Phase E already measured stability-only
    selection to be degenerate here.
    """
    import numpy as np
    import networkx as nx
    n = S.shape[0]
    A = np.zeros_like(S)
    order = np.argsort(-S, axis=1)
    for i in range(n):
        for j in order[i, 1:k + 1]:
            A[i, j] = S[i, j]
    if mutual:
        A = np.where((A > 0) & (A.T > 0), np.maximum(A, A.T), 0.0)
    else:
        A = np.maximum(A, A.T)
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i, j in zip(*np.nonzero(np.triu(A, 1))):
        G.add_edge(int(i), int(j), weight=float(A[i, j]))
    return G


def threshold_graph(S, thr: float):
    """Thresholded-similarity graph: an edge wherever S exceeds `thr`."""
    import numpy as np
    import networkx as nx
    n = S.shape[0]
    G = nx.Graph()
    G.add_nodes_from(range(n))
    A = np.triu(S, 1)
    for i, j in zip(*np.nonzero(A > thr)):
        G.add_edge(int(i), int(j), weight=float(S[i, j]))
    return G


def graph_stats(G) -> Dict[str, Any]:
    import networkx as nx
    deg = [d for _, d in G.degree()]
    n = G.number_of_nodes()
    return {
        "nodes": n, "edges": G.number_of_edges(),
        "density": round(nx.density(G), 5),
        "degree_min": min(deg) if deg else 0, "degree_p50": sorted(deg)[len(deg) // 2] if deg else 0,
        "degree_mean": round(sum(deg) / max(1, n), 2), "degree_max": max(deg) if deg else 0,
        "isolates": sum(1 for d in deg if d == 0),
        "components": nx.number_connected_components(G),
    }


def louvain(G, seed: int = 7, resolution: float = 1.0) -> List[int]:
    """`networkx.algorithms.community.louvain_communities` — already approved (ADR-007 rejects
    graph *databases*, not graph algorithms), accepts a seed, deterministic under it.

    Louvain chooses its own community count by modularity. That is not a convenience: it is
    the property that lets the same code select `k` on Dataset B without A's `k` transferring
    (ADR-010)."""
    import networkx as nx
    comms = nx.algorithms.community.louvain_communities(
        G, weight="weight", seed=seed, resolution=resolution)
    comms = sorted((sorted(c) for c in comms), key=lambda c: (-len(c), c[0]))
    lab = [0] * G.number_of_nodes()
    for ci, c in enumerate(comms):
        for v in c:
            lab[v] = ci
    return lab


def components(G) -> List[int]:
    import networkx as nx
    comms = sorted((sorted(c) for c in nx.connected_components(G)),
                   key=lambda c: (-len(c), c[0]))
    lab = [0] * G.number_of_nodes()
    for ci, c in enumerate(comms):
        for v in c:
            lab[v] = ci
    return lab


def group(reps: Sequence[Dict], weights: Optional[Dict[str, float]] = None,
          k: int = 10, seed: int = 7) -> Dict[str, Any]:
    """The shipped path: represent -> similarity -> kNN graph -> Louvain.

    Returns the assignment plus the evidence needed to justify it on a dataset with no ground
    truth: graph statistics, modularity, cluster-size distribution and cross-session reuse.
    """
    import networkx as nx
    if len(reps) < 3:
        return {"labels": list(range(len(reps))), "n_clusters": len(reps), "graph": {},
                "modularity": None}
    views = similarity_views(reps)
    S = combine(views, weights)
    G = knn_graph(S, k=k)
    lab = louvain(G, seed=seed)
    comms: Dict[int, List[int]] = collections.defaultdict(list)
    for i, c in enumerate(lab):
        comms[c].append(i)
    sizes = sorted((len(v) for v in comms.values()), reverse=True)
    sess: Dict[int, set] = collections.defaultdict(set)
    for i, c in enumerate(lab):
        sess[c].add(reps[i].get("session_id"))
    return {
        "labels": lab, "n_clusters": len(comms), "graph": graph_stats(G),
        "modularity": round(float(nx.algorithms.community.modularity(
            G, [set(v) for v in comms.values()], weight="weight")), 4),
        "cluster_sizes": sizes[:20], "singletons": sum(1 for s in sizes if s == 1),
        "cross_session_rate": round(sum(1 for v in sess.values() if len(v) > 1)
                                    / max(1, len(sess)), 4),
        "mean_sessions_per_cluster": round(sum(len(v) for v in sess.values())
                                           / max(1, len(sess)), 2),
        "_S": S,
    }


# ------------------------------------------------------------------ vector spaces
#
# The similarity above is a weighted sum of four similarities and is NOT a proper metric —
# it does not satisfy the triangle inequality, so a centroid method like k-means cannot be
# run on it. k-means is therefore run on an explicit vector space instead, and that is stated
# wherever its result is reported.

def where_matrix(reps: Sequence[Dict]):
    """Binary indicator matrix over surfaces, routes, origins, apps and surface bigrams."""
    from sklearn.feature_extraction import DictVectorizer
    ds = []
    for r in reps:
        w = r["where"]
        d = {}
        for pre, key in (("s", "surface_set"), ("r", "routes"), ("o", "origins"),
                         ("a", "apps"), ("b", "bigrams")):
            for x in w[key]:
                d[f"{pre}:{x}"] = 1.0
        ds.append(d)
    vec = DictVectorizer(sparse=True)
    return vec.fit_transform(ds), vec


def vector_space(reps: Sequence[Dict], views: Sequence[str] = ("where", "how", "what")):
    """A single sparse matrix for the named views, each L2-normalised so no view dominates by
    scale alone. Used by k-means and by the supervised probe of G-A3b."""
    import numpy as np
    from scipy import sparse
    from sklearn.preprocessing import normalize
    parts = []
    if "where" in views:
        Xw, _ = where_matrix(reps)
        parts.append(normalize(Xw))
    if "how" in views:
        parts.append(sparse.csr_matrix(normalize(np.asarray(how_matrix(reps)))))
    if "what" in views:
        Xt, _ = what_matrix(reps)
        parts.append(normalize(Xt))
    return sparse.hstack(parts).tocsr()


# ------------------------------------------------------------------ configuration selection
#
# The rule that has to run unsupervised on Dataset B. Two were measured in S-E6:
#
#   rule 1  modularity x cross-session reuse    -> how_heavy, k_nn=5   -> ARI 0.204
#   rule 2  stability  x cross-session reuse    -> where_heavy, k_nn=20 -> ARI 0.583
#
# Rule 1 fails for a structural reason, not a tuning accident: **modularity is not comparable
# across graphs of different density.** Sparser graphs score higher almost mechanically, so
# rule 1 was really selecting "the sparsest graph", and it scored `how_heavy` and
# `where_heavy` identically at 0.8669 — it could not see the difference between the view that
# carries the identity signal and the view that carries almost none.
#
# Rule 2 is the Phase E rule (`label.choose_k`) applied to a self-selecting-k method, and it
# needs both halves for the reasons recorded there: stability alone prefers the finest
# partition, reuse alone prefers one cluster. `session_id` is a directory name; no GT field
# is read.

K_NN_GRID = (5, 10, 20)


def _cocluster_jaccard(a, b) -> float:
    """Jaccard over CO-CLUSTERED pairs. Plain pairwise agreement is degenerate as k grows
    (Phase E measured it selecting k=849); Jaccard takes no credit for pairs apart in both
    partitions, so it cannot be gamed that way."""
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    iu = np.triu_indices(len(a), 1)
    p = (a[:, None] == a[None, :])[iu]
    q = (b[:, None] == b[None, :])[iu]
    u = int((p | q).sum())
    return float((p & q).sum() / u) if u else 0.0


def select_config(reps: Sequence[Dict], sessions: Optional[Sequence[str]] = None,
                  trials: int = 3, frac: float = 0.8, seed: int = 7) -> Dict[str, Any]:
    """Choose the similarity weighting and graph `k` on the dataset in front of us.

    Unsupervised: stability under node resampling x cross-session reuse. A's choice never
    transfers to B (ADR-010) — this runs again, from scratch, on whatever data it is given,
    and Louvain then selects the community count itself.
    """
    import numpy as np
    views = similarity_views(reps)
    rng = np.random.default_rng(seed)
    n = len(reps)
    rows: List[Dict[str, Any]] = []
    for wname, w in WEIGHT_GRID.items():
        S = combine(views, w)
        for k_nn in K_NN_GRID:
            base = np.array(louvain(knn_graph(S, k=k_nn), seed=seed))
            stab = []
            for _ in range(trials):
                idx = np.sort(rng.choice(n, size=max(3, int(frac * n)), replace=False))
                sub = np.array(louvain(knn_graph(S[np.ix_(idx, idx)], k=k_nn), seed=seed))
                stab.append(_cocluster_jaccard(sub, base[idx]))
            stability = float(np.mean(stab)) if stab else 0.0
            if sessions is not None and len(sessions) == n:
                g: Dict[int, set] = collections.defaultdict(set)
                for c, sd in zip(base, sessions):
                    g[c].add(sd)
                reuse = sum(1 for v in g.values() if len(v) > 1) / max(1, len(g))
            else:
                reuse = 1.0
            rows.append({"weights": wname, "k_nn": k_nn, "n_clusters": len(set(base.tolist())),
                         "stability": round(stability, 4),
                         "cross_session_reuse": round(reuse, 4),
                         "objective": round(stability * reuse, 4)})
    rows.sort(key=lambda r: (-r["objective"], r["weights"], r["k_nn"]))
    best = dict(rows[0])
    best["grid"] = rows
    best["_views"] = views
    return best
