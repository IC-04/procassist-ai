"""Phase 3.5 — reconcile three independent module keys.

reads only:  build/dataset_b/evidence/{screen_text,records}.jsonl
writes only: build/dataset_b/evidence/module_key_reconciliation.json

Phase 3 reported 539 of 3,011 records (17.9%) where the capture URL and the record-id prefix
disagree about which business module a record belongs to. That bears directly on the
`(origin, route)` module inventory in `docs/STEP2_AUTOMATION_OPPORTUNITY.md`, so it is settled
before anything is built on top of that inventory.

Three keys, deliberately independent:

  K1  URL/route      `(origin, route)` from `context.active_browser_tab.url` — what Step 2 uses
  K2  screen header  the system name and the `ダッシュボード / <module>` breadcrumb rendered IN
                     the capture text. This is what the operator was actually looking at.
  K3  record prefix  the `P<n>` of the record id. The P1-5/P6-10/P11-13 -> HR/FI/LO mapping is
                     treated as a HYPOTHESIS and derived from the queue headers, not assumed.

The decisive test for the leading explanation — "these are cross-module queue views, so both
keys are right about different things" — is whether a single capture contains rows with mixed
record-id prefixes belonging to different modules. That test is run here and its answer decides
which key is authoritative.
"""
from __future__ import annotations

import collections
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import common as C
from . import modules as M

RID_LINE = re.compile(r"^P\d{1,2}-\d{8}-\d{3}$")
BREADCRUMB = re.compile(r"ダッシュボード\s*/\s*(.+)")
SYSTEM_NAMES = {
    "HR人事給与システム": "HR",
    "財務会計システム": "FI",
    "受発注在庫管理システム": "LO",
}
# A list word is a weak test for "this capture shows a queue": modules use different ones
# (発注一覧 was missed by the first four, which silently dropped P10 / FI|発注管理 out of the
# derived map entirely). The robust test is simply that the capture contains two or more record
# id lines, which is what `is_queue_capture` uses.
LIST_WORDS = ("申請一覧", "処理一覧", "処理待ち一覧", "入社照合一覧", "発注一覧", "一覧")


def is_queue_capture(text: str) -> bool:
    """Two or more record-id lines. Independent of the module's choice of list heading."""
    return sum(1 for l in _lines(text) if RID_LINE.match(l)) >= 2


def _lines(text: str) -> List[str]:
    return [l.strip() for l in text.splitlines() if l.strip()]


def screen_key(text: str) -> Tuple[Optional[str], Optional[str]]:
    """K2 — `(system_code, module_name_ja)` as rendered on screen, verbatim Japanese."""
    system = next((code for name, code in SYSTEM_NAMES.items() if name in text), None)
    crumb = None
    for l in _lines(text):
        m = BREADCRUMB.match(l)
        if m:
            crumb = m.group(1).strip()
            break
    return system, crumb


def prefixes_in(text: str) -> collections.Counter:
    return collections.Counter(l.split("-")[0] for l in _lines(text) if RID_LINE.match(l))


def derive_prefix_map(captures: Sequence[Dict]) -> Dict[str, Any]:
    """K3, DERIVED rather than assumed.

    For every queue capture that renders both a system name and a breadcrumb, associate the
    record-id prefixes in its table with that screen-declared module. The mapping is only as
    good as its purity, which is reported per prefix.
    """
    assoc: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    covered = 0
    for cap in captures:
        if not is_queue_capture(cap["text_ja"]):
            continue
        system, crumb = screen_key(cap["text_ja"])
        if not (system and crumb):
            continue
        covered += 1
        for p, n in prefixes_in(cap["text_ja"]).items():
            assoc[p][f"{system}|{crumb}"] += n
    out: Dict[str, Any] = {}
    for p in sorted(assoc, key=lambda x: (len(x), x)):
        c = assoc[p]
        total = sum(c.values())
        modal, n = c.most_common(1)[0]
        out[p] = {"screen_module": modal, "system": modal.split("|")[0],
                  "module_name_ja": modal.split("|")[1],
                  "support": n, "total": total, "purity": round(n / total, 4),
                  "distribution": dict(c.most_common())}
    return {"map": out, "queue_captures_used": covered}


