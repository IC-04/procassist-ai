#!/usr/bin/env python3
"""S-E3 — intra-block candidate reachability (STEP1_SPEC §6). THE DECISIVE EXPERIMENT.

Measures the candidate space produced by `procmine/candidates.py` against the block-edge-only
arm, on S-E1's corrected population and unified tau grid. Builds no scorer, gate, decoder or
LLM.

Every reachability figure is reported beside the ACHIEVABLE CEILING at the same tau, because
absolute reachability is uninterpretable without it, and beside CANDIDATE DENSITY, because
reachability bought by nominating every event is not a result.

Run:  python3 experiments/SE3-candidate-reachability/run.py
"""
from __future__ import annotations
import bisect, collections, json, os, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from procmine import normalise as N, blocks as B, gt as GT, candidates as CA  # noqa: E402

DATASET = os.path.join(ROOT, "dataset_a")
GT_DIR = os.path.join(ROOT, "build", "dataset_a")
SE1 = os.path.join(ROOT, "experiments", "SE1-gt-metric-correction")
SE2 = os.path.join(ROOT, "experiments", "SE2-miss-attribution")
TAUS = [1000, 2000, 5000, 10000]


def usable(c):
    o = []
    for a, b in c.get("intervals", []):
        x, y = GT.parse_ts(a), GT.parse_ts(b)
        if x is not None and y is not None and y > x:
            o.append((x, y))
    return o


def nearest(sorted_vals, g):
    if not sorted_vals:
        return 10 ** 12
    i = bisect.bisect_left(sorted_vals, g)
    return min([abs(sorted_vals[j] - g) for j in (i - 1, i) if 0 <= j < len(sorted_vals)]
               or [10 ** 12])


