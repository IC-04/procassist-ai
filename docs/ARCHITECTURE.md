# Architecture — Submission-Ready Edition

**Document:** `ARCHITECTURE.md`  
**Document type:** System architecture / governing design record  
**Status:** **CLOSED**  
**Change authority:** Changes to this document require an ADR in `DECISIONS.md`.  
**Submission purpose:** Preserve the project’s governing architecture, responsibility boundaries, approved dependencies, and known risks, while making the document suitable for formal review.

> **Supersession status:** This architecture is partially superseded in the specific areas identified below. The supersession is preserved as part of the architectural record rather than silently rewritten.

## Submission Note

This edition preserves the substantive architecture and its recorded status. It does not silently reconcile older architectural stages with later ADRs or Step 1 specifications. In particular:

- The original pipeline and decoder sections remain visible as historical architectural decisions, with their current supersession explicitly identified.
- Step 1 is governed by the later `STEP1_SPEC.md` requirements and the corresponding ADRs.
- Stages 7–10 of the original pipeline remain **Step 2 / Step 3 scope and deferred**.
- The deterministic-versus-LLM responsibility boundary, approved dependency decisions, and known risks remain part of the architecture.
- No metrics, claims, dependencies, risks, or implementation constraints have been removed merely for presentation.

## Reviewer Navigation

1. **Problem definition** — what the system is intended to recover and how it is evaluated.
2. **Original pipeline** — the ten-stage architecture and its current supersession status.
3. **Division of responsibility** — what deterministic code controls versus what the LLM may produce.
4. **Decoder / safety mechanism** — the original global-consistency mechanism and its architectural rationale.
5. **Approved dependencies** — accepted and rejected technology choices.
6. **Known risks** — risks carried into implementation and their planned detection/fallbacks.

## Submission Integrity

- **Architectural authority is explicit:** this document is closed and changes require an ADR.
- **Superseded material is retained:** historical stages are not presented as currently authoritative where later specifications replaced them.
- **Scope boundaries are preserved:** deferred Step 2 / Step 3 work is not represented as completed.
- **Responsibility boundaries remain explicit:** structural validity and numerical quantities are not delegated to the LLM.
- **Negative/fallback paths remain visible:** the deterministic baseline and `--no-llm` execution mode are preserved.
- **Dependency decisions remain auditable:** both reused and rejected dependencies are retained.
- **Risk ownership remains visible:** each listed risk retains its detection and fallback path.

---

## 1. The problem, stated precisely

Given a chronological stream of low-level desktop events with no process labels, no case
identifiers and no task boundaries, recover **executions of business processes**, label
repeated executions of the same process consistently, and use the result to rank automation
opportunities and demonstrate a prototype.

Two things are scored (`README.md`, *Deliverables*): whether **boundaries between units of
work are correct**, and whether **the same process consistently receives the same label**.
Label *text* is not scored. They are measured separately and never reported as one number.

## 2. Why this architecture

The hard problem is not "where does the application change" — that is string comparison.
It is: *what business execution best explains this interleaved sequence of heterogeneous
interactions, including interruptions, switches and resumptions?* That is contextual
reasoning over structured evidence, so an LLM sits on the critical path — but bounded by a
deterministic perception layer in front of it and a deterministic decoder behind it.

Measured on `dataset_b` (see `PHASE_0_REPORT.md` once produced):
20,477 events → 7,408 raw context-state changes → **1,782 activity blocks**. The reasoning
unit is the block, not the event and not the raw state change. This is what makes an LLM
affordable on the critical path.

## 3. Pipeline

