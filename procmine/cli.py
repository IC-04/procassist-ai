"""Build the perception + TEKG layer for a dataset. No LLM involved."""
from __future__ import annotations
import json, os, sys, time, argparse, logging, collections
from typing import Dict, List, Optional

from . import normalise as N, blocks as B, tekg as G, context as C, schemas as S
from . import candidates as CA
from . import score as SC, gate as GA, decoder as DE, label as LB, identity as ID
from . import validate_segments as VS

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
          min_ms: int = 1500, max_lag: int = 12, write_windows: bool = True,
          write_candidates: bool = True) -> dict:
    """Run the deterministic pipeline over one dataset and write its artifacts."""
    t0 = time.time()
    os.makedirs(out_root, exist_ok=True)
    os.makedirs(os.path.join(out_root, "tekg"), exist_ok=True)
    all_blocks: List[Dict] = []
    all_cands: List[Dict] = []
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

        if write_candidates:
            all_cands.extend(CA.generate(rows, blks))

        all_blocks.extend(blks)
        all_stats.append({"session": sid, "events": len(rows), **B.block_stats(blks)})
        log.info("%s: %d events -> %d blocks", sid, len(rows), len(blks))

    _check(S.validate_blocks(all_blocks), "blocks.jsonl")
    with open(os.path.join(out_root, "blocks.jsonl"), "w", encoding="utf-8") as fh:
        for b in all_blocks:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")

    if write_candidates:
        # DATA_CONTRACT §10.2, ordered by (session_id, at_seq)
        all_cands.sort(key=lambda c: (c["session_id"], c["at_seq"]))
        with open(os.path.join(out_root, "candidates.jsonl"), "w", encoding="utf-8") as fh:
            for c in all_cands:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")

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
        "candidates": len(all_cands),
        "candidates_per_event": (round(len(all_cands) / n_events, 4)
                                 if write_candidates and n_events else None),
        "reasoner_windows": payload_count,
        "dataflow_edges": dataflow_edges,
        "edges_by_type": dict(edge_counter),
        "per_session": all_stats,
    }
    with open(os.path.join(out_root, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    log.info("wrote %s in %.1fs", out_root, time.time() - t0)
    return summary


# ---------------------------------------------------------------- Step 1 chain

SCORER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorer_v1.json")

# The submitted artifact (DATA_CONTRACT.md §6). Exactly ONE code path writes it: `segment()`,
# below. `emit_segments.py` — the Phase B block-run safety net — used to default to this same
# path, so `make run-b` silently replaced a Phase D/E deliverable with a block-edge-only one.
# That happened, during the S-E7 leakage check, and was caught only because a downstream
# experiment reported a segment count that could not be right.
DELIVERABLE = "segments.jsonl"


def _iso(ms: int) -> str:
    """Epoch ms -> ISO-8601 UTC at second precision (DATA_CONTRACT §6.2)."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fit_scorer(dataset_root: str, out_path: str = SCORER_PATH, tau_ms: int = 2000) -> Dict:
    """Fit the candidate scorer on a dataset's CLEAN ground-truth tier (ADR-011, ADR-019).

    Ground truth is imported here, in the orchestrator, and never by `candidates.py`,
    `score.py`, `gate.py` or `decoder.py` — an AST test enforces that. GT supplies the label
    and nothing else; no GT field is ever a feature.
    """
    import bisect
    from . import gt as GT                      # local: only the fitting path touches GT
    gt_dir = os.path.join("build", os.path.basename(dataset_root.rstrip("/")))
    canon = os.path.join(gt_dir, "executions_canonical.jsonl")
    if not os.path.exists(canon):
        raise FileNotFoundError(f"{canon} missing — run `python3 -m procmine.gt --dataset "
                                f"{dataset_root}` first")
    clean: Dict[str, List[int]] = collections.defaultdict(list)
    with open(canon, encoding="utf-8") as fh:
        for line in fh:
            c = json.loads(line)
            if c.get("confidence") != "clean":
                continue
            for a, b in c.get("intervals", []):
                x, y = GT.parse_ts(a), GT.parse_ts(b)
                if x is not None and y is not None and y > x:
                    clean[c["session_id"]].extend([x, y])

    cands: List[Dict] = []
    labels: List[int] = []
    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        rows = N.load_session(sdir)
        if not rows:
            continue
        cs = CA.generate(rows, B.build_blocks(rows))
        g = sorted(clean.get(sid, []))
        for c in cs:
            t = c.get("at_ms")
            d = 10 ** 12
            if t is not None and g:
                i = bisect.bisect_left(g, t)
                d = min([abs(g[j] - t) for j in (i - 1, i) if 0 <= j < len(g)] or [10 ** 12])
            cands.append(c)
            labels.append(1 if d <= tau_ms else 0)
    scorer = SC.fit(cands, labels)
    scorer.meta.update({"fitted_on": os.path.basename(dataset_root.rstrip("/")),
                        "tier": "clean", "tau_ms": tau_ms,
                        "provenance": "a_fitted — declared A->B transfer, ADR-019"})
    SC.save(scorer, out_path)
    return {"scorer": out_path, **scorer.meta}


def thresholds_manifest(cfg_cand: Dict, cfg_gate: Dict, cfg_dec: Dict,
                        scorer: Optional[SC.Scorer], calibration: str = "percentile") -> Dict:
    """Every threshold the pipeline uses, tagged with how it transfers to a new dataset.

    Makes the ADR-010 leakage check mechanical instead of a judgement call:
      tolerance_derived — computed from tau or a contract constant; transfers as-is
      structural        — derived from the dataset's OWN distribution at runtime; transfers
                          as a RULE, and its value legitimately differs per dataset
      a_fitted          — a value fitted on Dataset A; a declared A->B transfer (ADR-019)
    """
    return {
        "_schema": "thresholds/v1",
        "_tags": {"tolerance_derived": "from tau or a contract constant",
                  "structural": "from the dataset's own distribution at runtime",
                  "a_fitted": "fitted on Dataset A; declared A->B transfer (ADR-019)"},
        "candidates.dedup_ms": {
            "value": cfg_cand.get("dedup_ms"), "tag": "tolerance_derived",
            "note": ("a quarter of the tightest tau in the unified grid (1000 ms). S-E3 also "
                     "observed a 55 ms p50 inter-arrival on dataset_a; that observation "
                     "MOTIVATED dedup but does not set the value — the value is derived from "
                     "tau alone, so it transfers to any dataset scored at the same grid.")},
        "candidates.gap_percentile": {
            "value": cfg_cand.get("gap_percentile"), "tag": "structural",
            "note": "per-session percentile of ms_since_last; never an absolute ms (ADR-003)"},
        "candidates.window_ms": {
            "value": cfg_cand.get("window_ms"), "tag": "tolerance_derived",
            "note": "equals tau=2000 ms, the featurisation window"},
        "decoder.min_duration_ms": {
            "value": cfg_dec.get("min_duration_ms"), "tag": "a_fitted",
            "note": ("p01 of dataset_a's scoreable canonical FRAGMENT durations (19.0 s). "
                     "Phase 1's 34.8 s / 23.9 s were execution-active durations and are not "
                     "reused.")},
        "decoder.max_duration_ms": {
            "value": cfg_dec.get("max_duration_ms"), "tag": "a_fitted",
            "note": ("null — A's fragments reach 1144.8 s with p99 at 144.2 s, so no upper "
                     "bound is justified; STEP1_SPEC §3.6 permits one only where the "
                     "distribution supports it")},
        "decoder.calibration": {
            "value": calibration, "tag": "structural",
            "note": ("percentile — each candidate's score is replaced by its within-dataset "
                     "empirical CDF, so the operating point selects a FRACTION of the "
                     "dataset's own distribution. The RULE transfers; the score value at "
                     "which it bites is computed per dataset and never carried across.")},
        "decoder.lambda_per_segment": {
            "value": cfg_dec.get("lambda_per_segment"),
            "tag": "structural" if calibration == "percentile" else "a_fitted",
            "note": ("under percentile calibration this is a position on a uniform [0,1] "
                     "distribution, i.e. a target FRACTION of candidates, not a score "
                     "threshold. Chosen on dataset_a for count ratio ~1.0; it selects the "
                     "same fraction on any dataset.")},
        "decoder.nms_window_ms": {
            "value": cfg_dec.get("nms_window_ms"), "tag": "a_fitted",
            "note": "0 — the duration floor already suppresses candidate clusters"},
        # --- identity / labelling (S-E7 freeze). The view weighting is the one A->B transfer
        #     here and is declared as such under the ADR-019 conditions: it is a structural,
        #     domain-neutral choice over view families, and no A surface, route, origin, process
        #     name, vocabulary item or cluster count crosses over. `k` is NOT transferred.
        "label.weightings": {
            "value": list(LB.DEFAULT_CFG.get("weightings") or []),
            "tag": "a_fitted",
            "note": "where_heavy. Selected on dataset_a, where the supervised probe measured "
                    "WHERE at 0.851 accuracy against HOW at 0.256 (S-E6). Left to select "
                    "itself, the unsupervised rule picks how_heavy on B's 183 executions and "
                    "produces clusters whose members mostly do not share the cluster's own "
                    "modal surface (0.32-0.52 vs 0.765). Declared A->B transfer, ADR-021 "
                    "addendum. No A content crosses; only the choice of view family.",
        },
        "label.combine_mode": {
            "value": list(LB.DEFAULT_CFG.get("modes") or []),
            "tag": "a_fitted",
            "note": "tiebreak. Above a saturated surface Jaccard the WHERE term carries no "
                    "information and is discarded in favour of WHAT and sequence. The RULE is "
                    "structural; it was validated on A (ARI 0.585 -> 0.681 at identical "
                    "boundary F1 and match_rate). ADR-021 addendum.",
        },
        "identity.saturated_where": {
            "value": ID.SATURATED_WHERE,
            "tag": "structural",
            "note": "0.95 — a property of the Jaccard statistic (near-identical sets carry no "
                    "discriminating information), not a value fitted to A's content.",
        },
        "label.k": {
            "value": None,
            "tag": "structural",
            "note": "NOT transferred, by construction. Louvain selects its own community count "
                    "by modularity on whatever dataset is in front of it; A's 17 never reaches "
                    "B, which selects 13 (ADR-010).",
        },
        "gate.low": {"value": cfg_gate.get("low"),
                     "tag": "structural" if calibration == "percentile" else "a_fitted",
                     "note": ("confident non-boundary band edge; a percentile of the "
                              "dataset's own score distribution under percentile calibration")},
        "gate.high": {"value": cfg_gate.get("high"),
                      "tag": "structural" if calibration == "percentile" else "a_fitted",
                      "note": "confident boundary band edge; see gate.low"},
        "scorer.weights": {
            "value": (dict(zip(scorer.names, [round(w, 4) for w in scorer.weights]))
                      if scorer else None),
            "tag": "a_fitted",
            "note": ("logistic regression fitted on dataset_a's clean tier; features are "
                     "domain-neutral and structural — no A surface string, process name, "
                     "vocabulary or keyword list (ADR-019)")},
        "scorer.bias": {"value": round(scorer.bias, 4) if scorer else None, "tag": "a_fitted"},
    }


def segment(dataset_root: str, out_root: str, scorer_path: str = SCORER_PATH,
            no_llm: bool = True, cfg_gate: Optional[Dict] = None,
            cfg_dec: Optional[Dict] = None, calibration: str = "percentile",
            deliverable: Optional[str] = DELIVERABLE) -> Dict:
    """The full deterministic chain: candidates -> score -> CALIBRATE -> gate -> decode.

    Calibration is applied across the WHOLE dataset before gating, because the operating point
    is a fraction of that dataset's own score distribution (score.calibrate). Decoding then
    proceeds per session.

    **This function writes the deliverable.** `deliverable` is the path of the four-key
    `segments.jsonl` required by `DATA_CONTRACT.md` §6; pass `None` to write only the internal
    `segments_rich.jsonl`. It is written here, and nowhere else, because STEP1_SPEC §8 requires
    the submitted file to be produced by the same frozen code that was validated on A — not by
    an experiment script, and not by the Phase B safety net (see `emit_segments.py`).
    """
    if not no_llm:
        raise NotImplementedError("only --no-llm is implemented; the adjudicator is a later "
                                  "stage (STEP1_SPEC §3.5)")
    os.makedirs(out_root, exist_ok=True)
    scorer = SC.load(scorer_path)
    g_cfg = dict(GA.DEFAULT_CFG); g_cfg.update(cfg_gate or {})
    d_cfg = dict(DE.DEFAULT_CFG); d_cfg.update(cfg_dec or {})

    # pass 1: score every candidate in the dataset
    per_session: Dict[str, List[Dict]] = {}
    pooled: List[Dict] = []
    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        rows = N.load_session(sdir)
        if not rows:
            continue
        scored = scorer.apply(CA.generate(rows, B.build_blocks(rows)))
        per_session[sid] = scored
        pooled.extend(scored)

    # pass 2: calibrate the operating point on THIS dataset's distribution, then gate
    calibrated = SC.calibrate(pooled, calibration)
    by_session: Dict[str, List[Dict]] = collections.defaultdict(list)
    for c in calibrated:
        by_session[c["session_id"]].append(c)

    rows_by: Dict[str, List[Dict]] = {}
    blocks_by: Dict[str, List[Dict]] = {}
    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        if sid not in by_session:
            continue
        r = N.load_session(sdir)
        rows_by[sid] = r
        blocks_by[sid] = B.build_blocks(r)

    rich: List[Dict] = []
    all_routed: List[Dict] = []
    n_seg = 0
    for sid in sorted(by_session):
        routed = GA.route(sorted(by_session[sid], key=lambda x: x["at_seq"]), g_cfg)
        all_routed.extend(routed)
        segs = DE.decode_session(routed, d_cfg)
        for k, s in enumerate(segs):
            s["session_id"] = sid
            s["exec_uid"] = f"{sid}#e{k:04d}"
            s["confidence"] = round(s["score"], 4)
            rich.append(s)
        n_seg += len(segs)

    # stage 8: labelling. Clustering is GLOBAL across the dataset, which is what makes the
    # same process receive the same string in every session.
    rich = LB.label_segments(rich, rows_by, blocks_by)
    lab = LB.label_report(rich)

    problems = DE.violations(rich, d_cfg)
    _check(problems, "decoder hard constraints")

    with open(os.path.join(out_root, "segments_rich.jsonl"), "w", encoding="utf-8") as fh:
        for r in rich:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- the deliverable: exactly four keys, validated before it is considered written.
    # An invalid artifact is a hard failure, never a warning (schemas.py convention): a
    # malformed segments.jsonl is the one file a reviewer actually reads.
    delivered: Optional[str] = None
    if deliverable:
        rows_out: List[Dict] = []
        for r in sorted(rich, key=lambda x: (x["session_id"], x["start_ms"])):
            rows_out.append({"session_id": r["session_id"], "start": _iso(r["start_ms"]),
                             "end": _iso(r["end_ms"]), "label": r["label"]})
        _check(VS.validate(rows_out, session_ids=set(rows_by)),
               f"{deliverable} (DATA_CONTRACT §6)")
        with open(deliverable, "w", encoding="utf-8") as fh:
            for r in rows_out:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        delivered = deliverable
        log.info("wrote %s — %d segments, %d labels", deliverable, len(rows_out),
                 lab.get("n_labels"))
    with open(os.path.join(out_root, "thresholds.json"), "w", encoding="utf-8") as fh:
        json.dump(thresholds_manifest(CA.DEFAULT_CFG, g_cfg, d_cfg, scorer, calibration), fh,
                  ensure_ascii=False, indent=1, default=list)

    return {"dataset": dataset_root, "segments": n_seg,
            "deliverable": delivered,
            "calibration": calibration,
            "candidates": len(pooled),
            "conversion_pct": round(100 * 2 * n_seg / len(pooled), 2) if pooled else None,
            "constraint_violations": len(problems),
            "gate": GA.routing_report(all_routed),
            "labels": lab,
            "scorer": scorer.meta,
            "decoder_cfg": {k: v for k, v in d_cfg.items()}}


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
    ap.add_argument("--no-candidates", action="store_true",
                    help="skip candidates.jsonl (DATA_CONTRACT §10.2)")
    ap.add_argument("--segment", action="store_true",
                    help="run the Step 1 chain: candidates -> score -> gate -> decode")
    ap.add_argument("--fit-scorer", action="store_true",
                    help="fit the candidate scorer on this dataset's clean GT tier")
    ap.add_argument("--scorer", default=SCORER_PATH)
    ap.add_argument("--calibration", choices=SC.CALIBRATION_MODES, default="percentile",
                    help="operating-point calibration; percentile transfers across datasets")
    ap.add_argument("--no-llm", action="store_true", default=True,
                    help="the only supported mode; routed candidates use rule_decision")
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

    if a.fit_scorer:
        print(json.dumps(fit_scorer(root, a.scorer), ensure_ascii=False, indent=2))
        return 0
    if a.segment:
        try:
            print(json.dumps(segment(root, out, a.scorer, no_llm=True,
                                     calibration=a.calibration),
                             ensure_ascii=False, indent=2, default=str))
        except ArtifactInvalid as e:
            print(f"CONSTRAINT VIOLATION: {e}", file=sys.stderr)
            return 2
        return 0

    try:
        s = build(root, out, window=a.window, min_events=a.min_events, min_ms=a.min_ms,
                  max_lag=a.max_lag, write_windows=not a.no_windows,
                  write_candidates=not a.no_candidates)
    except ArtifactInvalid as e:
        print(f"ARTIFACT CONTRACT VIOLATION: {e}", file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in s.items() if k != "per_session"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
