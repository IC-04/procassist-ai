"""The one place where the pure core meets the loaded evidence.

`prepare_record` is what `POST /v1/prepare` calls and what the tests call, so the HTTP layer
adds nothing to the reasoning and cannot quietly diverge from it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .adapters.audit import AuditLog, new_trace_id
from .adapters.defs import DefinitionRegistry, registry
from .adapters.documents import DocumentIndex, index
from .adapters.records import RecordStore, store
from .core.definitions import ModuleDefinition
from .core.engine import prepare
from .core.result import PrepareResult, Provenance

#: Widened context shown under `View source`, in characters either side of the clause.
SOURCE_CONTEXT_CHARS = 160


class Service:
    """Definitions + records + documents + audit, assembled once and reused."""

    def __init__(
        self,
        defs: Optional[DefinitionRegistry] = None,
        records: Optional[RecordStore] = None,
        documents: Optional[DocumentIndex] = None,
        audit: Optional[AuditLog] = None,
    ) -> None:
        self.defs = defs or registry()
        self.records = records or store()
        self.documents = documents or index()
        self.audit = audit if audit is not None else AuditLog()
        self._population_cache: Dict[Any, Dict[str, Any]] = {}

    # -- queues ------------------------------------------------------------------------------

    def definitions(self) -> List[ModuleDefinition]:
        return self.defs.all

    def queue(self, definition_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        d = self.defs.by_id[definition_id]
        return self.records.queue(d.record_prefix, d.column_headers_ja, limit=limit)

    def record(self, record_id: str) -> Optional[Dict[str, Any]]:
        return self.records.get(record_id)

    def definition_for_record(self, record_id: str) -> Optional[ModuleDefinition]:
        return self.defs.for_record(record_id)

    # -- the engine --------------------------------------------------------------------------

    def prepare_record(self, record_id: str, trace_id: str = "", log: bool = True,
                       with_population: bool = True) -> PrepareResult:
        """Look the record up, load its clause, run the engine, record the suggestion."""
        row = self.records.get(record_id)
        if row is None:
            raise KeyError(record_id)
        definition = self.defs.for_record(record_id)
        if definition is None:
            raise KeyError(f"no definition for {record_id!r}")

        fields = row["fields"]
        clause = None
        document_meta = None
        parsed = None
        provenance = Provenance(evidence_type="OBSERVED")

        if definition.document is not None:
            ref = definition.document
            excerpt = self.documents.excerpt(ref.document_id, ref.clause_id,
                                             SOURCE_CONTEXT_CHARS)
            rule = (self.documents.rule(definition.threshold.rule_id)
                    if definition.threshold else None)
            parsed = (rule or {}).get("parsed")
            siblings = (self.documents.siblings_by_rule_text(rule["raw_text_ja"])
                        if rule else [])
            if excerpt is not None:
                clause = excerpt
                document_meta = {
                    "regulation_name_ja": ref.regulation_name_ja,
                    "document_id": ref.document_id,
                    "clause_heading_ja": excerpt.get("heading_ja") or ref.clause_heading_ja,
                    "title_aliases": excerpt["title_aliases"],
                    "capture_ids": excerpt["capture_ids"],
                    "session_ids": excerpt["session_ids"],
                    "n_captures": excerpt["n_captures"],
                    "sibling_document_ids": siblings,
                    "identity_note_en": ref.identity_note_en,
                    "raw_rule_text_ja": (rule or {}).get("raw_text_ja"),
                }
                provenance = Provenance(
                    document_id=ref.document_id,
                    clause_id=ref.clause_id,
                    clause_heading_ja=excerpt.get("heading_ja") or ref.clause_heading_ja,
                    char_span=tuple(excerpt["char_span"]),
                    rule_id=definition.threshold.rule_id if definition.threshold else None,
                    capture_ids=excerpt["capture_ids"],
                    session_ids=excerpt["session_ids"],
                    title_aliases=excerpt["title_aliases"],
                    sibling_document_ids=siblings,
                    evidence_type=(rule or {}).get("evidence_type", "OBSERVED"),
                )

        base = prepare(
            definition=definition,
            record_id=record_id,
            fields=fields,
            clause=clause,
            parsed_rule=parsed,
            provenance=provenance,
            document_meta=document_meta,
            trace_id=trace_id or new_trace_id(),
        )
        result = (base.model_copy(update={"population": self._population(definition, base)})
                  if with_population else base)
        if log:
            suggested = result.status.value
            authority = next((c.expected_ja for c in result.checks
                              if c.kind == "threshold" and c.expected_ja), None)
            if authority:
                suggested = f"{result.status.value}:{authority}"
            self.audit.append(
                result.trace_id, "prepare",
                definition_id=definition.definition_id,
                module_id=definition.module_id,
                record_id=record_id,
                suggested=suggested,
                detail={"checks": [{"check_id": c.check_id, "status": c.status.value}
                                   for c in result.checks],
                        "draft_offered": result.draft is not None},
            )
        return result

    # -- how common is this verdict on this queue? -------------------------------------------

    def _population(self, definition: ModuleDefinition,
                    result: PrepareResult) -> Optional[Dict[str, Any]]:
        """Re-run the engine over the whole queue and count how many share this verdict.

        A single FLAG reads as an anecdote until you know the denominator. This is the
        denominator, measured rather than asserted: the same deterministic engine, every
        record on the queue, no sampling. 120 records is small enough to do on each request
        and the result is cached per (definition, status).
        """
        key = (definition.definition_id, result.status.value)
        cached = self._population_cache.get(key)
        if cached is not None:
            return cached
        rows = self.records.queue(definition.record_prefix, definition.column_headers_ja)
        same = 0
        governed = 0
        for row in rows:
            try:
                other = self.prepare_record(row["record_id"], log=False, with_population=False)
            except KeyError:                      # pragma: no cover - defensive
                continue
            if definition.governs(row["fields"]):
                governed += 1
            if other.status == result.status:
                same += 1
        out: Dict[str, Any] = {
            "status": result.status.value,
            "n_same_status": same,
            "n_queue": len(rows),
            "n_governed": governed,
            "label_en": f"{same} of {len(rows)} records on this queue reach {result.status.value}",
        }
        self._population_cache[key] = out
        return out
