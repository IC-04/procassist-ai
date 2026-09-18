"""Pass 1 — screenshot indexing by perceptual hash.

reads only:  dataset_b/*/*/screenshots/*.jpg, dataset_b/*/*/events.jsonl
writes only: build/dataset_b/evidence/{states.jsonl,coverage_gaps.jsonl,.cache/**}

**No new dependency.** `imagehash` is not installed; the pHash here is Pillow for decoding plus a
NumPy DCT-II written out as a matrix product. `scipy` is deliberately not used even though it is
importable, so the module runs under either interpreter on this machine.

**No OCR.** `tesseract` is absent and ADR-007's rejection of global OCR pipelines stands. This
pass indexes *which frames are visually distinct*; it reads no text from them.

Coverage is reported under THREE window definitions, because the single figure is ambiguous and
a one-number answer would be quoted without its definition. The three differ in what counts as
"nearby": a symmetric window over the raw stream, a before-only window (the causally relevant
one — did the operator see the evidence *before* deciding), and a symmetric window over the
normalised stream with capture/SYSTEM events dissolved.
"""
from __future__ import annotations

import bisect
import collections
import glob
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import common as C
from . import modules as M
from . import pass0_text as P0
from . import CODE_VERSION

HASH_SIZE = 8
IMG_SIZE = 32
WINDOWS = (5, 10, 25)
DECISION_LOOKBACK = 5
BTN_OK = re.compile(r"^btn-\w+-ok$")

# Events the recorder generates about itself. Excluded from the "normalised" window definition,
# mirroring how `procmine.normalise` dissolves them, so the third figure is comparable to the
# stream Step 1 actually reasoned over.
CAPTURE_EVENT_TYPES = ("screenshot_smart", "session_start", "session_end",
                       "extension_connected", "extension_disconnected")


def _dct_matrix(n: int):
    import numpy as np
    k = np.arange(n).reshape(1, n)
    i = np.arange(n).reshape(n, 1)
    m = np.cos(np.pi * (2 * k + 1) * i / (2 * n))
    m[0, :] *= np.sqrt(1.0 / n)
    m[1:, :] *= np.sqrt(2.0 / n)
    return m


_DCT = None


def phash(path: str) -> int:
    """64-bit DCT perceptual hash. Deterministic for identical pixels."""
    global _DCT
    import numpy as np
    from PIL import Image
    if _DCT is None:
        _DCT = _dct_matrix(IMG_SIZE)
    with Image.open(path) as im:
        g = im.convert("L").resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
        a = np.asarray(g, dtype=np.float64)
    d = _DCT @ a @ _DCT.T
    block = d[:HASH_SIZE, :HASH_SIZE].flatten()
    med = np.median(block[1:])                      # exclude DC from the threshold
    bits = 0
    for i, v in enumerate(block):
        if i == 0:
            continue
        if v > med:
            bits |= (1 << i)
    return bits


def _cache_path(dataset: str) -> str:
    return os.path.join(C.evidence_dir(dataset), ".cache", f"phash-{CODE_VERSION}.json")


def load_cache(dataset: str) -> Dict[str, Any]:
    p = _cache_path(dataset)
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            return {}
    return {}


def save_cache(dataset: str, cache: Dict[str, Any]) -> None:
    p = C.guard_path(_cache_path(dataset), dataset)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({k: cache[k] for k in sorted(cache)}, fh)
    os.replace(tmp, p)


def hash_screenshots(dataset: str, dataset_root: str) -> Dict[str, Dict[str, Any]]:
    """`{screenshot_path: {sha256, phash, session_id}}`, incremental and restartable.

    Cache key is the file's sha256 plus the code version, so a changed algorithm invalidates
    every entry rather than silently mixing two hash definitions in one index.
    """
    cache = load_cache(dataset)
    out: Dict[str, Dict[str, Any]] = {}
    paths = sorted(glob.glob(os.path.join(dataset_root, "*", "*", "screenshots", "*.jpg")))
    dirty = 0
    for p in paths:
        rel = os.path.relpath(p, C.ROOT)
        fh = C.sha256_file(p)
        hit = cache.get(rel)
        if hit and hit.get("sha256") == fh:
            out[rel] = hit
            continue
        out[rel] = {"sha256": fh, "phash": phash(p),
                    "session_id": os.path.abspath(p).split(os.sep)[-4]}
        cache[rel] = out[rel]
        dirty += 1
        if dirty % 500 == 0:
            save_cache(dataset, cache)
    save_cache(dataset, cache)
    return out


def _events_by_session(dataset_root: str) -> Dict[str, List[Dict]]:
    by: Dict[str, List[Dict]] = collections.defaultdict(list)
    for e in P0.iter_raw_events(dataset_root):
        by[e["_session_id"]].append(e)
    for v in by.values():
        v.sort(key=lambda e: (e.get("timestamp_ms") or 0,
                              (e.get("correlation") or {}).get("sequence_number") or 0))
    return dict(by)


