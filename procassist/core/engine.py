"""Assemble one `PrepareResult`. Pure; no I/O — the caller supplies the loaded evidence.

Order matters and is the whole logic of the thing:

1. Does a document govern this record type? If not, stop at `MISS`. We do not fall back to a
   nearest document, because a wrong regulation cited confidently is worse than none.
2. Does the screen carry the fields the rule needs? If not, `REQUIRES_REVIEW`.
3. Evaluate the clause.
4. Render the operator's comment with the judgement left empty.

The draft is offered whatever the status, including `MISS`. The comment template and the
authority rule are independently evidenced — the invoice template was typed 129 times on
`:5133/#/payroll-items` whether or not any regulation governs an invoice amount — so
withholding the comment because the rule lookup missed would suppress evidence we have in
order to express a gap in evidence we do not. What the engine withholds, always, is the
judgement.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .comment import render
from .completeness import check_required_fields
from .definitions import ModuleDefinition, Status
from .lookup import find_document
from .lookup import miss_check
from .result import Check, PrepareResult, Provenance, rollup
from .rules import evaluate_threshold


def prepare(
    definition: ModuleDefinition,
    record_id: str,
    fields: Dict[str, Optional[str]],
    clause: Optional[Dict[str, Any]] = None,
    parsed_rule: Optional[Dict[str, Any]] = None,
    provenance: Optional[Provenance] = None,
    document_meta: Optional[Dict[str, Any]] = None,
    trace_id: str = "",
) -> PrepareResult:
    """Run the four steps above for one record."""
    checks: list[Check] = list(check_required_fields(definition, fields, provenance))
    notes: list[str] = []

    lookup = find_document(definition, fields)
    if lookup.hit:
        if definition.threshold is not None:
            checks.append(evaluate_threshold(definition, fields, parsed_rule,
                                             provenance or Provenance()))
    else:
        checks.append(miss_check(definition, lookup, fields))
        notes.append(lookup.reason_en)
        clause = None
        document_meta = None
        parsed_rule = None

    draft = render(definition, fields)
    if draft is None:
        notes.append("the observed comment template could not be rendered from this record's "
                     "fields, so no draft is offered")

    return PrepareResult(
        trace_id=trace_id,
        definition_id=definition.definition_id,
        module_id=definition.module_id,
        module_name_ja=definition.name_ja,
        record_id=record_id,
        record_fields=dict(fields),
        status=rollup(checks),
        document=document_meta,
        clause=clause,
        checks=checks,
        draft=draft,
        notes_en=notes,
    )
