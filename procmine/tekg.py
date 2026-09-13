"""Stage C — Temporal Execution Knowledge Graph (TEKG).

PURPOSE (read this before extending):
  The TEKG is NOT an inference engine. Connected components are NOT
  executions -- that formulation was tested and rejected. The graph exists
  to do two things well:

    1. build rich, typed, *local* evidence for the reasoner's prompt
    2. explain a decision afterwards ("these edges are why")

  Every edge below is deterministic and traceable to a log field.
"""
from __future__ import annotations
import collections, itertools
from typing import Dict, List, Tuple

# ---- typed edges -------------------------------------------------------
NEXT            = "temporal_next"      # b_i -> b_{i+1}
SAME_SURFACE    = "same_surface_as"    # non-adjacent, same surface
SAME_ROUTE      = "same_route_as"      # same business function
SAME_ORIGIN     = "same_system_as"     # same backend system
SAME_FIELD      = "same_field_as"      # same stable form field
SHARED_VALUE    = "shared_value_with"  # same dataflow value hash
DATAFLOW        = "dataflow_to"        # explicit copy -> paste lineage
RETURNS_TO      = "returns_to"         # A ... X ... A pattern


def build_graph(blocks: List[Dict], max_lag: int = 12) -> Dict:
    """Return {"nodes": [...], "edges": [(src, rel, dst, attrs)]}.

    `max_lag` bounds non-adjacent edges to a local window: a relation
    between blocks 200 apart is not evidence about an execution, it is a
    coincidence. This is the hub-control the earlier review demanded.
    """
    edges: List[Tuple[str, str, str, Dict]] = []
    by_id = {b["block_id"]: b for b in blocks}

    # sequential spine
    for a, b in zip(blocks, blocks[1:]):
        if a["session_id"] != b["session_id"]:
            continue
        gap = max(0, b["start_ms"] - a["end_ms"])
        edges.append((a["block_id"], NEXT, b["block_id"], {"gap_ms": gap}))

    # local relational edges
    for i, a in enumerate(blocks):
        for j in range(i + 1, min(i + 1 + max_lag, len(blocks))):
            b = blocks[j]
            if a["session_id"] != b["session_id"]:
                break
            lag = j - i
            if a["surface"] == b["surface"]:
                edges.append((a["block_id"], SAME_SURFACE, b["block_id"], {"lag": lag}))
                if lag > 1:
                    edges.append((a["block_id"], RETURNS_TO, b["block_id"], {"lag": lag}))
            else:
                if a["route"] and a["route"] == b["route"]:
                    edges.append((a["block_id"], SAME_ROUTE, b["block_id"], {"lag": lag}))
                if a["origin"] and a["origin"] == b["origin"]:
                    edges.append((a["block_id"], SAME_ORIGIN, b["block_id"], {"lag": lag}))
            shared_f = set(a["field_keys"]) & set(b["field_keys"])
            if shared_f:
                edges.append((a["block_id"], SAME_FIELD, b["block_id"],
                              {"lag": lag, "n": len(shared_f)}))
            shared_v = set(a["value_hashes"]) & set(b["value_hashes"])
            if shared_v:
                edges.append((a["block_id"], SHARED_VALUE, b["block_id"],
                              {"lag": lag, "n": len(shared_v)}))

    # explicit dataflow lineage (source_event_id -> containing block)
    ev2blk: Dict[str, str] = {}
    # (populated by caller via attach_dataflow if event-level ids are kept)
    return {"nodes": list(by_id.keys()), "edges": edges, "index": by_id}


def attach_dataflow(graph: Dict, rows: List[Dict], blocks: List[Dict]) -> int:
    """Add DATAFLOW edges using extensions.dataflow_v2.source_event_id.

    Coverage is low by design (~4% of events). Treated as a WEAK feature,
    never as an identity mechanism.
    """
    ev2blk: Dict[str, str] = {}
    bi = 0
    for r in rows:
        while bi + 1 < len(blocks) and r["ts_ms"] > blocks[bi]["end_ms"]:
            bi += 1
        ev2blk[r["event_id"]] = blocks[bi]["block_id"]
    added = 0
    for r in rows:
        src = r.get("dataflow_src")
        if src and src in ev2blk:
            a, b = ev2blk[src], ev2blk[r["event_id"]]
            if a != b:
                graph["edges"].append((a, DATAFLOW, b, {"op": r.get("dataflow_op", "")}))
                added += 1
    return added


def local_evidence(graph: Dict, center_idx: int, blocks: List[Dict],
                   window: int = 5) -> Dict:
    """Typed evidence around a candidate transition -> reasoner payload.

    Returns only edges whose BOTH endpoints are inside the window, so the
    prompt never references a block the model cannot see.
    """
    lo = max(0, center_idx - window)
    hi = min(len(blocks), center_idx + window + 1)
    win = blocks[lo:hi]
    ids = {b["block_id"] for b in win}
    ev = [
        {"src": s, "rel": r, "dst": d, **a}
        for (s, r, d, a) in graph["edges"]
        if s in ids and d in ids and r != NEXT
    ]
    return {"window": win, "evidence": ev, "center_idx": center_idx}


def edge_summary(graph: Dict) -> Dict:
    return dict(collections.Counter(r for (_, r, _, _) in graph["edges"]).most_common())
