"""Stage GT — ground-truth canonicaliser (Dataset A only).

Implements `EVALUATION_PROTOCOL.md` §4 and `DATA_CONTRACT.md` §5.

The ground truth is **evidence, not truth** (CLAUDE.md §6). `DATA_SCHEMA.md` §3 warns that
`gt.jsonl` emits duplicate `process_started` and that `process_switched_out` does not always
pair up, and instructs us to verify consistency ourselves. This module does that verification
and records what it finds; it never silently resolves a disagreement in our favour.

Two independent sources are read and **both are retained when they disagree**:

  * the **stream** (`gt.jsonl`)          authoritative for SEMANTICS
    — switch vs suspend, `split_id`, `phase`, tasks
  * the **manifest** (`gt_manifest.json`) authoritative for INTERVAL EXTENTS
    — and the likely origin of `expected_boundaries`

Repair rules are frozen here **before** any segmenter exists (ADR-011), so the generator's
defects cannot be fitted after the fact.
"""
from __future__ import annotations
import json, os, glob, argparse, logging, collections
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .normalise import _g, iter_session_dirs

log = logging.getLogger("procmine.gt")

# ---- repair flags (EVALUATION_PROTOCOL.md §4) ---------------------------
CHUNK_MERGE = "chunk_merge_applied"            # deterministic
DUPLICATE_START = "duplicate_start_collapsed"  # deterministic
UNPAIRED_SWITCH = "unpaired_switch_out"        # disputed
MANIFEST_STREAM = "manifest_stream_disagreement"  # disputed
ZERO_DURATION = "zero_duration"                # disputed

DETERMINISTIC = frozenset({CHUNK_MERGE, DUPLICATE_START})
DISPUTED = frozenset({UNPAIRED_SWITCH, MANIFEST_STREAM, ZERO_DURATION})

# Default disagreement tolerance. Calibrated against A's observed execution durations in
# Phase 1 Task 1.5 and passed in explicitly by the harness; this is only the fallback.
DEFAULT_TAU_MS = 2000


def parse_ts(s: Optional[str]) -> Optional[int]:
    """ISO-8601 with timezone -> epoch ms. Returns None on anything unparseable.

    `ts_utc` is never rewritten in the artifacts; this is only for arithmetic.
    """
    if not s or not isinstance(s, str):
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- 5.1 raw stream

def load_gt_events(session_dir: str) -> List[Dict]:
    """`gt.jsonl` -> flat records, VERBATIM. No repairs at this level (DATA_CONTRACT §5.1)."""
    out: List[Dict] = []
    path = os.path.join(session_dir, "gt.jsonl")
    if not os.path.exists(path):
        return out
    sid = os.path.basename(session_dir)
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                log.warning("%s: gt.jsonl line %d is not JSON, skipped", sid, n)
                continue
            r["session_id"] = sid
            r["raw_line_no"] = n
            r["source_file"] = os.path.relpath(path)
            out.append(r)
    return out


# ---------------------------------------------------------------- stream intervals

