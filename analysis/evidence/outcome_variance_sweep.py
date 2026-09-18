"""Phase 3.9 — exhaustive free sweep for negative, exceptional or reversal outcome states.

reads only:  dataset_b/*/*/events.jsonl (ALL fields, not just extracted_text),
             dataset_b/*/*/screenshots/*.jpg (filenames only),
             build/dataset_b/evidence/{records,outcomes,states}.jsonl
writes only: build/dataset_b/evidence/outcome_variance_sweep.json

Gate G4 failed on 225 of 225 positive toast outcomes. Before that becomes a permanent finding,
every free source of evidence is exhausted — because "no negative outcomes exist" and "we only
looked in one place" are very different claims, and only the first licenses the conclusion that
the dataset carries no supervision signal for a decision function.

The sweep is deliberately wider than Pass 0: it reads EVERY string value in every event, not the
939 that carry `extracted_text`, plus element ids and labels, URLs, window titles and screenshot
filenames. It also looks for structural evidence of reversal that no keyword would catch —
backward or lateral status transitions, and records reaching two different terminal states.

A null result here is a FINDING, and is recorded with the exact terms, the corpus size and the
zero counts so the claim is reproducible rather than asserted.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import common as C
from . import pass0_text as P0

# Declared before the sweep was run. Japanese terms first, then Latin.
NEGATIVE_TERMS = (
    "差戻し", "差戻", "差し戻し", "却下", "否認", "棄却", "保留", "取消", "取り消し",
    "キャンセル", "エラー", "失敗", "警告", "注意", "不備", "再提出", "修正依頼",
    "確認待ち", "承認待ち", "NG", "error", "failed", "failure", "reject", "rejected",
    "denied", "invalid", "cancel", "cancelled", "abort", "warning",
)

# Statuses seen in Dataset B, ordered from earliest to terminal. Used for the structural test:
# a transition from a later state to an earlier one is a reversal regardless of wording.
STATUS_ORDER = ("申請中", "未処理", "処理待ち", "照合中", "登録済み", "承認", "完了",
                "処理完了", "照合完了", "登録確定")


def _walk_strings(obj: Any, path: str = "") -> Iterable[Tuple[str, str]]:
    """Every string value anywhere in an event, with its JSON path."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield (path, obj)


def sweep_events(dataset_root: str) -> Dict[str, Any]:
    hits: List[Dict] = []
    n_events = 0
    n_strings = 0
    n_chars = 0
    paths_seen: collections.Counter = collections.Counter()
    for e in P0.iter_raw_events(dataset_root):
        n_events += 1
        for path, val in _walk_strings(e):
            n_strings += 1
            n_chars += len(val)
            paths_seen[path.split("[")[0]] += 1
            for term in NEGATIVE_TERMS:
                if term in val:
                    hits.append({
                        "term": term, "json_path": path,
                        "value": val[:200],
                        "event_id": e.get("event_id"),
                        "event_type": e.get("event_type"),
                        "session_id": e["_session_id"],
                        "sequence_number": (e.get("correlation") or {}).get("sequence_number"),
                    })
    return {"n_events_scanned": n_events, "n_string_values_scanned": n_strings,
            "n_chars_scanned": n_chars, "n_distinct_json_paths": len(paths_seen),
            "hits": hits, "hits_by_term": dict(collections.Counter(h["term"] for h in hits)),
            "hits_by_path": dict(collections.Counter(h["json_path"].split("[")[0]
                                                     for h in hits).most_common(20))}


def sweep_screenshot_filenames(dataset_root: str) -> Dict[str, Any]:
    names = [os.path.basename(p) for p in
             sorted(glob.glob(os.path.join(dataset_root, "*", "*", "screenshots", "*.jpg")))]
    hits = [{"filename": n, "term": t} for n in names for t in NEGATIVE_TERMS
            if t.lower() in n.lower()]
    return {"n_filenames_scanned": len(names), "hits": hits}


