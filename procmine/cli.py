"""Build the perception + TEKG layer for a dataset. No LLM involved."""
from __future__ import annotations
import json, os, sys, argparse, collections
from . import normalise as N, blocks as B, tekg as G, context as C


def build(dataset_root: str, out_root: str, window: int = 5) -> dict:
    os.makedirs(out_root, exist_ok=True)
    all_blocks, all_stats, payload_count = [], [], 0
    edge_counter = collections.Counter()
    dataflow_edges = 0

    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        rows = N.load_session(sdir)
        if not rows:
            continue
        blks = B.build_blocks(rows)
        graph = G.build_graph(blks)
        dataflow_edges += G.attach_dataflow(graph, rows, blks)
        edge_counter.update(G.edge_summary(graph))

        os.makedirs(os.path.join(out_root, "windows", sid), exist_ok=True)
        for i in range(1, len(blks)):
            ev = G.local_evidence(graph, blks[i]["idx"], blks, window=window)
            p = C.build_payload(ev, sid)
            if not p:
                continue
            with open(os.path.join(out_root, "windows", sid, f"w{i:04d}.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(p, fh, ensure_ascii=False, indent=1)
            payload_count += 1

        all_blocks.extend(blks)
        all_stats.append({"session": sid, "events": len(rows), **B.block_stats(blks)})

    with open(os.path.join(out_root, "blocks.jsonl"), "w", encoding="utf-8") as fh:
        for b in all_blocks:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")

    summary = {
        "dataset": dataset_root,
        "sessions": len(all_stats),
        "events": sum(s["events"] for s in all_stats),
        "blocks": len(all_blocks),
        "noise_blocks": sum(1 for b in all_blocks if b["is_noise"]),
        "compression_events_per_block": round(
            sum(s["events"] for s in all_stats) / max(1, len(all_blocks)), 1),
        "reasoner_windows": payload_count,
        "dataflow_edges": dataflow_edges,
        "edges_by_type": dict(edge_counter),
        "per_session": all_stats,
    }
    with open(os.path.join(out_root, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(prog="procmine")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--window", type=int, default=5)
    a = ap.parse_args(argv)
    out = a.out or os.path.join("build", os.path.basename(a.dataset.rstrip("/")))
    s = build(a.dataset, out, a.window)
    print(json.dumps({k: v for k, v in s.items() if k != "per_session"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
