"""Declarative shape of a governed queue. Pure data; no I/O, no network.

A `ModuleDefinition` is the whole of what ProcAssist knows about one screen: which host serves
it, which records appear on it, which document governs them, which clause carries the rule, and
what the operator types afterwards. Every claim the panel makes must be traceable to a field
here, and every field here must be traceable to Dataset B — see `definitions/*.toml`, where the
evidence for each value is written next to it.

Nothing in this module reads a file. `procassist.adapters` does that.
"""
from __future__ import annotations

import enum
import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Status(str, enum.Enum):
    """The only four verdicts ProcAssist emits. There are deliberately no confidence scores.

    A score would invite the reader to trade the four apart ("0.7 OK") when the whole point is
    that three of them mean *stop and look*, and only one of them means *the rule was applied
    and it held*.
    """

    OK = "OK"
    FLAG = "FLAG"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    MISS = "MISS"


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DocumentRef(Frozen):
    """A pointer into `documents.jsonl`, by regulation name *and* by capture identity.

    `document_id` is a sha256 of the captured body text, not a document identity: 15 distinct
    `document_id`s in Dataset B carry the same 接待交際費規程 第2条 under 5 different Word window
    titles. So the human-readable `regulation_name_ja` is the identity that means something, and
    `document_id` says *which capture of it* the excerpt on screen was taken from. Both are shown.
    """

    regulation_name_ja: str
    clause_id: str
    clause_heading_ja: str
    document_id: str
    sibling_document_ids: List[str] = Field(default_factory=list)
    identity_note_en: str = ""


class ThresholdRuleRef(Frozen):
    """Which parsed `threshold` rule to evaluate, and which record field feeds it.

    The tiers themselves are not restated here. They are read from `documents.jsonl`, where the
    Step 2 extractor already parsed them, so a divergence between this file and the corpus is
    impossible by construction.
    """

    rule_id: str
    variable_ja: str = "金額"
    source_field_ja: str = "金額"


class RecordTypeRule(Frozen):
    """When a definition's governing document applies to a record.

    `field_ja` differs between queues that are otherwise alike: the HR settlement queue calls it
    `区分`, the managerial approval queue calls it `申請種別`. Both are the screen's own wording.
    """

    field_ja: str
    equals_ja: Optional[str] = None
    startswith_ja: Optional[str] = None

    def matches(self, fields: Dict[str, Optional[str]]) -> bool:
        value = fields.get(self.field_ja)
        if not value:
            return False
        if self.equals_ja is not None:
            return value == self.equals_ja
        if self.startswith_ja is not None:
            return value.startswith(self.startswith_ja)
        return False


class RequiredFields(Frozen):
    """Fields the screen must show before the rule can be evaluated at all.

    Absence here is `REQUIRES_REVIEW`, never a guess and never a default.
    """

    fields_ja: List[str] = Field(default_factory=list)
    reason_ja: str = ""


class JudgementOption(Frozen):
    """One disposition actually observed in the capture window, with its count.

    `observed_n` is shown in the panel. A disposition the UI offers but nobody ever chose has
    `observed_n = 0` and is rendered all the same — 差戻し is offered by the `la-note` placeholder
    and was chosen zero times in 282 uses, and that is a finding, not an omission.
    """

    text_ja: str
    observed_n: int
    offered_by_ja: str = ""


class CommentTemplate(Frozen):
    """The comment the operator types, reconstructed verbatim from telemetry.

    `template_ja` uses `{slot}` placeholders. Every slot but the judgement slot is filled from
    the record. The judgement slot is left empty by the engine and can only be filled by a human
    clicking a chip in the panel — see `comment.render`, which asserts this.
    """

    element_id: str
    placeholder_ja: str
    template_ja: str
    slots: Dict[str, str] = Field(default_factory=dict)
    judgement_slot: str
    judgement_options: List[JudgementOption] = Field(default_factory=list)
    observed_n: int = 0
    evidence_note_en: str = ""

    @field_validator("template_ja")
    @classmethod
    def _judgement_slot_present(cls, v: str) -> str:
        if "{" not in v:
            raise ValueError("template_ja has no slots; it would not be a template")
        return v

    def slot_names(self) -> Tuple[str, ...]:
        return tuple(re.findall(r"\{(\w+)\}", self.template_ja))


class HostRef(Frozen):
    """The real `(origin, route)` this queue is served from in Dataset B.

    Reproduced verbatim so the panel's host detection is the same lookup `analysis/evidence/
    modules.py` performs over the telemetry, rather than an invented routing scheme.
    """

    origin: str
    route: str
    production_url_ja: str = ""


class ModuleDefinition(Frozen):
    """One governed queue, end to end."""

    definition_id: str
    module_id: str
    system: str
    name_ja: str
    name_en: str
    host: HostRef
    record_prefix: str
    column_headers_ja: List[str]
    note_element_id: str
    submit_element_id: str
    success_toast_ja: str
    required: RequiredFields
    governed_by: Optional[RecordTypeRule] = None
    document: Optional[DocumentRef] = None
    threshold: Optional[ThresholdRuleRef] = None
    comment: CommentTemplate
    miss_reason_ja: str = ""
    miss_reason_en: str = ""

    @field_validator("column_headers_ja")
    @classmethod
    def _nonempty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("column_headers_ja must be the screen's verbatim headers")
        return v

    def governs(self, fields: Dict[str, Optional[str]]) -> bool:
        """True when this definition's document governs the given record's type."""
        return bool(self.governed_by and self.document and self.governed_by.matches(fields))
