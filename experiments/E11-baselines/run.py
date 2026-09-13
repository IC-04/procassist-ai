#!/usr/bin/env python3
"""E11 — the Phase 1 baseline scorecard.

Scores every baseline in `EVALUATION_PROTOCOL.md` §6 against Dataset A's canonicalised
ground truth, under all three GT tiers (§4) and both reference conventions for discontinuous
executions (§5), in both coordinate domains (§2).

Nothing here tunes anything. No parameter is selected from these numbers; the scorecard's
job is to establish the floor and expose where trivial methods fail.

Run:  python3 experiments/E11-baselines/run.py [--all-sessions]
"""
from __future__ import annotations
import json, os, sys, time, argparse, statistics, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from procmine import normalise as N, blocks as B, gt as GT, evaluate as E, baselines as BL  # noqa: E402

DATASET = os.path.join(ROOT, "dataset_a")
SEED = 7
SAMPLE_N = 5


def pick_sessions(all_sessions: bool) -> list:
    alls = sorted(os.path.basename(p) for p in N.iter_session_dirs(DATASET))
    if all_sessions:
        return alls
    import random
    return sorted(random.Random(SEED).sample(alls, min(SAMPLE_N, len(alls))))


def load_world(sessions):
    """Normalised rows, blocks and the event timeline for each session."""
    world = {}
    for sid in sessions:
        rows = N.load_session(os.path.join(DATASET, sid))
        if not rows:
            continue
        world[sid] = {
            "rows": rows,
            "blocks": B.build_blocks(rows),
            "timeline": [r["ts_ms"] for r in rows],
        }
    return world


