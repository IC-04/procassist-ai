#!/usr/bin/env python3
"""S-E2 — miss attribution (STEP1_SPEC §6).

For every GT boundary in the scoreable canonical population NOT reachable within tau = 2 s of
a block edge, assign exactly one of five evidence categories. This experiment MEASURES; it
repairs nothing and builds no candidate generator, scorer, decoder or LLM.

The corrected population and the unified tau grid come from S-E1 and are not recomputed.

Run:  python3 experiments/SE2-miss-attribution/run.py
"""
from __future__ import annotations
import bisect, collections, glob, json, os, random, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from procmine import normalise as N, blocks as B, gt as GT  # noqa: E402
import classify as CL  # noqa: E402

DATASET = os.path.join(ROOT, "dataset_a")
GT_DIR = os.path.join(ROOT, "build", "dataset_a")
SE1 = os.path.join(ROOT, "experiments", "SE1-gt-metric-correction")

TAU_MS = 2000          # from S-E1's unified grid; the attribution tolerance
CONTROL_OFFSETS = (2000, 5000)   # 2 s as specified; 5 s additionally, see report.md
SEED = 7


def load_se1():
    cfg = json.load(open(f"{SE1}/config.json", encoding="utf-8"))
    met = json.load(open(f"{SE1}/metrics.json", encoding="utf-8"))
    return cfg, met


def usable_intervals(c):
    out = []
    for a, b in c.get("intervals", []):
        x, y = GT.parse_ts(a), GT.parse_ts(b)
        if x is not None and y is not None and y > x:
            out.append((x, y))
    return out


