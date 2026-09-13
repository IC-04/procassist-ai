# AI-Native Architecture — Decision Record
## Position revised. Perception layer built and running. Next task specified.

**Date:** 2026-09-12 · **Status:** design closed, implementation started
**Code written and executed during this session:** `procmine/{normalise,blocks,tekg,context,cli}.py` — run against Dataset B, results below.

---

## A. Revised position: yes, AI belongs in the core

I was too conservative, and I can now say precisely why — it was a unit-of-analysis error, not a values disagreement.

My cost argument was "~59,000 candidate boundaries in Dataset A, so an LLM per decision is a bill, not an architecture." That is true **and irrelevant**, because the boundary is the wrong unit. After deterministic perception the real unit is the **activity block**, and I measured it:

| | Before | After perception layer |
|---|---|---|
| Dataset B events | 20,477 | — |
| Raw context-state changes | **7,408** | — |
| **Semantic activity blocks** | — | **1,782** |
| Blocks per session | 464 (raw states) | **119** |
| Compression | — | **11.5 events/block; 4.2× fewer units than raw state changes** |

So the reasoning task is not "classify 59,000 boundaries." It is "explain ~119 blocks per session" — and only the *ambiguous* transitions need a model at all. That is a few hundred calls per dataset, not tens of thousands. The cost objection dissolves once the representation is right, and building the representation is what I should have done before arguing about cost.

The second thing that changed my mind is what the graph actually contains. I built it and counted the edges:

```
same_surface_as   2150      returns_to        2150      same_field_as      940
same_system_as     235      same_route_as      182      shared_value_with   74
dataflow_to         35
```

**`returns_to` and `same_field_as` are 60× more abundant than `dataflow_to`.** The evidence base for contextual reasoning is *structural and temporal*, not provenance — which both vindicates the earlier demotion of provenance and shows there is a genuinely rich, typed evidence signal to reason over. A flat event sequence hides all of it.

And here is the decisive artifact. This is a real payload the reasoner would see, from `ses_…164424`, verbatim from the build:

```
b2  Excel   expense_calc        8.1s  36 events  typed
b3  Edge    財務会計システム /payroll-items  7.7s  22 events  typed, 1 form input, 1 clipboard
                                  ui_label: "処理内容・確認コメントを入力してください…"
b6  Excel   expense_calc        9.4s  36 events  typed
b7  Edge    財務会計システム /payroll-items  3.5s  10 events  typed
b8  Word    getsujitsu_teigaku_torihikisaki_ichiran   4.4s   (glance)
b9  Edge    財務会計システム /payroll-items  7.0s  13 events  1 form input, 1 clipboard

relations: b2 –returns_to→ b6 (lag 4), b2 –same_field_as→ b6
           b3 –returns_to→ b7 (lag 4), b3 –same_field_as→ b7
           b3 –returns_to→ b9 (lag 6), b3 –same_field_as→ b9
```

That is *literally* the scenario you described in your message: calculate in Excel → paste into the business system → consult the procedure document → continue. **A deterministic rule sees an application switch. The reasoner sees a worker mid-task.** Deciding whether `b8` (a Word procedure reference) is an INTERRUPTION inside one execution, or a PROCESS_SWITCH, is a semantic judgement over typed evidence. That is real AI work, on the critical path, and it is defensible.

**Revised position:** AI is the reconstruction layer. Determinism is perception, arithmetic and validation.

---

## B. The architecture — one, not fifteen

**Neuro-symbolic execution reconstruction with a constrained decoder.**

```
  raw telemetry
        │  ① PERCEPTION            deterministic   ✅ BUILT
        ▼     normalise · dissolve chunks · surface keys · block builder
  semantic activity blocks                          1,782 for B
        │  ② TEKG                  deterministic   ✅ BUILT
        ▼     8 typed edge classes, locality-bounded (max_lag=12)
  temporal execution knowledge graph                5,768 edges for B
        │  ③ AMBIGUITY GATE        deterministic   ← NEXT
        ▼     confident transitions decided by rule; rest routed to ④
  ambiguous transitions only                        target: 10–20% of blocks
        │  ④ EXECUTION REASONER    LLM + tools     ← the AI core
        ▼     stateful window walk · structured output · evidence cited
  per-transition decisions + confidence + evidence
        │  ⑤ CONSTRAINT DECODER    deterministic
        ▼     Viterbi-style global decode under hard constraints
  executions  ──►  segments.jsonl
        │  ⑥ FAMILY / VARIANT      embedding + clustering, LLM names
        ▼  ⑦ AUTOMATION SCORING    deterministic metrics, LLM rationale
        ▼  ⑧ SOP / WORKFLOW GEN    LLM, grounded in step sequences
  ⑨ STREAMLIT DEMO                 timeline · graph · evidence · SOP
```

