"""Phase 3 — hypothesis harness, on Pass 0 + Pass 1 only. No VLM.

reads only:  build/dataset_b/evidence/*.jsonl, build/dataset_b/segments_rich.jsonl,
             build/dataset_b/blocks.jsonl, dataset_b/*/*/events.jsonl
writes only: build/dataset_b/evidence/hypothesis_tests.json

  H1  does a document-derived rule predict the observed disposition?
  H2  do rule-relevant record features predict handling effort?
  H3  is the governing document opened BEFORE the disposition, within the same execution,
      more often than a permutation null?
  H4  does the record carry the variables the rule needs?

`UNTESTABLE` and `INSUFFICIENT_EVIDENCE` are first-class results. A verdict is never forced: if
the dependent variable is constant, or n is below the floor declared here before the numbers were
looked at, that is the answer and it is returned with the number that produced it.

All 11 modules are tested. A module below the floor returns `INSUFFICIENT_EVIDENCE` carrying its
n, so a thin module is visible as thin rather than absent.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import common as C
from . import modules as M
from . import pass0_text as P0

EVIDENCE_FLOOR = 8          # declared before the numbers were inspected
N_PERMUTATIONS = 10_000
SEED = 7

SUPPORTED, REFUTED = "SUPPORTED", "REFUTED"
UNTESTABLE, INSUFFICIENT = "UNTESTABLE", "INSUFFICIENT_EVIDENCE"

AMOUNT_RE = re.compile(r"([0-9][0-9,]*)\s*円")
BTN_OK = re.compile(r"^btn-\w+-ok$")


def _load(dataset: str, name: str) -> List[Dict]:
    p = os.path.join(C.evidence_dir(dataset), name)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def _spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    import numpy as np
    if len(x) < 3:
        return None
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if np.all(a == a[0]) or np.all(b == b[0]):
        return None

    def rank(v):
        order = np.argsort(v, kind="stable")
        r = np.empty(len(v), dtype=float)
        r[order] = np.arange(len(v), dtype=float)
        # average ties, so a constant-heavy variable cannot inflate rho
        _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        sums = np.zeros(len(cnt))
        np.add.at(sums, inv, r)
        return (sums / cnt)[inv]

    ra, rb = rank(a), rank(b)
    ra -= ra.mean(); rb -= rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return float((ra * rb).sum() / den) if den else None


def _permutation_p(x: Sequence[float], y: Sequence[float], observed: float) -> Dict[str, Any]:
    import numpy as np
    rng = np.random.default_rng(SEED)
    b = np.asarray(y, dtype=float)
    null = []
    for _ in range(N_PERMUTATIONS):
        r = _spearman(x, rng.permutation(b))
        if r is not None:
            null.append(abs(r))
    if not null:
        return {"p_value": None, "null": None}
    arr = np.asarray(null)
    return {"p_value": round(float((arr >= abs(observed)).mean()), 5),
            "null": {"n": len(arr), "p50": round(float(np.percentile(arr, 50)), 4),
                     "p95": round(float(np.percentile(arr, 95)), 4),
                     "p99": round(float(np.percentile(arr, 99)), 4)}}


def _amount_of(rec: Dict) -> Optional[float]:
    for k, v in (rec.get("fields") or {}).items():
        if "金額" in k or "amount" in k.lower():
            m = AMOUNT_RE.search(str(v))
            if m:
                return float(m.group(1).replace(",", ""))
    for v in (rec.get("fields") or {}).values():
        m = AMOUNT_RE.search(str(v))
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def _verdict(hypothesis: str, module_id: str, n: int, statistic: Any, null_model: str,
             result: str, reason: str, refs: Sequence[str]) -> Dict[str, Any]:
    return {"hypothesis": hypothesis, "module_id": module_id, "n": n, "statistic": statistic,
            "null_model": null_model, "result": result, "reason": reason,
            "evidence_refs": list(refs)[:12]}


# ---------------------------------------------------------------- context

def build_context(dataset: str, dataset_root: str) -> Dict[str, Any]:
    caps = _load(dataset, "screen_text.jsonl")
    docs = _load(dataset, "documents.jsonl")
    recs = _load(dataset, "records.jsonl")
    outs = _load(dataset, "outcomes.jsonl")
    cov = _load(dataset, "coverage_gaps.jsonl")

    segs = [json.loads(l) for l in
            open(os.path.join(C.ROOT, "build", dataset, "segments_rich.jsonl"),
                 encoding="utf-8")]

    by_session: Dict[str, List[Dict]] = collections.defaultdict(list)
    for e in P0.iter_raw_events(dataset_root):
        by_session[e["_session_id"]].append(e)
    for v in by_session.values():
        v.sort(key=lambda e: (e.get("timestamp_ms") or 0,
                              (e.get("correlation") or {}).get("sequence_number") or 0))

    clip: Dict[str, List[Tuple[int, int, int]]] = collections.defaultdict(list)
    doc_events: Dict[str, List[Tuple[int, int]]] = collections.defaultdict(list)
    for sid, rows in by_session.items():
        for i, e in enumerate(rows):
            if e.get("event_type") == "clipboard_change":
                clip[sid].append((i, e.get("timestamp_ms") or 0,
                                  int((e.get("payload") or {}).get("text_length") or 0)))
            app = ((e.get("context") or {}).get("active_app") or {}).get("app_name") or ""
            if app in ("Microsoft Word", "Notepad", "WordPad"):
                doc_events[sid].append((i, e.get("timestamp_ms") or 0))

    return {"captures": caps, "documents": docs, "records": recs, "outcomes": outs,
            "coverage": cov, "segments": segs, "by_session": dict(by_session),
            "clip": dict(clip), "doc_events": dict(doc_events)}


# ---------------------------------------------------------------- H1

def h1(ctx: Dict[str, Any]) -> List[Dict]:
    outs = ctx["outcomes"]
    out: List[Dict] = []
    by_mod: Dict[Optional[str], List[Dict]] = collections.defaultdict(list)
    for o in outs:
        by_mod[o.get("module_id")].append(o)
    for mid in M.ALL_MODULE_IDS:
        rows = by_mod.get(mid, [])
        toasts = [r for r in rows if r["source"] == "toast"]
        pol = collections.Counter(r["outcome_polarity"] for r in toasts)
        n = len(toasts)
        if n < EVIDENCE_FLOOR:
            out.append(_verdict(
                "H1", mid, n, {"polarity": dict(pol)}, "none — not reached",
                INSUFFICIENT,
                f"only {n} toast outcomes for this module; the declared floor is "
                f"{EVIDENCE_FLOOR}. No verdict is forced.",
                [r["outcome_id"] for r in toasts]))
            continue
        if len(pol) <= 1:
            out.append(_verdict(
                "H1", mid, n, {"polarity": dict(pol), "distinct_outcomes": len(pol)},
                "none — the dependent variable is constant", UNTESTABLE,
                f"all {n} observed dispositions have polarity "
                f"{next(iter(pol))!r}. A rule cannot be shown to predict a constant: any "
                f"predictor scores 100% and the figure would be meaningless. Reporting an "
                f"accuracy here would be the error, not the finding.",
                [r["outcome_id"] for r in toasts]))
            continue
        out.append(_verdict("H1", mid, n, {"polarity": dict(pol)}, "permutation",
                            INSUFFICIENT,
                            "outcome varies, but no rule-to-outcome mapping is derivable from "
                            "Pass 0 alone; requires the Phase 4 residual.",
                            [r["outcome_id"] for r in toasts]))
    return out


# ---------------------------------------------------------------- H2

def h2(ctx: Dict[str, Any]) -> List[Dict]:
    """Rule-relevant record features vs handling effort.

    Feature: the record's amount (the variable every parsed threshold rule keys on).
    Effort:  seconds from the record's first appearance to its disposition toast.
    """
    outs = [o for o in ctx["outcomes"] if o["source"] == "toast"]
    first_seen: Dict[Tuple[str, str], int] = {}
    amount: Dict[str, float] = {}
    for r in ctx["records"]:
        k = (r["session_id"], r["record_id"])
        ts = r.get("timestamp_ms") or 0
        if k not in first_seen or ts < first_seen[k]:
            first_seen[k] = ts
        a = _amount_of(r)
        if a is not None:
            amount.setdefault(r["record_id"], a)

    by_mod: Dict[Optional[str], List[Tuple[float, float, str]]] = collections.defaultdict(list)
    for o in outs:
        k = (o["session_id"], o["record_id"])
        if k not in first_seen or o["record_id"] not in amount:
            continue
        secs = ((o.get("timestamp_ms") or 0) - first_seen[k]) / 1000.0
        if secs <= 0:
            continue
        by_mod[o.get("module_id")].append((amount[o["record_id"]], secs, o["outcome_id"]))

    out: List[Dict] = []
    for mid in M.ALL_MODULE_IDS:
        pts = sorted(by_mod.get(mid, []))
        n = len(pts)
        if n < EVIDENCE_FLOOR:
            out.append(_verdict("H2", mid, n, None, "permutation (not reached)", INSUFFICIENT,
                                f"{n} record-disposition pairs carrying both an amount and a "
                                f"positive elapsed time; floor is {EVIDENCE_FLOOR}.",
                                [p[2] for p in pts]))
            continue
        x = [p[0] for p in pts]
        y = [p[1] for p in pts]
        rho = _spearman(x, y)
        if rho is None:
            out.append(_verdict("H2", mid, n, None, "permutation", UNTESTABLE,
                                "one of the two variables is constant across this module.",
                                [p[2] for p in pts]))
            continue
        perm = _permutation_p(x, y, rho)
        res = (SUPPORTED if perm["p_value"] is not None and perm["p_value"] < 0.05
               else REFUTED)
        out.append(_verdict(
            "H2", mid, n,
            {"spearman_rho": round(rho, 4), "p_value": perm["p_value"],
             "feature": "record amount (JPY)", "effort": "seconds to disposition toast"},
            f"permutation, {N_PERMUTATIONS} shuffles, seed {SEED}; null |rho| "
            f"p50={perm['null']['p50'] if perm['null'] else None} "
            f"p95={perm['null']['p95'] if perm['null'] else None}",
            res,
            ("amount and elapsed time are associated beyond the permutation null"
             if res == SUPPORTED else
             "no association beyond the permutation null; the rule variable does not explain "
             "handling effort in this module"),
            [p[2] for p in pts]))
    return out


# ---------------------------------------------------------------- H3

def h3(ctx: Dict[str, Any]) -> List[Dict]:
    """Is a reference document opened BEFORE the disposition, inside the same Step 1 execution,
    more often than chance placement of the same documents within the same session?"""
    import numpy as np
    segs_by: Dict[str, List[Dict]] = collections.defaultdict(list)
    for s in ctx["segments"]:
        segs_by[s["session_id"]].append(s)
    for v in segs_by.values():
        v.sort(key=lambda s: s["start_ms"])

    by_mod: Dict[Optional[str], List[int]] = collections.defaultdict(list)
    refs: Dict[Optional[str], List[str]] = collections.defaultdict(list)
    pools: Dict[Optional[str], List[Tuple[int, int, int]]] = collections.defaultdict(list)

    for row in ctx["coverage"]:
        sid, idx, mid = row["session_id"], row["event_index"], row.get("module_id")
        seg = next((s for s in segs_by.get(sid, [])
                    if s["start_seq"] <= idx <= s["end_seq"]), None)
        if seg is None:
            continue
        docs = [i for i, _ in ctx["doc_events"].get(sid, [])
                if seg["start_seq"] <= i <= seg["end_seq"]]
        if not docs:
            continue
        by_mod[mid].append(1 if any(i < idx for i in docs) else 0)
        refs[mid].append(row["disposition_id"])
        pools[mid].append((seg["start_seq"], seg["end_seq"], idx))

    out: List[Dict] = []
    rng = np.random.default_rng(SEED)
    for mid in M.ALL_MODULE_IDS:
        hits = by_mod.get(mid, [])
        n = len(hits)
        if n < EVIDENCE_FLOOR:
            out.append(_verdict("H3", mid, n, None, "permutation (not reached)", INSUFFICIENT,
                                f"{n} dispositions inside an execution that also opened a "
                                f"document; floor is {EVIDENCE_FLOOR}.", refs.get(mid, [])))
            continue
        observed = float(np.mean(hits))
        null = []
        pool = pools[mid]
        for _ in range(N_PERMUTATIONS):
            c = 0
            for a, b, idx in pool:
                span = max(1, b - a)
                c += 1 if rng.integers(a, a + span + 1) < idx else 0
            null.append(c / len(pool))
        arr = np.asarray(null)
        p = float((arr >= observed).mean())
        res = SUPPORTED if p < 0.05 else REFUTED
        out.append(_verdict(
            "H3", mid, n,
            {"observed_rate_document_before": round(observed, 4), "p_value": round(p, 5)},
            f"permutation, {N_PERMUTATIONS} draws, seed {SEED}; a document event is placed "
            f"uniformly inside the same execution span. null p50="
            f"{round(float(np.percentile(arr, 50)), 4)} p95={round(float(np.percentile(arr, 95)), 4)}",
            res,
            ("documents are opened before the disposition more often than chance placement"
             if res == SUPPORTED else
             "document-before-disposition is not more frequent than chance placement within "
             "the same execution"),
            refs.get(mid, [])))
    return out


# ---------------------------------------------------------------- H4

def h4(ctx: Dict[str, Any]) -> List[Dict]:
    """Per module: do the records carry the variables the parsed rules need?

    This is the hypothesis that does NOT depend on outcome variance, so it is the one that can
    return a hard verdict on this dataset.
    """
    rules: List[Dict] = []
    for d in ctx["documents"]:
        for r in d["extracted_rules"]:
            if r["parsed"] and r["rule_kind"] in ("threshold", "conditional_item"):
                rules.append({"rule_id": r["rule_id"], "document_id": d["document_id"],
                              "kind": r["rule_kind"], "parsed": r["parsed"],
                              "raw": r["raw_text_ja"][:80]})
    required_units = set()
    for r in rules:
        p = r["parsed"]
        for c in (p.get("tiers") or p.get("conditions") or []):
            required_units.add(c.get("unit"))

    by_mod: Dict[Optional[str], List[Dict]] = collections.defaultdict(list)
    for rec in ctx["records"]:
        by_mod[rec.get("module_id")].append(rec)

    out: List[Dict] = []
    for mid in M.ALL_MODULE_IDS:
        recs = by_mod.get(mid, [])
        n = len(recs)
        if n < EVIDENCE_FLOOR:
            out.append(_verdict("H4", mid, n, None, "n/a — set comparison", INSUFFICIENT,
                                f"{n} parsed records for this module; floor is "
                                f"{EVIDENCE_FLOOR}.", []))
            continue
        with_amount = sum(1 for r in recs if _amount_of(r) is not None)
        headers = collections.Counter(h for r in recs for h in (r.get("column_headers") or []))
        has_authority = sum(1 for r in recs
                            if any("承認権限" in k for k in (r.get("fields") or {})))
        share = with_amount / n
        present = sorted(h for h, _ in headers.most_common())
        if share >= 0.9:
            res, why = SUPPORTED, (
                f"{with_amount}/{n} records ({share:.0%}) carry a 金額 value, which is the "
                f"variable every parsed threshold rule keys on.")
        elif share <= 0.1:
            res, why = REFUTED, (
                f"only {with_amount}/{n} records ({share:.0%}) carry any 金額 value, so a "
                f"monetary threshold rule is INAPPLICABLE to this module as recorded.")
        else:
            res, why = INSUFFICIENT, (
                f"{with_amount}/{n} records ({share:.0%}) carry 金額 — neither present nor "
                f"absent enough to rule on.")
        out.append(_verdict(
            "H4", mid, n,
            {"records_with_amount": with_amount, "share_with_amount": round(share, 4),
             "records_with_approval_authority": has_authority,
             "distinct_column_headers": present,
             "n_parsed_rules_dataset_wide": len(rules),
             "rule_units_required": sorted(u for u in required_units if u)},
            "n/a — set comparison between rule variables and record fields", res, why,
            [r["rule_id"] for r in rules[:8]]))
    return out


def run(dataset: str, dataset_root: str) -> Dict[str, Any]:
    ctx = build_context(dataset, dataset_root)
    tests = h1(ctx) + h2(ctx) + h3(ctx) + h4(ctx)
    tally = collections.Counter((t["hypothesis"], t["result"]) for t in tests)
    doc = {
        "_purpose": "hypothesis verdicts from Pass 0 + Pass 1 only. No VLM was called.",
        "_rules": {
            "evidence_floor_n": EVIDENCE_FLOOR,
            "permutations": N_PERMUTATIONS, "seed": SEED,
            "declared": "the floor and the permutation settings were fixed before the numbers "
                        "were inspected; UNTESTABLE and INSUFFICIENT_EVIDENCE are first-class "
                        "results and no verdict is forced.",
        },
        "summary": {f"{h}:{r}": n for (h, r), n in sorted(tally.items())},
        "tests": sorted(tests, key=lambda t: (t["hypothesis"], t["module_id"])),
    }
    art = C.write_json(doc, os.path.join(C.evidence_dir(dataset), "hypothesis_tests.json"),
                       dataset)
    C.merge_manifest(dataset, "pass3", C.run_manifest(
        dataset, "pass3", {"hypothesis_tests.json": art},
        config=doc["_rules"], extra={"summary": doc["summary"]}))
    return {"summary": {"pass": "3", "counts": doc["summary"],
                        "artifact": art["path"]}, "doc": doc}