def ref_bundles(exec_rows, canon_rows, sessions):
    """Build reference bundles per TIER x CONVENTION (EVALUATION_PROTOCOL §4, §5)."""
    tiers = {
        "clean": lambda c: c == "clean",
        "clean+repaired": lambda c: c in ("clean", "repaired"),
        "all": lambda c: True,
    }
    out = {}
    for tname, keep in tiers.items():
        ex = [e for e in exec_rows if keep(e["confidence"]) and e["session_id"] in sessions
              and e["start_ms"] is not None and e["end_ms"] is not None]
        ca = [c for c in canon_rows if keep(c["confidence"]) and c["session_id"] in sessions]

        # convention 1: fragment-level (HEADLINE) — each fragment is its own target
        frag = collections.defaultdict(lambda: {"intervals": [], "labels": [], "canonical": []})
        for e in sorted(ex, key=lambda r: (r["session_id"], r["start_ms"])):
            frag[e["session_id"]]["intervals"].append((e["start_ms"], e["end_ms"]))
            frag[e["session_id"]]["labels"].append(e["process_code"])

        # convention 2: canonical-level (LENIENT) — union the fragments
        canon = collections.defaultdict(lambda: {"intervals": [], "labels": [], "canonical": []})
        for c in ca:
            ms = [(GT.parse_ts(a), GT.parse_ts(b)) for a, b in c["intervals"]]
            ms = [(a, b) for a, b in ms if a is not None and b is not None]
            if not ms:
                continue
            canon[c["session_id"]]["intervals"].append(
                (min(a for a, _ in ms), max(b for _, b in ms)))
            canon[c["session_id"]]["labels"].append(c["process_code"])

        # attach canonical records (with ms intervals) for interruption_recall
        for c in ca:
            ms = [(GT.parse_ts(a), GT.parse_ts(b)) for a, b in c["intervals"]]
            ms = [(a, b) for a, b in ms if a is not None and b is not None]
            rec = {"n_fragments": c["n_fragments"], "interval_ms": ms,
                   "process_code": c["process_code"]}
            frag[c["session_id"]]["canonical"].append(rec)
            canon[c["session_id"]]["canonical"].append(rec)

        out[tname] = {"fragment": dict(frag), "canonical": dict(canon)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-sessions", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(DATASET):
        print("dataset_a not present — E11 cannot run.")
        return 0

    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    sessions = pick_sessions(a.all_sessions)
    world = load_world(sessions)
    sessions = [s for s in sessions if s in world]

    # --- ground truth, canonicalised with the FROZEN repair rules (ADR-011).
    # Artifacts land in build/<dataset>/ per DATA_CONTRACT §5; that tree is gitignored,
    # so dataset_a-derived ground truth never enters version control.
    gt_out = os.path.join(ROOT, "build", "dataset_a")
    GT.build(DATASET, gt_out, sessions=sessions)
    exec_rows = [json.loads(l) for l in open(f"{gt_out}/executions.jsonl", encoding="utf-8")]
    canon_rows = [json.loads(l) for l in open(f"{gt_out}/executions_canonical.jsonl",
                                              encoding="utf-8")]

    # --- tau calibrated from the DATA, not assumed (Task 1.5)
    cal = E.calibrate_tau(canon_rows)
    taus = cal["grid_ms"]
    kappas = list(E.DEFAULT_KAPPAS)
    ious = list(E.DEFAULT_IOUS)

    refs = ref_bundles(exec_rows, canon_rows, set(sessions))
    timelines = {s: world[s]["timeline"] for s in sessions}

    # --- true segment count per session (oracle k for B2/B3)
    k_true = {s: len(refs["clean+repaired"]["fragment"].get(s, {}).get("intervals", []))
              for s in sessions}

    HEADLINE = "clean+repaired|fragment"
    samples = []
    results = {}
    for name in BL.REGISTRY:
        seeds = range(BL.N_RANDOM_SEEDS) if name == "B3-random" else [0]
        per_seed = []
        for seed in seeds:
            hyp = {}
            for s in sessions:
                iv, lb = BL.run_baseline(name, world[s]["rows"], world[s]["blocks"],
                                         k=k_true.get(s), seed=seed)
                hyp[s] = {"intervals": iv, "labels": lb}
            arm = {}
            for tier in refs:
                for conv in ("fragment", "canonical"):
                    cfg = {"taus_ms": taus, "kappas": kappas, "ious": ious,
                           "timelines": timelines, "tier": tier, "arm": name}
                    arm[f"{tier}|{conv}"] = E.evaluate_all(refs[tier][conv], hyp, cfg)
            # Size control: per-session detail is retained for the HEADLINE combination
            # (clean+repaired | fragment) on every seed, and `overall` only for the other
            # five tier x convention combinations. Keeping per-session detail everywhere
            # for all 20 random seeds produced a 44 MB file with no added information.
            # The headline keeps it on every seed because the spread statistic below is
            # computed from it and must not mix per-session values with pooled ones.
            per_seed.append({
                k: (v if k == HEADLINE else {"config": v["config"], "overall": v["overall"]})
                for k, v in arm.items()})
            samples.append({"arm": name, "seed": seed,
                            "n_hyp": sum(len(hyp[s]["intervals"]) for s in sessions),
                            "headline_boundary_f1": arm["clean+repaired|fragment"]["overall"]
                                                      ["boundary_time"][str(taus[1])]["f1"]})
        results[name] = {"n_seeds": len(per_seed), "runs": per_seed}

    # --- per-session spread (EVALUATION_PROTOCOL §7). LOSO is degenerate for these
    #     baselines because none of them fits a parameter, so the informative quantity
    #     is the spread ACROSS sessions, which is what is reported.
    spread = {}
    tau_h = str(taus[1])
    for name, r in results.items():
        vals = []
        for run in r["runs"]:
            # always per-session, for every seed — see the size-control note above
            ps = run[HEADLINE]["per_session"]
            vals.extend(ps[s]["boundary_time"][tau_h]["f1"] for s in ps)
        spread[name] = {"mean": round(statistics.mean(vals), 4),
                        "sd": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
                        "min": round(min(vals), 4), "max": round(max(vals), 4), "n": len(vals)}

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    config = {
        "exp_id": "E11-baselines",
        "hypothesis": ("Establish the floor: what boundary and identity accuracy do trivial "
                       "methods reach on Dataset A, and where do they fail? No parameter is "
                       "selected from these numbers."),
        "dataset": "dataset_a",
        "sample": {"sessions": sessions, "n": len(sessions), "seed": SEED,
                   "selection": "all" if a.all_sessions else f"random {SAMPLE_N} @ seed {SEED}"},
        "arms": list(BL.REGISTRY),
        "oracle_k_arms": sorted(BL.ORACLE_K),
        "random_seeds": BL.N_RANDOM_SEEDS,
        "tau_calibration": cal,
        "params": {"taus_ms": taus, "kappas": kappas, "ious": ious,
                   "min_events": 3, "min_ms": 1500, "max_lag": 12},
        "tiers": list(refs),
        "conventions": ["fragment (headline)", "canonical (lenient)"],
        "git_sha": sha, "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    metrics = {"_note": ("Full evaluate_all() output is retained for seed 0 of every arm. "
                         "For B3-random seeds 1-19 only the `overall` block is kept; storing "
                         "per-session detail for all 20 seeds produced a 44 MB file with no "
                         "additional information. per_session_spread below is computed over "
                         "ALL seeds."),
               "results": results, "per_session_spread": spread,
               "k_true_per_session": k_true, "elapsed_s": round(time.time() - t0, 1)}

    suffix = "_all" if a.all_sessions else ""
    for nm, obj in ((f"config{suffix}.json", config), (f"metrics{suffix}.json", metrics)):
        with open(os.path.join(HERE, nm), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, f"samples{suffix}.jsonl"), "w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    # --- console scorecard
    print(f"\nE11 baseline scorecard — {len(sessions)} A sessions, "
          f"tau grid {taus} ms (calibrated, median exec {cal['median_duration_s']}s)")
    print(f"headline: tier=clean+repaired, convention=fragment, tau={tau_h}ms\n")
    hdr = (f"{'arm':<12}{'nseg':>6}{'ratio':>7}{'bF1':>7}{'bP':>7}{'bR':>7}"
           f"{'segF1@.5':>10}{'WD':>7}{'ARI':>7}{'match':>7}{'intr':>7}")
    print(hdr); print("-" * len(hdr))
    for name, r in results.items():
        o = [run["clean+repaired|fragment"]["overall"] for run in r["runs"]]
        def m(f): 
            vs = [f(x) for x in o if f(x) is not None]
            return round(statistics.mean(vs), 4) if vs else None
        bt = m(lambda x: x["boundary_time"][tau_h]["f1"])
        bp = m(lambda x: x["boundary_time"][tau_h]["precision"])
        br = m(lambda x: x["boundary_time"][tau_h]["recall"])
        sf = m(lambda x: x["segmental"]["0.5"]["f1"])
        wd = m(lambda x: x["windowdiff_mean"])
        ari = m(lambda x: (x.get("identity_pooled") or {}).get("ari"))
        mr = m(lambda x: (x.get("identity_pooled") or {}).get("match_rate"))
        ir = m(lambda x: (x.get("interruption") or {}).get("recall"))
        ns = m(lambda x: x["n_hyp_segments"])
        cr = m(lambda x: x["count_ratio"])
        f = lambda v: "  n/a" if v is None else f"{v:.3f}"
        print(f"{name:<12}{int(ns):>6}{cr:>7.2f}{f(bt):>7}{f(bp):>7}{f(br):>7}"
              f"{f(sf):>10}{f(wd):>7}{f(ari):>7}{f(mr):>7}{f(ir):>7}")
    print(f"\nper-session boundary F1 spread (mean +/- sd):")
    for n, s in spread.items():
        print(f"  {n:<12} {s['mean']:.3f} +/- {s['sd']:.3f}   [{s['min']:.3f}, {s['max']:.3f}]")
    print(f"\nwrote {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
