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
from .adapters.evidence import retrieval_baselines
from .challenger import Challenger, hybrid_scores
from .core.definitions import ModuleDefinition
from .core.impact import action_budget, total_budget
from .core.engine import prepare
from .core.result import PrepareResult, Provenance
from .core.rules import SEMANTICS, format_amount_jpy, parse_amount_jpy
from .core.trace import Trace
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
        self._challenger: Optional[Challenger] = None

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
        tr = Trace()
        row = self.records.get(record_id)
        if row is None:
            raise KeyError(record_id)
        definition = self.defs.for_record(record_id)
        if definition is None:
            raise KeyError(f"no definition for {record_id!r}")
        tr.step("resolve definition", "定義の特定", "lookup",
                definition.definition_id,
                f"{definition.definition_id} — by record_prefix {definition.record_prefix}, "
                f"not by module_id (ADR-022)")
        tr.step("load record", "レコードの読み込み", "lookup", record_id,
                f"{record_id} — {row['n_captures']} capture(s)")

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
            tr.step("resolve governing doc", "規程の特定", "lookup",
                    f"{ref.regulation_name_ja}（module + record_type）",
                    f"{ref.regulation_name_ja} (lookup: module + record_type)",
                    link=f"/v1/source/{ref.document_id}/{ref.clause_id}")
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
                tr.step("localise clause", "条文の特定", "lookup",
                        f"{excerpt.get('heading_ja')}  clause_id {ref.clause_id}",
                        f"{excerpt.get('heading_ja')} · clause_id {ref.clause_id} · "
                        f"char_span {excerpt['char_span']}",
                        link=f"/v1/source/{ref.document_id}/{ref.clause_id}")
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
        self._trace_engine_steps(tr, definition, base, fields)
        result = base
        if log:
            suggested = result.status.value
            authority = next((c.expected_ja for c in result.checks
                              if c.kind == "threshold" and c.expected_ja), None)
            if authority:
                suggested = f"{result.status.value}:{authority}"
            row_written = self.audit.append(
                result.trace_id, "prepare",
                definition_id=definition.definition_id,
                module_id=definition.module_id,
                record_id=record_id,
                suggested=suggested,
                detail={"checks": [{"check_id": c.check_id, "status": c.status.value}
                                   for c in result.checks],
                        "draft_offered": result.draft is not None},
            )
            # The audit write is a real step with a real cost; it belongs in the trace.
            tr.step("append audit", "監査ログの追記", "audit",
                    f"seq {row_written['seq']} · row_hash {row_written['row_hash'][:8]}…",
                    f"seq {row_written['seq']} · row_hash {row_written['row_hash'][:8]}… "
                    f"(hash-chained to the previous row)")

        update: Dict[str, Any] = {
            "trace": tr.dump(),
            "actions_avoided": action_budget(definition, base.draft,
                                             self._lookup_count(base), self._measured),
        }
        if with_population:
            update["population"] = self._population(definition, base)
        return base.model_copy(update=update)

    @staticmethod
    def _trace_engine_steps(tr: Trace, definition: ModuleDefinition, base: PrepareResult,
                            fields: Dict[str, Optional[str]]) -> None:
        """Record the steps the engine took after the evidence was loaded."""
        threshold = next((c for c in base.checks if c.kind == "threshold"), None)
        miss = next((c for c in base.checks if c.kind == "lookup"), None)
        if threshold is not None:
            amount = parse_amount_jpy(fields.get(
                definition.threshold.source_field_ja if definition.threshold else "金額"))
            shown = format_amount_jpy(amount) if amount is not None else "（画面に項目なし）"
            tr.step("evaluate threshold", "金額の判定", "threshold",
                    f"金額 {shown} → {threshold.expected_ja}（{SEMANTICS}）",
                    f"金額 {shown} → {threshold.expected_ja} ({SEMANTICS})")
        elif miss is not None:
            tr.step("resolve governing doc", "規程の特定", "lookup",
                    f"MISS — {miss.observed_ja}",
                    f"MISS — no rule governs {miss.observed_ja}; no fallback attempted")

        required = [c for c in base.checks if c.kind == "required_field"]
        marks = "  ".join(f"{c.label_ja.split('：')[-1]} "
                          f"{'✓' if c.status.value == 'OK' else '✗'}" for c in required)
        tr.step("check required fields", "必須項目の確認", "required", marks, marks)

        if base.draft is not None:
            tr.step("render draft", "下書きの生成", "template",
                    f"template {definition.definition_id} · judgement EMPTY",
                    f"template {definition.definition_id} · judgement EMPTY")
        else:
            tr.step("render draft", "下書きの生成", "template",
                    "下書きなし（項目不足）", "no draft: a template slot is unfillable")

    # -- the challenger: the alternative, run where it can be seen to lose -------------------

    def challenge(self, record_id: str) -> Dict[str, Any]:
        """Run the local retriever beside the lookup, for the same record.

        Built lazily: 365 clauses index in a few milliseconds, but a demo that never opens the
        challenger should not pay for it.
        """
        if self._challenger is None:
            self._challenger = Challenger.from_documents(self.documents.rows)
        result = self.prepare_record(record_id, log=False, with_population=False)
        definition = self.defs.for_record(record_id)
        lookup = None
        if definition is not None and definition.document is not None and result.document:
            lookup = {
                "document_id": definition.document.document_id,
                "clause_id": definition.document.clause_id,
                "regulation_name_ja": definition.document.regulation_name_ja,
                "heading_ja": (result.clause or {}).get("heading_ja"),
                "text_ja": (result.clause or {}).get("text_ja"),
                "mechanism": "(module, record type) -> document",
            }
        # The query is what the screen actually shows, nothing engineered for the retriever.
        query = "　".join(str(v) for v in result.record_fields.values() if v)
        baselines = retrieval_baselines() or {}
        out = hybrid_scores(self._challenger, query, lookup, baselines.get("bar"))
        payload = out.as_dict()
        payload["record_id"] = record_id
        payload["status"] = result.status.value
        return payload

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
            budget = result.actions_avoided or action_budget(
                definition, result.draft, self._lookup_count(result), self._measured)
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