def raw_event_index(session_dir):
    """(ts, event_id) for every raw line in the source chunk files — the (a) trace."""
    out = []
    for f in sorted(glob.glob(os.path.join(session_dir, "chunk_*", "events.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue          # counted separately by malformed_raw_lines()
                ts, eid = e.get("timestamp_ms"), e.get("event_id")
                if ts is None or eid is None:
                    continue
                out.append((ts, eid))
    out.sort()
    return out


def malformed_raw_lines(session_dir):
    n = 0
    for f in sorted(glob.glob(os.path.join(session_dir, "chunk_*", "events.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    n += 1
    return n


def build_world():
    world = {}
    for sdir in N.iter_session_dirs(DATASET):
        sid = os.path.basename(sdir)
        rows = N.load_session(sdir)
        if not rows:
            continue
        blks = B.build_blocks(rows)
        # absorption disabled: min_events=0 makes `len(rows) < min_events` unsatisfiable,
        # so blocks._absorb never fires. blocks.py is NOT modified.
        blks_na = B.build_blocks(rows, min_events=0, min_ms=0)
        ts = [r["ts_ms"] for r in rows]
        gaps = [r["ms_since_last"] for r in rows
                if isinstance(r.get("ms_since_last"), (int, float))]
        gaps.sort()
        world[sid] = {
            "rows": rows, "ts": ts, "blocks": blks,
            "edges": sorted({x for b in blks for x in (b["start_ms"], b["end_ms"])}),
            "edges_no_absorb": sorted({x for b in blks_na
                                       for x in (b["start_ms"], b["end_ms"])}),
            "telemetry_span": (ts[0], ts[-1]),
            "raw_ids_sorted": raw_event_index(sdir),
            "normalised_ids": {r["event_id"] for r in rows},
            "malformed_raw_lines": malformed_raw_lines(sdir),
            # a "large" gap is defined per session from its own distribution (ADR-003 keeps
            # relative gap as a feature; an absolute threshold would be a dataset-specific rule)
            "gap_threshold_ms": gaps[int(len(gaps) * 0.95)] if gaps else None,
            "n_blocks": len(blks), "n_blocks_no_absorb": len(blks_na),
        }
    return world


def verify_annotation_lead(C, world):
    """Re-verify the +820 ms lead on the CORRECTED population (S-E2 must not assume it)."""
    deltas = []
    for c in C:
        sid = c["session_id"]
        if sid not in world or c["confidence"] not in ("clean", "repaired"):
            continue
        ts = world[sid]["ts"]
        for a, b in usable_intervals(c):
            for g in (a, b):
                i = bisect.bisect_left(ts, g)
                cand = [ts[j] - g for j in (i - 1, i) if 0 <= j < len(ts)]
                if cand:
                    deltas.append(min(cand, key=abs))
    deltas.sort()
    def q(p):
        return deltas[min(len(deltas) - 1, int(len(deltas) * p))]
    return {"n": len(deltas), "p25_ms": q(.25), "median_ms": q(.5), "p75_ms": q(.75),
            "mean_ms": round(statistics.mean(deltas), 1),
            "note": "nearest retained event minus GT timestamp; positive = GT leads telemetry"}


def contingency(missed_points, world, all_gt_by_session, offsets):
    """Signal rate at missed boundaries vs at control points offset from them.

    Controls are excluded when they fall within TAU of ANY GT boundary, so a control is never
    secretly a boundary. Counts are reported, not only percentages.
    """
    rng = random.Random(SEED)
    tables = {}
    for off in offsets:
        # The comparison window must be narrower than the offset, otherwise the control
        # window contains the boundary it was offset from and is not a control at all.
        half = min(TAU_MS, off // 2)
        b_counts = collections.Counter()
        c_counts = collections.Counter()
        n_b = n_c = 0
        for sid, g in missed_points:
            w = world[sid]
            sig = CL.signals_in_window(CL.window_rows(w["rows"], w["ts"], g, half),
                                       w["gap_threshold_ms"])
            n_b += 1
            for k, v in sig.items():
                if v:
                    b_counts[k] += 1
            gts = all_gt_by_session.get(sid, [])
            for sign in (rng.choice([-1, 1]), -rng.choice([-1, 1])):
                cpt = g + sign * off
                t0, t1 = w["telemetry_span"]
                if cpt < t0 or cpt > t1:
                    continue
                if gts and min(abs(cpt - x) for x in gts) <= half:
                    continue          # a control's window must not contain a GT boundary
                csig = CL.signals_in_window(CL.window_rows(w["rows"], w["ts"], cpt, half),
                                            w["gap_threshold_ms"])
                n_c += 1
                for k, v in csig.items():
                    if v:
                        c_counts[k] += 1
        keys = sorted(set(b_counts) | set(c_counts),
                      key=lambda k: -(b_counts[k] + c_counts[k]))
        tables[str(off)] = {
            "n_missed_boundaries": n_b, "n_control_points": n_c,
            "window_half_ms": half, "control_offset_ms": off,
            "windows_overlap": half * 2 > off,
            "signals": {k: {"boundary_n": b_counts[k],
                            "boundary_pct": round(100 * b_counts[k] / n_b, 1) if n_b else None,
                            "control_n": c_counts[k],
                            "control_pct": round(100 * c_counts[k] / n_c, 1) if n_c else None}
                        for k in keys},
        }
    return tables


def main() -> int:
    if not os.path.isdir(DATASET):
        print("dataset_a not present — S-E2 cannot run.")
        return 0
    if not os.path.exists(f"{SE1}/metrics.json"):
        print("S-E1 artifacts missing — run experiments/SE1-gt-metric-correction/run.py first.")
        return 1
    se1_cfg, se1_met = load_se1()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()

    C = [json.loads(l) for l in open(f"{GT_DIR}/executions_canonical.jsonl", encoding="utf-8")]
    world = build_world()
    lead = verify_annotation_lead(C, world)
    LEAD_MS = int(round(lead["median_ms"]))

    all_gt_by_session = collections.defaultdict(list)
    for c in C:
        if c["confidence"] in ("clean", "repaired"):
            for a, b in usable_intervals(c):
                all_gt_by_session[c["session_id"]].extend([a, b])

    total_points = 0
    missed_points = []
    records = []
    for c in C:
        sid = c["session_id"]
        if sid not in world or c["confidence"] not in ("clean", "repaired"):
            continue
        w = world[sid]
        for a, b in usable_intervals(c):
            for g in (a, b):
                total_points += 1
                if w["edges"] and min(abs(g - e) for e in w["edges"]) <= TAU_MS:
                    continue
                missed_points.append((sid, g))
                r = CL.classify_boundary(g, w, TAU_MS, LEAD_MS)
                r.update({"session_id": sid, "process_code": c["process_code"],
                          "canonical_exec_id": c["canonical_exec_id"],
                          "confidence": c["confidence"]})
                records.append(r)

    counts = collections.Counter(r["category"] for r in records)
    subs = collections.Counter((r["category"], r.get("sub")) for r in records)
    n = len(records)
    assert sum(counts.values()) == n, "categories must partition the missed boundaries"

    tables = contingency(missed_points, world, all_gt_by_session, CONTROL_OFFSETS)

    # ---- three quoted examples per (a), (c), (d), with surrounding events
    def surround(sid, g, k=4):
        w = world[sid]
        i = bisect.bisect_left(w["ts"], g)
        out = []
        for j in range(max(0, i - k), min(len(w["rows"]), i + k)):
            r = w["rows"][j]
            out.append({"seq": r.get("seq"), "ts_ms": r["ts_ms"],
                        "delta_to_boundary_ms": r["ts_ms"] - g,
                        "layer": r.get("layer"), "event_type": r.get("event_type"),
                        "app": r.get("app_name"), "route": r.get("route"),
                        "title": (r.get("title") or "")[:40],
                        "ms_since_last": r.get("ms_since_last")})
        return out
    examples = {}
    for cat in ("a_information_destroyed", "c_absorbed_micro_excursion",
                "d_ambiguous_no_evidence"):
        picks = [r for r in records if r["category"] == cat][:3]
        examples[cat] = [{**p, "surrounding_events": surround(p["session_id"], p["ts_ms"])}
                         for p in picks]

    total_malformed = sum(w["malformed_raw_lines"] for w in world.values())
    total_raw = sum(len(w["raw_ids_sorted"]) for w in world.values())
    total_norm = sum(len(w["rows"]) for w in world.values())

    results = {
        "population": se1_cfg["population"],
        "tau_ms": TAU_MS,
        "tau_grid_from_SE1": se1_cfg["tau_grid_ms"],
        "boundary_points_total": total_points,
        "missed_boundaries": n,
        "reachable_pct_check": round(100 * (total_points - n) / total_points, 1),
        "annotation_lead": lead,
        "lead_used_ms": LEAD_MS,
        "categories": {k: {"n": counts.get(k, 0),
                           "pct": round(100 * counts.get(k, 0) / n, 1) if n else None}
                       for k in CL.CATEGORIES},
        "subcategories": {f"{a}|{b}": v for (a, b), v in sorted(subs.items())},
        "preprocessing_audit": {
            "raw_events_in_source_chunks": total_raw,
            "events_in_normalised_stream": total_norm,
            "malformed_raw_lines_skipped": total_malformed,
            "note": ("normalise.load_session drops only malformed JSON lines; blocks assigns "
                     "every retained row to exactly one block. Category (a) is therefore "
                     "expected to be near zero and is PROVEN per boundary, not assumed."),
        },
        "absorption": {
            "blocks_default": sum(w["n_blocks"] for w in world.values()),
            "blocks_absorption_disabled": sum(w["n_blocks_no_absorb"] for w in world.values()),
            "note": "min_events=0 disables blocks._absorb; blocks.py is not modified",
        },
        "contingency": tables,
        "elapsed_s": round(time.time() - t0, 1),
    }

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    config = {
        "exp_id": "SE2-miss-attribution",
        "hypothesis": ("Each missed GT boundary is explained by exactly one of five causes. "
                       "A large (a) means the perception layer must be rebuilt and S-E3 does "
                       "not run; a large (b)+(c) confirms the candidate-layer plan."),
        "dataset": "dataset_a", "sessions": len(world),
        "population_source": "experiments/SE1-gt-metric-correction (not recomputed)",
        "tau_ms": TAU_MS, "control_offsets_ms": list(CONTROL_OFFSETS), "seed": SEED,
        "categories": list(CL.CATEGORIES),
        "discriminating_event_types": sorted(CL.DISCRIMINATING_TYPES),
        "state_signals": list(CL.STATE_SIGNALS),
        "non_goals": ["candidate generator", "scorer", "decoder", "LLM", "any repair"],
        "git_sha": sha, "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(config, open(f"{HERE}/config.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(results, open(f"{HERE}/metrics.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    with open(f"{HERE}/samples.jsonl", "w", encoding="utf-8") as fh:
        for cat, exs in examples.items():
            for e in exs:
                fh.write(json.dumps({"kind": "example", **e}, ensure_ascii=False) + "\n")
        for r in records:
            fh.write(json.dumps({"kind": "classification", **r}, ensure_ascii=False) + "\n")

    # ---- console
    print(f"\nS-E2 — miss attribution, tau={TAU_MS} ms, {len(world)} sessions")
    print(f"boundary points {total_points} · reachable {results['reachable_pct_check']}% · "
          f"MISSED {n}")
    print(f"annotation lead re-verified: median {lead['median_ms']} ms "
          f"(p25 {lead['p25_ms']}, p75 {lead['p75_ms']}, n={lead['n']})\n")
    print(f"{'category':34}{'n':>7}{'pct':>8}")
    print("-" * 49)
    for k in CL.CATEGORIES:
        v = results["categories"][k]
        print(f"{k:34}{v['n']:>7}{v['pct']:>7}%")
    print("-" * 49)
    print(f"{'TOTAL':34}{n:>7}{100.0:>7}%")
    print("\nsubcategories:")
    for k, v in results["subcategories"].items():
        print(f"   {k:52}{v:>6}")
    a_pct = results["categories"]["a_information_destroyed"]["pct"] or 0
    print(f"\nGATE-1: category (a) = {a_pct}%  -> "
          f"{'*** EXCEEDS ~25% — STOP ***' if a_pct > 25 else 'below the 25% threshold'}")
    bc = (results["categories"]["b_preserved_inside_block"]["n"]
          + results["categories"]["c_absorbed_micro_excursion"]["n"])
    print(f"        (b)+(c) = {bc} = {round(100*bc/n,1)}% of missed boundaries")
    print(f"\ncontingency (offset {CONTROL_OFFSETS[0]} ms):")
    t = tables[str(CONTROL_OFFSETS[0])]
    print(f"   {'signal':24}{'bnd n':>7}{'bnd %':>8}{'ctl n':>7}{'ctl %':>8}")
    for k, v in list(t["signals"].items())[:12]:
        if v["boundary_n"] or v["control_n"]:
            bp = "  n/a" if v["boundary_pct"] is None else f"{v['boundary_pct']:>6}%"
            cp = "  n/a" if v["control_pct"] is None else f"{v['control_pct']:>6}%"
            print(f"   {k:24}{v['boundary_n']:>7}{bp:>8}{v['control_n']:>7}{cp:>8}")
    print(f"\nwrote {HERE}  ({results['elapsed_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
