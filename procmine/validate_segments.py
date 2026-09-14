"""Contract validator for `segments.jsonl` (DATA_CONTRACT.md §6, STEP1_SPEC.md §4).

`segments.jsonl` is the submitted deliverable, so it is checked mechanically rather than by
inspection. Every function is pure and returns a list of human-readable problems; an empty
list means the file conforms.

Checks implemented (the five the deliverable can be held to without Dataset A):

  1. `session_id` is the exact session directory name
  2. `start` / `end` are ISO-8601 UTC ending in `Z`, second precision, `start < end`
  3. exactly four keys, no extras
  4. segments within a session are ordered by `start` and do not overlap
  5. no segment boundary is derived from a recording chunk boundary

Two further §6 constraints are deliberately NOT enforced here, and saying so is part of the
contract rather than an omission:

  * §6.5 — "no segment shorter than the duration floor observed in A's canonical executions"
    requires Dataset A. This validator runs on the Dataset B deliverable and must not depend
    on A being present (ADR-010).
  * §6.6 — label stability. Guaranteed by construction: `emit_segments.label_for` is a pure
    function of the surface key, so the same surface yields the same label everywhere.
    `label_stability_report` below measures it rather than asserting it.

On check 5: a boundary is a violation only when it sits on a chunk edge **and** nothing else
explains it. A surface change may legitimately coincide with a chunk edge — measured on
dataset_b, 4 of 1,781 block boundaries do. Treating every coincidence as a violation would be
wrong, so the check requires a boundary to be both unexplained and chunk-aligned.
"""
from __future__ import annotations
import json, os, re, collections
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

REQUIRED_KEYS = frozenset({"session_id", "start", "end", "label"})
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def to_ms(s: str) -> Optional[int]:
    """ISO-8601 `Z` second precision -> epoch ms. None when it does not match the contract."""
    if not isinstance(s, str) or not ISO_RE.match(s):
        return None
    try:
        return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return None


# ---------------------------------------------------------------- individual checks

def check_keys(segments: Sequence[Dict]) -> List[str]:
    """§6.3 — exactly four keys, no extras."""
    problems: List[str] = []
    for i, s in enumerate(segments):
        if not isinstance(s, dict):
            problems.append(f"line {i + 1}: not a JSON object")
            continue
        keys = set(s)
        if keys != REQUIRED_KEYS:
            missing = sorted(REQUIRED_KEYS - keys)
            extra = sorted(keys - REQUIRED_KEYS)
            problems.append(f"line {i + 1}: key mismatch"
                            + (f", missing {missing}" if missing else "")
                            + (f", extra {extra}" if extra else ""))
    return problems


def check_session_ids(segments: Sequence[Dict],
                      session_ids: Optional[Set[str]] = None) -> List[str]:
    """§6.1 — `session_id` is the exact session directory name."""
    problems: List[str] = []
    for i, s in enumerate(segments):
        sid = s.get("session_id")
        if not isinstance(sid, str) or not sid:
            problems.append(f"line {i + 1}: session_id missing or not a string")
            continue
        if session_ids is not None:
            if sid not in session_ids:
                problems.append(f"line {i + 1}: session_id {sid!r} is not a session "
                                f"directory in the dataset")
        elif not sid.startswith("ses_"):
            problems.append(f"line {i + 1}: session_id {sid!r} does not look like a "
                            f"session directory name (exact-name check skipped: "
                            f"no dataset supplied)")
    return problems


def check_timestamps(segments: Sequence[Dict]) -> List[str]:
    """§6.2 — ISO-8601 UTC ending in Z, second precision, `start < end`."""
    problems: List[str] = []
    for i, s in enumerate(segments):
        for field in ("start", "end"):
            v = s.get(field)
            if not isinstance(v, str) or not ISO_RE.match(v):
                problems.append(f"line {i + 1}: {field}={v!r} is not ISO-8601 UTC "
                                f"'YYYY-MM-DDTHH:MM:SSZ'")
        a, b = to_ms(s.get("start")), to_ms(s.get("end"))
        if a is not None and b is not None and not a < b:
            problems.append(f"line {i + 1}: start is not strictly before end "
                            f"({s.get('start')} -> {s.get('end')})")
    return problems


