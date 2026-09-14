#!/usr/bin/env python3
"""S-E4 — full Dataset A validation of the deterministic Step 1 pipeline (--no-llm).

Reuses `procmine/evaluate.py` and `procmine/baselines.py` unchanged; no metric is
reimplemented. Population and tau grid come from S-E1 and are not recomputed.

Run:  python3 experiments/SE4-end-to-end-a/run.py
"""
from __future__ import annotations
import bisect, collections, json, os, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from procmine import (normalise as N, blocks as B, gt as GT, candidates as CA,  # noqa: E402
                      score as SC, gate as GA, decoder as DE, label as LB,
                      evaluate as EV, baselines as BL)

DATASET = os.path.join(ROOT, "dataset_a")
GT_DIR = os.path.join(ROOT, "build", "dataset_a")
TAUS = [1000, 2000, 5000, 10000]
CEILING = {"1000": 77.8, "2000": 90.0, "5000": 98.7, "10000": 98.9}   # S-E1/S-E2 correction
TAU_LABEL = 2000


def usable(c):
    o = []
    for a, b in c.get("intervals", []):
        x, y = GT.parse_ts(a), GT.parse_ts(b)
        if x is not None and y is not None and y > x:
            o.append((x, y))
    return o


def nearest(vals, g):
    if not vals:
        return 10 ** 12
    i = bisect.bisect_left(vals, g)
    return min([abs(vals[j] - g) for j in (i - 1, i) if 0 <= j < len(vals)] or [10 ** 12])


def build():
    C = [json.loads(l) for l in open(f"{GT_DIR}/executions_canonical.jsonl", encoding="utf-8")]
    ref = collections.defaultdict(lambda: {"intervals": [], "labels": [], "canonical": []})
    gtb = collections.defaultdict(list)
    gtb_clean = collections.defaultdict(list)
    for c in C:
        if c["confidence"] not in ("clean", "repaired"):
            continue
        iv = usable(c)
        if not iv:
            continue
        sid = c["session_id"]
        for a, b in iv:
            ref[sid]["intervals"].append((a, b))
            ref[sid]["labels"].append(c["process_code"])
            gtb[sid].extend([a, b])
            if c["confidence"] == "clean":
                gtb_clean[sid].extend([a, b])
        ref[sid]["canonical"].append({"n_fragments": c["n_fragments"], "interval_ms": iv,
                                      "process_code": c["process_code"]})
    for sid in ref:
        o = sorted(range(len(ref[sid]["intervals"])), key=lambda i: ref[sid]["intervals"][i])
        ref[sid]["intervals"] = [ref[sid]["intervals"][i] for i in o]
        ref[sid]["labels"] = [ref[sid]["labels"][i] for i in o]
    world = {}
    for sd in N.iter_session_dirs(DATASET):
        sid = os.path.basename(sd)
        rows = N.load_session(sd)
        if not rows:
            continue
        blks = B.build_blocks(rows)
        world[sid] = {"rows": rows, "blocks": blks, "cands": CA.generate(rows, blks),
                      "timeline": [r["ts_ms"] for r in rows]}
    return world, dict(ref), gtb, gtb_clean


def labels_of(cands, gts, tau=TAU_LABEL):
    g = sorted(gts)
    return [1 if (c.get("at_ms") is not None and nearest(g, c["at_ms"]) <= tau) else 0
            for c in cands]


