"""Phase 6 — is governing-document retrieval a real task, and does AI earn its place?

reads only:  build/dataset_b/evidence/{screen_text,documents,coverage_gaps}.jsonl,
             build/dataset_b/{segments_rich,blocks}.jsonl, dataset_b/*/*/events.jsonl
writes only: build/dataset_b/evidence/retrieval_feasibility.json

H3 is SUPPORTED in 10 of 11 modules: operators open a governing document before a disposition
far above a permutation null. That makes "which document?" a well-posed task with observed
labels — the (disposition, document-open) pairs that produced H3 ARE the training set.

This module formalises it and then tries to kill it, in that order:

  * how many labelled pairs exist, per module and in total
  * the label distribution across documents — a task dominated by one label is not a task
  * the train/eval split n actually supports, and whether n supports evaluation at all
  * **B0 random · B1 most-frequent overall · B2 most-frequent per module · B3 deterministic
    (module, record type) -> document lookup**

If B2 or B3 already scores high, **the retrieval task does not justify AI** and the honest
recommendation is a lookup table plus a good UI. The baselines are computed first and reported
whatever they say; nothing here rescues the AI framing.
"""
from __future__ import annotations

import collections
import json
import os
import re
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import common as C
from . import modules as M
from . import pass0_text as P0

SEED = 7
DOC_APPS = ("Microsoft Word", "Notepad", "WordPad")
BTN_OK = re.compile(r"^btn-\w+-ok$")


def _element_id(e: Dict) -> str:
    p = e.get("payload") or {}
    el = (p.get("element") or {}).get("attributes") or {}
    fld = p.get("field") or {}
    return el.get("id") or fld.get("id") or ""


def build_labelled_pairs(dataset: str) -> Dict[str, Any]:
    """One row per disposition that had a document open before it inside the same execution.

    The document is identified by CONTENT (its `document_id`), never by window title — titles do
    not identify documents in this dataset (`document_title_mismatch.csv`). Where the operator
    had a document open whose body was never captured, the pair is unlabelable and is counted as
    such rather than dropped silently.
    """
    ev_dir = C.evidence_dir(dataset)
    docs = [json.loads(l) for l in open(os.path.join(ev_dir, "documents.jsonl"),
                                        encoding="utf-8")]
    caps = [json.loads(l) for l in open(os.path.join(ev_dir, "screen_text.jsonl"),
                                        encoding="utf-8")]
    recs = [json.loads(l) for l in open(os.path.join(ev_dir, "records.jsonl"),
                                        encoding="utf-8")]
    segs = [json.loads(l) for l in
            open(os.path.join(C.ROOT, "build", dataset, "segments_rich.jsonl"),
                 encoding="utf-8")]
    recon = json.load(open(os.path.join(ev_dir, "module_key_reconciliation.json"),
                           encoding="utf-8"))
    pmap = recon["k3_derivation"]["map"]

    cap_to_doc: Dict[str, str] = {}
    doc_title: Dict[str, str] = {}
    for d in docs:
        doc_title[d["document_id"]] = d["doc_type_ja"]
        for cid in d["capture_ids"]:
            cap_to_doc[cid] = d["document_id"]
    cap_by_seq: Dict[str, List[Tuple[int, str]]] = collections.defaultdict(list)
    for c in caps:
        if c["active_app"] in DOC_APPS and c["capture_id"] in cap_to_doc:
            cap_by_seq[c["session_id"]].append((c["sequence_number"] or 0, c["capture_id"]))
    for v in cap_by_seq.values():
        v.sort()

    by_sess_segs: Dict[str, List[Dict]] = collections.defaultdict(list)
    for s in segs:
        by_sess_segs[s["session_id"]].append(s)

    # record context per session, for the (module, record type) key B3 needs
    rec_by_sess: Dict[str, List[Dict]] = collections.defaultdict(list)
    for r in recs:
        rec_by_sess[r["session_id"]].append(r)

    events: Dict[str, List[Dict]] = collections.defaultdict(list)
    for e in P0.iter_raw_events(os.path.join(C.ROOT, dataset)):
        events[e["_session_id"]].append(e)
    for v in events.values():
        v.sort(key=lambda e: (e.get("timestamp_ms") or 0,
                              (e.get("correlation") or {}).get("sequence_number") or 0))

    pairs: List[Dict] = []
    n_dispositions = 0
    n_no_doc = 0
    for sid, evs in sorted(events.items()):
        for i, e in enumerate(evs):
            if e.get("event_type") not in ("browser_click", "mouse_click"):
                continue
            if not BTN_OK.match(_element_id(e) or ""):
                continue
            n_dispositions += 1
            seq = (e.get("correlation") or {}).get("sequence_number") or i
            seg = next((s for s in by_sess_segs.get(sid, [])
                        if s["start_seq"] <= seq <= s["end_seq"]), None)
            if seg is None:
                n_no_doc += 1
                continue
            before = [(q, cid) for q, cid in cap_by_seq.get(sid, [])
                      if seg["start_seq"] <= q <= seq]
            if not before:
                n_no_doc += 1
                continue
            q, cid = before[-1]                       # the most recent document before the act
            did = cap_to_doc[cid]

            # features available at prediction time
            recs_in = [r for r in rec_by_sess.get(sid, [])
                       if r.get("sequence_number") is not None
                       and seg["start_seq"] <= r["sequence_number"] <= seq]
            prefixes = collections.Counter(r["record_id"].split("-")[0] for r in recs_in)
            module = None
            if prefixes:
                module = pmap.get(prefixes.most_common(1)[0][0], {}).get("screen_module")
            if module is None:
                url = ((e.get("context") or {}).get("active_browser_tab") or {}).get("url") or ""
                mid = M.module_id_of_url(url)
                hit = next((v for v in M.MODULE.values() if v[0] == mid), None)
                module = f"{hit[1]}|{hit[2]}" if hit else None
            rtypes = collections.Counter()
            for r in recs_in:
                for k in ("区分", "申請種別", "種別"):
                    v = (r.get("fields") or {}).get(k)
                    if v:
                        rtypes[str(v)] += 1
                        break
            pairs.append({
                "session_id": sid, "disposition_seq": seq,
                "element_id": _element_id(e),
                "module": module,
                "record_type": rtypes.most_common(1)[0][0] if rtypes else None,
                "document_id": did,
                "document_heading": doc_title.get(did, "")[:40],
                "doc_distance_events": seq - q,
            })
    return {"pairs": pairs, "n_dispositions": n_dispositions,
            "n_without_a_document": n_no_doc, "doc_title": doc_title}


