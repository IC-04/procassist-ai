#!/usr/bin/env python3
"""S-E1 — GT metric correction (STEP1_SPEC §6, EVALUATION_PROTOCOL §8-9).

Establishes the empirical baseline. Builds no algorithm: there is no candidate generator, no
scorer, no decoder and no LLM here. It answers six questions and changes which prior numbers
may still be quoted.

  (a) do the GT populations match the values ADR-017 records?
  (b) one tau grid, justified from the scoreable canonical duration distribution
  (c) block-edge-only candidate reachability, recomputed on the scoreable canonical
      population, per confidence tier, over all 63 sessions, with exact denominators
  (d) the "no surface change" figure on BOTH denominators
  (e) the one session whose GT outruns its telemetry, with every headline number twice
  (f) the six baselines re-scored on the corrected population and unified grid

Run:  python3 experiments/SE1-gt-metric-correction/run.py
"""
from __future__ import annotations
import bisect, collections, json, os, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from procmine import normalise as N, blocks as B, gt as GT, evaluate as E, baselines as BL  # noqa: E402

DATASET = os.path.join(ROOT, "dataset_a")
GT_DIR = os.path.join(ROOT, "build", "dataset_a")

# (b) THE UNIFIED GRID. Justified in report.md from the scoreable canonical durations.
TAU_GRID = [1000, 2000, 5000, 10000]
PRIOR_GRIDS = {"PHASE_1_REPORT.md": [1000, 2000, 5250, 10500],
               "experiments/E11-baselines/config.json": [1000, 2250, 5500, 11250]}

# (e) identified by name, never generalised into a dataset-wide failure
TRUNCATED_SESSION = "ses_20260701-152030-CHAITANYA0BCF"

EXPECTED_POPULATIONS = {"canonical": 1819, "unscoreable": 230, "scoreable_canonical": 1589,
                        "interrupted": 98, "clean": 1756, "repaired": 63,
                        "raw_manifest": 2009, "raw_without_end_ts": 257}


def usable_intervals(c):
    out = []
    for a, b in c.get("intervals", []):
        x, y = GT.parse_ts(a), GT.parse_ts(b)
        if x is not None and y is not None and y > x:
            out.append((x, y))
    return out


# ---------------------------------------------------------------- (a) populations

def populations():
    C = [json.loads(l) for l in open(f"{GT_DIR}/executions_canonical.jsonl", encoding="utf-8")]
    raw = noend = 0
    import glob
    for md in sorted(glob.glob(os.path.join(DATASET, "ses_*", "gt_manifest.json"))):
        d = json.load(open(md, encoding="utf-8"))
        for p in d.get("processes", []):
            for e in p.get("executions", []):
                raw += 1
                if not e.get("end_ts"):
                    noend += 1
    measured = {
        "canonical": len(C),
        "unscoreable": sum(1 for c in C if not usable_intervals(c)),
        "scoreable_canonical": sum(1 for c in C if usable_intervals(c)),
        "interrupted": sum(1 for c in C if c["n_fragments"] > 1),
        "clean": sum(1 for c in C if c["confidence"] == "clean"),
        "repaired": sum(1 for c in C if c["confidence"] == "repaired"),
        "raw_manifest": raw, "raw_without_end_ts": noend,
    }
    disagreements = {k: {"expected": v, "measured": measured[k]}
                     for k, v in EXPECTED_POPULATIONS.items() if measured[k] != v}
    return C, measured, disagreements


# ---------------------------------------------------------------- (b) tau justification

