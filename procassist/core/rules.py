"""Deterministic evaluation of the clauses already parsed out of Dataset B. Pure; no I/O.

This module does not parse Japanese. `analysis/evidence` did that in Step 2 and left the tiers
in `documents.jsonl` as structured `parsed.tiers`. What is left is arithmetic and the honest
reporting of what the arithmetic does *not* settle.

The one interesting decision is `evaluate_threshold`. 接待交際費規程 第２条 reads:

    1回あたり5万円未満：部門長承認。5万円以上：役員承認。10万円以上：社長承認。

Its tiers overlap. ¥135,181 satisfies both `5万円以上：役員承認` and `10万円以上：社長承認`, so the
clause as written does not select a single approval authority for it. We report that as `FLAG`
rather than silently applying a most-specific-wins convention the document never states. An
amount that satisfies exactly one tier is `OK`: the clause routes it unambiguously.
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


def strictest_tier(tiers: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The matching tier with the highest threshold; ties resolve to the later clause sentence."""
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

    strictest = strictest_tier(matched) or matched[-1]
    consequent = str(strictest.get("consequent") or "")
    reasons = [
        f"{ref.variable_ja} {shown_amount} は「{t.get('raw')}」に該当 → {t.get('consequent')}"
        for t in matched
    ]

    if len(matched) > 1:
        return Check(
            **base,
            status=Status.FLAG,
            expected_ja=consequent,
            observed_ja="この画面には承認権限の記録欄がありません",
            why_ja="。".join(reasons) + f"。区分が{len(matched)}件該当するため、{heading}だけでは決まりません。",
            why_en=(f"{len(matched)} tiers of the clause match {shown_amount}; the strictest is "
                    f"{consequent}. The clause as written does not select between them, and this "
                    f"screen records no approval authority, so a human decides."),
        )

    return Check(
        **base,
        status=Status.OK,
        expected_ja=consequent,
        observed_ja=shown_amount,
        why_ja=reasons[0] + "。該当区分は1件のみです。",
        why_en=(f"exactly one tier matches {shown_amount}; the clause routes it to {consequent} "
                f"without ambiguity."),
    )
