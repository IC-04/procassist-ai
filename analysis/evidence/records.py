"""Pass 0 — business records parsed from queue-table and detail-pane captures.

reads only:  screen_text.jsonl rows (in memory)
writes only: build/dataset_b/evidence/records.jsonl, record_module_disagreements.csv

STRUCTURE, measured rather than assumed. A portal capture is a flat newline-separated dump. It
may contain, in this order: a count banner, a list heading, an OPTIONAL detail pane
(`詳細 — <record id> · <name>` followed by label/value pairs), then a queue table — a run of
column headers beginning `ID` and ending `ステータス`, followed by cells in row-major order.

TWO WARNINGS THE PARSER IS BUILT AROUND.

1. **Column headers are reused across modules and are wrong for some of them.** On the module the
   URL calls FI 支払処理 the header run is `ID 社員ID 氏名 入社日 部署 照合項目数 ステータス`, i.e.
   onboarding headers. So headers are stored VERBATIM as keys *and* every value is stored again
   by POSITION in `fields_by_index`. Nothing downstream may rely on header semantics.

2. **The URL-derived module and the table content systematically disagree.** Captures whose URL
   says HR 経費精算 contain `P6-…` invoice rows; captures whose URL says FI 支払処理 contain `P3-…`
   onboarding rows. Both module keys are emitted — `module_id` from the URL and
   `prefix_modal_module_id` learned from co-occurrence — together with an explicit agreement
   flag. The disagreement is REPORTED, never resolved: silently trusting either key would
   fabricate the module attribution that half this analysis rests on.
"""
from __future__ import annotations

import collections
import csv
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import common as C
from . import modules as M

RID_RE = re.compile(r"^P\d{1,2}-\d{8}-\d{3}$")
RID_ANY = re.compile(r"P\d{1,2}-\d{8}-\d{3}")
DETAIL_RE = re.compile(r"^詳細\s*[—\-–]\s*(P\d{1,2}-\d{8}-\d{3})(?:\s*[·・]\s*(.*))?$")
LIST_WORDS = ("申請一覧", "処理一覧", "処理待ち一覧", "入社照合一覧")
HEADER_START = "ID"
HEADER_END = "ステータス"
EXCEPTION_MARKERS = ("⚠", "！", "!", "要確認", "例外", "差異", "不一致", "超過")


def _lines(text: str) -> List[str]:
    return [l.strip() for l in text.splitlines() if l.strip()]


def find_header_run(lines: Sequence[str]) -> Optional[Tuple[int, List[str]]]:
    """Index and content of the queue-table column header run, or None.

    A header run starts at a line exactly `ID` and ends at the next `ステータス` within a short
    window, with no record id in between. Anchoring on both ends is what keeps a detail pane's
    `管理ID` / `社員ID` labels from being mistaken for a table header.
    """
    for i, l in enumerate(lines):
        if l != HEADER_START:
            continue
        for j in range(i + 1, min(i + 12, len(lines))):
            if RID_RE.match(lines[j]):
                break
            if lines[j] == HEADER_END:
                return i, list(lines[i:j + 1])
    return None


def parse_detail_pane(lines: Sequence[str]) -> Optional[Dict[str, Any]]:
    """The per-record pane, when one is present.

    Layout, read off all five occurrences in Dataset B rather than assumed:

        詳細 — <record id> [· <display name>]
        <status>
        <label> / <value>  pairs, strictly alternating
        [参照：]
        [<reference line>]
        <comment-field label>
        <comment placeholder>
        ID … (the queue table begins)

    Rare — **5 captures of 939** — but it is the only place in the telemetry text where
    per-record values such as `承認権限` (approval authority) appear at all, which makes it the
    only direct evidence for H4 on the modules that have one.

    One of the five renders its labels as raw field identifiers (`name`, `emp_id`, `variant`,
    `procedure`, `target_month`, `reason`) rather than Japanese. That is preserved verbatim, like
    every other label: it is what the screen said.
    """
    COMMENT_LABELS = ("処理コメント", "処理メモ", "コメント", "備考")
    for i, l in enumerate(lines):
        m = DETAIL_RE.match(l)
        if not m:
            continue
        rid, name = m.group(1), (m.group(2) or "").strip()
        status = lines[i + 1] if i + 1 < len(lines) else None
        fields: Dict[str, str] = {}
        refs: List[str] = []
        j = i + 2
        while j < len(lines):
            cur = lines[j]
            if cur == HEADER_START and find_header_run(lines[j:]):
                break
            if cur in COMMENT_LABELS:
                j += 2                      # label + placeholder, neither is a value
                continue
            if cur.endswith("：") or cur.endswith(":"):
                if j + 1 < len(lines):
                    refs.append(lines[j + 1])
                j += 2
                continue
            if j + 1 < len(lines):
                fields[cur] = lines[j + 1]
                j += 2
                continue
            j += 1
        # `参照：申請者区分：manager　承認権限：役員` carries the authority level, which is exactly
        # the variable a threshold rule needs. Split it out, verbatim on both sides.
        derived: Dict[str, str] = {}
        for r in refs:
            for part in re.split(r"[\u3000\s]+", r):
                if "：" in part:
                    k, _, v = part.partition("：")
                    if k and v:
                        derived[k.strip()] = v.strip()
        return {"record_id": rid, "display_name": name, "status_ja": status,
                "fields": fields, "reference_lines": refs, "reference_fields": derived}
    return None


