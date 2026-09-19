"""Required-field checks. Pure; no I/O.

The screen's own column headers are the contract. A field the definition names as required and
the record does not carry is `REQUIRES_REVIEW` — never a default, never an inferred value.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .definitions import ModuleDefinition, Status
from .result import Check, Provenance


def check_required_fields(
    definition: ModuleDefinition,
    fields: Dict[str, Optional[str]],
    provenance: Optional[Provenance] = None,
) -> List[Check]:
    """One check per required field; `OK` when present and non-blank."""
    out: List[Check] = []
    for name in definition.required.fields_ja:
        value = fields.get(name)
        present = bool(value and str(value).strip())
        out.append(
            Check(
                check_id=f"required.{name}",
                kind="required_field",
                status=Status.OK if present else Status.REQUIRES_REVIEW,
                label_ja=f"必須項目：{name}",
                label_en=f"required field: {name}",
                expected_ja="入力あり",
                observed_ja=(str(value) if present else "（未入力）"),
                why_ja=(f"{name} は画面に表示されています。" if present
                        else f"{name} がこのレコードにありません。{definition.required.reason_ja}"),
                why_en=(f"{name} is present on the screen." if present
                        else f"{name} is absent from this record, so the queue's own contract "
                             f"is not satisfied."),
                provenance=provenance,
            )
        )
    return out
