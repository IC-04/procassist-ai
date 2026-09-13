"""Build the perception + TEKG layer for a dataset. No LLM involved."""
from __future__ import annotations
import json, os, sys, time, argparse, logging, collections
from typing import Dict, List

from . import normalise as N, blocks as B, tekg as G, context as C, schemas as S

log = logging.getLogger("procmine")


class ArtifactInvalid(RuntimeError):
    """An artifact failed its DATA_CONTRACT check. Never downgraded to a warning."""


def _check(problems: List[str], what: str) -> None:
    if problems:
        for p in problems[:10]:
            log.error("%s: %s", what, p)
        raise ArtifactInvalid(f"{what}: {len(problems)} contract violation(s); first: {problems[0]}")


def _tekg_document(session_id: str, graph: Dict) -> Dict:
    """Graph -> the DATA_CONTRACT.md §3 document, deterministically ordered.

    Edges are sorted by (src, rel, dst) so two runs diff clean (TEKG_SPEC.md §7).
    The in-memory `index` (whole block dicts) is deliberately not serialised.
    """
    edges = [
        {"src": s, "rel": r, "dst": d,
         "lag": a.get("lag"), "gap_ms": a.get("gap_ms"), "n": a.get("n")}
        for (s, r, d, a) in graph["edges"]
    ]
    edges.sort(key=lambda e: (e["src"], e["rel"], e["dst"]))
    return {"session_id": session_id, "nodes": list(graph["nodes"]), "edges": edges}


def build(dataset_root: str, out_root: str, window: int = 5, min_events: int = 3,
          min_ms: int = 1500, max_lag: int = 12, write_windows: bool = True) -> dict:
    """Run the deterministic pipeline over one dataset and write its artifacts."""
    t0 = time.time()
    os.makedirs(out_root, exist_ok=True)
    os.makedirs(os.path.join(out_root, "tekg"), exist_ok=True)
    all_blocks: List[Dict] = []
    all_stats: List[Dict] = []
    payload_count = 0
    edge_counter: collections.Counter = collections.Counter()
    dataflow_edges = 0

    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        rows = N.load_session(sdir)
        if not rows:
            log.warning("%s: no events, skipped", sid)
            continue
        blks = B.build_blocks(rows, min_events=min_events, min_ms=min_ms)
        graph = G.build_graph(blks, max_lag=max_lag)
        dataflow_edges += G.attach_dataflow(graph, rows, blks)
        edge_counter.update(G.edge_summary(graph))

        doc = _tekg_document(sid, graph)
        _check(S.validate_tekg(doc, max_lag=max_lag), f"tekg/{sid}")
        with open(os.path.join(out_root, "tekg", f"{sid}.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)

        if write_windows:
            wdir = os.path.join(out_root, "windows", sid)
            os.makedirs(wdir, exist_ok=True)
            for i in range(1, len(blks)):
                ev = G.local_evidence(graph, blks[i]["idx"], blks, window=window)
                p = C.build_payload(ev, sid)
                if not p:
                    continue
                _check(S.validate_window_payload(p), f"windows/{sid}/w{i:04d}")
                with open(os.path.join(wdir, f"w{i:04d}.json"), "w", encoding="utf-8") as fh:
                    json.dump(p, fh, ensure_ascii=False, indent=1)
                payload_count += 1

        all_blocks.extend(blks)
        all_stats.append({"session": sid, "events": len(rows), **B.block_stats(blks)})
        log.info("%s: %d events -> %d blocks", sid, len(rows), len(blks))

    _check(S.validate_blocks(all_blocks), "blocks.jsonl")
    with open(os.path.join(out_root, "blocks.jsonl"), "w", encoding="utf-8") as fh:
        for b in all_blocks:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")

    n_events = sum(s["events"] for s in all_stats)
    summary = {
        "dataset": dataset_root,
        "params": {"window": window, "min_events": min_events, "min_ms": min_ms,
                   "max_lag": max_lag},
        "sessions": len(all_stats),
        "events": n_events,
        "blocks": len(all_blocks),
        "noise_blocks": sum(1 for b in all_blocks if b["is_noise"]),
        "compression_events_per_block": round(n_events / max(1, len(all_blocks)), 1),
        "one_event_blocks": sum(1 for b in all_blocks if b["n_events"] == 1),
        "zero_duration_blocks": sum(1 for b in all_blocks if b["dur_ms"] == 0),
        "empty_surface_blocks": sum(1 for b in all_blocks
                                    if b["surface"] in ("app:", "app:None")),
        "absorbed_excursions": sum(b["absorbed_excursions"] for b in all_blocks),
        "reasoner_windows": payload_count,
        "dataflow_edges": dataflow_edges,
        "edges_by_type": dict(edge_counter),
        "per_session": all_stats,
    }
    with open(os.path.join(out_root, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    log.info("wrote %s in %.1fs", out_root, time.time() - t0)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="procmine")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--window", type=int, default=5, help="blocks either side of the centre")
    ap.add_argument("--min-events", type=int, default=3,
                    help="excursion shorter than this many events may be absorbed")
    ap.add_argument("--min-ms", type=int, default=1500,
                    help="excursion shorter than this many ms may be absorbed")
    ap.add_argument("--max-lag", type=int, default=12, help="TEKG locality bound")
    ap.add_argument("--no-windows", action="store_true",
                    help="skip reasoner payloads (parameter sweeps do not need them)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")

    root = a.dataset.rstrip("/")
    # Dataset readiness probe (PHASE_0.md Task 0.5). Absent data is a reportable state,
    # not a crash and not an empty artifact: writing a `sessions: 0` summary would be
    # fabricating a result for a dataset we never saw (CLAUDE.md §5).
    if not os.path.isdir(root) or not any(N.iter_session_dirs(root)):
        name = os.path.basename(root)
        why = "not present" if not os.path.isdir(root) else "contains no ses_* directories"
        print(f"{name} {why} — Phase 1 blocked. No artifacts written.")
        return 0

    out = a.out or os.path.join("build", os.path.basename(root))
    try:
        s = build(root, out, window=a.window, min_events=a.min_events, min_ms=a.min_ms,
                  max_lag=a.max_lag, write_windows=not a.no_windows)
    except ArtifactInvalid as e:
        print(f"ARTIFACT CONTRACT VIOLATION: {e}", file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in s.items() if k != "per_session"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
