#!/usr/bin/env python3
"""S-E6b task 4 — is Dataset B's 6-cluster result defensible, or does k-selection degrade?

B has no ground truth, so nothing here is an accuracy figure. What can be measured is INTERNAL
CONSISTENCY, in the same shape the Phase E calibration comparison used: cluster sizes,
cross-session reuse, and within-cluster surface/route diversity. A cluster whose members share
no surface and no route is not a process identity, whatever its modularity.

Also regenerates `segments.jsonl` under the configuration that wins.
"""
from __future__ import annotations
import collections, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import numpy as np                                                       # noqa: E402
from procmine import (normalise as N, blocks as B, candidates as CA, score as SC,   # noqa: E402
                      gate as GA, decoder as DE, identity as ID, label as LB)

DATASET = os.path.join(ROOT, "dataset_b")


def diversity(reps, labels):
    """Within-cluster agreement on surfaces and routes: the share of members carrying the
    cluster's most common surface / route. 1.0 = every member visits it."""
    by = collections.defaultdict(list)
    for i, l in enumerate(labels):
        by[l].append(i)
    rows = []
    for l, mem in sorted(by.items(), key=lambda kv: -len(kv[1])):
        surf = collections.Counter(x for i in mem for x in set(reps[i]["where"]["surface_set"]))
        rt = collections.Counter(x for i in mem for x in set(reps[i]["where"]["routes"]))
        rows.append({
            "cluster": int(l), "size": len(mem),
            "sessions": len({reps[i]["session_id"] for i in mem}),
            "distinct_surfaces": len(surf), "distinct_routes": len(rt),
            "modal_surface_share": round(surf.most_common(1)[0][1] / len(mem), 3) if surf else None,
            "modal_route_share": round(rt.most_common(1)[0][1] / len(mem), 3) if rt else None,
            "top_surface": surf.most_common(1)[0][0] if surf else None,
            "top_route": rt.most_common(1)[0][0] if rt else None,
        })
    return rows


def main() -> int:
    t0 = time.time()
    out = {}
    world = {}
    for sd in N.iter_session_dirs(DATASET):
        sid = os.path.basename(sd)
        rows = N.load_session(sd)
        if not rows:
            continue
        blks = B.build_blocks(rows)
        world[sid] = {"rows": rows, "blocks": blks, "cands": CA.generate(rows, blks)}
    sessions = sorted(world)
    scorer = SC.load(os.path.join(ROOT, "procmine", "scorer_v1.json"))
    pooled = []
    for s in sessions:
        pooled += [dict(c, session_id=s) for c in scorer.apply(world[s]["cands"])]
    cal = SC.calibrate(pooled, "percentile")
    by = collections.defaultdict(list)
    for c in cal:
        by[c["session_id"]].append(c)
    segs = []
    for s in sessions:
        r = GA.route(sorted(by[s], key=lambda x: x["at_seq"]))
        for x in DE.decode_session(r, {}):
            x["session_id"] = s
            segs.append(x)
    segs.sort(key=lambda s: (s["session_id"], s["start_ms"]))
    reps = [ID.represent(s, world[s["session_id"]]["rows"], world[s["session_id"]]["blocks"])
            for s in segs]
    print(f"B: {len(segs)} segments over {len(sessions)} sessions ({time.time()-t0:.0f}s)",
          flush=True)

    sel = ID.select_config(reps, [s["session_id"] for s in segs], seed=7)
    views = sel.pop("_views")
    arms = {}
    for mode in ID.COMBINE_MODES:
        for wname in ("where_heavy", "balanced"):
            for k_nn in ID.K_NN_GRID:
                S = ID.combine(views, ID.WEIGHT_GRID[wname], mode=mode)
                lab = ID.louvain(ID.knn_graph(S, k=k_nn), seed=7)
                d = diversity(reps, lab)
                sess_of = collections.defaultdict(set)
                for i, l in enumerate(lab):
                    sess_of[l].add(reps[i]["session_id"])
                arms[f"{wname}/{mode}/k{k_nn}"] = {
                    "n_clusters": len(set(lab)),
                    "sizes": [r["size"] for r in d][:12],
                    "largest_share": round(max(r["size"] for r in d) / len(segs), 3),
                    "cross_session_reuse": round(
                        sum(1 for v in sess_of.values() if len(v) > 1) / max(1, len(sess_of)), 3),
                    "mean_modal_surface_share": round(float(np.mean(
                        [r["modal_surface_share"] for r in d if r["modal_surface_share"]])), 3),
                    "mean_modal_route_share": round(float(np.mean(
                        [r["modal_route_share"] for r in d if r["modal_route_share"]] or [0])), 3),
                }
    out["b_arms"] = arms
    out["b_selected"] = {k: v for k, v in sel.items() if k != "grid"}
    out["b_selection_grid"] = sel.get("grid", [])[:10]
    print(f"[B select] {out['b_selected']}", flush=True)

    S = ID.combine(views, ID.WEIGHT_GRID[sel["weights"]], mode=sel["mode"])
    lab = ID.louvain(ID.knn_graph(S, k=sel["k_nn"]), seed=7)
    out["b_chosen_clusters"] = diversity(reps, lab)
    out["b_n_clusters"] = len(set(lab))
    out["b_n_segments"] = len(segs)
    out["b_n_sessions"] = len(sessions)

    labelled = LB.label_segments(segs, {s: world[s]["rows"] for s in sessions},
                                 {s: world[s]["blocks"] for s in sessions})
    rep = LB.label_report(labelled)
    out["b_label_report"] = rep
    import datetime as dt

    def iso(ms):
        return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = os.path.join(ROOT, "segments.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for x in sorted(labelled, key=lambda z: (z["session_id"], z["start_ms"])):
            fh.write(json.dumps({"session_id": x["session_id"], "start": iso(x["start_ms"]),
                                 "end": iso(x["end_ms"]), "label": x["label"]},
                                ensure_ascii=False) + "\n")
    out["segments_jsonl"] = {"path": "segments.jsonl", "n": len(labelled),
                             "n_labels": rep["n_labels"]}
    out["runtime_s"] = round(time.time() - t0, 1)
    json.dump(out, open(os.path.join(HERE, "dataset_b_sanity.json"), "w"), indent=2,
              ensure_ascii=False, default=str)
    print(json.dumps({k: v for k, v in out.items()
                      if k in ("b_n_clusters", "b_n_segments", "b_n_sessions", "b_label_report",
                               "segments_jsonl")}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