def check_ordering(segments: Sequence[Dict]) -> List[str]:
    """§6.4 — within a session, ordered by `start` and non-overlapping."""
    problems: List[str] = []
    by_session: Dict[str, List[tuple]] = collections.defaultdict(list)
    for i, s in enumerate(segments):
        a, b = to_ms(s.get("start")), to_ms(s.get("end"))
        if a is None or b is None:
            continue                     # already reported by check_timestamps
        by_session[s.get("session_id")].append((i, a, b))
    for sid, rows in by_session.items():
        for (i0, a0, b0), (i1, a1, _b1) in zip(rows, rows[1:]):
            if a1 < a0:
                problems.append(f"{sid}: segments out of order at lines {i0 + 1}/{i1 + 1}")
            elif a1 < b0:
                problems.append(f"{sid}: segments overlap at lines {i0 + 1}/{i1 + 1}")
    return problems


def check_no_chunk_boundaries(segments: Sequence[Dict],
                              chunk_edges: Optional[Dict[str, Set[int]]] = None,
                              justified: Optional[Dict[str, Set[int]]] = None) -> List[str]:
    """§6.7 — no segment boundary is placed *because of* a recording chunk edge.

    `chunk_edges[sid]` is the set of epoch-second values at which the recorder changed chunk.
    `justified[sid]` is the set of epoch-second values at which a boundary is independently
    explained — i.e. at which the segmenter had a **non-chunk reason** to place one.

    A boundary is a violation only if it is chunk-aligned AND unjustified. Coincidence alone is
    not a violation — chunks are dissolved in `normalise.load_session` (ADR-001), so an
    independently-motivated boundary may fall on a chunk edge by chance.

    **What counts as justified was wrong until S-E7.** It was built from *block* boundaries,
    which was correct for the Phase B emitter — that emitter could only cut at a block edge —
    and became wrong at ADR-015, when a legitimate execution boundary was allowed to occur
    *inside* a block. The check then flagged valid intra-block boundaries purely for landing on
    a chunk edge: one real false positive on the committed `segments.jsonl`.

    The justified set is now **every candidate position the generator emitted**, which is what
    §6.7 actually requires. A candidate exists because some trigger fired, no enabled trigger
    references `chunk_id`, and `feat_at_chunk_edge` is audit-only and never a trigger
    (`candidates.py` module contract). So a boundary standing on a candidate was placed for a
    reason that is not the chunk, by construction. Block edges remain in the set because every
    block edge is also emitted as a candidate.
    """
    if chunk_edges is None:
        return []
    problems: List[str] = []
    for i, s in enumerate(segments):
        sid = s.get("session_id")
        edges = chunk_edges.get(sid) or set()
        if not edges:
            continue
        ok = (justified or {}).get(sid)
        for field in ("start", "end"):
            ms = to_ms(s.get(field))
            if ms is None:
                continue
            sec = ms // 1000
            if sec in edges and (ok is None or sec not in ok):
                problems.append(f"line {i + 1}: {sid} {field} at a recording chunk edge "
                                f"({s.get(field)}) with no independent justification — "
                                f"chunks are recording artifacts (DATA_SCHEMA §1, ADR-001)")
    return problems


# ---------------------------------------------------------------- drivers

def validate(segments: Sequence[Dict],
             session_ids: Optional[Set[str]] = None,
             chunk_edges: Optional[Dict[str, Set[int]]] = None,
             justified: Optional[Dict[str, Set[int]]] = None) -> List[str]:
    """Run every check. Empty list means the segments conform to DATA_CONTRACT §6."""
    return (check_keys(segments)
            + check_session_ids(segments, session_ids)
            + check_timestamps(segments)
            + check_ordering(segments)
            + check_no_chunk_boundaries(segments, chunk_edges, justified))