Four LLM touchpoints (④⑥⑧ plus rationale in ⑦). One model. Three tools. No agent framework, no orchestration graph, no multi-agent theatre.

**Why the decoder matters more than the model.** The LLM emits *local* judgements. The decoder turns them into a *globally consistent* segmentation under hard constraints: monotone time, no zero-length executions, no execution shorter than the observed floor, `RESUMPTION` must reference a real earlier open execution, and a cap on how far the model may move a boundary from its deterministic candidate. Low-confidence and `UNCERTAIN` outputs fall back to the deterministic rule. **This is the design that makes an LLM safe on the critical path**, and it is the part an interviewer will recognise as engineering rather than prompting.

---

## C. Is the TEKG genuinely useful? Yes — and its purpose is specific

Not as an inference engine. Connected components are not executions; that was tested and rejected. Its two real jobs:

1. **Context construction for the reasoner.** The graph is what turns "block 8 is a Word document" into "block 8 sits between two blocks that share a form field and return to the same route" — evidence the model can reason over. Measured: a window of 11 blocks carries ~19 typed relations.
2. **Explanation.** The demo's "why did the system think these belong together?" is answered by *showing the edges the model cited*. `evidence_used` in the response schema is a required field, so every decision is traceable to named relations.

**Contents (built, running):**

*Nodes:* Block (primary), Surface, Field (`extensions.field_identity_v1.stable_key`), Session, Operator (`source.username_hash`), plus Execution once reconstructed.

*Typed edges:* `temporal_next` (with gap) · `same_surface_as` · `returns_to` (the A…X…A pattern — the interruption signature) · `same_route_as` · `same_system_as` · `same_field_as` · `shared_value_with` (dataflow value hashes) · `dataflow_to` (explicit lineage).

*Hub control:* every non-adjacent edge is bounded by `max_lag=12` blocks. A relation between blocks 200 apart is coincidence, not evidence. This is the pruning the earlier review demanded, enforced in code rather than asserted.

---

## D. The LLM's role, precisely

**Primary — Execution Reasoner (④).** Input: a TEKG window payload. Output: strict JSON — `decision ∈ {SAME_EXECUTION, INTERRUPTION, RESUMPTION, PROCESS_SWITCH, NEW_EXECUTION, UNCERTAIN}`, `confidence`, `resumes`, `evidence_used[]`, `rationale ≤200 chars`.

**Three hard rules, enforced in `context.py`, not in the prompt:**
- The model never sees an absolute timestamp — only seconds relative to window start.
- The model never sees a global index — only local ids `b0…bN`.
- It therefore **cannot** emit a time, an index or an interval. The entire class of LLM temporal-arithmetic errors is structurally impossible.

**Secondary:** family/variant naming (⑥ — C4 says label *text* is unscored, so zero risk), automation rationale (⑦), SOP and workflow generation (⑧).

---

## E. Retrieval, agentic behaviour, vision

**Retrieval — yes, and it is cheap.** Once executions exist, build an execution memory keyed on a *structural signature* (ordered surface-type sequence + fields + apps). Embed with `sentence-transformers`, nearest-neighbour with `sklearn`. Two uses: (a) retrieve 2–3 resolved similar cases as few-shot examples in the reasoner prompt — case-based reasoning, and it genuinely helps on repeated executions; (b) family assignment by nearest-neighbour instead of blind clustering. **Leakage rule: B's memory is built from B.** Hundreds of items — no vector DB, no FAISS.

**Agentic — minimal and justified.** One reasoner, three tools, invoked *only* when first-pass confidence is below threshold:
- `expand_window(n)` — more temporal context
- `similar_executions(signature)` — retrieval
- `look_at_screen(block_id)` — selective vision

