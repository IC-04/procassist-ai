#!/usr/bin/env python3
"""S-E6 addendum — a SECOND, pre-declared unsupervised selection rule.

The first rule (modularity x cross-session reuse) chose `how_heavy, k_nn=5` and scored ARI
0.204, while the best configuration in the same grid scores 0.583. The failure has a known
cause and it is not a tuning accident: **modularity is not comparable across graphs of
different density.** Sparser graphs score higher modularity almost mechanically, so the rule
was really selecting "the sparsest graph", and it could not distinguish `how_heavy` from
`where_heavy` at all (0.8669 vs 0.8669).

The replacement rule is the one Phase E established and `label.choose_k` already uses, applied
here to a self-selecting-k method: **partition stability under node resampling x cross-session
reuse**, with stability measured as co-clustering Jaccard (plain pairwise agreement is
degenerate as k grows — measured in Phase E). It is declared here before its ARI is looked at,
and whatever it selects is reported.

Run:  .venv/bin/python experiments/SE6-identity-grouping/select2.py
"""
from __future__ import annotations
import collections, json, os, pickle, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import numpy as np                                            # noqa: E402
from procmine import identity as ID, evaluate as EV           # noqa: E402

SEED, TRIALS, FRAC = 7, 3, 0.8
IOU = 0.5


def iou(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return 0.0 if hi <= lo else (hi - lo) / ((a[1] - a[0]) + (b[1] - b[0]) - (hi - lo))


def align(ref_iv, hyp_iv, thr=IOU):
    cands = sorted(((-iou(r, h), i, j) for i, r in enumerate(ref_iv)
                    for j, h in enumerate(hyp_iv) if iou(r, h) >= thr))
    ur, uh, out = set(), set(), []
    for _v, i, j in cands:
        if i in ur or j in uh:
            continue
        ur.add(i); uh.add(j); out.append((i, j))
    return out


def cocluster_jaccard(a, b):
    """Jaccard over CO-CLUSTERED pairs. Takes no credit for pairs apart in both partitions,
    so it cannot be gamed by making the clustering finer."""
    a = np.asarray(a); b = np.asarray(b)
    P = a[:, None] == a[None, :]
    Q = b[:, None] == b[None, :]
    iu = np.triu_indices(len(a), 1)
    p, q = P[iu], Q[iu]
    u = (p | q).sum()
    return float((p & q).sum() / u) if u else 0.0


def main() -> int:
    t0 = time.time()
    D = pickle.load(open(os.path.join(ROOT, "build", "dataset_a", "se6_frozen.pkl"), "rb"))
    segs = sorted(D["segments"], key=lambda s: (s["session_id"], s["start_ms"]))
    rows, blocks, ref, sessions = D["rows"], D["blocks"], D["ref"], D["sessions"]
    n = len(segs)
    reps = [ID.represent(s, rows[s["session_id"]], blocks[s["session_id"]]) for s in segs]
    views = ID.similarity_views(reps)
    sess = [s["session_id"] for s in segs]
    rng = np.random.default_rng(SEED)

    by_sess = collections.defaultdict(list)
    for i, s in enumerate(segs):
        by_sess[s["session_id"]].append(i)
    hyp_iv_by = {s: [(segs[i]["start_ms"], segs[i]["end_ms"]) for i in by_sess[s]]
                 for s in sessions}

    rowsout = []
    S_cache = {}
    for wname, w in ID.WEIGHT_GRID.items():
        S = ID.combine(views, w)
        S_cache[wname] = S
        for k_nn in (5, 10, 20):
            base = np.array(ID.louvain(ID.knn_graph(S, k=k_nn), seed=SEED))
            stab = []
            for t in range(TRIALS):
                idx = np.sort(rng.choice(n, size=int(FRAC * n), replace=False))
                sub = np.array(ID.louvain(ID.knn_graph(S[np.ix_(idx, idx)], k=k_nn),
                                          seed=SEED))
                stab.append(cocluster_jaccard(sub, base[idx]))
            stability = float(np.mean(stab))
            groups = collections.defaultdict(set)
            for c, sd in zip(base, sess):
                groups[c].add(sd)
            k = len(groups)
            reuse = sum(1 for v in groups.values() if len(v) > 1) / max(1, k)
            rowsout.append({"weights": wname, "k_nn": k_nn, "n_clusters": k,
                            "stability": round(stability, 4),
                            "cross_session_reuse": round(reuse, 4),
                            "objective": round(stability * reuse, 4)})
            print(f"  {wname:12} k_nn={k_nn:3} k={k:4} stab={stability:.4f} "
                  f"reuse={reuse:.3f} obj={stability*reuse:.4f}  ({time.time()-t0:.0f}s)",
                  flush=True)

    rowsout.sort(key=lambda r: -r["objective"])
    chosen = rowsout[0]
    print(f"\nRULE 2 selects: {chosen}", flush=True)

    # --- only now, evaluate the frozen choice against GT
    S = S_cache[chosen["weights"]]
    lab = ID.louvain(ID.knn_graph(S, k=chosen["k_nn"]), seed=SEED)
    hb = {}
    for s in sessions:
        hb[s] = {"intervals": hyp_iv_by[s], "labels": [str(lab[i]) for i in by_sess[s]]}
    cfg = {"taus_ms": [1000, 2000, 5000, 10000], "kappas": [1, 2, 5, 10],
           "ious": [0.3, 0.5, 0.7],
           "timelines": {s: [r["ts_ms"] for r in rows[s]] for s in sessions}}
    m = EV.evaluate_all(ref, hb, cfg)["overall"]
    ident = m["identity_pooled"]
    sess_of = collections.defaultdict(set)
    for i, l in enumerate(lab):
        sess_of[l].add(sess[i])
    result = {
        "_rule": "partition stability under 80% node resampling x cross-session reuse; "
                 "stability = co-clustering Jaccard. Declared BEFORE its ARI was inspected.",
        "_why_rule_1_failed": "modularity is not comparable across graphs of different "
                              "density — the first rule was selecting the sparsest graph, and "
                              "scored how_heavy and where_heavy identically at 0.8669.",
        "grid": rowsout, "chosen": chosen,
        "arm": f"graph kNN(k={chosen['k_nn']}, {chosen['weights']}) + Louvain [rule 2]",
        "n_labels": len(set(lab)),
        "boundary_f1_2000": m["boundary_time"]["2000"]["f1"],
        "boundary_f1_all": {t: m["boundary_time"][t]["f1"] for t in m["boundary_time"]},
        "count_ratio": m["count_ratio"],
        "ari": ident["ari"], "nmi": ident["nmi"], "homogeneity": ident["homogeneity"],
        "completeness": ident["completeness"], "match_rate": ident["match_rate"],
        "n_matched": ident["n_matched"],
        "interruption_recall": (m.get("interruption") or {}).get("recall"),
        "cross_session_reuse": round(sum(1 for v in sess_of.values() if len(v) > 1)
                                     / max(1, len(sess_of)), 4),
        "mean_sessions_per_label": round(sum(len(v) for v in sess_of.values())
                                         / max(1, len(sess_of)), 2),
        "runtime_s": round(time.time() - t0, 1),
    }
    json.dump(result, open(os.path.join(HERE, "selection_rule_2.json"), "w"),
              indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in result.items() if not k.startswith("_")
                      and k != "grid"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
