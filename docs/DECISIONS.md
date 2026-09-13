# DECISIONS — Architecture Decision Records

Append-only. An ADR is required to change anything in `ARCHITECTURE.md` or a `*_SPEC.md`.

**Format:** ID · Date · Status (`accepted` | `superseded by ADR-NNN`) · Context · Decision ·
Consequences · Evidence.

---

### ADR-001 · 2026-09-11 · accepted · Chunks are dissolved during normalisation
**Context** `DATA_SCHEMA.md` §1: chunks are fixed recording-time buckets with no business
meaning; `correlation.sequence_number` restarts per chunk.
**Decision** `normalise.load_session` merges all chunks of a session and rebuilds global order
from `timestamp_ms`. A chunk boundary may never appear as a predicted boundary.
**Consequences** Baseline `B1-chunk` exists solely to demonstrate that chunks are meaningless.
**Evidence** Schema, explicit.

### ADR-002 · 2026-09-12 · accepted · Provenance/correlation fields are NOT an identity mechanism
**Context** An earlier design proposed connected components over `correlation.*` and
`extensions.dataflow_v2` as the backbone of execution identity.
**Decision** Rejected. `triggered_by` and `correlated_events` are excluded from identity
reasoning. `dataflow_v2` is retained only as a weak `shared_value_with` / `dataflow_to` edge.
**Consequences** Family D demoted from backbone to complementary feature. No `networkx`
connected-component logic anywhere on the critical path.
**Evidence** Measured on `dataset_b`: `triggered_by` has 4,760 links of which **4,759 have
child `event_type = screenshot_smart`** (capture plumbing). `correlated_events` is 96%
singletons pairing `browser_click`↔`mouse_click` and `text_input_complete`↔`keystroke`
(layer de-duplication). `cross_layer_v1` matches `dom_event_id`↔`uia_event_id`.
`dataflow_v2.source_event_id` is present on 870 of 20,477 events (4.2%) with
`raw_value_persisted: false`. Resulting graph: only **35** `dataflow_to` edges.

### ADR-003 · 2026-09-12 · accepted · Time gaps are a baseline and a weak feature, not a method
**Context** Measured on `dataset_b`: median inter-event gap 62 ms, p99 6 s, **one** gap > 30 s
in 20,477 events. `README.md` notes waiting time is compressed in the test environment.
**Decision** No gap-threshold segmenter is a candidate method. `B2-gap` is kept permanently as
a published baseline floor. Relative gap (gap ÷ session rolling median) remains a feature in
the ambiguity gate.
**Consequences** Prevents re-litigating this; the negative result is report content.
**Evidence** As above. Note this is a **Dataset B** observation; Phase 2 re-checks it on A.

### ADR-004 · 2026-09-12 · accepted · The activity block is the unit of reasoning
**Context** Reasoning per event (162k in A) or per raw state change (~59k in A) is
unaffordable and semantically meaningless.
**Decision** Deterministic perception compresses events into activity blocks; all downstream
reasoning, retrieval and explanation operate on blocks.
**Consequences** Makes an LLM affordable on the critical path. Block quality becomes a
first-class engineering concern (Phase 0 and Phase 2 both measure it).
**Evidence** 20,477 events → 7,408 state changes → 1,782 blocks on `dataset_b`.

### ADR-005 · 2026-09-12 · accepted · The TEKG is an evidence and explanation layer
**Context** See ADR-002.
**Decision** The graph builds local typed context for the reasoner and explains decisions
afterwards. Connected components are never interpreted as executions.
**Consequences** `evidence_used` is a required output field; the prototype's P3/P4 pages depend
on it.
**Evidence** `returns_to` (2,150) and `same_field_as` (940) are ~60× more abundant than
`dataflow_to` (35) — structural/temporal relations are the real evidence base.

### ADR-006 · 2026-09-12 · accepted · The LLM never controls temporal arithmetic
**Decision** The reasoner is shown relative seconds and local ids `b0…bN` only. It cannot emit
a timestamp, duration, interval or global index because it never receives one.
**Consequences** An entire class of LLM failure is structurally impossible. A test asserts no
payload leaks absolute values.
**Evidence** Design; enforced in `context.build_payload`.

### ADR-007 · 2026-09-12 · accepted · Rejected dependencies
**Decision** Not used: Neo4j / FalkorDB / any graph database; Raphtory; any vector database;
LangGraph / CrewAI / any agent framework; `stumpy`; `streamlit-gantt`; ScreenRPA (CC BY-NC —
disqualifying for client-facing work); OpenAdapt; SmartRPA; fine-tuning stacks; global OCR.
**Consequences** Storage is JSON + dicts; graphs use `networkx` only where an algorithm is
needed; the demo uses built-in `plotly.express.timeline`.
**Evidence** Data scale is ~20k events / ~1.8k blocks per dataset. These tools solve problems
we do not have, or solve the inverse problem (replay a known task rather than discover one).

### ADR-008 · 2026-09-12 · accepted · PM4Py only with step structure
**Context** One row per execution yields a one-activity process model — degenerate.
**Decision** `pm4py` is introduced only after step/task structure exists
(`case = execution`, `activity = step`), in Phase 5.
**Consequences** Step recovery becomes a real objective, validated against GT `task_started`.

### ADR-009 · 2026-09-12 · accepted · Vision is selective and tool-gated
**Decision** No global OCR/VLM pass. Screenshots are requested only by `look_at_screen` when
reasoner confidence is low, capped at ≤5% of routed transitions.
**Consequences** `extensions.ocr_v1` and `context.extracted_text` are not primary inputs.
**Evidence** `DATA_SCHEMA.md` §2 states OCR is unnecessary; on `dataset_b`
`extracted_text` covers 4.6% of events and is largely browser chrome.

### ADR-010 · 2026-09-12 · accepted · Nothing dataset-specific transfers from A to B
**Decision** Transferable: code, featurisation, the *rule* for estimating a parameter, the
evaluation harness, domain-neutral prompts. Not transferable: A's process names/codes,
vocabulary, keyword lists, cluster count `k`, memory records, few-shot examples.
**Consequences** `make run-b` must succeed with `dataset_a/` absent — a CI-enforced test.
**Evidence** `README.md`: B is from different departments, processes and applications.

### ADR-011 · 2026-09-13 · accepted · GT repair rules are frozen before any segmenter runs
**Context** `DATA_SCHEMA.md` §3 documents duplicate `process_started` and unpaired
`process_switched_out`, and instructs us to verify consistency ourselves.
**Decision** Repair rules are written and committed in Phase 1 **before** the first segmenter.
Tuning uses the `clean` tier only; headline uses `clean + repaired`; a sensitivity line uses
`all`. Both GT sources are retained on disagreement.
**Consequences** Prevents fitting the generator's defects; the disagreement rate becomes a
reported finding.