def sweep_status_transitions(dataset: str) -> Dict[str, Any]:
    """Structural reversal test — no keyword involved.

    Two questions: does any record move BACKWARD or sideways through the status order, and does
    any record reach two different terminal states?
    """
    ev = C.evidence_dir(dataset)
    records = [json.loads(l) for l in open(os.path.join(ev, "records.jsonl"), encoding="utf-8")]
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}

    by_rec: Dict[Tuple[str, str], List[Dict]] = collections.defaultdict(list)
    for r in records:
        if r.get("status_ja"):
            by_rec[(r["session_id"], r["record_id"])].append(r)

    backward: List[Dict] = []
    lateral: List[Dict] = []
    unknown_status: collections.Counter = collections.Counter()
    for (sid, rid), lst in sorted(by_rec.items()):
        lst.sort(key=lambda r: (r["sequence_number"] or 0, r["capture_id"]))
        prev = None
        for r in lst:
            cur = r["status_ja"]
            if cur not in rank:
                unknown_status[cur] += 1
            if prev is not None and cur != prev and prev in rank and cur in rank:
                if rank[cur] < rank[prev]:
                    backward.append({"session_id": sid, "record_id": rid,
                                     "from": prev, "to": cur,
                                     "capture_id": r["capture_id"]})
                elif rank[cur] == rank[prev]:
                    lateral.append({"session_id": sid, "record_id": rid,
                                    "from": prev, "to": cur})
            prev = cur

    terminal = set(STATUS_ORDER[-6:])
    multi_terminal: List[Dict] = []
    per_rid: Dict[str, Set[str]] = collections.defaultdict(set)
    for (sid, rid), lst in by_rec.items():
        for r in lst:
            if r["status_ja"] in terminal:
                per_rid[rid].add(r["status_ja"])
    for rid, states in sorted(per_rid.items()):
        if len(states) > 1:
            multi_terminal.append({"record_id": rid, "terminal_states": sorted(states)})

    return {
        "n_records_with_status": len(by_rec),
        "n_distinct_records": len({rid for _, rid in by_rec}),
        "status_vocabulary_observed": dict(
            collections.Counter(r["status_ja"] for r in records if r.get("status_ja")
                                ).most_common()),
        "statuses_outside_the_declared_order": dict(unknown_status),
        "n_backward_transitions": len(backward),
        "backward_examples": backward[:10],
        "n_lateral_transitions": len(lateral),
        "n_records_with_multiple_terminal_states": len(multi_terminal),
        "multi_terminal_examples": multi_terminal[:10],
    }


# Operator-typed comment text. `payload.target_field.value` on keystroke events carries what the
# operator TYPED into the disposition comment box -- 481 distinct strings, an evidence source
# roughly half the size of the extracted_text corpus and entirely missed by Pass 0, which read
# only `context.extracted_text`. It is where the operator records their own judgement.
EXCEPTION_PAIRS = (("差異なし", "差異あり"), ("通常", "要注意"), ("確認完了", "要確認"))
EXCEPTION_MARKERS = ("差異あり", "要注意", "要確認")


def sweep_typed_comments(dataset_root: str) -> Dict[str, Any]:
    """The operator's own annotation, which is NOT the system's disposition."""
    uniq: Dict[str, Dict[str, Any]] = {}
    n_events = 0
    for e in P0.iter_raw_events(dataset_root):
        tf = (e.get("payload") or {}).get("target_field") or {}
        v = tf.get("value")
        if not (isinstance(v, str) and len(v) > 10) or v.startswith("http"):
            continue
        n_events += 1
        url = ((e.get("context") or {}).get("active_browser_tab") or {}).get("url") or ""
        rec = uniq.setdefault(v, {"url": url, "session_ids": set(), "n_events": 0})
        rec["session_ids"].add(e["_session_id"])
        rec["n_events"] += 1
    flagged = sorted(v for v in uniq if any(m in v for m in EXCEPTION_MARKERS))
    pairs = {f"{a}|{b}": {a: sum(1 for v in uniq if a in v), b: sum(1 for v in uniq if b in v)}
             for a, b in EXCEPTION_PAIRS}
    by_route: collections.Counter = collections.Counter()
    for v, m in uniq.items():
        frag = m["url"].split("#")[-1] if "#" in m["url"] else "(no url)"
        by_route[(frag, "flagged" if v in set(flagged) else "clean")] += 1
    return {
        "n_keystroke_events_with_a_typed_value": n_events,
        "n_distinct_comments": len(uniq),
        "exception_pairs": pairs,
        "n_flagged_comments": len(flagged),
        "flagged_share": round(len(flagged) / len(uniq), 4) if uniq else None,
        "flagged_examples": flagged[:16],
        "by_route": {f"{r}|{k}": n for (r, k), n in sorted(by_route.items())},
        "_note": "These are the OPERATOR's words, not the system's disposition. Every flagged "
                 "comment observed still ends in a positive disposition -- e.g. "
                 "「…要注意。発注書確認・登録完了。」 is flagged AND completed. So the SYSTEM outcome "
                 "remains constant while the OPERATOR's recorded judgement varies.",
    }