def _element_id(e: Dict) -> str:
    p = e.get("payload") or {}
    el = (p.get("element") or {}).get("attributes") or {}
    fld = p.get("field") or {}
    return el.get("id") or fld.get("id") or ""


def build_states(dataset: str, dataset_root: str) -> Dict[str, Any]:
    hashes = hash_screenshots(dataset, dataset_root)
    by_session = _events_by_session(dataset_root)

    shot_seq: Dict[str, List[Tuple[int, str]]] = collections.defaultdict(list)
    for sid, rows in by_session.items():
        for i, e in enumerate(rows):
            fn = (((e.get("payload") or {}).get("file_reference") or {}).get("filename")) or ""
            if fn:
                shot_seq[sid].append((i, os.path.basename(fn)))
    name_to_idx = {sid: {n: i for i, n in lst} for sid, lst in shot_seq.items()}

    text_idx: Dict[str, List[int]] = collections.defaultdict(list)
    text_cap: Dict[Tuple[str, int], str] = {}
    norm_idx: Dict[str, List[int]] = collections.defaultdict(list)
    for sid, rows in by_session.items():
        n = 0
        for i, e in enumerate(rows):
            if e.get("event_type") not in CAPTURE_EVENT_TYPES:
                n += 1
            xt = (e.get("context") or {}).get("extracted_text") or {}
            if isinstance(xt, dict) and (xt.get("text") or "").strip():
                text_idx[sid].append(i)
                norm_idx[sid].append(n)
                row = P0.capture_row({**e, "_session_id": sid, "_chunk_dir": ""})
                if row:
                    text_cap[(sid, i)] = row["capture_id"]

    decisions: Dict[str, List[int]] = collections.defaultdict(list)
    for sid, rows in by_session.items():
        for i, e in enumerate(rows):
            if e.get("event_type") in ("browser_click", "mouse_click") \
                    and BTN_OK.match(_element_id(e) or ""):
                decisions[sid].append(i)

    groups: Dict[Tuple[str, int], List[str]] = collections.defaultdict(list)
    for rel, h in sorted(hashes.items()):
        groups[(h["session_id"], h["phash"])].append(rel)

    states: List[Dict] = []
    for (sid, ph), members in sorted(groups.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        members = sorted(members)
        idxs = sorted(i for i in (name_to_idx.get(sid, {}).get(os.path.basename(m))
                                  for m in members) if i is not None)
        first_seq = idxs[0] if idxs else None
        last_seq = idxs[-1] if idxs else None
        rep = members[0]
        rows = by_session.get(sid, [])

        near_cap, near_dist = None, None
        if first_seq is not None and text_idx.get(sid):
            t = text_idx[sid]
            j = bisect.bisect_left(t, first_seq)
            best = None
            for k in (j - 1, j):
                if 0 <= k < len(t):
                    d = abs(t[k] - first_seq)
                    if best is None or d < best[0]:
                        best = (d, t[k])
            if best:
                near_dist, near_cap = best[0], text_cap.get((sid, best[1]))

        decision_adjacent = False
        if first_seq is not None:
            for d in decisions.get(sid, []):
                if 0 <= d - first_seq <= DECISION_LOOKBACK:
                    decision_adjacent = True
                    break

        tkey = None
        if first_seq is not None and first_seq < len(rows):
            e = rows[first_seq]
            url = ((e.get("context") or {}).get("active_browser_tab") or {}).get("url") or ""
            o, r = M.split_url(url)
            app = ((e.get("context") or {}).get("active_app") or {}).get("app_name") or ""
            title = ((e.get("context") or {}).get("active_app") or {}).get("window_title") or ""
            tkey = f"{o}|{r}|{app}|{title}"

        states.append({
            "state_id": f"{sid}#s{ph:016x}",
            "phash": f"{ph:016x}",
            "session_id": sid,
            "representative_screenshot_path": rep,
            "member_screenshot_paths": members,
            "n_members": len(members),
            "first_seq": first_seq,
            "last_seq": last_seq,
            "telemetry_state_key": tkey,
            "module_id": M.module_id_of_url(
                (((rows[first_seq].get("context") or {}) if first_seq is not None and
                  first_seq < len(rows) else {}).get("active_browser_tab") or {}).get("url")),
            "nearest_screen_text_capture_id": near_cap,
            "event_distance_to_that_capture": near_dist,
            "is_decision_adjacent": decision_adjacent,
            "extraction_method": "derived",
            "evidence_type": "OBSERVED",
        })

    return {"states": states, "n_images": len(hashes),
            "n_distinct_hashes": len({h["phash"] for h in hashes.values()}),
            "by_session": by_session, "text_idx": dict(text_idx), "norm_idx": dict(norm_idx),
            "decisions": dict(decisions), "text_cap": text_cap}


def build_coverage(ctx: Dict[str, Any]) -> List[Dict]:
    """Per disposition, whether text evidence exists nearby — under all three definitions."""
    by_session = ctx["by_session"]
    text_idx, norm_idx = ctx["text_idx"], ctx["norm_idx"]
    rows: List[Dict] = []
    for sid, ds in sorted(ctx["decisions"].items()):
        ev = by_session[sid]
        norm_of: List[int] = []
        n = 0
        for e in ev:
            if e.get("event_type") not in CAPTURE_EVENT_TYPES:
                n += 1
            norm_of.append(n)
        t = text_idx.get(sid, [])
        tn = norm_idx.get(sid, [])
        for d in ds:
            e = ev[d]
            url = ((e.get("context") or {}).get("active_browser_tab") or {}).get("url") or ""
            entry: Dict[str, Any] = {
                "disposition_id": f"{sid}#d{d:06d}",
                "session_id": sid,
                "event_index": d,
                "timestamp_ms": e.get("timestamp_ms"),
                "element_id": _element_id(e),
                "module_id": M.module_id_of_url(url),
                "extraction_method": "derived",
                "evidence_type": "OBSERVED",
            }
            dn = norm_of[d]
            for N in WINDOWS:
                sym = [abs(x - d) for x in t if abs(x - d) <= N]
                bef = [d - x for x in t if 0 <= d - x <= N]
                nrm = [abs(x - dn) for x in tn if abs(x - dn) <= N]
                entry[f"has_text_symmetric_{N}"] = bool(sym)
                entry[f"dist_symmetric_{N}"] = min(sym) if sym else None
                entry[f"has_text_before_only_{N}"] = bool(bef)
                entry[f"dist_before_only_{N}"] = min(bef) if bef else None
                entry[f"has_text_normalised_{N}"] = bool(nrm)
                entry[f"dist_normalised_{N}"] = min(nrm) if nrm else None
            near = [x for x in t if abs(x - d) <= max(WINDOWS)]
            texts = []
            for x in near:
                xt = (ev[x].get("context") or {}).get("extracted_text") or {}
                texts.append((xt.get("text") or "") if isinstance(xt, dict) else "")
            blob = "\n".join(texts)
            entry["queue_table_captured"] = any(
                w in blob for w in ("申請一覧", "処理一覧", "処理待ち一覧", "入社照合一覧"))
            entry["detail_pane_captured"] = bool(re.search(r"詳細\s*[—\-–]\s*P\d", blob))
            rows.append(entry)
    rows.sort(key=lambda r: (r["session_id"], r["event_index"]))
    return rows


def run(dataset: str, dataset_root: str, dry_run: bool = False) -> Dict[str, Any]:
    ctx = build_states(dataset, dataset_root)
    states, cov = ctx["states"], build_coverage(ctx)

    a1 = C.write_jsonl(states, os.path.join(C.evidence_dir(dataset), "states.jsonl"), dataset,
                       sort_key=lambda s: (s["session_id"], s["first_seq"] if
                                           s["first_seq"] is not None else 1 << 30,
                                           s["state_id"]),
                       required=("state_id", "phash", "session_id",
                                 "representative_screenshot_path", "n_members"))
    a2 = C.write_jsonl(cov, os.path.join(C.evidence_dir(dataset), "coverage_gaps.jsonl"),
                       dataset, sort_key=lambda r: (r["session_id"], r["event_index"]),
                       required=("disposition_id", "session_id", "event_index", "element_id"))

    n_img, n_hash = ctx["n_images"], ctx["n_distinct_hashes"]
    summary: Dict[str, Any] = {
        "pass": "1",
        "n_screenshots": n_img,
        "n_distinct_phashes": n_hash,
        "reduction_pct": round(100 * (1 - n_hash / n_img), 1) if n_img else None,
        "_baseline_note": "a 708-image sample was reported at 286 distinct hashes / 59.6% "
                          "reduction; the figure above is measured over ALL images",
        "n_states": len(states),
        "n_decision_adjacent_states": sum(1 for s in states if s["is_decision_adjacent"]),
        "n_dispositions": len(cov),
        "coverage": {},
        "queue_table_captured": sum(1 for r in cov if r["queue_table_captured"]),
        "detail_pane_captured": sum(1 for r in cov if r["detail_pane_captured"]),
    }
    for N in WINDOWS:
        for kind in ("symmetric", "before_only", "normalised"):
            hits = [r for r in cov if r[f"has_text_{kind}_{N}"]]
            ds = [r[f"dist_{kind}_{N}"] for r in hits]
            summary["coverage"][f"{kind}_{N}"] = {
                "n": len(hits), "of": len(cov),
                "pct": round(100 * len(hits) / len(cov), 1) if cov else None,
                "median_distance": sorted(ds)[len(ds) // 2] if ds else None}
    C.merge_manifest(dataset, "pass1", C.run_manifest(
        dataset, "pass1",
        {"states.jsonl": a1, "coverage_gaps.jsonl": a2},
        config={"hash": "PIL + numpy DCT-II, 32x32 -> 8x8, DC excluded", "hash_bits": 64,
                "windows": list(WINDOWS), "decision_lookback": DECISION_LOOKBACK,
                "ocr": "NOT USED"},
        extra={"summary": summary}))
    return {"summary": summary, "states": states, "coverage": cov}
