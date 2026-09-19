"""What ProcAssist hands back for one record. Pure data.

`PrepareResult` is the full contract between the engine and the panel. It carries a judgement
slot that is *always* empty, because the engine prepares and a human decides — the assertion is
in `comment.render` and again in `PrepareResult.model_post_init`, and there is a test for both.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from .definitions import Status


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Provenance(Frozen):
    """Where a statement came from, at capture granularity.

    Enough for the reader to open the source: which document capture, which clause, which
    character span of the captured body, which captures and sessions it was seen in, and what
    the Word title bar said at the time (which can disagree with the body — see ADR-025).
    """

    document_id: Optional[str] = None
    clause_id: Optional[str] = None
    clause_heading_ja: Optional[str] = None
    char_span: Optional[Tuple[int, int]] = None
    rule_id: Optional[str] = None
    capture_ids: List[str] = Field(default_factory=list)
    session_ids: List[str] = Field(default_factory=list)
    title_aliases: List[str] = Field(default_factory=list)
    sibling_document_ids: List[str] = Field(default_factory=list)
    evidence_type: str = "OBSERVED"


class Check(Frozen):
    """One deterministic test, with its reasoning shown rather than summarised.

    `expected` / `observed` / `why_ja` are separate fields on purpose: a reader who disagrees
    with the verdict should be able to see which of the three they disagree with.
    """

    check_id: str
    kind: str
    status: Status
    label_ja: str
    label_en: str
    expected_ja: Optional[str] = None
    observed_ja: Optional[str] = None
    why_ja: Optional[str] = None
    why_en: Optional[str] = None
    provenance: Optional[Provenance] = None


class DraftComment(Frozen):
    """A comment with the judgement removed, not merely defaulted.

    `text_ja` is the template with every record slot filled and the judgement slot left as the
    empty string. `judgement` is `None` and stays `None` on anything the engine produces.
    """

    element_id: str
    template_ja: str
    text_ja: str
    judgement_slot: str
    judgement: Optional[str] = None
    judgement_options: List[Dict[str, object]] = Field(default_factory=list)
    filled_slots: Dict[str, str] = Field(default_factory=dict)
    observed_n: int = 0
    evidence_note_en: str = ""


class PrepareResult(Frozen):
    """Everything the panel renders for one record."""

    trace_id: str
    definition_id: str
    module_id: str
    module_name_ja: str
    record_id: str
    record_fields: Dict[str, Optional[str]] = Field(default_factory=dict)
    status: Status
    document: Optional[Dict[str, object]] = None
    clause: Optional[Dict[str, object]] = None
    checks: List[Check] = Field(default_factory=list)
    draft: Optional[DraftComment] = None
    #: How many records on this same queue land in the same verdict, and out of how many. A
    #: single flagged record invites the reader to treat it as an anecdote; the denominator is
    #: what says whether it is one.
    population: Optional[Dict[str, object]] = None
    notes_en: List[str] = Field(default_factory=list)

    def model_post_init(self, _context: object) -> None:
        if self.draft is not None and self.draft.judgement is not None:
            raise ValueError(
                "PrepareResult.draft.judgement must be None: the engine never decides")


#: Ordering used to roll the individual checks up into the result's overall status.
#: `MISS` outranks `REQUIRES_REVIEW` because "no rule governs this" is a more fundamental
#: statement than "a rule governs this but an input is missing".
_SEVERITY: Dict[Status, int] = {
    Status.OK: 0,
    Status.REQUIRES_REVIEW: 2,
    Status.FLAG: 3,
    Status.MISS: 4,
}


def rollup(checks: List[Check]) -> Status:
    """The worst status among `checks`; `MISS` when there is nothing to check at all."""
    if not checks:
        return Status.MISS
    return max((c.status for c in checks), key=lambda s: _SEVERITY[s])