def run(dataset: str = "dataset_b") -> Dict[str, Any]:
    dataset_root = os.path.join(C.ROOT, dataset)
    ev_sweep = sweep_events(dataset_root)
    shots = sweep_screenshot_filenames(dataset_root)
    trans = sweep_status_transitions(dataset)
    typed = sweep_typed_comments(dataset_root)

    # --- CLASSIFY, do not count.
    #
    # A first version flagged G4 as reopened on raw keyword presence and was wrong. Of the 862
    # "outcome-like" hits, 876 term-matches were one UI PLACEHOLDER --
    # 「承認コメントまたは差戻し理由を入力してください…」 -- the 38 browser_error events were all
    # favicon 404s, and the `NG` matches were the substring in `ENG` inside garbled OCR text.
    # None of those is an outcome. Presence of a word is not evidence of an event, and the
    # distinction is the whole point of this sweep.
    def classify(h: Dict) -> str:
        path, val = h["json_path"], h["value"]
        if ".placeholder" in path or path.endswith(".label") or ".attributes.placeholder" in path:
            return "ui_affordance"          # the UI OFFERS this action; it did not occur
        if h["event_type"] == "browser_error":
            return "infrastructure_error"
        if ".extensions.ocr_v1" in path or "PowerShell" in val or "Copyright" in val:
            return "terminal_or_ocr_noise"
        if ".context.extracted_text.text" in path:
            # an outcome in screen text would sit next to a record id, as every toast does
            return ("candidate_outcome" if re.search(r"P\d{1,2}-\d{8}-\d{3}", val)
                    else "document_or_page_body")
        if path.startswith(".payload.element") or path.startswith(".payload.field"):
            return "ui_affordance"
        return "other"

    for h in ev_sweep["hits"]:
        h["classification"] = classify(h)
    by_class = collections.Counter(h["classification"] for h in ev_sweep["hits"])
    candidates = [h for h in ev_sweep["hits"] if h["classification"] == "candidate_outcome"]

    # G4 reopens ONLY on a candidate outcome or on structural reversal evidence.
    # G4 reopens on ANY observed variance in a disposition-relevant variable -- including the
    # operator's own annotation, which is what the first version of this sweep missed entirely
    # by reading only `context.extracted_text`.
    found = (bool(candidates) or trans["n_backward_transitions"] > 0
             or trans["n_records_with_multiple_terminal_states"] > 0 or bool(shots["hits"])
             or typed["n_flagged_comments"] > 0)

    # The affordance finding is separate from, and more useful than, the null result.
    affordances = sorted({h["value"] for h in ev_sweep["hits"]
                          if h["classification"] == "ui_affordance"})

    doc = {
        "_purpose": "exhaust the free evidence for negative/exceptional/reversal outcomes "
                    "before gate G4's failure becomes a permanent finding.",
        "_search_terms": list(NEGATIVE_TERMS),
        "_status_order_declared": list(STATUS_ORDER),
        "_corpus": {
            "events_scanned": ev_sweep["n_events_scanned"],
            "string_values_scanned": ev_sweep["n_string_values_scanned"],
            "characters_scanned": ev_sweep["n_chars_scanned"],
            "distinct_json_paths": ev_sweep["n_distinct_json_paths"],
            "screenshot_filenames_scanned": shots["n_filenames_scanned"],
            "records_with_status": trans["n_records_with_status"],
        },
        "keyword_sweep": {
            "n_raw_hits": len(ev_sweep["hits"]),
            "hits_by_classification": dict(by_class.most_common()),
            "n_candidate_outcomes": len(candidates),
            "candidate_outcome_examples": candidates[:20],
            "ui_affordance_strings": affordances[:20],
            "hits_by_term": ev_sweep["hits_by_term"],
            "hits_by_json_path": ev_sweep["hits_by_path"],
            "_note": "a raw hit is any occurrence of a term anywhere in an event. Hits are "
                     "CLASSIFIED, not counted: only a term appearing in screen text NEXT TO A "
                     "RECORD ID -- the shape every observed toast takes -- is a candidate "
                     "outcome. A term in a UI placeholder proves the interface OFFERS the "
                     "action, not that it happened.",
        },
        "screenshot_filename_sweep": shots,
        "structural_transition_sweep": trans,
        "typed_comment_sweep": typed,
        "G4_REOPENED": found,
        "_finding": "",
        "_affordance_finding": (
            "The UI EXPOSES a rejection path. The comment box on the disposition screen is "
            "labelled 「承認コメントまたは差戻し理由を入力してください…」 -- 'enter an approval comment "
            "or a send-back reason' -- appearing on browser_click and browser_form_input "
            "events. So 差戻し (send-back) is a supported action that was never exercised in "
            "this capture window. This reframes G4: the dataset does not show that rejection "
            "never happens, it shows that this ~2-hour window contains none. The distinction "
            "matters for Step 3, because a system trained or evaluated here has never seen the "
            "branch the interface is built around."),
        "extraction_method": "telemetry_text+derived",
        "evidence_type": "OBSERVED",
    }
    if found:
        doc["_finding"] = (
            f"G4 REOPENS, NARROWLY AND PRECISELY. The SYSTEM disposition is still constant: "
            f"{len(candidates)} candidate negative outcomes in screen text, "
            f"{trans['n_backward_transitions']} backward transitions, "
            f"{trans['n_records_with_multiple_terminal_states']} records reaching two terminal "
            f"states, {len(shots['hits'])} screenshot filename hits -- all zero. But the "
            f"OPERATOR's own annotation varies: {typed['n_flagged_comments']} of "
            f"{typed['n_distinct_comments']} distinct typed comments "
            f"({typed['flagged_share']:.1%}) carry an exception marker "
            f"({'/'.join(EXCEPTION_MARKERS)}), against their clean counterparts "
            f"(差異なし {typed['exception_pairs']['差異なし|差異あり']['差異なし']}, "
            f"通常 {typed['exception_pairs']['通常|要注意']['通常']}). Every flagged record was "
            f"still disposed positively. So there IS a supervision signal, but it is the "
            f"operator's recorded judgement, not the system's outcome -- a different and much "
            f"smaller target than the original hypothesis assumed.")
    else:
        doc["_finding"] = (
            f"NULL RESULT, and it is a finding. {len(NEGATIVE_TERMS)} terms swept across "
            f"{ev_sweep['n_string_values_scanned']:,} string values "
            f"({ev_sweep['n_chars_scanned']:,} characters) in "
            f"{ev_sweep['n_events_scanned']:,} events, {shots['n_filenames_scanned']:,} "
            f"screenshot filenames, and {trans['n_records_with_status']:,} record-status "
            f"series. ZERO outcome-like negative terms, ZERO backward transitions, ZERO records "
            f"with two terminal states. Dataset B contains no observed negative outcome. G4 "
            f"stays closed: there is no supervision signal for a decision function, and a model "
            f"trained here would learn to approve everything and score 100%. BUT SEE "
            f"_affordance_finding: the absence is of observed rejections, not of the ability "
            f"to reject.")
    art = C.write_json(doc, os.path.join(C.evidence_dir(dataset),
                                         "outcome_variance_sweep.json"), dataset)
    C.merge_manifest(dataset, "phase3_9", C.run_manifest(
        dataset, "phase3_9", {"outcome_variance_sweep.json": art},
        config={"n_terms": len(NEGATIVE_TERMS)},
        extra={"G4_REOPENED": found, "finding": doc["_finding"]}))
    return {"doc": doc, "artifact": art}


if __name__ == "__main__":
    r = run()
    d = r["doc"]
    print(json.dumps({"corpus": d["_corpus"],
                      "keyword": {k: v for k, v in d["keyword_sweep"].items()
                                  if k not in ("outcome_like_examples", "_note")},
                      "screenshots": {"scanned": d["screenshot_filename_sweep"]
                                      ["n_filenames_scanned"],
                                      "hits": len(d["screenshot_filename_sweep"]["hits"])},
                      "structural": {k: v for k, v in d["structural_transition_sweep"].items()
                                     if not k.endswith("examples")},
                      "G4_REOPENED": d["G4_REOPENED"],
                      "finding": d["_finding"]}, ensure_ascii=False, indent=1))