def stream_intervals(events: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Reconstruct execution intervals from the annotation stream.

    Returns (intervals, anomalies). An interval is opened by `process_started` or
    `process_resumed` and closed by `process_switched_out`, `process_suspended`,
    the next start, or `session_ended`.

    Anomalies are RECORDED, never repaired here: a `process_switched_out` with nothing
    open (`unpaired_switch_out`), and consecutive duplicate `process_started` for the
    same `(code, case_id)` with no intervening annotation (`duplicate_start_collapsed`),
    which `DATA_SCHEMA.md` §3 names explicitly.
    """
    intervals: List[Dict] = []
    anomalies: List[Dict] = []
    open_exec: Optional[Dict] = None
    prev_start_key: Optional[Tuple] = None
    prev_was_start = False

    def close(ts: Optional[int], reason: str) -> None:
        nonlocal open_exec
        if open_exec is None:
            return
        open_exec["end_ms"] = ts
        open_exec["closed_by"] = reason
        intervals.append(open_exec)
        open_exec = None

    for e in events:
        ev = e.get("event")
        ts = parse_ts(e.get("ts_utc"))

        if ev == "process_started":
            key = (e.get("process_code"), e.get("case_id"))
            if prev_was_start and key == prev_start_key:
                # SCHEMA §3: the generator emits the same start twice in a row.
                anomalies.append({"kind": DUPLICATE_START, "ts_utc": e.get("ts_utc"),
                                  "process_code": key[0], "case_id": key[1],
                                  "raw_line_no": e.get("raw_line_no")})
                continue                       # collapse: keep the first
            close(ts, "next_start")
            open_exec = {"process_code": e.get("process_code"),
                         "case_id": e.get("case_id"),
                         "process_name": e.get("process_name"),
                         "variant": e.get("process_variant"),
                         "start_ms": ts, "start_ts": e.get("ts_utc"),
                         "split_id": None, "phase": None, "opened_by": "process_started",
                         "n_tasks": 0}
            prev_start_key, prev_was_start = key, True
            continue

        prev_was_start = False

        if ev == "process_resumed":
            close(ts, "next_resume")
            open_exec = {"process_code": e.get("process_code"),
                         "case_id": e.get("case_id"),
                         "process_name": e.get("process_name"),
                         "variant": e.get("process_variant"),
                         "start_ms": ts, "start_ts": e.get("ts_utc"),
                         "split_id": e.get("split_id"), "phase": e.get("phase"),
                         "opened_by": "process_resumed", "n_tasks": 0}
        elif ev in ("process_switched_out", "process_suspended"):
            if open_exec is None:
                anomalies.append({"kind": UNPAIRED_SWITCH, "ts_utc": e.get("ts_utc"),
                                  "event": ev, "from": e.get("from"), "to": e.get("to"),
                                  "raw_line_no": e.get("raw_line_no")})
            else:
                if ev == "process_suspended" and e.get("split_id") is not None:
                    open_exec["split_id"] = e.get("split_id")
                close(ts, ev)
        elif ev == "task_started":
            if open_exec is not None:
                open_exec["n_tasks"] += 1
        elif ev == "session_ended":
            close(ts, "session_ended")

    close(None, "unterminated")
    return intervals, anomalies


# ---------------------------------------------------------------- 5.2 executions

def load_manifest_executions(session_dir: str) -> Tuple[List[Dict], Any, Dict]:
    """`gt_manifest.json` -> flat execution records + `expected_boundaries` + session meta."""
    path = os.path.join(session_dir, "gt_manifest.json")
    if not os.path.exists(path):
        return [], None, {}
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("%s: gt_manifest.json unreadable (%s)", session_dir, e)
        return [], None, {}

    sid = os.path.basename(session_dir)
    out: List[Dict] = []
    for proc in doc.get("processes") or []:
        for ex in proc.get("executions") or []:
            out.append({
                "session_id": sid,
                "process_code": ex.get("code") or proc.get("code"),
                "family_name": proc.get("family_name"),
                "domain": proc.get("domain"),
                "case_id": ex.get("case_id"),
                "variant": ex.get("variant"),
                "seq": ex.get("seq"),
                "phase": ex.get("phase"),
                "split_id": ex.get("split_id"),
                "exec_id": ex.get("exec_id"),
                "start_ts": ex.get("start_ts"),
                "end_ts": ex.get("end_ts"),
                "start_ms": parse_ts(ex.get("start_ts")),
                "end_ms": parse_ts(ex.get("end_ts")),
                "apps": ex.get("apps") or [],
                "continues_from_prev": bool(ex.get("continues_from_prev")),
                "continues_to_next": bool(ex.get("continues_to_next")),
            })
    out.sort(key=lambda r: (r["start_ms"] if r["start_ms"] is not None else 0))
    return out, doc.get("expected_boundaries"), (doc.get("session") or {})


def reconcile(manifest: List[Dict], stream: List[Dict], tau_ms: int) -> List[Dict]:
    """Pair manifest executions with stream intervals and record disagreement.

    Matching is on `(process_code, case_id)` in temporal order — the only identifiers both
    sources share. A manifest record with no stream counterpart keeps `source="manifest"`
    and vice versa; neither source is allowed to win by default.
    """
    by_key: Dict[Tuple, List[Dict]] = collections.defaultdict(list)
    for s in stream:
        by_key[(s.get("process_code"), s.get("case_id"))].append(s)
    for v in by_key.values():
        v.sort(key=lambda r: (r["start_ms"] if r["start_ms"] is not None else 0))
    used: set = set()

    out: List[Dict] = []
    for m in manifest:
        key = (m["process_code"], m["case_id"])
        cands = [s for i, s in enumerate(by_key.get(key, []))
                 if (key, i) not in used]
        match = None
        if cands:
            # nearest start among unused candidates
            ms = m["start_ms"]
            match = min(cands, key=lambda s: abs((s["start_ms"] or 0) - (ms or 0)))
            idx = by_key[key].index(match)
            used.add((key, idx))

        flags: List[str] = []
        if m["continues_from_prev"] or m["continues_to_next"]:
            flags.append(CHUNK_MERGE)
        if m["start_ms"] is not None and m["end_ms"] is not None and m["end_ms"] <= m["start_ms"]:
            flags.append(ZERO_DURATION)

        delta_start = delta_end = None
        if match is not None:
            if m["start_ms"] is not None and match["start_ms"] is not None:
                delta_start = match["start_ms"] - m["start_ms"]
            if m["end_ms"] is not None and match["end_ms"] is not None:
                delta_end = match["end_ms"] - m["end_ms"]
            worst = max((abs(d) for d in (delta_start, delta_end) if d is not None), default=0)
            if worst > tau_ms:
                flags.append(MANIFEST_STREAM)

        # The stream is authoritative for SEMANTICS (EVALUATION_PROTOCOL §4), and split_id is
        # the clearest case: the manifest records it only on the phase-2 fragment, leaving the
        # suspended phase-1 fragment with split_id=null. Only the stream's `process_suspended`
        # carries it for that side, so the manifest ALONE cannot link an interrupted execution.
        split_id = m["split_id"]
        split_source = "manifest" if split_id is not None else None
        if split_id is None and match is not None and match.get("split_id") is not None:
            split_id = match["split_id"]
            split_source = "stream"

        source = "both" if match is not None else "manifest"
        confidence = ("disputed" if DISPUTED & set(flags)
                      else "repaired" if DETERMINISTIC & set(flags) else "clean")

        out.append({
            "exec_uid": f"{m['session_id']}#{m['process_code']}#{m['case_id']}#{m['seq']}",
            "session_id": m["session_id"],
            "process_code": m["process_code"], "family_name": m["family_name"],
            "domain": m["domain"], "case_id": m["case_id"], "variant": m["variant"],
            "seq": m["seq"], "phase": m["phase"],
            "split_id": split_id, "split_id_source": split_source,
            "start_ts": m["start_ts"], "end_ts": m["end_ts"],
            "start_ms": m["start_ms"], "end_ms": m["end_ms"],
            "apps": m["apps"],
            "continues_from_prev": m["continues_from_prev"],
            "continues_to_next": m["continues_to_next"],
            "n_tasks": match.get("n_tasks") if match else None,
            "source": source,
            "repair_flags": sorted(flags),
            "confidence": confidence,
            "delta_start_ms": delta_start, "delta_end_ms": delta_end,
            # both values retained on disagreement (EVALUATION_PROTOCOL §4)
            "manifest_value": {"start_ts": m["start_ts"], "end_ts": m["end_ts"]},
            "stream_value": ({"start_ts": match.get("start_ts"),
                              "end_ts": None, "closed_by": match.get("closed_by"),
                              "split_id": match.get("split_id"), "phase": match.get("phase")}
                             if match else None),
        })

    # stream intervals with no manifest counterpart are kept, flagged, never dropped
    for key, lst in by_key.items():
        for i, s in enumerate(lst):
            if (key, i) in used:
                continue
            out.append({
                "exec_uid": f"{s.get('session_id','?')}#{key[0]}#{key[1]}#stream{i}",
                "session_id": s.get("session_id"),
                "process_code": key[0], "family_name": None, "domain": None,
                "case_id": key[1], "variant": s.get("variant"),
                "seq": None, "phase": s.get("phase"), "split_id": s.get("split_id"),
                "start_ts": s.get("start_ts"), "end_ts": None,
                "start_ms": s.get("start_ms"), "end_ms": s.get("end_ms"),
                "apps": [], "continues_from_prev": False, "continues_to_next": False,
                "n_tasks": s.get("n_tasks"),
                "source": "stream", "repair_flags": [MANIFEST_STREAM],
                "confidence": "disputed",
                "delta_start_ms": None, "delta_end_ms": None,
                "manifest_value": None,
                "stream_value": {"start_ts": s.get("start_ts"), "closed_by": s.get("closed_by")},
            })
    out.sort(key=lambda r: (r["session_id"] or "", r["start_ms"] or 0))
    return out


# ---------------------------------------------------------------- 5.3 canonical

def canonicalise(executions: List[Dict]) -> List[Dict]:
    """Group execution fragments into canonical executions (DATA_CONTRACT §5.3).

    Grouping key: `split_id` when the execution has one, else `case_id`.

    Measured on Dataset A, `case_id` is **unique per fragment** — the two halves of a split
    execution carry *different* case_ids (e.g. `PI-175009-002` phase 1 suspended, resumed as
    `PI-175009-003` phase 2). `split_id` is the only field that links them, which is why it is
    the primary key here and why `reconcile` back-fills it from the stream. Grouping on
    `case_id` alone would report an interruption rate of exactly zero.

    `intervals` with length > 1 means the execution was INTERRUPTED — the representation
    `segments.jsonl` cannot express, and the reason this file exists (EVALUATION_PROTOCOL §5).
    """
    groups: Dict[Tuple, List[Dict]] = collections.defaultdict(list)
    for e in executions:
        link = e.get("split_id") or e["case_id"]
        groups[(e["session_id"], e["process_code"], link)].append(e)

    out: List[Dict] = []
    for (sid, code, case), frs in groups.items():
        frs.sort(key=lambda r: (r["start_ms"] or 0))
        intervals = [[f["start_ts"], f["end_ts"]] for f in frs
                     if f["start_ts"] and f["end_ts"]]
        spans = [(f["start_ms"], f["end_ms"]) for f in frs
                 if f["start_ms"] is not None and f["end_ms"] is not None]
        total = sum(max(0, b - a) for a, b in spans) / 1000 if spans else 0.0
        wall = ((max(b for _a, b in spans) - min(a for a, _b in spans)) / 1000
                if spans else 0.0)
        conf = ("disputed" if any(f["confidence"] == "disputed" for f in frs)
                else "repaired" if any(f["confidence"] == "repaired" for f in frs)
                else "clean")
        out.append({
            "canonical_exec_id": f"{sid}#{code}#{case}",
            "session_id": sid, "process_code": code,
            "link_key": case,
            "case_ids": [f["case_id"] for f in frs],
            "split_id": frs[0].get("split_id") or frs[-1].get("split_id"),
            "variant": frs[0].get("variant"),
            "family_name": frs[0].get("family_name"),
            "domain": frs[0].get("domain"),
            "intervals": intervals,
            "n_fragments": len(frs),
            "total_duration_s": round(total, 3),
            "wall_span_s": round(wall, 3),
            "confidence": conf,
            "repair_flags": sorted({f for fr in frs for f in fr["repair_flags"]}),
        })
    out.sort(key=lambda r: (r["session_id"], r["intervals"][0][0] if r["intervals"] else ""))
    return out


# ---------------------------------------------------------------- driver

def build(dataset_root: str, out_root: str, sessions: Optional[List[str]] = None,
          tau_ms: int = DEFAULT_TAU_MS) -> Dict:
    """Write the four DATA_CONTRACT §5 artifacts. Returns a summary dict."""
    os.makedirs(out_root, exist_ok=True)
    all_events: List[Dict] = []
    all_execs: List[Dict] = []
    all_anoms: List[Dict] = []
    boundaries: Dict[str, Any] = {}
    session_meta: Dict[str, Any] = {}

    for sdir in iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        if sessions and sid not in sessions:
            continue
        ev = load_gt_events(sdir)
        if not ev:
            log.warning("%s: no gt.jsonl", sid)
        all_events.extend(ev)
        sints, anoms = stream_intervals(ev)
        for s in sints:
            s["session_id"] = sid
        for a in anoms:
            a["session_id"] = sid
        all_anoms.extend(anoms)
        man, eb, meta = load_manifest_executions(sdir)
        all_execs.extend(reconcile(man, sints, tau_ms))
        boundaries[sid] = eb
        session_meta[sid] = meta

    canon = canonicalise(all_execs)

    def dump(name: str, rows: List[Dict]) -> None:
        with open(os.path.join(out_root, name), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump("gt_events.jsonl", all_events)
    dump("executions.jsonl", all_execs)
    dump("executions_canonical.jsonl", canon)
    with open(os.path.join(out_root, "expected_boundaries.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "_note": ("Verbatim copy of gt_manifest.json.expected_boundaries per session. "
                      "Semantics are recorded in docs/GT_DEFECT_REPORT.md and the Phase 1 "
                      "report; see PHASE_1.md Task 1.4."),
            "sessions": boundaries,
        }, fh, ensure_ascii=False, indent=1)

    tiers = collections.Counter(e["confidence"] for e in all_execs)
    return {
        "dataset": dataset_root,
        "sessions": len(boundaries),
        "gt_events": len(all_events),
        "executions": len(all_execs),
        "canonical_executions": len(canon),
        "tau_ms": tau_ms,
        "tiers": dict(tiers),
        "repair_flags": dict(collections.Counter(
            f for e in all_execs for f in e["repair_flags"])),
        "stream_anomalies": dict(collections.Counter(a["kind"] for a in all_anoms)),
        "interrupted_executions": sum(1 for c in canon if c["n_fragments"] > 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="procmine.gt")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--sample", type=int, default=0, help="use N sessions chosen by --seed")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tau-ms", type=int, default=DEFAULT_TAU_MS)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")

    root = a.dataset.rstrip("/")
    if not os.path.isdir(root) or not any(iter_session_dirs(root)):
        print(f"{os.path.basename(root)} not present — ground truth unavailable. "
              "No artifacts written.")
        return 0

    sessions = None
    if a.sample:
        import random
        alls = sorted(os.path.basename(p) for p in iter_session_dirs(root))
        sessions = sorted(random.Random(a.seed).sample(alls, min(a.sample, len(alls))))

    out = a.out or os.path.join("build", os.path.basename(root))
    s = build(root, out, sessions=sessions, tau_ms=a.tau_ms)
    if sessions:
        s["sampled_sessions"] = sessions
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
