"""What the panel saves the operator, counted in actions. Pure; no I/O.

Three rules the README and ADR-024 impose on anything in this file:

  * **Ranges, never point estimates.** Execution counts in this corpus are ranges (ADR-022),
    and the Word round trip is measured as a proportion with a Wilson 95% interval.
  * **No seconds, no yen, no FTE.** Waiting times were compressed in the capture environment,
    so this corpus cannot support an absolute time claim. The page ships a calculator with the
    three inputs *empty*, because they are the client's numbers, not ours.
  * **Named to its module key**, `(origin, route)` — ADR-022 — never to a Step 1 label.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .definitions import ModuleDefinition
from .result import DraftComment


def _round_range(lo: float, hi: float) -> List[float]:
    return [round(lo, 2), round(hi, 2)]


def action_budget(
    definition: ModuleDefinition,
    draft: Optional[DraftComment],
    n_lookups: int,
    measured: Dict[str, Any],
) -> Dict[str, Any]:
    """The actions this one prepared record avoids, with the evidence for each line.

    `app_switches` is a range because it is a measured proportion. `keystrokes` is exact —
    it is the length of the string the panel actually staged — and is reported next to the
    range of comment lengths observed on that same screen, so the reader can see the draft is
    the same size as the thing operators typed. `lookups` is a count of what the panel put on
    one screen.
    """
    key = definition.host.production_url_ja or (definition.host.origin + definition.host.route)
    row = (measured.get("by_route") or {}).get(key) or {}
    lo, hi = row.get("switches_ci95") or [0.0, 0.0]
    n = row.get("dispositions") or 0
    s = row.get("word_switches") or 0
    chars = row.get("comment_chars_observed") or {}

    keystrokes = len(draft.text_ja) if draft is not None else 0
    return {
        "module_key": key,
        "app_switches": {
            "range": _round_range(lo, hi),
            "point": row.get("switches_per_disposition"),
            "basis_en": (f"{s} foreground switches into WINWORD.EXE over {n} dispositions on "
                         f"this screen; Wilson 95%"),
            "basis_ja": f"この画面の処分 {n} 件に対し Word への切替 {s} 回（Wilson 95%）",
        },
        "keystrokes": {
            "exact": keystrokes,
            "observed_range": [chars.get("min"), chars.get("max")],
            "basis_en": (f"the staged draft is {keystrokes} characters; comments typed into "
                         f"#{definition.note_element_id} on this screen ran "
                         f"{chars.get('min')}–{chars.get('max')} characters"),
            "basis_ja": (f"下書きは {keystrokes} 字。この画面の #{definition.note_element_id} に"
                         f"実際に入力された文字数は {chars.get('min')}〜{chars.get('max')} 字"),
        },
        "lookups": {
            "exact": n_lookups,
            "basis_en": ("record fields, the governing document and the clause, collected onto "
                         "one screen instead of being looked up separately"),
            "basis_ja": "レコード項目・規程・条文を 1 画面にまとめた件数",
        },
        "caveat_en": measured.get("caveat_en", ""),
    }


def total_budget(per_record: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum the per-record budgets into the queue-level range shown in the summary strip."""
    lo = sum((b["app_switches"]["range"][0] for b in per_record), 0.0)
    hi = sum((b["app_switches"]["range"][1] for b in per_record), 0.0)
    keys = sum(b["keystrokes"]["exact"] for b in per_record)
    looks = sum(b["lookups"]["exact"] for b in per_record)
    return {
        "n_records": len(per_record),
        "app_switches_range": [int(lo), int(round(hi + 0.5))],
        "keystrokes_total": keys,
        "lookups_total": looks,
        # The number that is not a saving. It is here because it is the point.
        "dispositions_taken": 0,
    }