def tau_justification(C):
    scoreable = [c for c in C if usable_intervals(c)]
    frag = [(b - a) / 1000 for c in scoreable for a, b in usable_intervals(c)]
    total = [sum(b - a for a, b in usable_intervals(c)) / 1000 for c in scoreable]
    def q(a, p):
        a = sorted(a)
        return round(a[min(len(a) - 1, int(len(a) * p))], 1)
    return {
        "n_scoreable": len(scoreable), "n_fragments": len(frag),
        "fragment_duration_s": {"p10": q(frag, .1), "p50": q(frag, .5), "p90": q(frag, .9),
                                "max": round(max(frag), 1)},
        "execution_active_duration_s": {"p10": q(total, .1), "p50": q(total, .5),
                                        "p90": q(total, .9), "max": round(max(total), 1)},
        "grid_ms": TAU_GRID,
        "grid_as_pct_of_median_fragment": [round(100 * t / (q(frag, .5) * 1000), 1)
                                           for t in TAU_GRID],
        "superseded": PRIOR_GRIDS,
        "annotation_lead_ms": 820,
    }


# ---------------------------------------------------------------- world

def load_world(sessions):
    world = {}
    for sid in sessions:
        rows = N.load_session(os.path.join(DATASET, sid))
        if not rows:
            continue
        blks = B.build_blocks(rows)
        world[sid] = {"rows": rows, "blocks": blks,
                      "timeline": [r["ts_ms"] for r in rows],
                      "edges": sorted({x for b in blks
                                       for x in (b["start_ms"], b["end_ms"])})}
    return world


# ---------------------------------------------------------------- (c) reachability

def reachability(C, world, tiers=("clean", "repaired"), exclude=()):
    """For each boundary of the scoreable canonical population: is ANY block edge within tau?

    This measures the CANDIDATE SPACE, not a segmenter (EVALUATION_PROTOCOL §9 rule 1). It is
    an upper bound on recall for methods restricted to block edges, and nothing else.
    """
    pts, inside, dists = 0, 0, []
    per_tier = {t: {"points": 0, "hits": {str(x): 0 for x in TAU_GRID}} for t in tiers}
    hits = {str(t): 0 for t in TAU_GRID}
    for c in C:
        if c["confidence"] not in tiers:
            continue
        sid = c["session_id"]
        if sid in exclude or sid not in world:
            continue
        edges = world[sid]["edges"]
        blks = world[sid]["blocks"]
        for a, b in usable_intervals(c):
            for g in (a, b):
                pts += 1
                per_tier[c["confidence"]]["points"] += 1
                d = min(abs(g - e) for e in edges) if edges else 10 ** 12
                dists.append(d)
                for t in TAU_GRID:
                    if d <= t:
                        hits[str(t)] += 1
                        per_tier[c["confidence"]]["hits"][str(t)] += 1
                if any(bl["start_ms"] < g < bl["end_ms"] for bl in blks):
                    inside += 1
    def q(a, p):
        a = sorted(a)
        return a[min(len(a) - 1, int(len(a) * p))]
    return {
        "boundary_points": pts,
        "reachable_pct": {t: round(100 * h / pts, 1) for t, h in hits.items()} if pts else {},
        "reachable_n": hits,
        "strictly_inside_a_block_pct": round(100 * inside / pts, 1) if pts else None,
        "median_distance_ms": q(dists, .5) if dists else None,
        "p75_distance_ms": q(dists, .75) if dists else None,
        "per_tier": {t: {"points": v["points"],
                         "reachable_pct": {k: round(100 * n / v["points"], 1)
                                           for k, n in v["hits"].items()} if v["points"] else {}}
                     for t, v in per_tier.items()},
    }


def candidate_density(world, exclude=()):
    """EVALUATION_PROTOCOL §9 rule 3: reachability without density is not a result."""
    ev = sum(len(w["rows"]) for s, w in world.items() if s not in exclude)
    bl = sum(len(w["blocks"]) for s, w in world.items() if s not in exclude)
    cand = sum(len(w["edges"]) for s, w in world.items() if s not in exclude)
    return {"candidates": cand, "events": ev, "blocks": bl,
            "candidates_per_event": round(cand / ev, 4) if ev else None,
            "candidates_per_block": round(cand / bl, 3) if bl else None}


# ---------------------------------------------------------------- (d) two denominators