def baselines(pairs: Sequence[Dict], label_key: str = "document_id") -> Dict[str, Any]:
    """B0 random · B1 most-frequent overall · B2 most-frequent per module · B3 (module, record
    type) lookup. Leave-one-out, so every pair is evaluated and n is not spent on a split."""
    import random
    rng = random.Random(SEED)
    labels = [p[label_key] for p in pairs]
    docs = sorted(set(labels))
    n = len(pairs)
    if n == 0:
        return {"n": 0}

    def loo_score(predict) -> float:
        ok = 0
        for i, p in enumerate(pairs):
            train = pairs[:i] + pairs[i + 1:]
            ok += 1 if predict(train, p) == p[label_key] else 0
        return round(ok / n, 4)

    def b0(train, p):
        return rng.choice(docs)

    def b1(train, p):
        return collections.Counter(x[label_key] for x in train).most_common(1)[0][0]

    def b2(train, p):
        c = collections.Counter(x[label_key] for x in train if x["module"] == p["module"])
        return c.most_common(1)[0][0] if c else b1(train, p)

    def b3(train, p):
        key = (p["module"], p["record_type"])
        c = collections.Counter(x[label_key] for x in train
                                if (x["module"], x["record_type"]) == key)
        return c.most_common(1)[0][0] if c else b2(train, p)

    dist = collections.Counter(labels)
    top, top_n = dist.most_common(1)[0]

    def wilson(p_hat: float, n_: int, z: float = 1.96) -> Tuple[float, float]:
        """Wilson interval. The point of reporting it: a learned model must clear the UPPER
        bound before this evidence can tell it apart from the lookup table."""
        d_ = 1 + z * z / n_
        c = (p_hat + z * z / (2 * n_)) / d_
        h = z * ((p_hat * (1 - p_hat) / n_ + z * z / (4 * n_ * n_)) ** 0.5) / d_
        return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))

    out = {
        "n": n,
        "n_distinct_documents": len(docs),
        "majority_label_share": round(top_n / n, 4),
        "majority_label": top[:12],
        "label_distribution_top10": [(d[:12], c) for d, c in dist.most_common(10)],
        "B0_random": loo_score(b0),
        "B1_most_frequent_overall": loo_score(b1),
        "B2_most_frequent_per_module": loo_score(b2),
        "B3_module_and_record_type_lookup": loo_score(b3),
        "B3_wilson_95ci": None,          # filled below
        "_method": "leave-one-out over all pairs, seed 7. LOO rather than a held-out split "
                   "because n is small and a split would spend evidence the task cannot spare.",
    }
    out["B3_wilson_95ci"] = wilson(out["B3_module_and_record_type_lookup"], n)
    return out