Iterative evidence gathering when the model is unsure is real agentic value. Five agents with job titles is not. **Cap: 2 tool calls per transition.**

**Vision — selective, tool-gated, budget-capped.** Not an OCR pass. The reasoner requests a screenshot only when structured evidence is insufficient; B has 4,746 images already on disk, resolved via `payload.file_reference`. If under ~5% of transitions request it, the branch is cheap; if the model requests it constantly, that itself is a finding about representation quality.

---

## F. The smallest experiment — run it today

**Blocked on one thing: `dataset_a` is still not on disk.** Everything below needs ground truth. Get it first; the experiment is half a day after that.

**E1 · Reasoner value on stratified transitions (~150 calls, ~3 h).**
Sample 150 block transitions from ~6 sessions of A, stratified into five buckets: *easy* (same surface, no excursion), *ambiguous* (surface change with `returns_to` present), *interruption* (short excursion between same-surface blocks), *cross-application*, *resumption* (gap > lag 4 with `same_field_as`). Ground truth from canonicalised GT. Compare three arms on each bucket: deterministic rule → LLM-without-graph-evidence (blocks only) → LLM-with-graph-evidence.

That middle arm is the control that matters. **It isolates whether the TEKG earns its place, separately from whether the LLM does.**

*Continue if:* the LLM-with-evidence arm beats the deterministic rule on the *ambiguous + interruption + resumption* buckets, with ≥95% run-to-run stability at temperature 0.
*Simplify if:* it only matches the rule — then keep AI at naming, SOP and automation reasoning, and ship the deterministic reconstructor.

**E0 · Perception sanity on A (1 h, no LLM).** Run the built pipeline on A, compare blocks-per-session and events-per-block against B. If A's window titles are generic (risk R1), block quality collapses and we learn it immediately.

---

## G. The Day 5/6 demo

A Streamlit app — *not* a notebook — over the reconstructed output:

1. **Session timeline** (`plotly.express.timeline`): executions as bars, colour = process family, hatch = interrupted.
2. **Click an execution** → its blocks, the TEKG neighbourhood, and **the evidence the reasoner cited**, with its confidence and rationale.
3. **Process family view**: frequency, effort share, operators, variant breakdown, typical step sequence.
4. **Automation panel**: score, the measured components behind it, and — generated live — the **SOP with `REQUIRES_HUMAN` markers** plus a workflow-skeleton JSON.

The line that sells it: *"click any execution and the system shows you which relationships convinced it."* That is explainable AI on real telemetry, and it is achievable because `evidence_used` is a required schema field from the start.

---

## H. What stays deterministic — non-negotiable

Normalisation and chunk dissolution · block construction · TEKG construction · **all time and interval arithmetic** · the ambiguity gate · the constraint decoder · every metric · `segments.jsonl` emission · all Step-2 aggregation. If any of these depended on a model, the system would be unreproducible and the evaluation meaningless.

---

## I. What we will NOT build

Multi-agent orchestration · LangGraph/CrewAI state machines · a graph database (Neo4j, FalkorDB) · **Raphtory** (a Rust temporal-graph engine — overkill at 20k events; `networkx` and plain dicts win) · a vector DB service · fine-tuning · custom embedding training · a full OCR pass · real automation against a mock target we build ourselves · `streamlit-gantt` (fragile third-party component; `plotly.express.timeline` is built in) · `stumpy` (matrix profile is for continuous signals; our alphabet is categorical).

---

## Build / Reuse / Adapt

