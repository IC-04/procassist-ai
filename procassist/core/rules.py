"""Deterministic evaluation of the clauses already parsed out of Dataset B. Pure; no I/O.

This module does not parse Japanese. `analysis/evidence` did that in Step 2 and left the tiers
in `documents.jsonl` as structured `parsed.tiers`. What is left is arithmetic and the honest
reporting of what the arithmetic does *not* settle.

The one interesting decision is how to read overlapping tiers. 接待交際費規程 第２条 reads:

    1回あたり5万円未満：部門長承認。5万円以上：役員承認。10万円以上：社長承認。

As a string, ¥135,181 satisfies both `5万円以上` and `10万円以上`. As a Japanese
approval-authority clause it does not: tiers of this form are conventionally read as **bands**,
where `5万円以上` means 5万〜10万 and the most specific matching tier wins. We apply band
semantics — `MOST_SPECIFIC_TIER` — so ¥135,181 is unambiguously 社長承認. The literal overlap is
kept and reported as a lower-prominence `INF` note rather than being silently resolved.

A `FLAG` is then not a statement about the clause but about **where the record was found**: the
authority the clause requires exceeds the ceiling declared for the queue the record sits in.
That ceiling lives in `definitions/*.toml`, tagged with its basis, because on the HR settlement
queue it is a declared policy parameter and not something the capture determines.
"""
from __future__ import annotations

import operator
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

from .definitions import ModuleDefinition, Status
from .result import Check, Provenance

#: Comparison operators the Step 2 extractor emits in `parsed.tiers[].operator`.
_OPS: Dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
}

_AMOUNT = re.compile(r"^\s*([0-9][0-9,]*)\s*円\s*$")


def parse_amount_jpy(raw: Optional[str]) -> Optional[int]:
    """`"135,181円"` -> `135181`; anything else -> `None`.

    Deliberately strict. A value the screen renders in a shape we have not observed is missing
    information, not an amount to be coerced — the caller turns `None` into `REQUIRES_REVIEW`.
    """
    if not raw:
        return None
    m = _AMOUNT.match(str(raw))
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def format_amount_jpy(value: int) -> str:
    """`135181` -> `"135,181円"`. `円` is a suffix; this module never emits `¥`."""
    return f"{value:,}円"


def _tier_label(tier: Dict[str, Any]) -> str:
    return f"{tier.get('raw', '')}：{tier.get('consequent', '')}"


