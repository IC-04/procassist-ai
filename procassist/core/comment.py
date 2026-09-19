"""Render the operator's own comment, minus the judgement. Pure; no I/O.

Every template here was reconstructed from `payload.target_element.value` on Dataset B click
events, so the rendered string is the operator's wording, not ours — including the ideographic
space `　` (U+3000) before 金額 and `円` as a suffix. The templates are in `definitions/*.toml`
with their observed counts.

The invariant this module exists to enforce: **the judgement slot is never filled here.**
`render` fills every record slot, leaves the judgement slot as the empty string, and asserts
that the result carries `judgement=None`. A human fills it by clicking a chip in the panel.
"""
from __future__ import annotations

from typing import Dict, Optional

from .definitions import CommentTemplate, ModuleDefinition
from .result import DraftComment
from .rules import format_amount_jpy, parse_amount_jpy


class SlotUnfilled(ValueError):
    """A record slot the template needs and the record does not supply."""


def _resolve(spec: str, fields: Dict[str, Optional[str]]) -> Optional[str]:
    """Resolve one slot spec against a record.

    Two forms, both declared in the definition file:
      `field:金額`        the field's text, verbatim
      `amount:金額`       the field parsed to an integer and re-rendered as `1,234円`
      `suffix:区分: `     the part of the field's text after a literal prefix
    """
    kind, _, arg = spec.partition(":")
    if kind == "field":
        return fields.get(arg)
    if kind == "amount":
        value = parse_amount_jpy(fields.get(arg))
        return None if value is None else format_amount_jpy(value)
    if kind == "amount_digits":
        value = parse_amount_jpy(fields.get(arg))
        return None if value is None else f"{value:,}"
    if kind == "suffix":
        field_ja, _, prefix = arg.partition("|")
        raw = fields.get(field_ja)
        if not raw or not raw.startswith(prefix):
            return None
        return raw[len(prefix):].strip() or None
    raise ValueError(f"unknown slot spec {spec!r}")


def render(definition: ModuleDefinition,
           fields: Dict[str, Optional[str]]) -> Optional[DraftComment]:
    """Fill the record slots and leave the judgement empty, or `None` if a slot is unfillable.

    Returning `None` rather than a partially-filled string is deliberate: a draft with a hole in
    it reads as finished text and invites the operator to paste it. If we cannot render the
    comment from the record, we offer no comment.
    """
    tpl: CommentTemplate = definition.comment
    filled: Dict[str, str] = {}
    for name in tpl.slot_names():
        if name == tpl.judgement_slot:
            continue
        spec = tpl.slots.get(name)
        if spec is None:
            raise SlotUnfilled(f"template slot {name!r} has no spec in {definition.definition_id}")
        value = _resolve(spec, fields)
        if value is None:
            return None
        filled[name] = value

    text = tpl.template_ja.format(**filled, **{tpl.judgement_slot: ""})
    draft = DraftComment(
        element_id=tpl.element_id,
        template_ja=tpl.template_ja,
        text_ja=text,
        judgement_slot=tpl.judgement_slot,
        judgement=None,
        judgement_options=[
            {"text_ja": o.text_ja, "observed_n": o.observed_n, "offered_by_ja": o.offered_by_ja}
            for o in tpl.judgement_options
        ],
        filled_slots=filled,
        observed_n=tpl.observed_n,
        evidence_note_en=tpl.evidence_note_en,
    )
    assert draft.judgement is None, "the engine must never choose a judgement"
    return draft


def complete(draft: DraftComment, judgement_ja: str) -> str:
    """The finished comment, given a judgement a **human** chose.

    Not called by the engine. The panel calls the equivalent in JavaScript when a chip is
    clicked, and this exists so the same composition can be asserted in a test.
    """
    options = [str(o.get("text_ja")) for o in draft.judgement_options]
    if judgement_ja not in options:
        raise ValueError(f"{judgement_ja!r} is not one of the observed dispositions {options}")
    return draft.template_ja.format(**draft.filled_slots,
                                    **{draft.judgement_slot: judgement_ja})
