#!/usr/bin/env python3
"""S-E6 — where is the identity ceiling, and which grouping method is justified?

Bounded experiment. Segmentation is FROZEN (G-A0): every arm receives the exact 1,717
hypothesis segments S-E4 produced, and boundary F1 is asserted identical on every row. No arm
may add, delete, move or merge a boundary.

Reuses `evaluate.evaluate_all` (and through it `identity_scores` / `matched_identity` /
`interruption_recall`) for every reported metric. No metric is reimplemented here. The only
alignment computed locally is hypothesis->reference pairing for the *supervised probe's*
training target, which is a diagnostic input, not a score.

Run:  .venv/bin/python experiments/SE6-identity-grouping/run.py
"""
from __future__ import annotations
import collections, json, os, pickle, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                    # noqa: E402
from procmine import identity as ID, label as LB, evaluate as EV      # noqa: E402

FROZEN = os.path.join(ROOT, "build", "dataset_a", "se6_frozen.pkl")
TAUS = [1000, 2000, 5000, 10000]
SEED = 7
IOU = 0.5


def iou(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    if hi <= lo:
        return 0.0
    return (hi - lo) / ((a[1] - a[0]) + (b[1] - b[0]) - (hi - lo))


def align(ref_iv, hyp_iv, thr=IOU):
    """Greedy one-to-one IoU pairing — the same rule `evaluate.matched_identity` uses, applied
    here only to obtain the supervised probe's TARGET. It produces no reported score."""
    cands = sorted(((-iou(r, h), i, j) for i, r in enumerate(ref_iv)
                    for j, h in enumerate(hyp_iv) if iou(r, h) >= thr))
    ur, uh, out = set(), set(), []
    for _v, i, j in cands:
        if i in ur or j in uh:
            continue
        ur.add(i); uh.add(j); out.append((i, j))
    return out


def main() -> int:
    t0 = time.time()
    if not os.path.exists(FROZEN):
        print(f"{FROZEN} missing — run build_frozen.py first.")
        return 1
    D = pickle.load(open(FROZEN, "rb"))
    segs, ref, rows, blocks = D["segments"], D["ref"], D["rows"], D["blocks"]
    sessions = D["sessions"]
    segs = sorted(segs, key=lambda s: (s["session_id"], s["start_ms"]))
    n = len(segs)
    print(f"frozen: {n} segments, bF1@2s={D['frozen_boundary']['2000']['f1']}", flush=True)

    cfg = {"taus_ms": TAUS, "kappas": [1, 2, 5, 10], "ious": [0.3, 0.5, 0.7],
           "timelines": {s: [r["ts_ms"] for r in rows[s]] for s in sessions}}
    out = {"frozen": {"n_segments": n,
                      "boundary_time": D["frozen_boundary"],
                      "count_ratio": D["frozen_count_ratio"]}}

    # ---------------------------------------------------- G-A1 representation
    reps = [ID.represent(s, rows[s["session_id"]], blocks[s["session_id"]]) for s in segs]
    out["audit"] = ID.audit(reps)
    print(f"[G-A1] representation built ({time.time()-t0:.0f}s)", flush=True)

    # three example executions in all three views
    ex = []
    for i in (0, n // 2, n - 1):
        r = reps[i]
        ex.append({"session_id": r["session_id"], "start_ms": r["start_ms"],
                   "n_events": r["n_events"], "n_blocks": r["n_blocks"],
                   "WHERE": {"surface_shape": r["where"]["surface_shape"][:6],
                             "routes": r["where"]["routes"][:5],
                             "origins": r["where"]["origins"][:3],
                             "apps": r["where"]["apps"]},
                   "HOW": {k: round(r["how"][k], 3) for k in ID.HOW_KEYS},
                   "WHAT": r["what"][:220]})
    out["examples"] = ex

    # ---------------------------------------------------- G-A2 similarity
    views = ID.similarity_views(reps)
    print(f"[G-A2] similarity views ({time.time()-t0:.0f}s)", flush=True)
    grid = {}
    for name, w in ID.WEIGHT_GRID.items():
        S = ID.combine(views, w)
        off = S[np.triu_indices(n, 1)]
        grid[name] = {"weights": w, "mean": round(float(off.mean()), 4),
                      "p50": round(float(np.percentile(off, 50)), 4),
                      "p95": round(float(np.percentile(off, 95)), 4),
                      "p99": round(float(np.percentile(off, 99)), 4)}
    out["similarity_grid"] = grid

    # ---------------------------------------------------- reference alignment (eval only)
    by_sess = collections.defaultdict(list)
    for i, s in enumerate(segs):
        by_sess[s["session_id"]].append(i)
    hyp_iv_by = {s: [(segs[i]["start_ms"], segs[i]["end_ms"]) for i in by_sess[s]]
                 for s in sessions}
    target = {}          # global segment index -> reference process_code
    for s in sessions:
        r = ref.get(s, {})
        for i, j in align(r.get("intervals", []), hyp_iv_by[s]):
            target[by_sess[s][j]] = r["labels"][i]
    idx_sup = sorted(target)
    y = np.array([target[i] for i in idx_sup])
    print(f"aligned {len(idx_sup)}/{n} segments to a reference code "
          f"(match_rate over ref = {len(idx_sup)/sum(len(ref[s]['intervals']) for s in ref):.3f})",
          flush=True)

    def score_arm(name, labels, extra=None):
        hb = {}
        for s in sessions:
            ii = by_sess[s]
            hb[s] = {"intervals": hyp_iv_by[s], "labels": [str(labels[i]) for i in ii]}
        m = EV.evaluate_all(ref, hb, dict(cfg, arm=name))["overall"]
        ident = m.get("identity_pooled") or {}
        row = {
            "arm": name, "n_labels": len(set(labels)),
            "boundary_f1_2000": m["boundary_time"]["2000"]["f1"],
            "boundary_f1_all": {t: m["boundary_time"][t]["f1"] for t in m["boundary_time"]},
            "count_ratio": m["count_ratio"],
            "ari": ident.get("ari"), "nmi": ident.get("nmi"),
            "homogeneity": ident.get("homogeneity"), "completeness": ident.get("completeness"),
            "match_rate": ident.get("match_rate"), "n_matched": ident.get("n_matched"),
            "interruption_recall": (m.get("interruption") or {}).get("recall"),
        }
        sess_of = collections.defaultdict(set)
        for i, lab in enumerate(labels):
            sess_of[lab].add(segs[i]["session_id"])
        row["cross_session_reuse"] = round(
            sum(1 for v in sess_of.values() if len(v) > 1) / max(1, len(sess_of)), 4)
        row["mean_sessions_per_label"] = round(
            sum(len(v) for v in sess_of.values()) / max(1, len(sess_of)), 2)
        sizes = collections.Counter(labels)
        row["singleton_labels"] = sum(1 for v in sizes.values() if v == 1)
        row["largest_label_share"] = round(max(sizes.values()) / n, 4)
        row.update(extra or {})
        return row

    arms = []

    # ---------------------------------------------------- control: S-E4 structural labeller
    t = time.time()
    lab_struct = LB.label_segments(segs, rows, blocks)
    key = {(x["session_id"], x["start_ms"]): x["label"] for x in lab_struct}
    ctrl = [key[(s["session_id"], s["start_ms"])] for s in segs]
    arms.append(score_arm("S-E4 structural (control)", ctrl,
                          {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                           "k_selection": "threshold sweep, stability x cross-session reuse"}))
    print(f"[control] {arms[-1]['ari']} ARI, k={arms[-1]['n_labels']} "
          f"({time.time()-t0:.0f}s)", flush=True)

    # ---------------------------------------------------- G-A3a merge-only oracle
    #
    # Bounds RELABELLING only: cluster MEMBERSHIP is held fixed and each existing label is
    # mapped to the reference code its members most often carry. Re-clustering arms are NOT
    # bounded by this and may legitimately exceed it.
    sup_ctrl = [ctrl[i] for i in idx_sup]
    maj = {}
    for lab in set(sup_ctrl):
        c = collections.Counter(y[k] for k, l in enumerate(sup_ctrl) if l == lab)
        maj[lab] = c.most_common(1)[0][0]
    merged = [maj[l] for l in sup_ctrl]
    oracle_a = EV.identity_scores(list(y), merged)
    codes_split = sum(1 for code in set(y)
                      if len({sup_ctrl[k] for k in range(len(y)) if y[k] == code}) > 1)
    impure = sum(1 for lab in set(sup_ctrl)
                 if len({y[k] for k in range(len(y)) if sup_ctrl[k] == lab}) > 1)
    impure_members = sum(1 for k in range(len(y)) if y[k] != maj[sup_ctrl[k]])
    out["ceiling_merge_only"] = {
        "_bounds": "RELABELLING ONLY — membership fixed. Re-clustering arms are not bounded "
                   "by this row and may exceed it.",
        "n_matched": len(y), "n_reference_codes": len(set(y)),
        "n_predicted_labels": len(set(sup_ctrl)),
        "ari": oracle_a["ari"], "nmi": oracle_a["nmi"],
        "homogeneity": oracle_a["homogeneity"], "completeness": oracle_a["completeness"],
        "reference_codes_split_across_labels": codes_split,
        "predicted_labels_impure": impure,
        "impure_membership_share": round(impure_members / max(1, len(y)), 4),
    }
    print(f"[G-A3a] merge-only oracle ARI {oracle_a['ari']}", flush=True)

    # ---------------------------------------------------- G-A3b supervised probe
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score
    sess_sup = np.array([segs[i]["session_id"] for i in idx_sup])
    probe = {}
    for vname, vv in (("WHERE", ("where",)), ("HOW", ("how",)), ("WHAT", ("what",)),
                      ("ALL", ("where", "how", "what"))):
        X = ID.vector_space(reps, vv)[idx_sup]
        pred = np.empty(len(y), dtype=object)
        for s in sessions:
            te = sess_sup == s
            tr = ~te
            if te.sum() == 0 or len(set(y[tr])) < 2:
                pred[te] = collections.Counter(y[tr]).most_common(1)[0][0] if tr.sum() else y[0]
                continue
            clf = LogisticRegression(max_iter=2000, C=1.0, n_jobs=1, random_state=SEED)
            clf.fit(X[tr], y[tr])
            pred[te] = clf.predict(X[te])
        sc = EV.identity_scores(list(y), list(pred))
        probe[vname] = {"accuracy": round(float(accuracy_score(y, pred)), 4),
                        "macro_f1": round(float(f1_score(y, pred, average="macro")), 4),
                        "ari": sc["ari"], "nmi": sc["nmi"],
                        "n_classes": len(set(y)), "n": len(y)}
        print(f"[G-A3b] probe {vname}: acc {probe[vname]['accuracy']} "
              f"macroF1 {probe[vname]['macro_f1']} ARI {probe[vname]['ari']} "
              f"({time.time()-t0:.0f}s)", flush=True)
    out["ceiling_supervised_probe"] = {
        "_status": "DIAGNOSTIC ONLY — supervised, LOSO by session. An upper bound on any "
                   "unsupervised method over this representation. Never runs on Dataset B.",
        "per_view": probe}

    # ---------------------------------------------------- G-A3c segmentation-inherited error
    gt_segs, gt_codes = [], []
    for s in sessions:
        for (a, b), lab in zip(ref.get(s, {}).get("intervals", []),
                               ref.get(s, {}).get("labels", [])):
            gt_segs.append({"session_id": s, "start_ms": a, "end_ms": b})
            gt_codes.append(lab)
    gt_reps = [ID.represent(x, rows[x["session_id"]], blocks[x["session_id"]]) for x in gt_segs]
    g_gt = ID.group(gt_reps, k=10, seed=SEED)
    sc_gt = EV.identity_scores(gt_codes, [str(x) for x in g_gt["labels"]])
    out["segmentation_inherited"] = {
        "_status": "DIAGNOSTIC ONLY — clustering run on GT SEGMENTS, never shipped.",
        "n_gt_segments": len(gt_segs), "n_clusters": g_gt["n_clusters"],
        "ari": sc_gt["ari"], "nmi": sc_gt["nmi"],
        "homogeneity": sc_gt["homogeneity"], "completeness": sc_gt["completeness"],
        "match_rate": 1.0, "_match_rate_note": "1.0 by construction — the segments ARE the "
                                               "reference intervals",
    }
    print(f"[G-A3c] on GT segments: ARI {sc_gt['ari']} k={g_gt['n_clusters']}", flush=True)

    # ---------------------------------------------------- unsupervised configuration choice
    #
    # Selected BEFORE looking at ARI, on: graph density in a usable band, a practical cluster
    # count, cross-session reuse, and modularity. The GT-informed sweep is reported separately
    # and labelled as a development analysis.
    S_by_w = {name: ID.combine(views, w) for name, w in ID.WEIGHT_GRID.items()}
    unsup = []
    for wname, S in S_by_w.items():
        for kk in (5, 10, 20):
            G = ID.knn_graph(S, k=kk)
            lab = ID.louvain(G, seed=SEED)
            st = ID.graph_stats(G)
            sess_of = collections.defaultdict(set)
            for i, l in enumerate(lab):
                sess_of[l].add(segs[i]["session_id"])
            nl = len(set(lab))
            reuse = sum(1 for v in sess_of.values() if len(v) > 1) / max(1, nl)
            sizes = collections.Counter(lab)
            import networkx as nx
            comms = collections.defaultdict(set)
            for i, l in enumerate(lab):
                comms[l].add(i)
            mod = float(nx.algorithms.community.modularity(G, list(comms.values()),
                                                           weight="weight"))
            unsup.append({"weights": wname, "k_nn": kk, "n_clusters": nl,
                          "modularity": round(mod, 4), "cross_session_reuse": round(reuse, 4),
                          "largest_share": round(max(sizes.values()) / n, 4),
                          "singletons": sum(1 for v in sizes.values() if v == 1),
                          "density": st["density"], "components": st["components"],
                          "objective": round(mod * reuse, 4)})
    unsup.sort(key=lambda r: -r["objective"])
    out["unsupervised_selection"] = {
        "_rule": "modularity x cross-session reuse, both unsupervised. Chosen BEFORE any GT "
                 "comparison. Reference process codes never enter the similarity or this rule.",
        "grid": unsup}
    chosen = unsup[0]
    print(f"[select] weights={chosen['weights']} k_nn={chosen['k_nn']} "
          f"-> {chosen['n_clusters']} clusters, modularity {chosen['modularity']}", flush=True)
    S = S_by_w[chosen["weights"]]
    out["chosen_config"] = chosen

    # ---------------------------------------------------- G-A4 classical arms
    from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
    D_mat = (1.0 - S).astype(np.float64)
    np.fill_diagonal(D_mat, 0.0)
    K_GRID = (15, 30, 60, 120)

    # k for the centroid/agglomerative arms is selected by silhouette on the PRECOMPUTED
    # distance — unsupervised, and it must be able to run on B. "15 reference codes" is never
    # a production assumption.
    from sklearn.metrics import silhouette_score
    Xv = ID.vector_space(reps)
    sil = {}
    t = time.time()
    for k in K_GRID:
        km = KMeans(n_clusters=k, random_state=SEED, n_init=10).fit(Xv)
        sil[k] = round(float(silhouette_score(D_mat, km.labels_, metric="precomputed")), 4)
    k_star = max(sil, key=sil.get)
    out["k_selection_silhouette"] = {"grid": sil, "chosen_k": k_star,
                                     "_note": "silhouette on the precomputed (1-S) distance; "
                                              "unsupervised, runs identically on B"}
    km = KMeans(n_clusters=k_star, random_state=SEED, n_init=10).fit(Xv)
    arms.append(score_arm(f"k-means (k={k_star}, vector space)", list(km.labels_),
                          {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                           "k_selection": "silhouette over a fixed grid — NOT self-selecting",
                           "_note": "S is a weighted sum of similarities and is not a proper "
                                    "metric, so k-means runs on the vector space, not on S"}))
    print(f"[G-A4] k-means k={k_star} ARI {arms[-1]['ari']}", flush=True)

    for linkage in ("average", "complete"):
        t = time.time()
        ag = AgglomerativeClustering(n_clusters=k_star, metric="precomputed",
                                     linkage=linkage).fit(D_mat)
        arms.append(score_arm(f"agglomerative {linkage} (k={k_star})", list(ag.labels_),
                              {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                               "k_selection": "silhouette over a fixed grid — NOT self-selecting"}))
        print(f"[G-A4] agglom {linkage} ARI {arms[-1]['ari']}", flush=True)

    # DBSCAN, bounded to two settings. Its uniform-density assumption is a poor fit here:
    # business processes plausibly differ in frequency and in how tightly their executions
    # cluster, so one global eps cannot suit both a 300-execution routine and a 3-execution
    # rarity. Reported, not tuned.
    for eps in (0.30, 0.45):
        t = time.time()
        db = DBSCAN(eps=eps, min_samples=3, metric="precomputed").fit(D_mat)
        lab = [f"n{i}" if l == -1 else int(l) for i, l in enumerate(db.labels_)]
        arms.append(score_arm(f"DBSCAN (eps={eps}, min_samples=3)", lab,
                              {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                               "k_selection": "self-selecting, but density-based",
                               "noise_points": int((db.labels_ == -1).sum())}))
        print(f"[G-A4] DBSCAN eps={eps} ARI {arms[-1]['ari']} "
              f"noise {arms[-1]['noise_points']}", flush=True)

    # ---------------------------------------------------- G-A5 graph arms
    graphs = {}
    t = time.time()
    G_knn = ID.knn_graph(S, k=chosen["k_nn"])
    graphs[f"kNN k={chosen['k_nn']}"] = ID.graph_stats(G_knn)
    lab_louvain = ID.louvain(G_knn, seed=SEED)
    arms.append(score_arm(f"graph kNN(k={chosen['k_nn']}) + Louvain", lab_louvain,
                          {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                           "k_selection": "SELF-SELECTING (modularity)",
                           "modularity": chosen["modularity"]}))
    print(f"[G-A5] kNN+Louvain ARI {arms[-1]['ari']} k={arms[-1]['n_labels']}", flush=True)

    t = time.time()
    G_mut = ID.knn_graph(S, k=chosen["k_nn"], mutual=True)
    graphs[f"mutual-kNN k={chosen['k_nn']}"] = ID.graph_stats(G_mut)
    arms.append(score_arm(f"graph mutual-kNN(k={chosen['k_nn']}) + Louvain",
                          ID.louvain(G_mut, seed=SEED),
                          {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                           "k_selection": "SELF-SELECTING (modularity)"}))
    print(f"[G-A5] mutual-kNN+Louvain ARI {arms[-1]['ari']} k={arms[-1]['n_labels']}", flush=True)

    off = S[np.triu_indices(n, 1)]
    thr = float(np.percentile(off, 99.5))
    t = time.time()
    G_thr = ID.threshold_graph(S, thr)
    graphs[f"threshold S>{thr:.3f} (p99.5)"] = ID.graph_stats(G_thr)
    arms.append(score_arm(f"graph threshold(p99.5) + components", ID.components(G_thr),
                          {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                           "k_selection": "SELF-SELECTING (components)", "threshold": round(thr, 4)}))
    print(f"[G-A5] threshold+components ARI {arms[-1]['ari']} k={arms[-1]['n_labels']}", flush=True)

    t = time.time()
    arms.append(score_arm(f"graph threshold(p99.5) + Louvain", ID.louvain(G_thr, seed=SEED),
                          {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                           "k_selection": "SELF-SELECTING (modularity)"}))
    out["graphs"] = graphs

    try:
        from sklearn.cluster import SpectralClustering
        t = time.time()
        sp = SpectralClustering(n_clusters=k_star, affinity="precomputed",
                                random_state=SEED, assign_labels="kmeans").fit(S.astype(np.float64))
        arms.append(score_arm(f"spectral (k={k_star}, precomputed affinity)", list(sp.labels_),
                              {"runtime_s": round(time.time() - t, 1), "deterministic": True,
                               "k_selection": "silhouette over a fixed grid — NOT self-selecting"}))
        print(f"[G-A5] spectral ARI {arms[-1]['ari']}", flush=True)
    except Exception as e:                                   # noqa: BLE001
        out["spectral_error"] = repr(e)

    out["arms"] = arms

    # ---------------------------------------------------- contract: boundary F1 identical
    bf = {a["arm"]: a["boundary_f1_all"] for a in arms}
    frozen_bf = {t: D["frozen_boundary"][t]["f1"] for t in D["frozen_boundary"]}
    violations = [k for k, v in bf.items() if v != frozen_bf]
    out["contract_boundary_f1"] = {"frozen": frozen_bf, "identical_on_every_arm": not violations,
                                   "violations": violations}
    if violations:
        print("CONTRACT VIOLATION — boundary F1 moved between arms:", violations)

    # ---------------------------------------------------- G-A5 graph inspection
    best_graph = max((a for a in arms if a["arm"].startswith("graph kNN")),
                     key=lambda a: a["ari"] or -1)
    comms = collections.defaultdict(list)
    for i, l in enumerate(lab_louvain):
        comms[l].append(i)
    insp = []
    for l, members in sorted(comms.items(), key=lambda kv: -len(kv[1]))[:5]:
        sub = [reps[i] for i in members]
        surf = collections.Counter(x for r in sub for x in r["where"]["surface_set"])
        rt = collections.Counter(x for r in sub for x in r["where"]["routes"])
        how = {k: round(float(np.mean([r["how"][k] for r in sub])), 3) for k in ID.HOW_KEYS}
        toks = collections.Counter()
        for r in sub:
            for w in set(r["what"].split()):
                toks[w] += 1
        codes = collections.Counter(target[i] for i in members if i in target)
        insp.append({
            "community": int(l), "size": len(members),
            "sessions": len({segs[i]["session_id"] for i in members}),
            "top_surfaces": surf.most_common(5), "top_routes": rt.most_common(5),
            "mean_how": {k: how[k] for k in ("p_typing", "p_pointing", "p_navigating",
                                             "p_form", "rate_events_per_min", "log_duration")},
            "top_what_tokens": toks.most_common(8),
            "reference_codes_inside": codes.most_common(6),
            "n_distinct_surfaces": len(surf), "n_distinct_routes": len(rt),
            "example_segments": [{"session_id": segs[i]["session_id"],
                                  "start_ms": segs[i]["start_ms"],
                                  "surfaces": reps[i]["where"]["surface_shape"][:3]}
                                 for i in members[:3]],
        })
    out["graph_inspection"] = insp

    # ---------------------------------------------------- GT-informed sweep (dev analysis)
    dev = []
    for r in unsup:
        Sx = S_by_w[r["weights"]]
        lab = ID.louvain(ID.knn_graph(Sx, k=r["k_nn"]), seed=SEED)
        sl = [str(lab[i]) for i in idx_sup]
        sc = EV.identity_scores(list(y), sl)
        dev.append(dict(r, ari=sc["ari"], nmi=sc["nmi"],
                        homogeneity=sc["homogeneity"], completeness=sc["completeness"]))
    out["gt_informed_sweep"] = {
        "_status": "DEVELOPMENT/EVALUATION ANALYSIS, NOT an unsupervised selection. Shown so "
                   "the cost of the unsupervised choice is visible.",
        "rows": sorted(dev, key=lambda r: -(r["ari"] or 0))}

    # ---------------------------------------------------- case studies
    win = lab_louvain
    cases = {}
    # 1. same process, different route: pairs sharing a code, grouped, with disjoint routes
    by_code = collections.defaultdict(list)
    for i in idx_sup:
        by_code[target[i]].append(i)
    def route_set(i):
        return set(reps[i]["where"]["routes"])
    def surf_set(i):
        return set(reps[i]["where"]["surface_set"])
    for key_, pred, want in (
            ("1_same_process_different_route",
             lambda a, b: not (route_set(a) & route_set(b)) and (route_set(a) or route_set(b)), True),
            ("2_same_process_different_surface",
             lambda a, b: not (surf_set(a) & surf_set(b)), True)):
        found = []
        for code, mem in by_code.items():
            for a in mem[:40]:
                for b in mem[:40]:
                    if a >= b or not pred(a, b):
                        continue
                    found.append({"code": code, "a": {"session": segs[a]["session_id"],
                                                      "routes": sorted(route_set(a))[:3],
                                                      "surfaces": sorted(surf_set(a))[:3]},
                                  "b": {"session": segs[b]["session_id"],
                                        "routes": sorted(route_set(b))[:3],
                                        "surfaces": sorted(surf_set(b))[:3]},
                                  "same_community": win[a] == win[b],
                                  "similarity": round(float(S[a, b]), 4)})
                    if len(found) >= 60:
                        break
                if len(found) >= 60:
                    break
            if len(found) >= 60:
                break
        cases[key_] = {"n_pairs_examined": len(found),
                       "grouped_together_rate": round(
                           sum(1 for f in found if f["same_community"]) / max(1, len(found)), 4),
                       "examples": found[:3]}
    # 3. different processes that look structurally similar
    conf = []
    hi_thr = float(np.percentile(off, 99.9))
    for a in idx_sup[:900]:
        for b in idx_sup[:900]:
            if a < b and target[a] != target[b] and S[a, b] > hi_thr:
                conf.append({"codes": [target[a], target[b]], "similarity": round(float(S[a, b]), 4),
                             "same_community": win[a] == win[b],
                             "shared_surfaces": sorted(surf_set(a) & surf_set(b))[:3]})
    cases["3_different_processes_structurally_similar"] = {
        "n_pairs": len(conf),
        "wrongly_grouped_rate": round(sum(1 for c in conf if c["same_community"])
                                      / max(1, len(conf)), 4),
        "examples": conf[:3]}
    # 4. fragments of one interrupted execution
    frag = []
    for s in sessions:
        for c in ref.get(s, {}).get("canonical", []):
            if c["n_fragments"] > 1 and len(c["interval_ms"]) > 1:
                hit = []
                for a, b in c["interval_ms"]:
                    best, bi = 0.0, None
                    for j in by_sess[s]:
                        v = iou((a, b), (segs[j]["start_ms"], segs[j]["end_ms"]))
                        if v > best:
                            best, bi = v, j
                    if bi is not None:
                        hit.append(bi)
                if len(hit) > 1:
                    frag.append({"session_id": s, "code": c["process_code"],
                                 "n_fragments": c["n_fragments"],
                                 "same_community": len({win[i] for i in hit}) == 1,
                                 "communities": sorted({int(win[i]) for i in hit})})
    cases["4_interrupted_execution_fragments"] = {
        "n_interrupted_with_multiple_matched_fragments": len(frag),
        "all_fragments_same_community_rate": round(
            sum(1 for f in frag if f["same_community"]) / max(1, len(frag)), 4),
        "examples": frag[:3]}
    # 5. rare process / small cluster
    code_freq = collections.Counter(target[i] for i in idx_sup)
    rare = [c for c, v in code_freq.items() if v <= max(3, int(0.01 * len(idx_sup)))]
    rare_rows = []
    for c in rare[:5]:
        mem = by_code[c]
        rare_rows.append({"code": c, "n": len(mem),
                          "communities": sorted({int(win[i]) for i in mem}),
                          "community_sizes": [int(sum(1 for x in win if x == w))
                                              for w in sorted({win[i] for i in mem})]})
    cases["5_rare_process"] = {"n_rare_codes": len(rare), "rows": rare_rows}
    out["case_studies"] = cases

    out["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(HERE, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, default=str)
    with open(os.path.join(HERE, "samples.jsonl"), "w", encoding="utf-8") as fh:
        for r in insp:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print("\n=== ARMS (boundary F1 identical on every row by construction) ===")
    hdr = f"{'arm':44} {'ARI':>7} {'NMI':>7} {'hom':>6} {'cmp':>6} {'match':>6} {'k':>5} {'reuse':>6} {'intR':>6} {'bF1':>6}"
    print(hdr)
    for a in arms:
        print(f"{a['arm'][:44]:44} {str(a['ari']):>7} {str(a['nmi']):>7} "
              f"{str(a['homogeneity']):>6} {str(a['completeness']):>6} "
              f"{str(a['match_rate']):>6} {a['n_labels']:>5} "
              f"{a['cross_session_reuse']:>6} {str(a['interruption_recall']):>6} "
              f"{a['boundary_f1_2000']:>6}")
    print(f"\nmerge-only oracle ARI {out['ceiling_merge_only']['ari']} "
          f"(relabelling only)   probe ALL acc {probe['ALL']['accuracy']} "
          f"ARI {probe['ALL']['ari']}")
    print(f"GT-segment diagnostic ARI {out['segmentation_inherited']['ari']}")
    print(f"contract ok: {out['contract_boundary_f1']['identical_on_every_arm']}")
    print(f"wrote {HERE}  ({out['runtime_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
