#!/usr/bin/env python3
"""E01 — block-quality ablation and absorption-threshold sweep.

Two questions:

  1. **Ablation.** Which of the perception rules actually removes block degeneracy,
     and how much does each contribute on its own?
  2. **Sweep.** What `min_events` x `min_ms` should micro-excursion absorption use?

Selection is NOT by block count. A target band is easy to hit by merging distinct work,
which is the failure mode that matters here. The sweep reports, per cell:

  surface_purity      share of a block's user-layer (L2/L3) events whose own surface key
                      equals the block's key. Falls when absorption merges distinct work.
  fragmentation       share of `returns_to` edges at lag 2 -- A|x|A, the signature of a
                      run split by a single intruding block.
  short_work_at_risk  blocks that are brief AND on a different application from both
                      neighbours: genuinely short, genuinely distinct activity that a
                      more aggressive threshold would destroy.
  stability           max relative change in block count across the neighbouring cells
                      of the grid; a good operating point is on a plateau, not a cliff.

Run:  python3 experiments/E01-block-sweep/run.py
Writes config.json, metrics.json, samples.jsonl and the tables used in report.md.
"""
from __future__ import annotations
import json, os, sys, time, statistics, subprocess, collections
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from procmine import normalise as N, blocks as B, tekg as G   # noqa: E402

DATASET = os.path.join(ROOT, "dataset_b")
MIN_EVENTS_GRID = [2, 3, 5, 8]
MIN_MS_GRID = [1000, 1500, 3000]


# ---------------------------------------------------------------- ablation arms
# Each arm disables one rule so its individual contribution is visible. The rules are
# properties of normalise/blocks, so they are toggled by monkey-patching the predicate
# rather than by forking the implementation.

def _load(dataset: str) -> Dict[str, List[Dict]]:
    return {os.path.basename(sd): N.load_session(sd) for sd in N.iter_session_dirs(dataset)}


def _load_without_carry_forward(dataset: str) -> Dict[str, List[Dict]]:
    orig = N.carry_forward_tab_state
    N.carry_forward_tab_state = lambda rows: rows          # type: ignore[assignment]
    try:
        return _load(dataset)
    finally:
        N.carry_forward_tab_state = orig                   # type: ignore[assignment]


def _legacy_route_of(url):
    """The pre-Phase-0 route_of, for the R5 ablation row."""
    import re
    if not url:
        return ""
    if "#" in url:
        frag = url.split("#", 1)[1]
        return frag if frag.startswith("/") else "/" + frag
    m = re.match(r"^(https?://[^/]+)", url)
    return m.group(1) if m else url


def _legacy_surface_key(r: Dict) -> str:
    """The pre-Phase-0 surface_key, including the hard-coded browser allow-list."""
    browsers = {"Microsoft Edge", "Google Chrome", "Chrome", "Firefox", "msedge"}
    if r["app_name"] in browsers and r["url"]:
        return f"web:{r['origin']}{r['route']}"
    if r["title"]:
        return f"app:{r['app_name']}:{r['title']}"
    return f"app:{r['app_name']}"


def _legacy_build_blocks(rows, min_events=3, min_ms=1500):
    """Pass 1 without R1/R2: every event defines a surface."""
    if not rows:
        return []
    raw = []
    for r in rows:
        k = B.surface_key(r)
        if raw and raw[-1]["surface"] == k:
            raw[-1]["rows"].append(r)
        else:
            raw.append({"surface": k, "app": r.get("app_name") or "", "rows": [r]})
    return B._summarise(B._absorb(raw, min_events, min_ms))


# ---------------------------------------------------------------- metrics

def measure(blocks: List[Dict]) -> Dict:
    if not blocks:
        return {}
    ns = sorted(b["n_events"] for b in blocks)
    per_session = collections.Counter(b["session_id"] for b in blocks)
    return {
        "blocks": len(blocks),
        "median_events": statistics.median(ns),
        "mean_events": round(sum(ns) / len(ns), 2),
        "one_event": sum(1 for b in blocks if b["n_events"] == 1),
        "zero_duration": sum(1 for b in blocks if b["dur_ms"] == 0),
        "empty_surface": sum(1 for b in blocks if b["surface"] in ("app:", "app:None")),
        "malformed_surface": sum(1 for b in blocks
                                 if b["surface"].startswith("web:")
                                 and b["surface"].count("http") > 1),
        "absorbed": sum(b["absorbed_excursions"] for b in blocks),
        "blocks_per_session_median": statistics.median(per_session.values()),
    }