def parse_queue(lines: Sequence[str]) -> Tuple[List[str], List[List[str]]]:
    """Column headers and row-major cells. Rows stop at the first non-record-id first cell."""
    found = find_header_run(lines)
    if not found:
        return [], []
    i, headers = found
    w = len(headers)
    rows: List[List[str]] = []
    j = i + w
    while j + w <= len(lines) and RID_RE.match(lines[j]):
        rows.append(list(lines[j:j + w]))
        j += w
    return headers, rows


def _status_of(headers: Sequence[str], cells: Sequence[str]) -> Optional[str]:
    if HEADER_END in headers:
        k = list(headers).index(HEADER_END)
        if k < len(cells):
            return cells[k]
    return cells[-1] if cells else None


def build(captures: Sequence[Dict]) -> Dict[str, Any]:
    """`records.jsonl` rows plus the module-disagreement table."""
    staged: List[Dict] = []
    for cap in captures:
        lines = _lines(cap["text_ja"])
        if not lines:
            continue
        headers, rows = parse_queue(lines)
        detail = parse_detail_pane(lines)
        has_list = any(w in cap["text_ja"] for w in LIST_WORDS)

        for pos, cells in enumerate(rows):
            rid = cells[0]
            blob = " ".join(cells)
            staged.append({
                "record_id": rid,
                "module_id": cap["module_id"],
                "capture_id": cap["capture_id"],
                "session_id": cap["session_id"],
                "sequence_number": cap["sequence_number"],
                "timestamp_ms": cap["timestamp_ms"],
                "row_index": pos,
                "source_view": "queue_table" if has_list else "table",
                "column_headers": list(headers),
                "fields": {h: c for h, c in zip(headers, cells)},
                "fields_by_index": {str(k): c for k, c in enumerate(cells)},
                "status_ja": _status_of(headers, cells),
                "badge_ja": None,
                "exception_marker": (True if any(x in blob for x in EXCEPTION_MARKERS) else False),
                "extraction_method": "telemetry_text",
                "evidence_type": "OBSERVED",
            })

        if detail:
            blob = " ".join(list(detail["fields"].values()) + detail["reference_lines"])
            merged = dict(detail["fields"])
            merged.update(detail["reference_fields"])
            staged.append({
                "record_id": detail["record_id"],
                "module_id": cap["module_id"],
                "capture_id": cap["capture_id"],
                "session_id": cap["session_id"],
                "sequence_number": cap["sequence_number"],
                "timestamp_ms": cap["timestamp_ms"],
                "row_index": -1,
                "source_view": "detail_pane",
                "column_headers": sorted(merged),
                "fields": merged,
                "fields_by_index": {str(k): v for k, v in enumerate(merged.values())},
                "status_ja": detail["status_ja"],
                "badge_ja": None,
                "exception_marker": (True if any(x in blob for x in EXCEPTION_MARKERS) else False),
                "display_name": detail["display_name"],
                "reference_lines": list(detail["reference_lines"]),
                "reference_fields": dict(detail["reference_fields"]),
                "extraction_method": "telemetry_text",
                "evidence_type": "OBSERVED",
            })

    prefix_map = M.learn_prefix_map((r["record_id"], r["module_id"]) for r in staged)
    for r in staged:
        r.update(M.crosscheck(r["record_id"], r["module_id"], prefix_map))

    disagreements = [r for r in staged if r["module_id_agrees_with_prefix"] is False]
    return {"rows": staged, "prefix_map": prefix_map, "disagreements": disagreements}


REQUIRED = ("record_id", "module_id", "capture_id", "session_id", "sequence_number",
            "timestamp_ms", "fields", "fields_by_index", "status_ja")


def run(dataset: str, captures: Sequence[Dict]) -> Dict[str, Any]:
    built = build(captures)
    rows = built["rows"]
    art = C.write_jsonl(rows, os.path.join(C.evidence_dir(dataset), "records.jsonl"), dataset,
                        sort_key=lambda r: (r["session_id"], r["sequence_number"] or 0,
                                            r["row_index"], r["record_id"]),
                        required=REQUIRED)

    path = C.guard_path(os.path.join(C.evidence_dir(dataset),
                                     "record_module_disagreements.csv"), dataset)
    by = collections.Counter(
        (r["module_id"], r["prefix_modal_module_id"]) for r in built["disagreements"])
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["module_id_from_url", "prefix_modal_module_id", "n_records",
                    "note"])
        for (u, p), n in sorted(by.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            w.writerow([u, p, n, "REPORTED, NOT RESOLVED — the URL and the record-id prefix "
                                 "are independent module keys and they disagree here"])
    return {"artifact": art, "rows": rows, "prefix_map": built["prefix_map"],
            "n_disagreements": len(built["disagreements"]),
            "disagreement_csv": os.path.relpath(path, C.ROOT)}