def mixed_prefix_test(captures: Sequence[Dict], pmap: Dict[str, Any]) -> Dict[str, Any]:
    """THE DECISIVE TEST.

    If the disagreements are cross-module queue views, a single capture will contain prefixes
    belonging to DIFFERENT screen-declared modules. If every mixed capture's prefixes map to the
    SAME module, the mixing is within-module (a module with two record streams) and the
    cross-module-view explanation is wrong.
    """
    mixed: List[Dict] = []
    for cap in captures:
        if not is_queue_capture(cap["text_ja"]):
            continue
        pf = prefixes_in(cap["text_ja"])
        if len(pf) <= 1:
            continue
        system, crumb = screen_key(cap["text_ja"])
        mods = {pmap["map"].get(p, {}).get("screen_module") for p in pf}
        mixed.append({
            "capture_id": cap["capture_id"], "session_id": cap["session_id"],
            "url_module_id": cap["module_id"],
            "screen_module": f"{system}|{crumb}" if system and crumb else None,
            "prefixes": dict(pf),
            "prefix_modules": sorted(x for x in mods if x),
            "crosses_modules": len({x for x in mods if x}) > 1,
        })
    cross = [m for m in mixed if m["crosses_modules"]]
    return {
        "n_mixed_prefix_captures": len(mixed),
        "n_that_cross_modules": len(cross),
        "verdict": ("cross-module queue views exist" if cross else
                    "NO capture mixes prefixes from different modules — the cross-module-view "
                    "explanation is REFUTED"),
        "examples": mixed[:8],
        "cross_examples": cross[:8],
    }


def contingency(captures: Sequence[Dict], records: Sequence[Dict],
                pmap: Dict[str, Any]) -> Dict[str, Any]:
    """Three-way agreement over all extracted records."""
    cap_by = {c["capture_id"]: c for c in captures}
    rows: List[Dict] = []
    for r in records:
        cap = cap_by.get(r["capture_id"])
        if not cap:
            continue
        system, crumb = screen_key(cap["text_ja"])
        k2 = f"{system}|{crumb}" if system and crumb else None
        p = r["record_id"].split("-")[0]
        k3 = pmap["map"].get(p, {}).get("screen_module")
        k1 = r.get("module_id")
        k1_named = None
        if k1 and k1 != "PORTAL":
            hit = next((v for v in M.MODULE.values() if v[0] == k1), None)
            if hit:
                k1_named = f"{hit[1]}|{hit[2]}"
        rows.append({"record_id": r["record_id"], "capture_id": r["capture_id"],
                     "k1_url": k1, "k1_named": k1_named, "k2_screen": k2, "k3_prefix": k3})

    def agree(a: str, b: str) -> Dict[str, Any]:
        both = [r for r in rows if r[a] and r[b]]
        same = sum(1 for r in both if r[a] == r[b])
        return {"comparable": len(both), "agree": same,
                "rate": round(same / len(both), 4) if both else None}

    three = [r for r in rows if r["k1_named"] and r["k2_screen"] and r["k3_prefix"]]
    all3 = sum(1 for r in three if r["k1_named"] == r["k2_screen"] == r["k3_prefix"])
    pair = collections.Counter(
        (r["k1_named"] == r["k2_screen"], r["k1_named"] == r["k3_prefix"],
         r["k2_screen"] == r["k3_prefix"]) for r in three)
    return {
        "n_records": len(rows),
        "n_three_way_comparable": len(three),
        "three_way_agreement": all3,
        "three_way_agreement_rate": round(all3 / len(three), 4) if three else None,
        "pairwise": {"K1_url_vs_K2_screen": agree("k1_named", "k2_screen"),
                     "K1_url_vs_K3_prefix": agree("k1_named", "k3_prefix"),
                     "K2_screen_vs_K3_prefix": agree("k2_screen", "k3_prefix")},
        "agreement_patterns": {f"K1=K2:{a} K1=K3:{b} K2=K3:{c}": n
                               for (a, b, c), n in pair.most_common()},
        "_rows": rows,
    }


