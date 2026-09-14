"""Provisional segment emission for Dataset B, from activity blocks.

**Superseded. This is the Phase B safety net, not the deliverable.** It contains no candidate
boundary generation, no scoring, no decoder and no LLM. It asserts nothing about accuracy. Its
purpose was that a contract-valid segment file existed on disk while the real Step 1 pipeline
(`docs/STEP1_SPEC.md`) was built. That pipeline now exists and is frozen, so this module is
retained only as the block-edge-only reference arm and for reproducing the provisional output.

**It no longer writes `segments.jsonl`.** It used to default to exactly that path, which made
`make run-b` — `build-b` plus this emitter — silently replace a Phase D/E deliverable with a
block-edge-only one. That happened during the S-E7 leakage check and was caught only because a
downstream experiment reported a segment count that could not be right. The default output is
now `build/<dataset>/segments_provisional.jsonl`; `procmine/cli.py --segment` is the single
writer of the deliverable, as STEP1_SPEC §8 requires ("the same frozen code produced it that
was validated on A"). Passing `--out segments.jsonl` explicitly is refused unless `--force` is
also given, so the trap cannot be re-sprung by habit.

Method, in full:

  1. `normalise.load_session` -> `blocks.build_blocks` (the existing Phase 0 perception layer)
  2. `baselines.b5_dwell` turns those blocks into (interval, surface) pairs
  3. each surface key is slugged into a **stable label** — the same surface yields the same
     label in every session, which is `DATA_CONTRACT.md` §6.6
  4. adjacent segments carrying the same label are merged
  5. any segment too short to be representable at second precision is absorbed into its
     neighbour, because `DATA_CONTRACT.md` §6.2 requires `start < end`
  6. `baselines.to_segments` renders the rows

Known limitations, stated rather than hidden:

  * **Segment boundaries are block boundaries.** Phase 1 measured that only 59.9% of Dataset A
    GT boundaries lie within 2 s of a block edge, and that 98.4% of the misses are process
    switches with no screen change. That figure is the reachability of the **block-edge
    candidate space**, not a limit of the telemetry: 74.5% of GT boundaries fall strictly
    inside a block, and the discriminating events survive into the retained stream. This
    emitter uses only block edges, so it inherits that reachability exactly and **cannot place
    a boundary inside a block**. `STEP1_SPEC.md` §4 requires the real pipeline to do so, via an
    event-level candidate layer beneath the blocks; this one does not pretend to.
  * **Labels name a screen, not a business process.** A slug derived from a surface key is a
    location, and two different processes visiting the same screen receive the same label.
  * Step 5 reassigns a sub-second sliver's events to a neighbouring label. No timestamp is
    invented; the events are absorbed, never fabricated or dropped.
"""
from __future__ import annotations
import argparse, json, logging, os, re, unicodedata
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import normalise as N, blocks as B, baselines as BL

log = logging.getLogger("procmine.emit_segments")

Interval = Tuple[int, int]
# NOT "segments.jsonl". See the module docstring: exactly one code path writes the deliverable,
# and it is `cli.segment()`.
DEFAULT_OUT = os.path.join("build", "{dataset}", "segments_provisional.jsonl")
DELIVERABLE = "segments.jsonl"

# Label schemes. `route` is the default and follows the shape asked for: the route alone,
# e.g. web:http://127.0.0.1:5132/payroll-items -> "payroll-items". `surface` additionally
# keeps the origin, because measured on dataset_b **93.3% of web blocks sit on a route that
# is served by more than one origin** (/payroll-items appears on all three ports, which carry
# three different system titles). Route-only therefore merges screens that may belong to
# different backend systems. The default is kept as specified and the trade-off is reported.
LABEL_SCHEMES = ("route", "surface")

_SLUG_STRIP = re.compile(r"[^\w]+", re.UNICODE)
_SLUG_EDGE = re.compile(r"^[-_]+|[-_]+$")


