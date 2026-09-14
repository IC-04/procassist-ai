#!/usr/bin/env python3
"""S-E6 step 0 — materialise the FROZEN S-E4 segmentation, once.

G-A0 contract: every identity arm operates on the exact segmentation S-E4 produced. This
script reproduces it by running the identical LOSO chain (fit -> percentile calibrate ->
gate -> decode) and caches the result, so no arm can accidentally re-segment.

It also records the frozen boundary metrics. `run.py` asserts every arm reproduces them
byte-identically; if one does not, that is a contract violation, not a result.

Output: build/dataset_a/se6_frozen.pkl (gitignored).
"""
from __future__ import annotations
import bisect, collections, os, pickle, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from procmine import (normalise as N, blocks as B, gt as GT, candidates as CA,   # noqa: E402
                      score as SC, gate as GA, decoder as DE, evaluate as EV)

DATASET = os.path.join(ROOT, "dataset_a")
GT_DIR = os.path.join(ROOT, "build", "dataset_a")
OUT = os.path.join(GT_DIR, "se6_frozen.pkl")
TAUS = [1000, 2000, 5000, 10000]
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


def labels_of(cands, gts, tau=TAU_LABEL):
    g = sorted(gts)
    return [1 if (c.get("at_ms") is not None and nearest(g, c["at_ms"]) <= tau) else 0
            for c in cands]


def main() -> int:
    if not os.path.isdir(DATASET):
        print("dataset_a not present — S-E6 cannot run.")
        return 0
    t0 = time.time()
    C = [json.loads(l) for l in open(f"{GT_DIR}/executions_canonical.jsonl", encoding="utf-8")]
    ref = collections.defaultdict(lambda: {"intervals": [], "labels": [], "canonical": []})
    gtb, gtb_clean = collections.defaultdict(list), collections.defaultdict(list)
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
        world[sid] = {"rows": rows, "blocks": blks, "cands": CA.generate(rows, blks)}
    sessions = sorted(world)
    print(f"world built in {time.time()-t0:.0f}s  sessions={len(sessions)}", flush=True)

    scored = {}
    for held in sessions:
        tr_c, tr_y = [], []
        for s in sessions:
            if s == held:
                continue
            tr_c += world[s]["cands"]
            tr_y += labels_of(world[s]["cands"], gtb_clean.get(s, []))
        scored[held] = SC.fit(tr_c, tr_y).apply(world[held]["cands"])
    print(f"LOSO scored in {time.time()-t0:.0f}s", flush=True)

    pooled = []
    for s in sessions:
        pooled += [dict(c, session_id=s) for c in scored[s]]
    cal = SC.calibrate(pooled, "percentile")
    by = collections.defaultdict(list)
    for c in cal:
        by[c["session_id"]].append(c)

    all_segs, hyp = [], {}
    for s in sessions:
        r = GA.route(sorted(by[s], key=lambda x: x["at_seq"]))
        segs = DE.decode_session(r, {})
        for x in segs:
            x["session_id"] = s
        all_segs += segs
        hyp[s] = {"intervals": [(x["start_ms"], x["end_ms"]) for x in segs],
                  "labels": ["seg"] * len(segs)}

    cfg = {"taus_ms": TAUS, "kappas": [1, 2, 5, 10], "ious": [0.3, 0.5, 0.7],
           "timelines": {s: [r["ts_ms"] for r in world[s]["rows"]] for s in sessions}}
    frozen_metrics = EV.evaluate_all(dict(ref), hyp, cfg)["overall"]

    with open(OUT, "wb") as fh:
        pickle.dump({
            "segments": all_segs,
            "ref": dict(ref),
            "gtb": dict(gtb),
            "rows": {s: world[s]["rows"] for s in sessions},
            "blocks": {s: world[s]["blocks"] for s in sessions},
            "cands": {s: cal_s for s, cal_s in by.items()},
            "frozen_boundary": frozen_metrics["boundary_time"],
            "frozen_count_ratio": frozen_metrics["count_ratio"],
            "sessions": sessions,
        }, fh, protocol=4)
    print(f"wrote {OUT}  segments={len(all_segs)}  "
          f"bF1@2s={frozen_metrics['boundary_time']['2000']['f1']}  "
          f"ratio={frozen_metrics['count_ratio']}  ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