def concentration(cont: Dict[str, Any]) -> Dict[str, Any]:
    """Are disagreements concentrated in a few captures, or diffuse? Counts, not adjectives."""
    rows = cont["_rows"]
    bad = [r for r in rows if r["k2_screen"] and r["k3_prefix"]
           and r["k1_named"] and r["k1_named"] != r["k2_screen"]]
    by_cap = collections.Counter(r["capture_id"] for r in bad)
    total_caps = len({r["capture_id"] for r in rows})
    return {
        "n_records_where_url_disagrees_with_screen": len(bad),
        "n_captures_involved": len(by_cap),
        "n_captures_total": total_caps,
        "share_of_captures_involved": round(len(by_cap) / total_caps, 4) if total_caps else None,
        "records_per_involved_capture_median": (
            sorted(by_cap.values())[len(by_cap) // 2] if by_cap else None),
        "top_captures": by_cap.most_common(8),
    }


def module_census(captures: Sequence[Dict], pmap: Dict[str, Any]) -> Dict[str, Any]:
    """Which modules does the SCREEN declare, and does the (origin, route) map cover them?"""
    seen: collections.Counter = collections.Counter()
    for cap in captures:
        system, crumb = screen_key(cap["text_ja"])
        if system and crumb:
            seen[f"{system}|{crumb}"] += 1
    mapped = {f"{v[1]}|{v[2]}": v[0] for v in M.MODULE.values()}
    return {
        "screen_declared_modules": dict(seen.most_common()),
        "n_screen_declared": len(seen),
        "n_in_origin_route_map": len(mapped),
        "declared_but_not_in_map": sorted(k for k in seen if k not in mapped),
        "in_map_but_never_declared_on_screen": sorted(k for k in mapped if k not in seen),
    }


def inventory_impact(dataset: str, captures: Sequence[Dict], records: Sequence[Dict],
                     pmap: Dict[str, Any]) -> Dict[str, Any]:
    """Re-derive the per-execution module under K1 and under K3, and diff the inventory.

    `analysis/step2_reanalysis.py` assigns each execution the module that a MAJORITY of its
    blocks carry under K1. The same majority rule is applied here under K3 — the modal
    record-id prefix among the records extracted inside that execution's seq range — so the two
    inventories differ only in the key, never in the aggregation. `step2_reanalysis.py` is not
    modified; its logic is replicated.
    """
    segs = [json.loads(l) for l in
            open(os.path.join(C.ROOT, "build", dataset, "segments_rich.jsonl"),
                 encoding="utf-8")]
    blocks = [json.loads(l) for l in
              open(os.path.join(C.ROOT, "build", dataset, "blocks.jsonl"), encoding="utf-8")]
    by_sess_blocks: Dict[str, List[Dict]] = collections.defaultdict(list)
    for b in blocks:
        by_sess_blocks[b.get("session_id")].append(b)
    cap_by = {c["capture_id"]: c for c in captures}
    by_sess_recs: Dict[str, List[Dict]] = collections.defaultdict(list)
    for r in records:
        by_sess_recs[r["session_id"]].append(r)

    named = {v[0]: f"{v[1]}|{v[2]}" for v in M.MODULE.values()}
    rows: List[Dict] = []
    for s in segs:
        sid, a, z = s["session_id"], s["start_seq"], s["end_seq"]
        k1 = collections.Counter()
        for b in by_sess_blocks.get(sid, []):
            if b.get("first_seq") is None or b["last_seq"] < a or b["first_seq"] > z:
                continue
            mid = M.module_id_of_url(f"{b.get('origin') or ''}/#{b.get('route') or ''}")
            if mid and mid != "PORTAL":
                k1[named.get(mid, mid)] += 1
        k3 = collections.Counter()
        for r in by_sess_recs.get(sid, []):
            q = r.get("sequence_number")
            if q is None or q < a or q > z:
                continue
            m = pmap["map"].get(r["record_id"].split("-")[0], {}).get("screen_module")
            if m:
                k3[m] += 1
        rows.append({
            "exec_uid": s["exec_uid"], "session_id": sid,
            "k1_module": k1.most_common(1)[0][0] if k1 else None,
            "k1_purity": round(k1.most_common(1)[0][1] / sum(k1.values()), 3) if k1 else None,
            "k3_module": k3.most_common(1)[0][0] if k3 else None,
            "k3_purity": round(k3.most_common(1)[0][1] / sum(k3.values()), 3) if k3 else None,
        })

    both = [r for r in rows if r["k1_module"] and r["k3_module"]]
    same = sum(1 for r in both if r["k1_module"] == r["k3_module"])
    inv_k1 = collections.Counter(r["k1_module"] for r in rows if r["k1_module"])
    inv_k3 = collections.Counter(r["k3_module"] for r in rows if r["k3_module"])
    keys = sorted(set(inv_k1) | set(inv_k3))
    diff = [{"module": k, "n_executions_K1": inv_k1.get(k, 0),
             "n_executions_K3": inv_k3.get(k, 0),
             "delta": inv_k3.get(k, 0) - inv_k1.get(k, 0)} for k in keys]
    return {
        "n_executions": len(rows),
        "n_assignable_under_both": len(both),
        "execution_level_agreement": same,
        "execution_level_agreement_rate": round(same / len(both), 4) if both else None,
        "n_unassignable_K1": sum(1 for r in rows if not r["k1_module"]),
        "n_unassignable_K3": sum(1 for r in rows if not r["k3_module"]),
        "inventory_diff": sorted(diff, key=lambda d: -abs(d["delta"])),
        "changed_rows": [d for d in diff if d["delta"] != 0],
        "_rows": rows,
    }


def run(dataset: str = "dataset_b") -> Dict[str, Any]:
    ev = C.evidence_dir(dataset)
    captures = [json.loads(l) for l in open(os.path.join(ev, "screen_text.jsonl"),
                                            encoding="utf-8")]
    records = [json.loads(l) for l in open(os.path.join(ev, "records.jsonl"),
                                           encoding="utf-8")]
    pmap = derive_prefix_map(captures)
    mixed = mixed_prefix_test(captures, pmap)
    cont = contingency(captures, records, pmap)
    conc = concentration(cont)
    census = module_census(captures, pmap)
    impact = inventory_impact(dataset, captures, records, pmap)
    exec_rows = impact.pop("_rows")
    rows = cont.pop("_rows")

    doc = {
        "_purpose": "three-way module-key reconciliation. Settles which key is authoritative "
                    "for which unit of analysis before anything is built on the inventory.",
        "_keys": {
            "K1_url": "(origin, route) from context.active_browser_tab.url — what Step 2 uses",
            "K2_screen": "system name + ダッシュボード/<module> breadcrumb rendered in the "
                         "capture text — what the operator was looking at",
            "K3_prefix": "record-id P<n>, mapped to a module by DERIVATION from queue headers",
        },
        "k3_derivation": pmap,
        "decisive_test_mixed_prefixes": mixed,
        "contingency": cont,
        "concentration": conc,
        "module_census": census,
        "inventory_impact": impact,
        "extraction_method": "derived",
        "evidence_type": "OBSERVED",
    }
    art = C.write_json(doc, os.path.join(ev, "module_key_reconciliation.json"), dataset)
    C.merge_manifest(dataset, "phase3_5", C.run_manifest(
        dataset, "phase3_5", {"module_key_reconciliation.json": art},
        config={"keys": list(doc["_keys"])},
        extra={"three_way_agreement_rate": cont["three_way_agreement_rate"],
               "mixed_prefix_verdict": mixed["verdict"]}))
    return {"doc": doc, "rows": rows, "artifact": art}


if __name__ == "__main__":
    r = run()
    d = r["doc"]
    print(json.dumps({"k3_map": {k: f"{v['screen_module']} (purity {v['purity']})"
                                 for k, v in d["k3_derivation"]["map"].items()},
                      "mixed": {k: v for k, v in d["decisive_test_mixed_prefixes"].items()
                                if not k.endswith("examples")},
                      "contingency": {k: v for k, v in d["contingency"].items()
                                      if k != "agreement_patterns"},
                      "patterns": d["contingency"]["agreement_patterns"],
                      "concentration": d["concentration"],
                      "census": {k: v for k, v in d["module_census"].items()
                                 if k != "screen_declared_modules"}},
                     ensure_ascii=False, indent=1))