def matching_tiers(amount_jpy: int, tiers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every tier whose comparison the amount satisfies, in document order."""
    out: List[Dict[str, Any]] = []
    for tier in tiers:
        op = _OPS.get(str(tier.get("operator")))
        threshold = tier.get("value_jpy")
        if op is None or threshold is None:
            continue
        if op(float(amount_jpy), float(threshold)):
            out.append(tier)
    return out


#: How overlapping tiers are read. Named so the choice is visible in the trace and the UI.
SEMANTICS = "MOST_SPECIFIC_TIER"


def strictest_tier(tiers: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The most specific matching tier: highest threshold, later clause sentence breaking ties.

    Under band semantics this is *the* applicable tier, not merely the strictest of several.
    """
    if not tiers:
        return None
    return max(enumerate(tiers), key=lambda p: (float(p[1].get("value_jpy") or 0.0), p[0]))[1]


def evaluate_threshold(
    definition: ModuleDefinition,
    fields: Dict[str, Optional[str]],
    parsed: Optional[Dict[str, Any]],
    provenance: Provenance,
) -> Check:
    """Apply one parsed `threshold` rule to one record.

    `REQUIRES_REVIEW` when the amount is absent or in an unobserved shape, or when the clause
    covers no tier for it. `FLAG` when more than one tier matches. `OK` when exactly one does.
    """
    ref = definition.threshold
    assert ref is not None, "evaluate_threshold called on a definition with no threshold rule"
    source = ref.source_field_ja
    raw = fields.get(source)
    amount = parse_amount_jpy(raw)

    # The clause is named by the heading captured in the document, verbatim: Dataset B writes
    # 第２条 with a fullwidth ２, and normalising it here would be a silent edit of source text.
    heading = provenance.clause_heading_ja or "該当条文"
    base = dict(
        check_id="threshold.approval_authority",
        kind="threshold",
        label_ja=f"承認権限（{ref.variable_ja}）",
        label_en="approval authority by amount",
        provenance=provenance,
    )

    if amount is None:
        shown = "（画面に項目なし）" if raw is None else str(raw)
        return Check(
            **base,
            status=Status.REQUIRES_REVIEW,
            expected_ja=f"{ref.variable_ja}（数値）",
            observed_ja=shown,
            why_ja=f"{ref.variable_ja}がこの画面にないため、{heading}の判定ができません。",
            why_en=(f"{ref.variable_ja} is required to evaluate the clause and this screen does "
                    f"not carry it; the tier cannot be selected without inventing a value."),
        )

    tiers = list((parsed or {}).get("tiers") or [])
    matched = matching_tiers(amount, tiers)
    shown_amount = format_amount_jpy(amount)

    if not matched:
        return Check(
            **base,
            status=Status.REQUIRES_REVIEW,
            expected_ja="該当する区分",
            observed_ja=shown_amount,
            why_ja=f"{ref.variable_ja} {shown_amount} に該当する区分が{heading}にありません。",
            why_en=(f"no tier of the clause covers {shown_amount}; the clause does not decide "
                    f"this case and a human must."),
        )

    applicable = strictest_tier(matched) or matched[-1]
    consequent = str(applicable.get("consequent") or "")
    why_tier = (f"{ref.variable_ja} {shown_amount} は「{applicable.get('raw')}」に該当 "
                f"→ {consequent}")

    # The literal overlap is kept, but as a note rather than as the verdict.
    overlap_note_ja = overlap_note_en = None
    if len(matched) > 1:
        others = "・".join(f"「{t.get('raw')}」" for t in matched if t is not applicable)
        overlap_note_ja = (f"[INF] {heading}の区分は文字どおりには重複します（{others} にも該当）。"
                           f"帯（バンド）解釈をとり、最も限定的な区分を適用しました。")
        overlap_note_en = (f"[INF] the tiers of {heading} overlap as written; band semantics "
                           f"assumed and the most specific tier applied "
                           f"({SEMANTICS}).")

    ladder = definition.authority
    if ladder is None:
        return Check(
            **base,
            status=Status.OK,
            expected_ja=consequent,
            observed_ja=shown_amount,
            why_ja=why_tier + "。",
            why_en=f"the clause routes {shown_amount} to {consequent}.",
            semantics=SEMANTICS,
            inference_note_ja=overlap_note_ja,
            inference_note_en=overlap_note_en,
        )

    ceiling = ladder.ceiling_ja
    if ladder.exceeds_ceiling(consequent):
        return Check(
            **base,
            status=Status.FLAG,
            expected_ja=consequent,
            observed_ja=f"このキューの権限上限：{ceiling}",
            why_ja=(why_tier + f"。必要な承認権限が、このキュー（{definition.name_ja}）の"
                    f"権限上限 {ceiling} を超えています。"),
            why_en=(f"{shown_amount} falls in the {applicable.get('raw')} band, which requires "
                    f"{consequent}. That exceeds the declared ceiling for this queue "
                    f"({definition.name_ja}), which is {ceiling}."),
            semantics=SEMANTICS,
            basis=ladder.basis,
            basis_note_ja=ladder.basis_note_ja,
            basis_note_en=ladder.basis_note_en,
            inference_note_ja=overlap_note_ja,
            inference_note_en=overlap_note_en,
        )

    return Check(
        **base,
        status=Status.OK,
        expected_ja=consequent,
        observed_ja=f"このキューの権限上限：{ceiling}",
        why_ja=why_tier + f"。キューの権限上限 {ceiling} の範囲内です。",
        why_en=(f"{shown_amount} falls in the {applicable.get('raw')} band, which requires "
                f"{consequent}, within this queue's declared ceiling of {ceiling}."),
        semantics=SEMANTICS,
        basis=ladder.basis,
        basis_note_ja=ladder.basis_note_ja,
        basis_note_en=ladder.basis_note_en,
        inference_note_ja=overlap_note_ja,
        inference_note_en=overlap_note_en,
    )