def no_surface_change(C, world, exclude=(), tau=2000):
    """The same claim on both denominators (EVALUATION_PROTOCOL §9 rule 5)."""
    # denominator A: execution-to-execution transitions
    per_sess = collections.defaultdict(list)
    for c in C:
        if c["session_id"] in exclude:
            continue
        for a, b in usable_intervals(c):
            per_sess[c["session_id"]].append((a, b, c["process_code"]))
    trans_tot = trans_missed = trans_missed_same = 0
    for sid, items in per_sess.items():
        if sid not in world:
            continue
        items.sort()
        edges = world[sid]["edges"]
        rows = world[sid]["rows"]
        ts = world[sid]["timeline"]
        for (_a0, _b0, _p0), (a1, _b1, _p1) in zip(items, items[1:]):
            trans_tot += 1
            if min(abs(a1 - e) for e in edges) <= tau:
                continue
            trans_missed += 1
            i = bisect.bisect_left(ts, a1)
            pre = B.surface_key(rows[i - 1]) if i > 0 else None
            post = B.surface_key(rows[min(i, len(rows) - 1)])
            if pre == post:
                trans_missed_same += 1
    # denominator B: every boundary point
    pts_tot = pts_missed = pts_missed_same = 0
    for c in C:
        sid = c["session_id"]
        if sid in exclude or sid not in world:
            continue
        edges = world[sid]["edges"]
        rows = world[sid]["rows"]
        ts = world[sid]["timeline"]
        for a, b in usable_intervals(c):
            for g in (a, b):
                pts_tot += 1
                if min(abs(g - e) for e in edges) <= tau:
                    continue
                pts_missed += 1
                i = bisect.bisect_left(ts, g)
                pre = B.surface_key(rows[i - 1]) if i > 0 else None
                post = B.surface_key(rows[min(i, len(rows) - 1)])
                if pre == post:
                    pts_missed_same += 1
    return {
        "tau_ms": tau,
        "denominator_A_execution_transitions": {
            "transitions": trans_tot, "missed": trans_missed,
            "missed_with_no_surface_change": trans_missed_same,
            "pct_of_missed": round(100 * trans_missed_same / trans_missed, 1) if trans_missed else None},
        "denominator_B_all_boundary_points": {
            "points": pts_tot, "missed": pts_missed,
            "missed_with_no_surface_change": pts_missed_same,
            "pct_of_missed": round(100 * pts_missed_same / pts_missed, 1) if pts_missed else None},
    }


# ---------------------------------------------------------------- (f) baselines

