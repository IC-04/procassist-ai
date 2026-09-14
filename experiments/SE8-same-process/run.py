#!/usr/bin/env python3
"""S-E8 — consecutive executions of the SAME process: the case Dataset A cannot test.

`EVALUATION_PROTOCOL.md` §8: **0 of 1,689** consecutive execution pairs in A share a process
code. So every accuracy figure in this project was measured on a dataset where the segmenter
never had to split two adjacent executions of the same process — the hardest boundary there is,
because no surface changes, no application changes and no route changes across it.

This records what the frozen system does on B, where no ground truth exists. It is a documented
limitation, not a licence to change anything: nothing here modifies the pipeline.
"""
from __future__ import annotations
import collections, datetime as dt, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from procmine import normalise as N, blocks as BK, identity as ID     # noqa: E402


def ms(t):
    return int(dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def main() -> int:
    segs = [json.loads(l) for l in open(os.path.join(ROOT, "segments.jsonl"), encoding="utf-8")]
    by = collections.defaultdict(list)
    for s in segs:
        by[s["session_id"]].append(s)
    for v in by.values():
        v.sort(key=lambda s: s["start"])

    rows, blocks = {}, {}
    for sd in N.iter_session_dirs(os.path.join(ROOT, "dataset_b")):
        sid = os.path.basename(sd)
        r = N.load_session(sd)
        if r:
            rows[sid], blocks[sid] = r, BK.build_blocks(r)

    consecutive = 0
    same = []
    gaps = []
    for sid, v in by.items():
        for a, b in zip(v, v[1:]):
            consecutive += 1
            gaps.append(ms(b["start"]) - ms(a["end"]))
            if a["label"] == b["label"]:
                ra = ID.represent({"session_id": sid, "start_ms": ms(a["start"]),
                                   "end_ms": ms(a["end"])}, rows[sid], blocks[sid])
                rb = ID.represent({"session_id": sid, "start_ms": ms(b["start"]),
                                   "end_ms": ms(b["end"])}, rows[sid], blocks[sid])
                sa, sb = set(ra["where"]["surface_set"]), set(rb["where"]["surface_set"])
                same.append({
                    "session_id": sid, "label": a["label"],
                    "gap_ms": ms(b["start"]) - ms(a["end"]),
                    "surface_jaccard": round(len(sa & sb) / max(1, len(sa | sb)), 3),
                    "identical_surface_sets": sa == sb,
                    "a": {"start": a["start"], "end": a["end"], "surfaces": sorted(sa)[:3]},
                    "b": {"start": b["start"], "end": b["end"], "surfaces": sorted(sb)[:3]},
                })

    out = {
        "_status": "OBSERVATION ON DATASET B. No ground truth exists here: this records what "
                   "the frozen system DOES, never that it is correct.",
        "_why": "Dataset A contains 0 of 1,689 consecutive same-process pairs, so the case was "
                "untestable on the dataset every accuracy number comes from.",
        "n_segments": len(segs), "n_sessions": len(by),
        "n_consecutive_pairs": consecutive,
        "n_consecutive_same_label": len(same),
        "rate": round(len(same) / max(1, consecutive), 4),
        "n_with_identical_surface_sets": sum(1 for s in same if s["identical_surface_sets"]),
        "median_gap_ms_all_pairs": sorted(gaps)[len(gaps) // 2] if gaps else None,
        "median_gap_ms_same_label": (sorted(s["gap_ms"] for s in same)[len(same) // 2]
                                     if same else None),
        "examples": same[:5],
    }
    json.dump(out, open(os.path.join(HERE, "metrics.json"), "w"), indent=2, ensure_ascii=False)
    with open(os.path.join(HERE, "samples.jsonl"), "w", encoding="utf-8") as fh:
        for s in same:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "examples"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