def surface_purity(rows_by_session: Dict[str, List[Dict]], blocks: List[Dict]) -> float:
    """Share of user-layer events sitting in a block whose surface key matches their own.

    Capture events (L1/SYSTEM) are excluded: they are surface-transparent by design, so
    counting them would penalise the very rule that fixes them.
    """
    by_session: Dict[str, List[Dict]] = {}
    for b in blocks:
        by_session.setdefault(b["session_id"], []).append(b)
    agree = total = 0
    for sid, bl in by_session.items():
        rows = rows_by_session.get(sid, [])
        i = 0
        for r in rows:
            while i + 1 < len(bl) and r["ts_ms"] > bl[i]["end_ms"]:
                i += 1
            if B.is_capture_event(r) or not B.has_discriminator(r):
                continue
            total += 1
            if B.surface_key(r) == bl[i]["surface"]:
                agree += 1
    return round(agree / total, 4) if total else 0.0


def fragmentation(blocks: List[Dict], max_lag: int = 12) -> float:
    """Share of returns_to edges at lag 2 — the A|x|A split signature."""
    by_session: Dict[str, List[Dict]] = {}
    for b in blocks:
        by_session.setdefault(b["session_id"], []).append(b)
    lag2 = tot = 0
    for bl in by_session.values():
        g = G.build_graph(bl, max_lag=max_lag)
        for (_s, rel, _d, a) in g["edges"]:
            if rel == G.RETURNS_TO:
                tot += 1
                if a.get("lag") == 2:
                    lag2 += 1
    return round(lag2 / tot, 4) if tot else 0.0


def short_work_at_risk(blocks: List[Dict], min_ms: int) -> int:
    """Brief blocks on a different application from BOTH neighbours.

    These are the ones a more aggressive absorption threshold would destroy, and they
    are the reason the sweep is not decided by block count alone.
    """
    by_session: Dict[str, List[Dict]] = {}
    for b in blocks:
        by_session.setdefault(b["session_id"], []).append(b)
    n = 0
    for bl in by_session.values():
        for i, b in enumerate(bl):
            if b["dur_ms"] >= min_ms:
                continue
            prev_app = bl[i - 1]["app"] if i else None
            next_app = bl[i + 1]["app"] if i + 1 < len(bl) else None
            if b["app"] and b["app"] != prev_app and b["app"] != next_app:
                n += 1
    return n


# ---------------------------------------------------------------- driver