def rescore_baselines(C, world, exclude=()):
    ref = collections.defaultdict(lambda: {"intervals": [], "labels": [], "canonical": []})
    for c in C:
        sid = c["session_id"]
        if sid in exclude or sid not in world:
            continue
        iv = usable_intervals(c)
        for a, b in iv:
            ref[sid]["intervals"].append((a, b))
            ref[sid]["labels"].append(c["process_code"])
        ref[sid]["canonical"].append({"n_fragments": c["n_fragments"], "interval_ms": iv,
                                      "process_code": c["process_code"]})
    for sid in ref:
        order = sorted(range(len(ref[sid]["intervals"])),
                       key=lambda i: ref[sid]["intervals"][i])
        ref[sid]["intervals"] = [ref[sid]["intervals"][i] for i in order]
        ref[sid]["labels"] = [ref[sid]["labels"][i] for i in order]
    sessions = [s for s in world if s not in exclude]
    k_true = {s: len(ref[s]["intervals"]) for s in sessions}
    timelines = {s: world[s]["timeline"] for s in sessions}
    cfg = {"taus_ms": TAU_GRID, "kappas": list(E.DEFAULT_KAPPAS), "ious": [0.5],
           "timelines": timelines, "tier": "clean+repaired", "arm": None}

    out = {}
    for name in BL.REGISTRY:
        seeds = range(BL.N_RANDOM_SEEDS) if name == "B3-random" else [0]
        runs = []
        for seed in seeds:
            hyp = {}
            for s in sessions:
                iv, lb = BL.run_baseline(name, world[s]["rows"], world[s]["blocks"],
                                         k=k_true.get(s), seed=seed)
                hyp[s] = {"intervals": iv, "labels": lb}
            runs.append(E.evaluate_all(dict(ref), hyp, dict(cfg, arm=name))["overall"])
        def m(f):
            vs = [f(r) for r in runs if f(r) is not None]
            return round(statistics.mean(vs), 4) if vs else None
        out[name] = {
            "n_hyp_segments": m(lambda r: r["n_hyp_segments"]),
            "count_ratio": m(lambda r: r["count_ratio"]),
            "boundary_f1": {str(t): m(lambda r, t=t: r["boundary_time"][str(t)]["f1"])
                            for t in TAU_GRID},
            "precision_2000": m(lambda r: r["boundary_time"]["2000"]["precision"]),
            "recall_2000": m(lambda r: r["boundary_time"]["2000"]["recall"]),
            "segmental_f1_iou50": m(lambda r: r["segmental"]["0.5"]["f1"]),
            "windowdiff": m(lambda r: r["windowdiff_mean"]),
            "ari": m(lambda r: (r.get("identity_pooled") or {}).get("ari")),
            "match_rate": m(lambda r: (r.get("identity_pooled") or {}).get("match_rate")),
            "interruption_recall": m(lambda r: (r.get("interruption") or {}).get("recall")),
            "n_seeds": len(runs),
        }
    return out, {"n_ref_segments": sum(len(v["intervals"]) for v in ref.values()),
                 "n_sessions": len(sessions)}


# ---------------------------------------------------------------- driver

