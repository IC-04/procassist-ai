"""Pass 0 — observed dispositions.

reads only:  screen_text.jsonl and records.jsonl rows (in memory)
writes only: build/dataset_b/evidence/outcomes.jsonl, outcome_polarity.json

Two sources. **Toasts** are the portal's own confirmation banner, appended to the same capture as
the queue it confirms. **Status transitions** are derived by diffing a record's `ステータス` across
successive captures within a session — weaker evidence, and tagged `DERIVED` rather than
`OBSERVED` to keep the distinction visible.

REQUIRED FINDING. Polarity is classified against a declared lexicon and the distribution is a
first-class output, because if the observed outcome variable turns out to have no variance then
no hypothesis about *predicting* the outcome can be tested at all — and reporting an accuracy
figure over a constant would be worse than reporting nothing.
"""
from __future__ import annotations

import collections
import os
import re
from typing import Any, Dict, List, Optional, Sequence

from . import common as C

TOAST_RE = re.compile(r"(P\d{1,2}-\d{8}-\d{3})\s*[：:]\s*(.{2,40})")

# Declared lexicon. Negative is checked FIRST, so a message containing both reads as negative.
NEGATIVE = ("却下", "差戻", "差し戻", "エラー", "失敗", "拒否", "取消", "取り消", "無効",
            "警告", "不備", "返戻", "否認", "中止", "できません", "ません")
POSITIVE = ("登録確定", "照合完了", "申請を承認", "処理完了", "完了", "承認", "確定",
            "登録しました", "保存", "成功")


def polarity(message: str) -> str:
    if any(k in message for k in NEGATIVE):
        return "negative"
    if any(k in message for k in POSITIVE):
        return "positive"
    return "unknown"


def from_toasts(captures: Sequence[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    for cap in captures:
        for m in TOAST_RE.finditer(cap["text_ja"]):
            msg = m.group(2).strip().splitlines()[0].strip()
            rows.append({
                "outcome_id": C.sha256_text(
                    f"{cap['capture_id']}|{m.group(1)}|{msg}|toast")[:16],
                "record_id": m.group(1),
                "module_id": cap["module_id"],
                "outcome_text_ja": msg,
                "outcome_polarity": polarity(msg),
                "capture_id": cap["capture_id"],
                "session_id": cap["session_id"],
                "sequence_number": cap["sequence_number"],
                "timestamp_ms": cap["timestamp_ms"],
                "source": "toast",
                "extraction_method": "telemetry_text",
                "evidence_type": "OBSERVED",
            })
    return rows


def from_status_transitions(records: Sequence[Dict]) -> List[Dict]:
    """Diff each record's status across successive captures within a session."""
    seen: Dict[tuple, List[Dict]] = collections.defaultdict(list)
    for r in records:
        if r.get("status_ja"):
            seen[(r["session_id"], r["record_id"])].append(r)
    rows: List[Dict] = []
    for (sid, rid), lst in sorted(seen.items()):
        lst.sort(key=lambda r: (r["sequence_number"] or 0, r["capture_id"]))
        prev = None
        for r in lst:
            cur = r["status_ja"]
            if prev is not None and cur != prev:
                msg = f"{prev}→{cur}"
                rows.append({
                    "outcome_id": C.sha256_text(
                        f"{r['capture_id']}|{rid}|{msg}|status")[:16],
                    "record_id": rid,
                    "module_id": r["module_id"],
                    "outcome_text_ja": msg,
                    "outcome_polarity": polarity(cur),
                    "status_from_ja": prev,
                    "status_to_ja": cur,
                    "capture_id": r["capture_id"],
                    "session_id": sid,
                    "sequence_number": r["sequence_number"],
                    "timestamp_ms": r["timestamp_ms"],
                    "source": "status_transition",
                    "extraction_method": "telemetry_text",
                    "evidence_type": "DERIVED",
                })
            prev = cur
    return rows


REQUIRED = ("outcome_id", "record_id", "outcome_text_ja", "outcome_polarity", "capture_id",
            "sequence_number", "timestamp_ms", "source")


def build(captures: Sequence[Dict], records: Sequence[Dict]) -> Dict[str, Any]:
    rows = from_toasts(captures) + from_status_transitions(records)
    rows.sort(key=lambda r: (r["session_id"], r["sequence_number"] or 0, r["outcome_id"]))
    by_source: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    msgs: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        by_source[r["source"]][r["outcome_polarity"]] += 1
        msgs[r["source"]][r["outcome_text_ja"]] += 1
    report = {
        "_finding": "",
        "_lexicon": {"negative_checked_first": list(NEGATIVE), "positive": list(POSITIVE)},
        "n_outcomes": len(rows),
        "by_source": {k: dict(v) for k, v in sorted(by_source.items())},
        "distinct_messages": {k: v.most_common(20) for k, v in sorted(msgs.items())},
    }
    toast = by_source.get("toast", collections.Counter())
    if toast and toast.get("negative", 0) == 0:
        report["_finding"] = (
            f"ZERO VARIANCE IN THE OBSERVED TOAST OUTCOME: {sum(toast.values())} toasts, "
            f"{toast.get('positive', 0)} positive, 0 negative, "
            f"{toast.get('unknown', 0)} unknown, across "
            f"{len(msgs.get('toast', {}))} distinct messages. Any hypothesis that a rule "
            f"PREDICTS the disposition is untestable on this evidence: the dependent variable "
            f"is a constant. Reported as UNTESTABLE, never as an accuracy figure.")
    else:
        report["_finding"] = "Toast outcomes show more than one polarity; H1 is testable."
    return {"rows": rows, "report": report}


def run(dataset: str, captures: Sequence[Dict], records: Sequence[Dict]) -> Dict[str, Any]:
    built = build(captures, records)
    art = C.write_jsonl(built["rows"],
                        os.path.join(C.evidence_dir(dataset), "outcomes.jsonl"), dataset,
                        sort_key=lambda r: (r["session_id"], r["sequence_number"] or 0,
                                            r["outcome_id"]),
                        required=REQUIRED)
    rep = C.write_json(built["report"],
                       os.path.join(C.evidence_dir(dataset), "outcome_polarity.json"), dataset)
    return {"artifact": art, "rows": built["rows"], "report": built["report"],
            "report_artifact": rep}
