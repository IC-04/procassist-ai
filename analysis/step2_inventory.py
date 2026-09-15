"""Step 2 — Dataset B process inventory.

One deterministic script. It produces **evidence**, not a recommendation: metrics per process
label, the pass/fail of gates declared before the numbers were seen, and an ordinal band on two
axes that are never summed. The shortlist and the business judgement are written by a human in
`reports/STEP2_ANALYSIS.md` and are marked there as such.

Four rules this file is built around, each of which is easy to violate by accident:

  * **Attribution is by `seq`, never by block containment.** A segment's `start_seq`/`end_seq`
    index the normalised event stream directly. Block containment silently undercounts every
    label that averages less than one whole block per execution — measured here,
    `payroll-items__p05` at ~0.8 blocks/execution and
    `leave-applications-payroll-items__p11` at ~0.7 would both lose events to it. Block-level
    fields (operator, element ids/labels, field keys, screenshots) are joined by seq-range
    OVERLAP with the block's `first_seq`/`last_seq`, which is the correct join for a field that
    belongs to a block rather than to an event.

  * **No fabricated business variables.** Labour cost, monetary ROI, FTE savings, business
    criticality, compliance exposure, API availability, error/rework rate and true production
    volume are MISSING from this telemetry. Nothing here computes, estimates or imputes them.

  * **No absolute-time claims.** `README.md` states that waiting time is compressed in the
    capture environment. Every duration is emitted for RELATIVE comparison between processes,
    and the JSON carries that caveat in `_caveats` so it travels with the numbers.

  * **Deterministic.** Every collection is sorted before it is written; two runs are
    byte-identical, asserted by test.

No ground truth is read. Dataset A is not opened.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import hashlib
import json
import logging
import os
import statistics
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from procmine import normalise as N
from procmine import identity as ID

log = logging.getLogger("analysis.step2_inventory")

# Event-type families. These mirror the vocabulary in `DATA_SCHEMA.md` §2; they are counted,
# never interpreted as intent.
KEYSTROKE = ("keystroke", "text_input_complete")
CLICK = ("mouse_click", "browser_click", "mouse_double_click")
CLIPBOARD = ("clipboard_change",)
FORM_INPUT = ("browser_form_input",)
NAV = ("app_switch", "browser_navigation", "window_title_change", "browser_tab_event")

# --- gates, declared BEFORE the numbers were looked at (see the module docstring and the
#     report). A gate failure must be explainable in one sentence from gates.json alone, so
#     every gate records the number that decided it.
GATES = {
    "G1_evidence_sufficiency": "n_executions >= 5 AND n_sessions >= 3 AND n_operators >= 2",
    "G2_is_business_work": ("NOT (portal-root/dashboard navigation AND "
                            "form_inputs_per_execution < 0.5 AND clipboard_per_execution < 1.0)"),
    "G3_has_target_surface": "distinct_routes >= 1 AND distinct_element_ids >= 1",
}

# Routes that are a portal entry point rather than a place work is done. Structural: a bare
# root or a dashboard path. Used ONLY by G2, and only in conjunction with the two interaction
# thresholds — a dashboard label with real form input would pass.
NAVIGATIONAL_ROUTES = ("/", "/dashboard", "/index", "/home")

# Shells and recording infrastructure that appear in the app list but are not business systems.
# `procmine-desktop-agent` is the recorder itself; `prl_cc` is the VM control centre; the rest
# are OS shells a user passes through. Counted and reported SEPARATELY — `distinct_apps` keeps
# its declared definition and the suitability band is NOT re-tuned around this, because the
# band boundaries were declared before the numbers were seen. Reporting both makes the
# distortion visible instead of silently correcting for it.
CAPTURE_SHELL_APPS = ("procmine-desktop-agent", "prl_cc", "OpenWith", "WindowsTerminal",
                      "Windows Explorer")

# --- banding boundaries, stated here and repeated in the report. Ordinal only; the two axes
#     are NEVER summed into a composite score.
IMPACT_BANDS = {
    "share_of_segmented_time": (0.15, 0.07),   # High >= .15, Medium >= .07
    "n_executions": (20, 10),
    "n_operators": (3, 2),
    "n_sessions": (10, 5),
}
SUITABILITY_BANDS = {
    "route_jaccard": (0.85, 0.60),             # High >= .85, Medium >= .60
    "transfer_per_execution": (2.0, 0.5),      # clipboard + form inputs
    "distinct_apps": (2, 3),                   # FEWER is better: High <= 2, Medium <= 3
    "route_concentration": (0.80, 0.60),       # share of the modal route
}


# ---------------------------------------------------------------- helpers

def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _family(label: str) -> str:
    """The route family: everything before the `__pNN` sub-label suffix."""
    return label.rsplit("__p", 1)[0] if "__p" in label else label


def _mean(v: Sequence[float]) -> Optional[float]:
    return round(float(statistics.mean(v)), 4) if v else None


def _pairwise_jaccard(sets: Sequence[Sequence[str]]) -> Optional[float]:
    """Mean pairwise Jaccard, reusing `identity._binary_jaccard` rather than reimplementing it.

    `idf=False` because this is a within-process repeatability measure over a handful of
    executions, where an IDF weighting computed from that same handful would be noise. It is a
    proxy for the Bosco et al. determinism condition (STEP2_RESEARCH_REVIEW §3.2), not a
    validated production predictor, and the report says so wherever it appears.
    """
    if len(sets) < 2:
        return None
    if not any(sets):
        # `_binary_jaccard` defines both-empty as 1.0 — correct for its own purpose, and
        # actively misleading here: a label whose executions have NO routes at all would read
        # as perfectly deterministic. Absence of evidence is reported as absence.
        # (Caught in Task 7 validation on `hr人事給与システム__p09`, which has 0 routes.)
        return None
    M = ID._binary_jaccard(list(sets), idf=False)
    n = len(sets)
    vals = [float(M[i][j]) for i in range(n) for j in range(i + 1, n)]
    return round(sum(vals) / len(vals), 4) if vals else None


def _band(value: Optional[float], hi: float, lo: float, lower_is_better: bool = False) -> str:
    if value is None:
        return "Unknown"
    if lower_is_better:
        return "High" if value <= hi else ("Medium" if value <= lo else "Low")
    return "High" if value >= hi else ("Medium" if value >= lo else "Low")


def _collapse(seq: Sequence[str]) -> List[str]:
    out: List[str] = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


# ---------------------------------------------------------------- loading

def load_world(dataset_root: str, build_root: str) -> Dict[str, Any]:
    """Segments, blocks and the normalised event stream, keyed by session."""
    seg_path = os.path.join(build_root, "segments_rich.jsonl")
    blk_path = os.path.join(build_root, "blocks.jsonl")
    segments = [json.loads(l) for l in open(seg_path, encoding="utf-8")]
    blocks = [json.loads(l) for l in open(blk_path, encoding="utf-8")]

    rows_by: Dict[str, List[Dict]] = {}
    for sdir in N.iter_session_dirs(dataset_root):
        sid = os.path.basename(sdir)
        r = N.load_session(sdir)
        if r:
            rows_by[sid] = r

    blocks_by: Dict[str, List[Dict]] = collections.defaultdict(list)
    for b in blocks:
        blocks_by[b["session_id"]].append(b)
    for v in blocks_by.values():
        v.sort(key=lambda b: b["first_seq"])

    return {"segments": segments, "blocks_by": dict(blocks_by), "rows_by": rows_by,
            "segments_sha256": _sha256(seg_path), "blocks_sha256": _sha256(blk_path)}


def attribute(segment: Dict, rows: Sequence[Dict], blocks: Sequence[Dict]) -> Dict[str, Any]:
    """Events and block-level evidence belonging to one execution.

    Events: `start_seq <= seq <= end_seq` against the normalised stream — direct indexing, not
    containment. Blocks: seq-range OVERLAP with `first_seq`/`last_seq`, because a block-level
    field describes the whole block and an execution may cover only part of one.
    """
    a, b = segment["start_seq"], segment["end_seq"]
    seqs = [r["seq"] for r in rows]
    lo = bisect.bisect_left(seqs, a)
    hi = bisect.bisect_right(seqs, b)
    events = list(rows[lo:hi])
    blks = [x for x in blocks if x["first_seq"] <= b and x["last_seq"] >= a]
    return {"events": events, "blocks": blks}


# ---------------------------------------------------------------- per-execution record

def execution_record(segment: Dict, rows: Sequence[Dict], blocks: Sequence[Dict]) -> Dict:
    """Everything measurable about one execution. Pure; reads no GT field."""
    att = attribute(segment, rows, blocks)
    ev, blks = att["events"], att["blocks"]
    et = collections.Counter(r.get("event_type") for r in ev)

    surfaces = _collapse([x.get("surface", "") for x in blks if x.get("surface")])
    routes = sorted({x.get("route") or "" for x in blks if x.get("route")})
    origins = sorted({x.get("origin") or "" for x in blks if x.get("origin")})
    apps = sorted({x.get("app") or "" for x in blks if x.get("app")})
    operators = sorted({x.get("operator") or "" for x in blks if x.get("operator")})

    def _bag(key: str) -> List[str]:
        out: set = set()
        for x in blks:
            v = x.get(key) or []
            if isinstance(v, (list, tuple)):
                out.update(str(t) for t in v if t)
        return sorted(out)

    return {
        "exec_uid": segment["exec_uid"],
        "label": segment["label"],
        "session_id": segment["session_id"],
        "score": round(float(segment.get("score") or 0.0), 4),
        "duration_seconds": round((segment["end_ms"] - segment["start_ms"]) / 1000.0, 3),
        "n_events": len(ev),
        "operators": operators,
        "surface_shape": surfaces,
        "surface_set": sorted(set(surfaces)),
        "routes": routes,
        "origins": origins,
        "apps": apps,
        "transitions": max(0, len(surfaces) - 1),
        "keystrokes": sum(et.get(t, 0) for t in KEYSTROKE),
        "clicks": sum(et.get(t, 0) for t in CLICK),
        "clipboard": sum(et.get(t, 0) for t in CLIPBOARD),
        "form_inputs": sum(et.get(t, 0) for t in FORM_INPUT),
        "nav": sum(et.get(t, 0) for t in NAV),
        "element_ids": _bag("element_ids"),
        "element_labels": _bag("element_labels"),
        "field_keys": _bag("field_keys"),
        "value_hashes": _bag("value_hashes"),
        "screenshots": sum(len(x.get("screenshots") or []) for x in blks),
        "n_blocks_overlapping": len(blks),
    }


# ---------------------------------------------------------------- per-label aggregation

def summarise_label(label: str, execs: Sequence[Dict], total_seconds_all: float) -> Dict:
    """Aggregate one process label. Durations are RELATIVE-comparison figures only."""
    durs = sorted(x["duration_seconds"] for x in execs)
    total = round(sum(durs), 3)
    med = statistics.median(durs)
    p25 = durs[max(0, int(0.25 * (len(durs) - 1)))]
    p75 = durs[min(len(durs) - 1, int(round(0.75 * (len(durs) - 1))))]
    n = len(execs)

    apps = sorted({a for x in execs for a in x["apps"]})
    routes = sorted({r for x in execs for r in x["routes"]})
    origins = sorted({o for x in execs for o in x["origins"]})
    operators = sorted({o for x in execs for o in x["operators"]})
    sessions = sorted({x["session_id"] for x in execs})

    route_freq = collections.Counter(r for x in execs for r in x["routes"])
    modal_route_share = (round(route_freq.most_common(1)[0][1] / n, 4)
                         if route_freq else 0.0)

    shapes = [tuple(x["surface_shape"]) for x in execs]
    identical_shapes = max(collections.Counter(shapes).values()) if shapes else 0

    def per_exec(k: str) -> float:
        return round(sum(x[k] for x in execs) / n, 4)

    return {
        "label": label,
        "route_family": _family(label),
        # --- volume
        "n_executions": n,
        "n_sessions": len(sessions),
        "n_operators": len(operators),
        # --- effort (RELATIVE ONLY — waits are compressed in the capture environment)
        "total_seconds": total,
        "median_seconds": round(med, 3),
        "p25_seconds": round(p25, 3),
        "p75_seconds": round(p75, 3),
        "iqr_over_median": round((p75 - p25) / med, 4) if med else None,
        # 9dp, not 6: thirteen labels each rounded to 6dp drift up to ~6e-6 from a sum of 1.0,
        # which is larger than the tolerance the conformance test should be allowed to assert.
        # The REPORT quotes one decimal place of a percentage; this precision is for the sum
        # identity, not for any ranking claim.
        "share_of_segmented_time": round(total / total_seconds_all, 9) if total_seconds_all else 0.0,
        # --- systems
        "distinct_apps": len(apps),
        "distinct_routes": len(routes),
        "distinct_origins": len(origins),
        "distinct_business_apps": len([a for a in apps if a not in CAPTURE_SHELL_APPS]),
        "capture_shell_apps": [a for a in apps if a in CAPTURE_SHELL_APPS],
        "apps": apps,
        "routes": routes,
        "origins": origins,
        "mean_transitions_per_execution": per_exec("transitions"),
        # --- interaction
        "total_keystrokes": sum(x["keystrokes"] for x in execs),
        "total_clicks": sum(x["clicks"] for x in execs),
        "total_clipboard": sum(x["clipboard"] for x in execs),
        "total_form_inputs": sum(x["form_inputs"] for x in execs),
        "total_nav": sum(x["nav"] for x in execs),
        "keystrokes_per_execution": per_exec("keystrokes"),
        "clicks_per_execution": per_exec("clicks"),
        "nav_per_execution": per_exec("nav"),
        # --- transfer signature (the transcription fingerprint)
        "clipboard_per_execution": per_exec("clipboard"),
        "form_inputs_per_execution": per_exec("form_inputs"),
        "transfer_per_execution": round(per_exec("clipboard") + per_exec("form_inputs"), 4),
        # --- determinism (a PROXY for Bosco et al. §3.2, not a validated predictor)
        "route_set_jaccard": _pairwise_jaccard([x["routes"] for x in execs]),
        "surface_set_jaccard": _pairwise_jaccard([x["surface_set"] for x in execs]),
        "max_identical_shapes": identical_shapes,
        "route_concentration": modal_route_share,
        # --- confidence
        "mean_score": _mean([x["score"] for x in execs]),
        "min_score": round(min(x["score"] for x in execs), 4),
        # --- observability of the target system
        "distinct_element_ids": len({e for x in execs for e in x["element_ids"]}),
        "distinct_element_labels": len({e for x in execs for e in x["element_labels"]}),
        "distinct_field_keys": len({e for x in execs for e in x["field_keys"]}),
        "distinct_value_hashes": len({e for x in execs for e in x["value_hashes"]}),
        "screenshots": sum(x["screenshots"] for x in execs),
        "element_ids": sorted({e for x in execs for e in x["element_ids"]}),
        "field_keys": sorted({e for x in execs for e in x["field_keys"]}),
        "mean_blocks_per_execution": per_exec("n_blocks_overlapping"),
    }


# ---------------------------------------------------------------- gates

def apply_gates(p: Dict) -> Dict[str, Any]:
    """Each gate records the NUMBER that decided it, so a failure is explainable from this
    file alone. Declared before the results were seen; not tuned afterwards."""
    g1_pass = p["n_executions"] >= 5 and p["n_sessions"] >= 3 and p["n_operators"] >= 2
    nav_only = (all(r in NAVIGATIONAL_ROUTES for r in p["routes"]) if p["routes"] else True)
    g2_fail = (nav_only and p["form_inputs_per_execution"] < 0.5
               and p["clipboard_per_execution"] < 1.0)
    g3_pass = p["distinct_routes"] >= 1 and p["distinct_element_ids"] >= 1
    return {
        "label": p["label"],
        "G1_evidence_sufficiency": {
            "pass": bool(g1_pass), "rule": GATES["G1_evidence_sufficiency"],
            "n_executions": p["n_executions"], "n_sessions": p["n_sessions"],
            "n_operators": p["n_operators"],
            "decided_by": ("passed" if g1_pass else
                           "; ".join(
                               [f"n_executions={p['n_executions']} < 5"] * (p["n_executions"] < 5)
                               + [f"n_sessions={p['n_sessions']} < 3"] * (p["n_sessions"] < 3)
                               + [f"n_operators={p['n_operators']} < 2"] * (p["n_operators"] < 2))),
        },
        "G2_is_business_work": {
            "pass": bool(not g2_fail), "rule": GATES["G2_is_business_work"],
            "routes": p["routes"], "all_routes_navigational": bool(nav_only),
            "form_inputs_per_execution": p["form_inputs_per_execution"],
            "clipboard_per_execution": p["clipboard_per_execution"],
            "decided_by": ("passed" if not g2_fail else
                           f"routes {p['routes']} are portal navigation and "
                           f"form_inputs_per_execution={p['form_inputs_per_execution']} < 0.5 "
                           f"and clipboard_per_execution={p['clipboard_per_execution']} < 1.0"),
        },
        "G3_has_target_surface": {
            "pass": bool(g3_pass), "rule": GATES["G3_has_target_surface"],
            "distinct_routes": p["distinct_routes"],
            "distinct_element_ids": p["distinct_element_ids"],
            "decided_by": ("passed" if g3_pass else
                           f"distinct_routes={p['distinct_routes']}, "
                           f"distinct_element_ids={p['distinct_element_ids']}"),
        },
        "all_pass": bool(g1_pass and not g2_fail and g3_pass),
    }


# ---------------------------------------------------------------- banding

def band(p: Dict) -> Dict[str, Any]:
    """Two ordinal axes. They are NEVER summed: the research review records volume and
    suitability as separate questions, and netting them hides which one carried the answer
    (STEP2_RESEARCH_REVIEW §3.3, §5)."""
    ib = IMPACT_BANDS
    sb = SUITABILITY_BANDS
    impact_parts = {
        "share_of_segmented_time": _band(p["share_of_segmented_time"], *ib["share_of_segmented_time"]),
        "n_executions": _band(p["n_executions"], *ib["n_executions"]),
        "n_operators": _band(p["n_operators"], *ib["n_operators"]),
        "n_sessions": _band(p["n_sessions"], *ib["n_sessions"]),
    }
    suit_parts = {
        "route_set_jaccard": _band(p["route_set_jaccard"], *sb["route_jaccard"]),
        "transfer_per_execution": _band(p["transfer_per_execution"], *sb["transfer_per_execution"]),
        "distinct_apps": _band(p["distinct_apps"], *sb["distinct_apps"], lower_is_better=True),
        "route_concentration": _band(p["route_concentration"], *sb["route_concentration"]),
    }

    def roll(parts: Dict[str, str]) -> str:
        # Majority of the component bands, ties broken DOWNWARD. Ordinal throughout: no
        # arithmetic is performed on a band, and no composite score is produced.
        c = collections.Counter(v for v in parts.values() if v != "Unknown")
        if not c:
            return "Unknown"
        top = max(c.values())
        winners = [b for b in ("Low", "Medium", "High") if c.get(b, 0) == top]
        return winners[0]

    return {"impact": roll(impact_parts), "impact_components": impact_parts,
            "suitability": roll(suit_parts), "suitability_components": suit_parts}


# ---------------------------------------------------------------- driver

CSV_COLUMNS = [
    "label", "route_family", "n_executions", "n_sessions", "n_operators",
    "total_seconds", "median_seconds", "p25_seconds", "p75_seconds", "iqr_over_median",
    "share_of_segmented_time", "distinct_apps", "distinct_routes", "distinct_origins",
    "distinct_business_apps",
    "mean_transitions_per_execution", "keystrokes_per_execution", "clicks_per_execution",
    "clipboard_per_execution", "form_inputs_per_execution", "transfer_per_execution",
    "nav_per_execution", "route_set_jaccard", "surface_set_jaccard", "max_identical_shapes",
    "route_concentration", "mean_score", "min_score", "distinct_element_ids",
    "distinct_element_labels", "distinct_field_keys", "distinct_value_hashes", "screenshots",
    "mean_blocks_per_execution", "impact_band", "suitability_band", "gates_all_pass",
]


def build(dataset_root: str, build_root: str) -> Dict[str, Any]:
    world = load_world(dataset_root, build_root)
    segments = sorted(world["segments"], key=lambda s: (s["session_id"], s["start_ms"]))

    execs: List[Dict] = []
    for s in segments:
        sid = s["session_id"]
        execs.append(execution_record(s, world["rows_by"].get(sid, []),
                                      world["blocks_by"].get(sid, [])))

    by_label: Dict[str, List[Dict]] = collections.defaultdict(list)
    for x in execs:
        by_label[x["label"]].append(x)
    for v in by_label.values():
        v.sort(key=lambda x: x["exec_uid"])

    total_seconds_all = sum(x["duration_seconds"] for x in execs)
    processes = [summarise_label(lab, by_label[lab], total_seconds_all)
                 for lab in sorted(by_label)]
    for p in processes:
        p.update({f"{k}_band" if k in ("impact", "suitability") else k: v
                  for k, v in band(p).items()})
    processes.sort(key=lambda p: (-p["share_of_segmented_time"], p["label"]))

    gates = {p["label"]: apply_gates(p) for p in processes}
    for p in processes:
        p["gates_all_pass"] = gates[p["label"]]["all_pass"]

    families: Dict[str, Dict] = {}
    for fam in sorted({p["route_family"] for p in processes}):
        members = [p for p in processes if p["route_family"] == fam]
        families[fam] = {
            "n_sub_labels": len(members),
            "sub_labels": sorted(p["label"] for p in members),
            "n_executions": sum(p["n_executions"] for p in members),
            "executions_by_sub_label": {p["label"]: p["n_executions"]
                                        for p in sorted(members, key=lambda x: x["label"])},
            "share_of_segmented_time": round(
                sum(p["share_of_segmented_time"] for p in members), 6),
        }

    return {
        "dataset": os.path.basename(dataset_root.rstrip("/\\")),
        "generated_from": {
            "segments_rich_sha256": world["segments_sha256"],
            "blocks_sha256": world["blocks_sha256"],
        },
        "_caveats": [
            "DURATIONS ARE RELATIVE ONLY. README.md states waiting time is compressed in the "
            "capture environment; these figures compare processes with each other and are not "
            "wall-clock effort.",
            "NO BUSINESS VARIABLES. Labour cost, monetary ROI, FTE savings, business "
            "criticality, compliance exposure, API availability, error/rework rate and true "
            "production volume are MISSING from this telemetry and are not computed here.",
            "DETERMINISM IS A PROXY for the Bosco et al. (BPM 2019) automatability condition "
            "(STEP2_RESEARCH_REVIEW §3.2), not a validated production predictor.",
            "Dataset B has NO GROUND TRUTH. Step 1's measured accuracy on Dataset A does not "
            "transfer to these labels.",
            "max_identical_shapes is exact ordered-sequence equality — a harsh test, reported "
            "for completeness. route_set_jaccard is the operative determinism measure.",
        ],
        "totals": {
            "n_executions": len(execs),
            "n_labels": len(processes),
            "n_sessions": len({x["session_id"] for x in execs}),
            "n_operators": len({o for x in execs for o in x["operators"]}),
            "segmented_seconds": round(total_seconds_all, 3),
            "n_route_families": len(families),
        },
        "route_families": families,
        "processes": processes,
        "_gates": gates,
    }


def write(inv: Dict[str, Any], out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    gates = inv.pop("_gates")
    inv_path = os.path.join(out_dir, "process_inventory.json")
    with open(inv_path, "w", encoding="utf-8") as fh:
        json.dump(inv, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    gates_path = os.path.join(out_dir, "gates.json")
    with open(gates_path, "w", encoding="utf-8") as fh:
        json.dump({"_rules": GATES,
                   "_note": "Declared before the numbers were seen and not tuned afterwards. "
                            "Every gate carries the number that decided it.",
                   "labels": {k: gates[k] for k in sorted(gates)}},
                  fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    csv_path = os.path.join(out_dir, "process_inventory.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for p in inv["processes"]:
            w.writerow({k: p.get(k) for k in CSV_COLUMNS})
    inv["_gates"] = gates
    return {"inventory": inv_path, "gates": gates_path, "csv": csv_path}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="analysis.step2_inventory")
    ap.add_argument("--dataset", default="dataset_b")
    ap.add_argument("--build", default=None, help="default: build/<dataset>")
    ap.add_argument("--out", default=None, help="default: build/<dataset>/step2")
    ap.add_argument("--figures", default="figures", help="figure output directory")
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING)

    name = os.path.basename(a.dataset.rstrip("/\\"))
    build_root = a.build or os.path.join("build", name)
    out_dir = a.out or os.path.join(build_root, "step2")

    inv = build(a.dataset, build_root)
    paths = write(inv, out_dir)

    if not a.no_figures:
        from analysis import step2_figures
        paths.update(step2_figures.render(inv, a.figures))

    t = inv["totals"]
    print(json.dumps({"totals": t, "written": paths,
                      "gated_in": sorted(p["label"] for p in inv["processes"]
                                         if p["gates_all_pass"]),
                      "gated_out": sorted(p["label"] for p in inv["processes"]
                                          if not p["gates_all_pass"])},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