def slugify(text: str) -> str:
    """Deterministic, stable slug. Unicode is preserved (labels are not scored on text)."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text)).strip().lower()
    s = _SLUG_STRIP.sub("-", s)
    s = _SLUG_EDGE.sub("", s)
    return s


def label_for(block: Dict, scheme: str = "route") -> str:
    """Surface key -> stable label. Same surface, same label, in every session."""
    surface = block.get("surface") or ""
    if surface.startswith("web:"):
        route = block.get("route") or ""
        base = slugify(route.strip("/")) or "home"
        if scheme == "surface":
            origin = (block.get("origin") or "").rsplit("/", 1)[-1]
            return f"{slugify(origin)}--{base}" if origin else base
        return base
    # app surfaces: prefer the window title, fall back to the application name
    title = slugify(block.get("title") or "")
    app = slugify(block.get("app") or "")
    if title and app and scheme == "surface":
        return f"{app}--{title}"
    return title or app or slugify(surface) or "unknown"


def _merge_same_label(segs: List[List]) -> List[List]:
    """Merge temporally adjacent segments carrying the same label.

    Note: merging on the *surface key* — the literal instruction — is a strict no-op here.
    `blocks.build_blocks` pass 1 already guarantees that consecutive blocks never share a
    surface key (measured on dataset_b: 0 of 1,323 adjacent pairs). Merging on the emitted
    LABEL is the operative step, and it is what prevents two adjacent segments carrying an
    identical label, which would be a meaningless boundary.
    """
    out: List[List] = []
    for s in segs:
        if out and out[-1][2] == s[2]:
            out[-1][1] = max(out[-1][1], s[1])
            out[-1][3] += s[3]
        else:
            out.append(list(s))
    return out


def _absorb_subsecond(segs: List[List]) -> Tuple[List[List], int]:
    """Absorb segments that cannot satisfy `start < end` at second precision.

    `DATA_CONTRACT.md` §6.2 fixes the output at second precision, but 25.9% of dataset_b's
    blocks begin and end inside the same second. Such a segment is merged into the previous
    one (or the next, when it is first), which extends a real interval over events that
    really happened. Nothing is invented and nothing is discarded; the absorbed events simply
    take the neighbour's label. The count is reported.
    """
    if not segs:
        return [], 0
    absorbed = 0
    changed = True
    while changed:
        changed = False
        for i, s in enumerate(segs):
            if s[0] // 1000 < s[1] // 1000:
                continue                       # representable, leave it alone
            if len(segs) == 1:
                return segs, absorbed          # a lone sub-second session: cannot absorb
            j = i - 1 if i > 0 else i + 1
            segs[j][0] = min(segs[j][0], s[0])
            segs[j][1] = max(segs[j][1], s[1])
            segs[j][3] += s[3]
            segs.pop(i)
            absorbed += 1
            changed = True
            break
    return segs, absorbed


def segments_for_session(blocks: Sequence[Dict], scheme: str = "route"
                         ) -> Tuple[List[List], Dict[str, int]]:
    """Blocks -> provisional segments for one session."""
    intervals, _surfaces = BL.b5_dwell(None, list(blocks))     # reuse the existing baseline
    if not intervals:
        return [], {"blocks": 0, "merged": 0, "absorbed": 0}
    segs = [[a, b, label_for(blk, scheme), 1]
            for (a, b), blk in zip(intervals, blocks)]
    n0 = len(segs)
    segs = _merge_same_label(segs)
    segs, absorbed = _absorb_subsecond(segs)
    segs = _merge_same_label(segs)             # absorption can create new adjacency
    return segs, {"blocks": n0, "merged": n0 - len(segs), "absorbed": absorbed}


def default_out(dataset_root: str) -> str:
    """Where the provisional output goes — under `build/`, never the deliverable path."""
    return DEFAULT_OUT.format(dataset=os.path.basename(dataset_root.rstrip("/\\")))


def emit(dataset_root: str, out_path: Optional[str] = None, scheme: str = "route",
         min_events: int = 3, min_ms: int = 1500) -> Dict:
    """Write the PROVISIONAL segment file for every session in `dataset_root`.

    `out_path` defaults to `build/<dataset>/segments_provisional.jsonl`. This function does not
    write the deliverable — `cli.segment()` does.
    """
    out_path = out_path or default_out(dataset_root)
    rows_out: List[Dict] = []
    per_session: List[Dict] = []
    dropped_unrepresentable = 0

    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        rows = N.load_session(sdir)
        if not rows:
            log.warning("%s: no events, skipped", sid)
            continue
        blks = B.build_blocks(rows, min_events=min_events, min_ms=min_ms)
        segs, stats = segments_for_session(blks, scheme)
        keep = [s for s in segs if s[0] // 1000 < s[1] // 1000]
        dropped_unrepresentable += len(segs) - len(keep)
        rows_out.extend(BL.to_segments(sid, [(s[0], s[1]) for s in keep],
                                       [s[2] for s in keep]))
        per_session.append({"session": sid, "segments": len(keep), **stats})
        log.info("%s: %d blocks -> %d segments", sid, stats["blocks"], len(keep))

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in rows_out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    durs = sorted((_iso_to_ms(r["end"]) - _iso_to_ms(r["start"])) / 1000 for r in rows_out)
    labels = sorted({r["label"] for r in rows_out})
    return {
        "provisional": True,
        "method": "block runs merged by label; no candidate generation, no decoder, no LLM",
        "accuracy_validated": False,
        "dataset": dataset_root,
        "out": out_path,
        "label_scheme": scheme,
        "sessions": len(per_session),
        "segments": len(rows_out),
        "distinct_labels": len(labels),
        "labels": labels,
        "median_duration_s": round(durs[len(durs) // 2], 1) if durs else None,
        "p90_duration_s": round(durs[int(len(durs) * 0.9)], 1) if durs else None,
        "blocks_in": sum(p["blocks"] for p in per_session),
        "merged_by_label": sum(p["merged"] for p in per_session),
        "absorbed_subsecond": sum(p["absorbed"] for p in per_session),
        "dropped_unrepresentable": dropped_unrepresentable,
        "per_session": per_session,
    }


def _iso_to_ms(s: str) -> int:
    from datetime import datetime, timezone
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="procmine.emit_segments")
    ap.add_argument("--dataset", default="dataset_b")
    ap.add_argument("--out", default=None,
                    help="default: build/<dataset>/segments_provisional.jsonl. This emitter "
                         "does NOT write the deliverable; cli.py --segment does.")
    ap.add_argument("--force", action="store_true",
                    help="permit --out to be the deliverable path. Refused without it.")
    ap.add_argument("--label-scheme", choices=LABEL_SCHEMES, default="route")
    ap.add_argument("--min-events", type=int, default=3)
    ap.add_argument("--min-ms", type=int, default=1500)
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    out = a.out or default_out(a.dataset)
    if os.path.abspath(out) == os.path.abspath(DELIVERABLE) and not a.force:
        ap.error(
            f"refusing to write {DELIVERABLE!r}: this is the Phase B safety net, and the "
            f"deliverable is written by `python -m procmine.cli --dataset {a.dataset} "
            f"--segment` (STEP1_SPEC §8). Re-run without --out, or pass --force if you "
            f"really mean to overwrite the submission with block-edge-only segments.")
    a.out = out
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")

    root = a.dataset.rstrip("/")
    if not os.path.isdir(root) or not any(N.iter_session_dirs(root)):
        print(f"{os.path.basename(root)} not present — no segments written.")
        return 0

    summary = emit(root, a.out, a.label_scheme, a.min_events, a.min_ms)

    if not a.no_validate:
        from . import validate_segments as V
        problems = V.validate_file(a.out, dataset_root=root)
        summary["contract_valid"] = not problems
        if problems:
            for p in problems[:10]:
                print(f"CONTRACT VIOLATION: {p}")
            print(json.dumps({k: v for k, v in summary.items() if k != "per_session"},
                             ensure_ascii=False, indent=2))
            return 2

    print(json.dumps({k: v for k, v in summary.items() if k != "per_session"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