def main() -> int:
    if not os.path.isdir(DATASET):
        print("dataset_a not present — S-E4 cannot run.")
        return 0
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    world, ref, gtb, gtb_clean = build()
    sessions = sorted(world)
    timelines = {s: world[s]["timeline"] for s in sessions}

    # ---- LOSO scoring: the honest number. Fitting on all of A and scoring A is optimistic.
    scored = {}
    for held in sessions:
        tr_c, tr_y = [], []
        for s in sessions:
            if s == held:
                continue
            tr_c += world[s]["cands"]
            tr_y += labels_of(world[s]["cands"], gtb_clean.get(s, []))
        scored[held] = SC.fit(tr_c, tr_y).apply(world[held]["cands"])
    t_score = time.time() - t0

    pooled = []
    for s in sessions:
        pooled += [dict(c, session_id=s) for c in scored[s]]
    cal = SC.calibrate(pooled, "percentile")
    by = collections.defaultdict(list)
    for c in cal:
        by[c["session_id"]].append(c)

    routed_all = []
    hyp, all_segs = {}, []
    for s in sessions:
        r = GA.route(sorted(by[s], key=lambda x: x["at_seq"]))
        routed_all += r
        segs = DE.decode_session(r, {})
        for x in segs:
            x["session_id"] = s
        all_segs += segs
        hyp[s] = {"intervals": [(x["start_ms"], x["end_ms"]) for x in segs],
                  "labels": ["seg"] * len(segs)}

    labelled = LB.label_segments(all_segs, {s: world[s]["rows"] for s in sessions},
                                 {s: world[s]["blocks"] for s in sessions})
    lab_by = collections.defaultdict(list)
    for x in labelled:
        lab_by[x["session_id"]].append(x)
    hyp_lab = {s: {"intervals": [(x["start_ms"], x["end_ms"]) for x in sorted(v, key=lambda y: y["start_ms"])],
                   "labels": [x["label"] for x in sorted(v, key=lambda y: y["start_ms"])]}
               for s, v in lab_by.items()}

    cfg = {"taus_ms": TAUS, "kappas": [1, 2, 5, 10], "ious": [0.3, 0.5, 0.7],
           "timelines": timelines}
    m = EV.evaluate_all(ref, hyp_lab, cfg)
    o = m["overall"]
    runtime = time.time() - t0

    # ---- baselines on the SAME population and grid
    k_true = {s: len(ref.get(s, {}).get("intervals", [])) for s in sessions}
    base = {}
    for name in BL.REGISTRY:
        seeds = range(BL.N_RANDOM_SEEDS) if name == "B3-random" else [0]
        runs = []
        for seed in seeds:
            h = {}
            for s in sessions:
                iv, lb = BL.run_baseline(name, world[s]["rows"], world[s]["blocks"],
                                         k=k_true.get(s), seed=seed)
                h[s] = {"intervals": iv, "labels": lb}
            runs.append(EV.evaluate_all(ref, h, cfg)["overall"])
        def mean(f):
            v = [f(r) for r in runs if f(r) is not None]
            return round(statistics.mean(v), 4) if v else None
        base[name] = {
            "boundary_f1": {str(t): mean(lambda r, t=t: r["boundary_time"][str(t)]["f1"])
                            for t in TAUS},
            "precision_2000": mean(lambda r: r["boundary_time"]["2000"]["precision"]),
            "recall_2000": mean(lambda r: r["boundary_time"]["2000"]["recall"]),
            "count_ratio": mean(lambda r: r["count_ratio"]),
            "segmental_f1_iou50": mean(lambda r: r["segmental"]["0.5"]["f1"]),
            "windowdiff": mean(lambda r: r["windowdiff_mean"]),
            "ari": mean(lambda r: (r.get("identity_pooled") or {}).get("ari")),
            "match_rate": mean(lambda r: (r.get("identity_pooled") or {}).get("match_rate")),
            "interruption_recall": mean(lambda r: (r.get("interruption") or {}).get("recall")),
        }

    # ---- candidate-space quality, reported SEPARATELY (never an accuracy figure)
    reach = {str(t): 0 for t in TAUS}
    n_pts = n_cand = n_ev = 0
    for s in sessions:
        cts = sorted(c["at_ms"] for c in world[s]["cands"] if c["at_ms"] is not None)
        n_cand += len(world[s]["cands"])
        n_ev += len(world[s]["rows"])
        for g in gtb.get(s, []):
            n_pts += 1
            d = nearest(cts, g)
            for t in TAUS:
                if d <= t:
                    reach[str(t)] += 1

    # ---- AUC on the candidate population (different denominator from F1 — explained in report)
    allc, ally = [], []
    for s in sessions:
        allc += scored[s]
        ally += labels_of(scored[s], gtb.get(s, []))
    rank = SC.ranking_report(allc, ally)
    n_pos = sum(ally)
    distinct_boundaries = sum(len(v) for v in gtb.values())

    # ---- Phase G sizing on the PRECISION axis, computed at BOUNDARY level.
    #
    # The obvious version of this calculation is wrong, and wrong in the way this project keeps
    # being wrong: it counts CANDIDATES inside the routed band and adds them to a BOUNDARY-level
    # confusion matrix. Roughly two candidates sit within tau of each GT boundary and only one
    # can ever be used, so a candidate-level "recoverable FN" count overstates the boundary-level
    # gain several-fold. Everything below is therefore counted in GT boundaries and emitted
    # boundary points, never in candidates.
    emitted = {s: sorted({x for iv in hyp[s]["intervals"] for x in iv}) for s in sessions}
    b2 = o["boundary_time"]["2000"]
    phase_g = {}
    for frac in (0.034, 0.05, 0.10, 0.15):
        lo = max(0.0, 0.872 - frac / 2)
        hi = min(1.0, 0.872 + frac / 2)
        band_by = collections.defaultdict(list)
        n_band = 0
        for c in cal:
            if lo <= c["score"] <= hi:
                band_by[c["session_id"]].append(c)
                n_band += 1
        rec_fn = rem_fp = 0
        for s in sessions:
            g = sorted(gtb.get(s, []))
            bs = [c for c in band_by.get(s, []) if c.get("at_ms") is not None]
            em = emitted.get(s, [])
            for gg in g:                      # unmatched GT a routed candidate could reach
                if nearest(em, gg) > TAU_LABEL and any(abs(c["at_ms"] - gg) <= TAU_LABEL
                                                        for c in bs):
                    rec_fn += 1
            for e in em:                      # emitted FPs that came from a routed candidate
                if nearest(g, e) > TAU_LABEL and any(abs(c["at_ms"] - e) <= 1 for c in bs):
                    rem_fp += 1
        tp = b2["tp"] + rec_fn
        fp = max(0, b2["fp"] - rem_fp)
        fn = max(0, b2["fn"] - rec_fn)
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        phase_g[f"{frac:.3f}"] = {
            "routing_fraction": round(n_band / len(cal), 4), "n_routed": n_band,
            "recoverable_boundary_fn": rec_fn, "removable_boundary_fp": rem_fp,
            "oracle_precision": round(p, 4), "oracle_recall": round(r, 4),
            "oracle_f1_upper_bound": round(2 * p * r / (p + r), 4) if (p + r) else 0.0,
            "delta_f1_vs_current": round((2 * p * r / (p + r) if (p + r) else 0) - b2["f1"], 4),
            "_unit": "GT boundaries and emitted boundary points, NOT candidates",
        }

    # ---- an interior-to-block boundary, quoted concretely
    example = None
    for s in sessions:
        blks = world[s]["blocks"]
        rows = world[s]["rows"]
        ts = world[s]["timeline"]
        for seg in sorted(lab_by.get(s, []), key=lambda x: x["start_ms"]):
            for pt in (seg["start_ms"], seg["end_ms"]):
                inside = next((b for b in blks if b["start_ms"] < pt < b["end_ms"]), None)
                if inside and nearest(sorted(gtb.get(s, [])), pt) <= 2000:
                    i = bisect.bisect_left(ts, pt)
                    example = {
                        "session_id": s, "boundary_ms": pt,
                        "inside_block": inside["block_id"], "block_surface": inside["surface"],
                        "block_span_ms": [inside["start_ms"], inside["end_ms"]],
                        "block_n_events": inside["n_events"],
                        "distance_to_nearest_gt_ms": nearest(sorted(gtb.get(s, [])), pt),
                        "segment_label": seg["label"],
                        "surrounding_events": [
                            {"delta_ms": rows[j]["ts_ms"] - pt, "event_type": rows[j]["event_type"],
                             "app": rows[j]["app_name"], "route": rows[j]["route"]}
                            for j in range(max(0, i - 3), min(len(rows), i + 3))],
                    }
                    break
            if example:
                break
        if example:
            break

    lab_rep = LB.label_report(labelled)
    per_sess = {s: m["per_session"][s]["boundary_time"]["2000"]["f1"]
                for s in sessions if s in m["per_session"]}

    # ---- +/-20% threshold perturbation
    pert = {}
    for name, base_v in (("lambda_per_segment", DE.DEFAULT_CFG["lambda_per_segment"]),
                         ("min_duration_ms", DE.DEFAULT_CFG["min_duration_ms"])):
        for mult in (0.8, 1.2):
            h = {}
            for s in sessions:
                r = GA.route(sorted(by[s], key=lambda x: x["at_seq"]))
                sg = DE.decode_session(r, {name: base_v * mult})
                h[s] = {"intervals": [(x["start_ms"], x["end_ms"]) for x in sg],
                        "labels": ["seg"] * len(sg)}
            oo = EV.evaluate_all(ref, h, cfg)["overall"]
            pert[f"{name} x{mult}"] = {"f1_2000": oo["boundary_time"]["2000"]["f1"],
                                       "count_ratio": oo["count_ratio"]}

    results = {
        "population": "scoreable canonical (1,589 executions -> 1,752 fragments -> 3,504 points)",
        "operating_point": {"calibration": "percentile",
                            "lambda_per_segment": DE.DEFAULT_CFG["lambda_per_segment"],
                            "min_duration_ms": DE.DEFAULT_CFG["min_duration_ms"],
                            "gate_bands": [GA.DEFAULT_CFG["low"], GA.DEFAULT_CFG["high"]]},
        "overall": o,
        "ceiling_pct": CEILING,
        "baselines": base,
        "candidate_space_quality": {
            "boundary_points": n_pts,
            "reachability_pct": {t: round(100 * v / n_pts, 1) for t, v in reach.items()},
            "density_per_event": round(n_cand / n_ev, 4),
            "density_per_block": round(n_cand / sum(len(world[s]["blocks"]) for s in sessions), 2),
            "_note": "candidate-space quality, NOT segmentation quality (EVALUATION_PROTOCOL §9)",
        },
        "ranking": rank,
        "auc_denominators": {
            "auc_population": "all candidates", "n_candidates": len(allc),
            "auc_positive_definition": f"candidate within {TAU_LABEL} ms of any GT boundary",
            "n_positive_candidates": n_pos,
            "n_distinct_gt_boundaries": distinct_boundaries,
            "candidates_per_true_boundary": round(n_pos / distinct_boundaries, 2),
        },
        "labels": lab_rep,
        "per_session_f1_2000": {"mean": round(statistics.mean(per_sess.values()), 4),
                                "sd": round(statistics.pstdev(per_sess.values()), 4),
                                "min": min(per_sess.values()), "max": max(per_sess.values())},
        "perturbation": pert,
        "phase_g_oracle": phase_g,
        "interior_to_block_example": example,
        "runtime_s": {"total": round(runtime, 1), "loso_scoring": round(t_score, 1)},
    }
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    config = {"exp_id": "SE4-end-to-end-a", "dataset": "dataset_a", "sessions": len(sessions),
              "mode": "--no-llm", "calibration": "percentile", "tau_grid_ms": TAUS,
              "population_source": "experiments/SE1-gt-metric-correction",
              "evaluation": "procmine/evaluate.py, reused unchanged",
              "git_sha": sha, "started_at": started,
              "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(config, open(f"{HERE}/config.json", "w", encoding="utf-8"), indent=2)
    json.dump(results, open(f"{HERE}/metrics.json", "w", encoding="utf-8"), indent=2, default=str)
    with open(f"{HERE}/samples.jsonl", "w", encoding="utf-8") as fh:
        if example:
            fh.write(json.dumps({"kind": "interior_boundary", **example}) + "\n")
        for s, f1 in sorted(per_sess.items()):
            fh.write(json.dumps({"kind": "per_session", "session_id": s, "f1_2000": f1}) + "\n")
        for n, v in base.items():
            fh.write(json.dumps({"kind": "baseline", "arm": n, **v}) + "\n")

    print(f"\nS-E4 — {len(sessions)} A sessions, --no-llm, percentile calibration "
          f"({results['runtime_s']['total']}s)\n")
    print(f"{'tau':>7}{'P':>8}{'R':>8}{'F1':>8}{'ceiling':>9}{'R/ceil':>9}")
    for t in TAUS:
        b = o["boundary_time"][str(t)]
        c = CEILING[str(t)]
        print(f"{t:>7}{b['precision']:>8.3f}{b['recall']:>8.3f}{b['f1']:>8.3f}"
              f"{c:>8.1f}%{100*b['recall']*100/c:>8.1f}%")
    print(f"\ncount ratio {o['count_ratio']}  segmental F1@.5 {o['segmental']['0.5']['f1']}  "
          f"WD {o['windowdiff_mean']}  Pk {o['pk_mean']}")
    idp = o.get("identity_pooled") or {}
    print(f"identity: ARI {idp.get('ari')}  NMI {idp.get('nmi')}  match_rate {idp.get('match_rate')}")
    print(f"interruption_recall {(o.get('interruption') or {}).get('recall')} "
          f"(read with count ratio {o['count_ratio']})")
    print(f"\nbaselines (F1@2s): " + "  ".join(
        f"{k.split('-')[0]}={v['boundary_f1']['2000']}" for k, v in base.items()))
    print(f"\nPhase G oracle upper bound:")
    for f, v in phase_g.items():
        print(f"   routing {float(f):.1%}: n={v['n_routed']:>5}  recoverable FN "
              f"{v['recoverable_boundary_fn']:>3}  removable FP {v['removable_boundary_fp']:>4}"
              f"  -> F1 {v['oracle_f1_upper_bound']} ({v['delta_f1_vs_current']:+.4f})")
    print(f"\nwrote {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