def main() -> int:
    if not os.path.isdir(DATASET):
        print("dataset_b not present — E01 cannot run.")
        return 0
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()

    rows_now = _load(DATASET)
    rows_no_cf = _load_without_carry_forward(DATASET)
    samples: List[Dict] = []

    # ---- ablation -------------------------------------------------------
    ablation = []

    def arm(name: str, note: str, blocks: List[Dict], rows_src: Dict[str, List[Dict]]):
        m = measure(blocks)
        m["arm"], m["note"] = name, note
        m["surface_purity"] = surface_purity(rows_src, blocks)
        ablation.append(m)
        samples.append({"kind": "ablation", **m})

    # A0: everything off — legacy route_of, legacy surface_key, no R1/R2, no carry-forward
    orig_route, orig_key = N.route_of, B.surface_key
    try:
        N.route_of = _legacy_route_of                       # type: ignore[assignment]
        rows_legacy = _load_without_carry_forward(DATASET)
        B.surface_key = _legacy_surface_key                 # type: ignore[assignment]
        blks = [b for s in rows_legacy.values() for b in _legacy_build_blocks(s)]
        arm("A0 baseline", "pre-Phase-0 behaviour", blks, rows_legacy)

        # A1: + R5 route_of fix
        N.route_of = orig_route                             # type: ignore[assignment]
        rows_r5 = _load_without_carry_forward(DATASET)
        blks = [b for s in rows_r5.values() for b in _legacy_build_blocks(s)]
        arm("A1 +R5", "route_of returns a path, not the origin", blks, rows_r5)
    finally:
        N.route_of, B.surface_key = orig_route, orig_key    # type: ignore[assignment]

    # A2: + R4 structural surface_key (still no R1/R2, no carry-forward)
    blks = [b for s in rows_no_cf.values() for b in _legacy_build_blocks(s)]
    arm("A2 +R4", "surface type from origin presence; BROWSERS deleted", blks, rows_no_cf)

    # A3: + R1/R2 capture and undiscriminated transparency
    blks = [b for s in rows_no_cf.values() for b in B.build_blocks(s)]
    arm("A3 +R1+R2", "L1/SYSTEM and no-discriminator rows cannot open a block",
        blks, rows_no_cf)

    # A4: + R3 tab carry-forward  == the shipped pipeline
    blks = [b for s in rows_now.values() for b in B.build_blocks(s)]
    arm("A4 +R3 (shipped)", "active_browser_tab carried forward within an app",
        blks, rows_now)

    # ---- sweep ----------------------------------------------------------
    sweep = []
    for me in MIN_EVENTS_GRID:
        for ms in MIN_MS_GRID:
            blks = [b for s in rows_now.values() for b in B.build_blocks(s, me, ms)]
            m = measure(blks)
            m.update({
                "min_events": me, "min_ms": ms,
                "surface_purity": surface_purity(rows_now, blks),
                "fragmentation_lag2": fragmentation(blks),
                "short_work_at_risk": short_work_at_risk(blks, ms),
            })
            sweep.append(m)
            samples.append({"kind": "sweep", **m})

    # stability: max relative block-count change against grid neighbours
    idx = {(c["min_events"], c["min_ms"]): c for c in sweep}
    for c in sweep:
        me, ms = c["min_events"], c["min_ms"]
        nbrs = []
        for g, val, other in ((MIN_EVENTS_GRID, me, "e"), (MIN_MS_GRID, ms, "m")):
            p = g.index(val)
            for q in (p - 1, p + 1):
                if 0 <= q < len(g):
                    key = (g[q], ms) if other == "e" else (me, g[q])
                    nbrs.append(idx[key]["blocks"])
        c["stability"] = round(max(abs(n - c["blocks"]) / c["blocks"] for n in nbrs), 4)

    metrics = {"ablation": ablation, "sweep": sweep,
               "elapsed_s": round(time.time() - t0, 1)}

    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    config = {
        "exp_id": "E01-block-sweep",
        "hypothesis": ("Block degeneracy is caused by identifiable perception defects, not "
                       "by absorption thresholds; once the defects are fixed the threshold "
                       "choice is a plateau rather than a cliff."),
        "dataset": "dataset_b",
        "note": ("dataset_b is the VALIDATION dataset here, not the source of any rule. "
                 "Every rule under test is keyed on a DATA_SCHEMA.md property and runs "
                 "unchanged on any conforming dataset."),
        "arms": [a["arm"] for a in ablation],
        "grid": {"min_events": MIN_EVENTS_GRID, "min_ms": MIN_MS_GRID},
        "params": {"window": 5, "max_lag": 12},
        "git_sha": sha, "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    for name, obj in (("config.json", config), ("metrics.json", metrics)):
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "samples.jsonl"), "w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    # ---- console tables -------------------------------------------------
    print("\nABLATION")
    h = f"{'arm':<18}{'blocks':>7}{'med':>5}{'mean':>7}{'1-ev':>6}{'0-dur':>7}{'empty':>7}{'malf':>6}{'purity':>8}"
    print(h); print("-" * len(h))
    for a in ablation:
        print(f"{a['arm']:<18}{a['blocks']:>7}{a['median_events']:>5}{a['mean_events']:>7}"
              f"{a['one_event']:>6}{a['zero_duration']:>7}{a['empty_surface']:>7}"
              f"{a['malformed_surface']:>6}{a['surface_purity']:>8}")

    print("\nSWEEP")
    h = (f"{'min_ev':>7}{'min_ms':>8}{'blocks':>8}{'med':>5}{'mean':>7}{'1-ev':>6}"
         f"{'purity':>8}{'frag':>8}{'risk':>6}{'stab':>7}")
    print(h); print("-" * len(h))
    for c in sweep:
        print(f"{c['min_events']:>7}{c['min_ms']:>8}{c['blocks']:>8}{c['median_events']:>5}"
              f"{c['mean_events']:>7}{c['one_event']:>6}{c['surface_purity']:>8}"
              f"{c['fragmentation_lag2']:>8}{c['short_work_at_risk']:>6}{c['stability']:>7}")
    print(f"\nwrote {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
