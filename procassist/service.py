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
from .core.impact import action_budget, total_budget
from .core.engine import prepare
from .core.result import PrepareResult, Provenance
from .measured import measured_action_budget

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
        self._measured = measured_action_budget()

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

    # -- the whole queue at once -------------------------------------------------------------

    def prepare_queue(self, definition_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run the engine over every record on one queue.

        This is the operator's actual unit of pain — 120 records, each needing a Word round
        trip — and nothing in the single-record view shows it. The engine already did this
        internally to compute the population denominator; this only gives it a surface.

        Returns per-row what the queue table needs to resolve in place, plus the before/after
        totals. `dispositions_taken` is in the totals and is always 0: the agent does every
        part of the work except the part it is not allowed to do.
        """
        definition = self.defs.by_id[definition_id]
        rows = self.records.queue(definition.record_prefix, definition.column_headers_ja,
                                  limit=limit)
        batch_trace = new_trace_id()
        out_rows: List[Dict[str, Any]] = []
        budgets: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {"OK": 0, "FLAG": 0, "REQUIRES_REVIEW": 0, "MISS": 0}
        n_documents = 0
        n_drafts = 0

        for row in rows:
            result = self.prepare_record(row["record_id"], log=True, with_population=False)
            counts[result.status.value] = counts.get(result.status.value, 0) + 1
            if result.document:
                n_documents += 1
            if result.draft is not None:
                n_drafts += 1
            budget = action_budget(definition, result.draft, self._lookup_count(result),
                                   self._measured)
            budgets.append(budget)
            out_rows.append({
                "record_id": result.record_id,
                "status": result.status.value,
                "document_heading": ((result.document or {}).get("regulation_name_ja")
                                     if result.document else None),
                "clause_heading": ((result.clause or {}).get("heading_ja")
                                   if result.clause else None),
                "checks_summary": self._checks_summary(result),
                "expected_ja": next((c.expected_ja for c in result.checks
                                     if c.kind == "threshold"), None),
                "draft_ready": result.draft is not None,
                "draft_preview": result.draft.text_ja if result.draft else None,
                "trace_id": result.trace_id,
                "actions_avoided": budget,
            })

        totals = total_budget(budgets)
        summary = {
            "definition_id": definition_id,
            "module_id": definition.module_id,
            "module_name_ja": definition.name_ja,
            "module_name_en": definition.name_en,
            "batch_trace_id": batch_trace,
            "n_records": len(rows),
            "before": {"documents_resolved": 0, "drafts_staged": 0,
                       "actions_avoided": 0, "dispositions_taken": 0},
            "after": {"documents_resolved": n_documents, "drafts_staged": n_drafts,
                      "actions_avoided_range": totals["app_switches_range"],
                      "keystrokes_total": totals["keystrokes_total"],
                      "lookups_total": totals["lookups_total"],
                      "dispositions_taken": 0},
            "counts": counts,
            "caveat_en": self._measured.get("caveat_en", ""),
        }
        self.audit.append(
            batch_trace, "prepare_queue",
            definition_id=definition_id, module_id=definition.module_id,
            suggested=" · ".join(f"{k}:{v}" for k, v in counts.items() if v),
            detail={"n_records": len(rows), "drafts_staged": n_drafts,
                    "dispositions_taken": 0})
        return {"summary": summary, "rows": out_rows}

    @staticmethod
    def _checks_summary(result: PrepareResult) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for check in result.checks:
            out[check.status.value] = out.get(check.status.value, 0) + 1
        return out

    @staticmethod
    def _lookup_count(result: PrepareResult) -> int:
        """Fields + document + clause: what the panel put on one screen."""
        return len(result.record_fields) + (1 if result.document else 0) + \
            (1 if result.clause else 0)

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