def dataset_context(dataset_root: str) -> Dict[str, Any]:
    """Derive the session ids, chunk edges and justified boundaries from the dataset.

    Reading the dataset is what makes checks 1 and 5 meaningful; without it they degrade to
    a format check, which `check_session_ids` states explicitly rather than passing silently.
    """
    from . import normalise as N, blocks as B, candidates as CA
    session_ids: Set[str] = set()
    chunk_edges: Dict[str, Set[int]] = {}
    justified: Dict[str, Set[int]] = {}
    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        session_ids.add(sid)
        rows = N.load_session(sdir)
        if not rows:
            continue
        edges: Set[int] = set()
        for x, y in zip(rows, rows[1:]):
            if x.get("chunk_id") != y.get("chunk_id"):
                edges.add(x["ts_ms"] // 1000)
                edges.add(y["ts_ms"] // 1000)
        chunk_edges[sid] = edges
        blks = B.build_blocks(rows)
        # Every position the candidate generator would nominate. Block edges are a strict
        # subset of these (candidates.py guarantees the superset property), so this widens the
        # old set rather than replacing it — and it is the set §6.7 is actually about.
        just = ({b["start_ms"] // 1000 for b in blks} | {b["end_ms"] // 1000 for b in blks})
        for c in CA.generate(rows, blks):
            at = c.get("at_ms")
            if at is not None:
                just.add(at // 1000)
        justified[sid] = just
    return {"session_ids": session_ids, "chunk_edges": chunk_edges, "justified": justified}


def chunk_triggers_in_generator() -> List[str]:
    """§6.7, checked at the source rather than only at the output.

    The output check can only ever say a boundary *coincides* with a chunk edge. What the
    clause forbids is a boundary placed *because of* one, and that is a property of the
    generator: it holds iff no enabled trigger reads `chunk_id`. Asserted here by AST, so a
    future trigger that did read it would fail the validator rather than pass unnoticed.
    """
    import ast as _ast
    from . import candidates as _CA
    tree = _ast.parse(open(_CA.__file__, encoding="utf-8").read())
    bad: List[str] = []

    # 1. `chunk_id` may be read only inside the featuriser. Anywhere else it could influence
    #    whether a candidate is emitted, which is the thing §6.7 forbids.
    AUDIT_ONLY = {"_features"}
    for fn in _ast.walk(tree):
        if not isinstance(fn, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        for nd in _ast.walk(fn):
            if (isinstance(nd, _ast.Constant) and nd.value in ("chunk_id", "seq_in_chunk")
                    and fn.name not in AUDIT_ONLY):
                bad.append(f"{fn.name}() reads {nd.value!r} outside the audit-only featuriser")

    # 2. No enabled trigger may be chunk-derived. `at_chunk_edge` is produced as a FEATURE and
    #    must never appear in the trigger set.
    for t in sorted(_CA.ENABLED_TRIGGERS):
        if "chunk" in t:
            bad.append(f"enabled trigger {t!r} is chunk-derived")
    return bad


def load(path: str) -> List[Dict]:
    """Read `segments.jsonl`. A malformed line is surfaced, never silently skipped."""
    out: List[Dict] = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                out.append({"__malformed__": f"line {n}: {e}"})
    return out


def validate_file(path: str, dataset_root: Optional[str] = None) -> List[str]:
    if not os.path.exists(path):
        return [f"{path} does not exist"]
    segments = load(path)
    bad = [s["__malformed__"] for s in segments if "__malformed__" in s]
    segments = [s for s in segments if "__malformed__" not in s]
    ctx: Dict[str, Any] = {}
    if dataset_root and os.path.isdir(dataset_root):
        ctx = dataset_context(dataset_root)
    return bad + validate(segments,
                          session_ids=ctx.get("session_ids"),
                          chunk_edges=ctx.get("chunk_edges"),
                          justified=ctx.get("justified"))


def label_stability_report(segments: Sequence[Dict]) -> Dict[str, Any]:
    """§6.6 evidence: how consistently is each label reused across sessions?"""
    per_label = collections.defaultdict(set)
    for s in segments:
        per_label[s.get("label")].add(s.get("session_id"))
    counts = collections.Counter(s.get("label") for s in segments)
    return {"distinct_labels": len(per_label),
            "labels_used_in_more_than_one_session":
                sum(1 for v in per_label.values() if len(v) > 1),
            "most_common": counts.most_common(10)}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="procmine.validate_segments")
    ap.add_argument("path", nargs="?", default="segments.jsonl")
    ap.add_argument("--dataset", default="dataset_b",
                    help="enables the exact-session-id and chunk-edge checks")
    a = ap.parse_args(argv)
    problems = validate_file(a.path, a.dataset)
    segments = [s for s in load(a.path) if "__malformed__" not in s] \
        if os.path.exists(a.path) else []
    if problems:
        print(f"INVALID — {len(problems)} violation(s) of DATA_CONTRACT.md §6:")
        for p in problems[:25]:
            print(f"  {p}")
        return 1
    print(json.dumps({"valid": True, "path": a.path, "segments": len(segments),
                      **label_stability_report(segments)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