| # | Stage | Nature | Module | Contract |
|---|---|---|---|---|
| 1 | Perception / normalisation | deterministic | `procmine/normalise.py` | chunks dissolved, global ordering by `timestamp_ms`, every optional field absent-tolerant |
| 2 | Activity blocks | deterministic | `procmine/blocks.py` | maximal same-surface runs, micro-excursions absorbed |
| 3 | TEKG | deterministic | `procmine/tekg.py` | 8 typed edge classes, locality-bounded |
| 4 | Ambiguity gate | deterministic | `procmine/gate.py` | routes only the uncertain tail to stage 5 |
| 5 | Execution reasoner | **LLM** | `procmine/reasoner.py` | structured output, cites evidence, may abstain |
| 6 | Constrained decoder | deterministic | `procmine/decoder.py` | global consistency under hard constraints |
| 7 | Family / variant | statistical (+LLM naming) | `procmine/families.py` | clustering decides membership; LLM only names |
| 8 | Automation scoring | deterministic (+LLM rationale) | `procmine/automation.py` | every number traceable to a measurement |
| 9 | SOP / workflow | **LLM** | `procmine/sop.py` | grounded in the reconstructed step sequence |
| 10 | Prototype | — | `app/` | Streamlit; see `PROTOTYPE_SPEC.md` |

## 4. Division of responsibility

**The LLM may produce:** types, relationship judgements, names, descriptions, prose,
generated procedures.

**The LLM may never produce:** timestamps, durations, intervals, absolute indices, counts,
metrics, or anything that determines structural validity. This is enforced in `context.py`
by never *showing* it those quantities — the model sees relative seconds and local ids
`b0…bN` only, so it is structurally incapable of emitting them.

**Deterministic and non-negotiable:** normalisation, chunk dissolution, block construction,
TEKG construction, all time and interval arithmetic, the ambiguity gate, the decoder, every
metric, `segments.jsonl` emission, all Step-2 aggregation.

## 5. The decoder is the safety mechanism

The reasoner emits *local* judgements. The decoder makes them *globally* consistent under
hard constraints (`DATA_CONTRACT.md` §6): monotone time, no zero-length executions, no
execution below the observed duration floor, `RESUMPTION` must reference a genuinely open
earlier execution, and a cap on how far a boundary may move from its deterministic
candidate. `UNCERTAIN` and low-confidence outputs fall back to the deterministic rule.

Consequence: **a total LLM failure degrades the system to its deterministic baseline rather
than breaking it.** `--no-llm` must remain a supported, tested execution mode.

## 6. Approved dependencies

| Package | Purpose | Decision |
|---|---|---|
| `pandas`, `numpy` | tabular work | REUSE |
| `networkx` | graph algorithms where needed (storage stays plain dicts) | REUSE |
| `pydantic` + `instructor` | structured LLM output with enum constraints and retries | REUSE |
| `scikit-learn` | clustering, ARI/NMI, bootstrap stability | REUSE |
| `rapidfuzz` | sequence distance | REUSE |
| `segeval` | Pk, WindowDiff, boundary similarity | REUSE |
| `sentence-transformers` | execution-memory embeddings | REUSE (Phase 5) |
| `ruptures` | change-point baseline / fallback segmenter | REUSE (Phase 2, conditional) |
| `pm4py` | step-level process maps and variant analysis | REUSE (Phase 5, conditional on step structure) |
| `prefixspan` | sequential pattern mining for variants | REUSE (Phase 5, optional) |
| `streamlit`, `plotly` | prototype | REUSE (Phase 6) |
| `pytest` | tests | REUSE |

**Rejected** (ADR-007): Neo4j/FalkorDB, Raphtory, any vector DB, LangGraph/CrewAI or any agent
framework, `stumpy`, `streamlit-gantt`, ScreenRPA, OpenAdapt, SmartRPA, fine-tuning stacks,
global OCR pipelines.

## 7. Known risks carried into implementation

| ID | Risk | Detection | Fallback |
|---|---|---|---|
| R1 | Dataset A window titles are generic, so surface keys carry little signal | Phase 2, `E0` block-quality comparison A vs B | promote `ruptures` change-point segmenter; increase reasoner routing |
| R2 | `extensions.*` fields absent or different in A | Phase 1 ingestion | all consumers already optional; features degrade, nothing breaks |
| R3 | Reasoner does not beat the deterministic rule | Phase 3 `E1` | ship deterministic reconstruction; AI stays at naming, SOP, automation rationale |
| R4 | GT canonicalisation over-runs | Phase 1 | sample 5 sessions; expand only when stable |
| R5 | Time spent on boundaries crowds out Steps 2–3 | Phase 4 gate | ship `segments.jsonl` for B early and imperfect, then refine |
