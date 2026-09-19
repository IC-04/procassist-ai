"""(module, record type) -> governing document. Pure; no I/O.

The lookup is explicit in both directions. When no document governs a record type, the answer is
`MISS` carrying the reason — not the nearest document, not a ranked list, not a similarity
score. Dataset B contains exactly one parsed threshold rule and it governs 接待交際費 expense
records; an invoice amount is not governed by it, and saying so is the correct output.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .definitions import DocumentRef, ModuleDefinition, Status
from .result import Check, Provenance


class LookupResult:
    """Either a `DocumentRef` or an explained `MISS`. Deliberately not an `Optional`."""

    __slots__ = ("document", "status", "reason_ja", "reason_en")

    def __init__(self, document: Optional[DocumentRef], status: Status,
                 reason_ja: str = "", reason_en: str = "") -> None:
        self.document = document
        self.status = status
        self.reason_ja = reason_ja
        self.reason_en = reason_en

    @property
    def hit(self) -> bool:
        return self.document is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"LookupResult(status={self.status.value}, hit={self.hit})"


def find_document(definition: ModuleDefinition,
                  fields: Dict[str, Optional[str]]) -> LookupResult:
    """Resolve the governing document for one record, or explain why there is none."""
    if definition.governs(fields):
        return LookupResult(definition.document, Status.OK)
    return LookupResult(
        None,
        Status.MISS,
        definition.miss_reason_ja or "このレコード種別を規定する規程は確認されていません。",
        definition.miss_reason_en or ("no governing rule has been established for this record "
                                      "type in the captured corpus"),
    )


def miss_check(definition: ModuleDefinition, lookup: LookupResult,
               fields: Dict[str, Optional[str]]) -> Check:
    """The single check that stands in for a whole evaluation that could not be attempted."""
    observed = None
    if definition.governed_by:
        observed = fields.get(definition.governed_by.field_ja) or "（区分なし）"
    return Check(
        check_id="lookup.governing_document",
        kind="lookup",
        status=Status.MISS,
        label_ja="規程の特定",
        label_en="governing document",
        expected_ja="該当する規程",
        observed_ja=observed,
        why_ja=lookup.reason_ja,
        why_en=lookup.reason_en,
        provenance=Provenance(evidence_type="OBSERVED"),
    )


def governing_checks(definition: ModuleDefinition,
                     fields: Dict[str, Optional[str]]) -> List[Check]:
    """`[]` when a document governs the record, one `MISS` check when none does."""
    lookup = find_document(definition, fields)
    return [] if lookup.hit else [miss_check(definition, lookup, fields)]