| Component | Tool | Decision | Why | Effort | Priority |
|---|---|---|---|---|---|
| Normalisation, blocks | — | **BUILD** ✅ done | Telemetry-specific; no library fits | done | **P0** |
| TEKG | `networkx` (+ plain dicts) | **BUILD on primitives** ✅ done | Typing is ours; storage is trivial | done | **P0** |
| Reasoner context builder | — | **BUILD** ✅ done | The prompt interface is the product | done | **P0** |
| Structured LLM output | **`instructor`** + pydantic | **REUSE** | Enum-constrained, retries, provider-agnostic; most established of the current options | 1 h | **P0** |
| Ambiguity gate | — | **BUILD** | Domain-specific scoring | 3 h | **P0** |
| Constraint decoder | — | **BUILD** | Small Viterbi-style pass; no library | 4 h | **P0** |
| Segmentation metrics | **`segeval`** + ours | **REUSE** | Pk, WindowDiff, boundary similarity — do not reimplement | 2 h | **P0** |
| GT canonicalisation | — | **BUILD** | Assignment-specific; mandated by schema §3 | 1 d | **P0** |
| Clustering, ARI/NMI, bootstrap stability | **`scikit-learn`** | **REUSE** | Obvious | 2 h | **P1** |
| Sequence distance | **`rapidfuzz`** | **REUSE** | Fast; trivially replaceable | 1 h | **P1** |
| Retrieval / memory | **`sentence-transformers` + sklearn NN** | **REUSE** | Hundreds of items — no vector DB | 3 h | **P1** |
| Step-level process maps, variant analysis | **`pm4py`** | **REUSE** | Meaningful *only* with step structure (`case`=execution, `activity`=step) | 3 h | **P1** |
| Change-point baseline | **`ruptures`** | **REUSE** | Insurance if A's titles are generic | 2 h | **P1** |
| Demo UI | **Streamlit + Plotly** | **REUSE** | Fastest path to a clickable demo | 1 d | **P1** |
| Vision on ambiguous cases | provider VLM API | **ADAPT** | Tool-gated, capped | 3 h | **P2** |
| Sequential pattern mining | `prefixspan` | **REUSE** | Variant/procedure extraction | 3 h | **P2** |
| Agent framework | — | **REMOVE** | One reasoner + 3 tools needs no framework | — | **DROP** |
| Graph DB, Raphtory, vector DB, stumpy | — | **REMOVE** | Complexity without ROI at this scale | — | **DROP** |

---

## J. The exact first coding task — started, and what comes next

**Already built and verified this session** (in `procmine/`, run against Dataset B):

- `normalise.py` — chunk-dissolving flattener; every `context.*` and `extensions.*` field optional; title normalisation and SPA-route extraction unit-tested.
- `blocks.py` — surface keys + block builder with micro-excursion absorption. **Measured: 7,408 raw state changes → 1,782 blocks, 2,771 excursions absorbed.**
- `tekg.py` — 8 typed edge classes, locality-bounded. **5,768 edges on B.**
- `context.py` — payload builder + system prompt + JSON response schema, with the no-timestamps/no-indices guarantee enforced in code.
- `cli.py` — `python3 -m procmine.cli --dataset dataset_b` → `build/dataset_b/{blocks.jsonl, summary.json, windows/**}`.

**Your next three tasks, in order:**

**1. Get `dataset_a` onto disk.** Still the critical-path blocker. Everything with a number attached needs it.

**2. Fix the block builder's degenerate tail (≈2 h).** The build exposed a real defect: many 1-event, 0-second blocks survive (`b0`, `b1`, `b4`, `b5` in the sample above), and 63 blocks have an empty surface key. Raise `min_events`/`min_ms`, absorb zero-duration blocks into their successor, and route empty-surface blocks to the previous block. Target: median events/block from 4 up to ~8–10, and blocks/session from 119 down toward 60–80. **Measure before and after — this is a reportable engineering result.**

**3. Build the ambiguity gate (≈3 h).** Score each transition on: surface change type (route vs. system vs. app), presence of `returns_to`, `same_field_as` across the transition, gap magnitude relative to the session's rolling median, and block size. Confident transitions decide by rule; the uncertain tail routes to the reasoner. **This is what makes the LLM affordable** — the current 1,767 windows at ~1,750 tokens each would be ~3M tokens for Dataset B alone, which is exactly why the gate is not optional.

Then, and only then, wire `instructor` to the payload that already exists and run E1.

---

**One honest note.** The perception layer working on B does not mean it works on A — A has different departments and applications, and its window titles may be generic where B's are semantic. Task 1 exists for that reason, and `E0` will tell us within an hour of A landing. If A's blocks look like B's, this architecture is on solid ground. If they do not, the ambiguity gate routes more to the reasoner and the AI layer becomes *more* important, not less.