def main() -> int:
    if not os.path.isdir(DATASET):
        print("dataset_a not present — S-E3 cannot run.")
        return 0
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()

    C = [json.loads(l) for l in open(f"{GT_DIR}/executions_canonical.jsonl", encoding="utf-8")]
    # SE2 categories are GT-derived: used ONLY here, in evaluation, never in generation.
    se2 = {}
    for l in open(f"{SE2}/samples.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r.get("kind") == "classification":
            se2[(r["session_id"], r["ts_ms"])] = r["category"]

    gt_by = collections.defaultdict(list)
    for c in C:
        if c["confidence"] in ("clean", "repaired"):
            for a, b in usable(c):
                gt_by[c["session_id"]].extend([a, b])

    arms = {
        "candidates": {},                                   # shipped default
        "candidates_with_mode_transition": {
            "enabled_triggers": CA.ENABLED_TRIGGERS | {"mode_transition"}},
        "candidates_no_dedup": {"dedup_ms": 0},             # literal §3.2 contract 3
    }
    out = {}
    per_session_rows = collections.defaultdict(dict)
    feat_tables = {}

    for arm, cfg in arms.items():
        tot = 0
        hit = {t: 0 for t in TAUS}
        edge_hit = {t: 0 for t in TAUS}
        ceil_hit = {t: 0 for t in TAUS}
        n_c = n_e = n_b = n_intra = 0
        per_sess = {}
        recov = collections.defaultdict(lambda: collections.Counter())
        # contingency accumulators (only for the shipped arm)
        want_feats = arm == "candidates"
        pos_all = collections.Counter(); neg_all = collections.Counter()
        pos_missed = collections.Counter(); neg_missed = collections.Counter()
        n_pos_all = n_neg_all = n_pos_missed = n_neg_missed = 0

        for sdir in N.iter_session_dirs(DATASET):
            sid = os.path.basename(sdir)
            rows = N.load_session(sdir)
            if not rows:
                continue
            blks = B.build_blocks(rows)
            cand = CA.generate(rows, blks, cfg)
            n_c += len(cand); n_e += len(rows); n_b += len(blks)
            n_intra += sum(1 for x in cand if x["kind"] == "intra_block")
            cts = sorted(x["at_ms"] for x in cand if x["at_ms"] is not None)
            ets = sorted({x for b in blks for x in (b["start_ms"], b["end_ms"])})
            tl = [r["ts_ms"] for r in rows]

            s_tot = 0; s_hit = 0
            for g in gt_by.get(sid, []):
                tot += 1; s_tot += 1
                dc, de, dv = nearest(cts, g), nearest(ets, g), nearest(tl, g)
                for t in TAUS:
                    if dc <= t: hit[t] += 1
                    if de <= t: edge_hit[t] += 1
                    if dv <= t: ceil_hit[t] += 1
                if dc <= 2000:
                    s_hit += 1
                cat = se2.get((sid, g))
                if cat:                                     # was missed at tau=2s by block edges
                    recov[cat]["total"] += 1
                    for t in TAUS:
                        if dc <= t:
                            recov[cat][f"reached_{t}"] += 1
            if s_tot:
                per_sess[sid] = round(100 * s_hit / s_tot, 1)

            if want_feats:
                gts = sorted(gt_by.get(sid, []))
                missed_gts = sorted(g for g in gts if nearest(ets, g) > 2000)
                for x in cand:
                    ms = x["at_ms"]
                    if ms is None:
                        continue
                    is_b = nearest(gts, ms) <= 2000
                    near_missed = nearest(missed_gts, ms) <= 2000
                    for k, v in x["features"].items():
                        if v is True or (isinstance(v, (int, float))
                                         and not isinstance(v, bool) and False):
                            pass
                    flags = {k for k, v in x["features"].items() if v is True}
                    if is_b:
                        n_pos_all += 1
                        for k in flags: pos_all[k] += 1
                    else:
                        n_neg_all += 1
                        for k in flags: neg_all[k] += 1
                    if near_missed:
                        n_pos_missed += 1
                        for k in flags: pos_missed[k] += 1
                    elif not is_b:
                        n_neg_missed += 1
                        for k in flags: neg_missed[k] += 1

        ceiling = {str(t): round(100 * ceil_hit[t] / tot, 1) for t in TAUS}
        reach = {str(t): round(100 * hit[t] / tot, 1) for t in TAUS}
        edge = {str(t): round(100 * edge_hit[t] / tot, 1) for t in TAUS}
        out[arm] = {
            "boundary_points": tot,
            "reachability_pct": reach,
            "reachability_n": {str(t): hit[t] for t in TAUS},
            "block_edge_pct": edge,
            "ceiling_pct": ceiling,
            "ceiling_adjusted_pct": {str(t): round(100 * hit[t] / ceil_hit[t], 1)
                                     if ceil_hit[t] else None for t in TAUS},
            "density": {"candidates": n_c, "events": n_e, "blocks": n_b,
                        "intra_block": n_intra,
                        "per_event": round(n_c / n_e, 4), "per_block": round(n_c / n_b, 2)},
            "per_session_tau2000": {
                "mean": round(statistics.mean(per_sess.values()), 1),
                "sd": round(statistics.pstdev(per_sess.values()), 1),
                "min": min(per_sess.values()), "max": max(per_sess.values()),
                "n_sessions": len(per_sess)},
            "recovery_by_se2_category": {
                k: {"total": v["total"],
                    **{f"reached_{t}": v[f"reached_{t}"] for t in TAUS},
                    "pct_2000": round(100 * v["reached_2000"] / v["total"], 1) if v["total"] else None}
                for k, v in sorted(recov.items())},
        }
        if want_feats:
            def tbl(pos, npos, neg, nneg):
                keys = sorted(set(pos) | set(neg), key=lambda k: -(pos[k] + neg[k]))
                return {"n_boundary_candidates": npos, "n_non_boundary_candidates": nneg,
                        "features": {k: {"boundary_n": pos[k],
                                         "boundary_pct": round(100 * pos[k] / npos, 1) if npos else None,
                                         "non_boundary_n": neg[k],
                                         "non_boundary_pct": round(100 * neg[k] / nneg, 1) if nneg else None}
                                     for k in keys}}
            feat_tables = {
                "all_boundaries": tbl(pos_all, n_pos_all, neg_all, n_neg_all),
                "missed_only": tbl(pos_missed, n_pos_missed, neg_missed, n_neg_missed),
            }
        per_session_rows[arm] = per_sess

    results = {"arms": out, "contingency": feat_tables,
               "tau_grid_from_SE1": TAUS, "elapsed_s": round(time.time() - t0, 1)}

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    config = {
        "exp_id": "SE3-candidate-reachability",
        "hypothesis": ("An event-level candidate space recovers the boundaries S-E2 showed are "
                       "present inside blocks, at a density that is not indiscriminate."),
        "dataset": "dataset_a", "population_source": "experiments/SE1-gt-metric-correction",
        "population": "scoreable canonical, tiers clean+repaired",
        "tau_grid_ms": TAUS, "arms": list(arms),
        "generator_cfg_default": {k: (sorted(v) if isinstance(v, frozenset) else v)
                                  for k, v in CA.DEFAULT_CFG.items()},
        "non_goals": ["scorer", "gate", "decoder", "labelling", "LLM"],
        "git_sha": sha, "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(config, open(f"{HERE}/config.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(results, open(f"{HERE}/metrics.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    with open(f"{HERE}/samples.jsonl", "w", encoding="utf-8") as fh:
        for arm, v in out.items():
            fh.write(json.dumps({"kind": "arm", "arm": arm, **v}, ensure_ascii=False) + "\n")
        for arm, ps in per_session_rows.items():
            for sid, pct in sorted(ps.items()):
                fh.write(json.dumps({"kind": "per_session", "arm": arm,
                                     "session_id": sid, "reach_tau2000_pct": pct},
                                    ensure_ascii=False) + "\n")

    # ---- console
    a = out["candidates"]
    print(f"\nS-E3 — candidate reachability, {a['boundary_points']} boundary points, "
          f"{a['per_session_tau2000']['n_sessions']} sessions")
    print(f"\n{'tau':>8}{'block-edge':>13}{'CANDIDATES':>13}{'ceiling':>10}{'adj%':>9}")
    print("-" * 53)
    for t in TAUS:
        k = str(t)
        print(f"{t:>8}{a['block_edge_pct'][k]:>12.1f}%{a['reachability_pct'][k]:>12.1f}%"
              f"{a['ceiling_pct'][k]:>9.1f}%{a['ceiling_adjusted_pct'][k]:>8.1f}%")
    d = a["density"]
    print(f"\ndensity: {d['per_event']}/event ({d['candidates']} cands / {d['events']} events), "
          f"{d['per_block']}/block   [gate: <= 0.30/event]")
    p = a["per_session_tau2000"]
    print(f"per-session @tau=2s: mean {p['mean']}% sd {p['sd']} range [{p['min']}, {p['max']}]")
    print("\nrecovery of S-E2's missed boundaries (by category, at tau=2s):")
    for k, v in a["recovery_by_se2_category"].items():
        print(f"   {k:34}{v['reached_2000']:>5}/{v['total']:<6}{v['pct_2000']:>6}%")
    print("\narms:")
    for arm, v in out.items():
        print(f"   {arm:34} tau2s={v['reachability_pct']['2000']:>5}%  "
              f"adj={v['ceiling_adjusted_pct']['2000']:>5}%  "
              f"density={v['density']['per_event']:.4f}/ev")
    print(f"\nruntime {results['elapsed_s']}s -> {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