def run(dataset: str = "dataset_b") -> Dict[str, Any]:
    built = build_labelled_pairs(dataset)
    pairs = built["pairs"]
    by_module = collections.Counter(p["module"] for p in pairs)
    per_module_docs = collections.defaultdict(collections.Counter)
    for p in pairs:
        per_module_docs[p["module"]][p["document_id"]] += 1
    # TWO LABEL SPACES, because the choice is not obvious and it changes the answer.
    #
    # `document_id` is the content sha256, which is the right key for "is this the same bytes".
    # It is the WRONG key for "is this the same document": a long regulation captured at two
    # scroll positions yields two ids. Dataset B is stated to contain ~13 reference documents
    # and content hashing yields 112, so the fragmentation is real and large.
    #
    # `document_heading` -- the first heading of the body, verbatim Japanese -- is the
    # document's own identity claim. Both are reported; neither is assumed.
    base = baselines(pairs, "document_id")
    base_heading = baselines(pairs, "document_heading")

    modules_evaluable = {m: n for m, n in by_module.items() if n >= 8}
    doc = {
        "_purpose": "is governing-document retrieval a well-posed task, and does a learned "
                    "component beat a lookup table?",
        "labelled_pairs": {
            "n_dispositions_total": built["n_dispositions"],
            "n_with_a_document_before_them": len(pairs),
            "n_without": built["n_without_a_document"],
            "coverage": round(len(pairs) / built["n_dispositions"], 4)
            if built["n_dispositions"] else None,
            "by_module": dict(by_module.most_common()),
            "modules_at_or_above_floor_n8": modules_evaluable,
            "per_module_label_counts": {str(m): dict(c.most_common(5))
                                        for m, c in sorted(per_module_docs.items(),
                                                           key=lambda kv: str(kv[0]))},
        },
        "baselines_by_content_hash": base,
        "baselines_by_document_heading": base_heading,
        "_label_space_note": "content sha256 fragments one document into several when it is "
                             "captured at different scroll positions; the heading is the "
                             "document's own identity claim. The heading space is the "
                             "operative one and the hash space is reported as the pessimistic "
                             "bound.",
        "verdict": "",
        "extraction_method": "derived",
        "evidence_type": "OBSERVED",
    }
    b = base_heading
    best_simple = max(b.get("B2_most_frequent_per_module", 0),
                      b.get("B3_module_and_record_type_lookup", 0))
    base = b
    if base.get("n", 0) < 30:
        doc["verdict"] = (
            f"INSUFFICIENT EVIDENCE TO EVALUATE. n={base.get('n', 0)} labelled pairs. "
            f"No model should be proposed that cannot be tested.")
    elif best_simple >= 0.80:
        doc["verdict"] = (
            f"AI IS NOT JUSTIFIED. A deterministic baseline already reaches "
            f"{best_simple:.1%} (B2 {base['B2_most_frequent_per_module']:.1%}, B3 "
            f"{base['B3_module_and_record_type_lookup']:.1%}) against random "
            f"{base['B0_random']:.1%}. The honest recommendation is a lookup table and a good "
            f"UI, not a learned retriever.")
    else:
        hi = (base.get("B3_wilson_95ci") or [0, 1])[1]
        doc["verdict"] = (
            f"NOT SETTLED AT THIS n, AND THE HONEST ANSWER IS A LOOKUP TABLE FIRST. The best "
            f"deterministic baseline -- (module, record type) -> document -- reaches "
            f"{best_simple:.1%} (95% Wilson CI "
            f"{base['B3_wilson_95ci'][0]:.1%}-{base['B3_wilson_95ci'][1]:.1%}) against "
            f"{base['B0_random']:.1%} random, on n={base['n']} pairs over "
            f"{base['n_distinct_documents']} document labels. A learned retriever would have to "
            f"exceed {hi:.1%} before this evidence could tell it apart from the lookup table at "
            f"all. Build the lookup table, instrument it, and let the residual decide whether a "
            f"model is warranted.")
    art = C.write_json(doc, os.path.join(C.evidence_dir(dataset),
                                         "retrieval_feasibility.json"), dataset)
    C.merge_manifest(dataset, "phase6", C.run_manifest(
        dataset, "phase6", {"retrieval_feasibility.json": art},
        config={"seed": SEED, "evaluation": "leave-one-out"},
        extra={"verdict": doc["verdict"], "n_pairs": base.get("n")}))
    return {"doc": doc, "artifact": art}


if __name__ == "__main__":
    d = run()["doc"]
    print(json.dumps({"pairs": {k: v for k, v in d["labelled_pairs"].items()
                                if k != "per_module_label_counts"},
                      "baselines_by_content_hash": {
                          k: v for k, v in d["baselines_by_content_hash"].items()
                          if not k.startswith("_") and k != "label_distribution_top10"},
                      "baselines_by_document_heading": {
                          k: v for k, v in d["baselines_by_document_heading"].items()
                          if not k.startswith("_") and k != "label_distribution_top10"},
                      "verdict": d["verdict"]}, ensure_ascii=False, indent=1))