def main() -> int:
    if not os.path.isdir(DATASET):
        print("dataset_a not present — S-E1 cannot run.")
        return 0
    if not os.path.exists(f"{GT_DIR}/executions_canonical.jsonl"):
        print("build/dataset_a ground truth missing — run `python3 -m procmine.gt "
              "--dataset dataset_a` first.")
        return 1
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()

    C, measured, disagreements = populations()
    tau = tau_justification(C)
    sessions = sorted(os.path.basename(p) for p in N.iter_session_dirs(DATASET))
    world = load_world(sessions)

    excl = (TRUNCATED_SESSION,)
    results = {
        "populations": {"expected": EXPECTED_POPULATIONS, "measured": measured,
                        "disagreements": disagreements},
        "tau": tau,
        "reachability_all63": reachability(C, world),
        "reachability_excl_truncated": reachability(C, world, exclude=excl),
        "reachability_clean_only": reachability(C, world, tiers=("clean",)),
        "candidate_density_all63": candidate_density(world),
        "candidate_density_excl": candidate_density(world, exclude=excl),
        "no_surface_change_all63": no_surface_change(C, world),
        "no_surface_change_excl": no_surface_change(C, world, exclude=excl),
    }
    bl_all, ref_all = rescore_baselines(C, world)
    bl_ex, ref_ex = rescore_baselines(C, world, exclude=excl)
    results["baselines_all63"] = {"reference": ref_all, "arms": bl_all}
    results["baselines_excl_truncated"] = {"reference": ref_ex, "arms": bl_ex}

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    config = {
        "exp_id": "SE1-gt-metric-correction",
        "hypothesis": ("Prior Phase 1 figures were computed on an unstated GT population and "
                       "two different tau grids. Recompute on the scoreable canonical "
                       "population (ADR-017) at one justified grid and state which prior "
                       "numbers survive."),
        "dataset": "dataset_a",
        "sample": {"sessions": sessions, "n": len(sessions),
                   "selection": "ALL 63 sessions — not the 5-session sample E11 used"},
        "population": "scoreable canonical (ADR-017), tiers clean+repaired",
        "tau_grid_ms": TAU_GRID,
        "superseded_grids": PRIOR_GRIDS,
        "identified_outlier_session": TRUNCATED_SESSION,
        "blocks_built_with": "post D-1/D-2 perception layer (commit c9d1c05)",
        "non_goals": ["candidate generation", "scorer", "decoder", "LLM", "labelling",
                      "block hyperparameter tuning"],
        "git_sha": sha, "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    results["elapsed_s"] = round(time.time() - t0, 1)

    with open(f"{HERE}/config.json", "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
    with open(f"{HERE}/metrics.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    with open(f"{HERE}/samples.jsonl", "w", encoding="utf-8") as fh:
        for k in ("reachability_all63", "reachability_excl_truncated",
                  "reachability_clean_only"):
            fh.write(json.dumps({"kind": k, **results[k]}, ensure_ascii=False) + "\n")
        for scope in ("baselines_all63", "baselines_excl_truncated"):
            for arm, v in results[scope]["arms"].items():
                fh.write(json.dumps({"kind": scope, "arm": arm, **v},
                                    ensure_ascii=False) + "\n")

    # ---- console
    print(f"\nS-E1 — {len(sessions)} A sessions, tau grid {TAU_GRID} ms\n")
    print("(a) POPULATIONS")
    for k, v in measured.items():
        e = EXPECTED_POPULATIONS[k]
        print(f"    {k:24} expected {e:>6}  measured {v:>6}  "
              f"{'OK' if e == v else '*** DISAGREE ***'}")
    print(f"    disagreements: {len(disagreements)}")
    r, rx = results["reachability_all63"], results["reachability_excl_truncated"]
    print(f"\n(c) BLOCK-EDGE REACHABILITY  (candidate space, NOT accuracy)")
    print(f"    {'':22}{'all 63':>12}{'excl truncated':>16}")
    print(f"    {'boundary points':22}{r['boundary_points']:>12}{rx['boundary_points']:>16}")
    for t in TAU_GRID:
        print(f"    tau={t:>6} ms{'':9}{r['reachable_pct'][str(t)]:>11.1f}%"
              f"{rx['reachable_pct'][str(t)]:>15.1f}%")
    print(f"    {'inside a block':22}{r['strictly_inside_a_block_pct']:>11.1f}%"
          f"{rx['strictly_inside_a_block_pct']:>15.1f}%")
    print(f"    {'median distance ms':22}{r['median_distance_ms']:>12}{rx['median_distance_ms']:>16}")
    d = results["no_surface_change_all63"]
    print(f"\n(d) 'NO SURFACE CHANGE' — both denominators, tau=2000 ms")
    a_, b_ = d["denominator_A_execution_transitions"], d["denominator_B_all_boundary_points"]
    print(f"    A: {a_['missed_with_no_surface_change']}/{a_['missed']} missed of "
          f"{a_['transitions']} transitions   = {a_['pct_of_missed']}%")
    print(f"    B: {b_['missed_with_no_surface_change']}/{b_['missed']} missed of "
          f"{b_['points']} boundary points = {b_['pct_of_missed']}%")
    print(f"\n(f) BASELINES on the corrected population, all 63 sessions "
          f"(ref n={ref_all['n_ref_segments']})")
    h = f"    {'arm':<12}{'segs':>7}{'ratio':>7}{'bF1@2s':>9}{'P':>7}{'R':>7}{'segF1':>7}{'ARI':>7}{'match':>7}"
    print(h); print("    " + "-" * (len(h) - 4))
    for arm, v in bl_all["arms"].items() if isinstance(bl_all, dict) and "arms" in bl_all else bl_all.items():
        f = lambda x: "  n/a" if x is None else f"{x:.3f}"
        print(f"    {arm:<12}{int(v['n_hyp_segments']):>7}{v['count_ratio']:>7.2f}"
              f"{f(v['boundary_f1']['2000']):>9}{f(v['precision_2000']):>7}"
              f"{f(v['recall_2000']):>7}{f(v['segmental_f1_iou50']):>7}"
              f"{f(v['ari']):>7}{f(v['match_rate']):>7}")
    print(f"\nwrote {HERE}  ({results['elapsed_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
