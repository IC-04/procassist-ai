# Where GenAI Earns Its Place
## A neuro-symbolic design study for the operation-log → automation-proposal assignment

**Date:** 2026-09-12 · **Contract:** `README.md` + `DATA_SCHEMA.md` (authoritative) · **Dataset A:** not downloaded
**Register:** this is an engineering design note, not a research review. Schemas, prompts and file layouts are specified so they can be built directly.

---

## 0. Direct answer to your intuition

You wrote that adding GenAI would cut engineering effort and speed the project up. **That is right, but not where the previous documents — or the framing in your question — put it.**

The measured facts constrain this sharply. Dataset B has **20,477 events and 7,408 context-state changes across 15 sessions**; Dataset A is ~8× larger by event count (~162,000 events **[S]**), implying on the order of **~59,000 candidate boundaries**. An LLM call per candidate is not a design — it is a bill and a reproducibility problem. But B also has only **57 distinct window titles and 19 distinct URLs**. That asymmetry is the whole insight:

> **The expensive, slow, domain-knowledge-heavy part of this project is not deciding 59,000 boundaries. It is knowing what 76 Japanese strings mean.** A deterministic system cannot know that. An LLM knows it in one batched pass, offline, for a fraction of a cent — and the result is a frozen file you commit to the repo.

So the highest-value GenAI component is **a compiler, not an interpreter**. It runs once, before the pipeline, converts an unknown vocabulary into a typed symbol table, and then gets out of the way. Runtime LLM calls: **zero**. Reproducibility: perfect. Effort saved: the several hours of Japanese business-domain classification we are otherwise unqualified to do by hand.

Where GenAI does **not** save effort — and this is most of the build — is normalisation, ground-truth canonicalisation, the evaluation harness, the baselines, and the boundary/merge logic. That is roughly 60% of the engineering and it is pure determinism. Adding an LLM there *adds* work: caching, prompt versioning, schema validation, cost control, fallback paths.

**Net recommendation, stated up front:** three GenAI components, in descending order of confidence — one adopted unconditionally, one gated by a 150-call experiment, one reserved for the Step 3 prototype where the README explicitly sanctions it. No agent framework. No multi-agent system. No LLM in the scored critical path unless an experiment earns it.

---

## 1. What is inherently semantic, and what is not

| Sub-problem | Semantic? | Why | Owner |
|---|---|---|---|
| Parsing events, ordering, dissolving chunks | No | Mechanical | **Deterministic** |
| Detecting that context state changed | No | String comparison | **Deterministic** |
| Time arithmetic, interval algebra, overlap | No | Arithmetic — and LLMs are *bad* at it | **Deterministic, always** |
| **What does `keiyaku_kaijo_tetsuzuki` mean, and is it a work surface or a reference document?** | **Yes** | Requires Japanese + business-domain knowledge. No deterministic rule exists. | **LLM (offline compiler)** |
| **Is opening a Word procedure file mid-task a reference lookup or a new execution?** | **Yes** | Depends on what the document *is for* | **LLM once (as a type), deterministic thereafter** |
| Is this excursion short enough to merge | No | Threshold on a measured distribution | **Deterministic** |
| **Is this boundary a PROCESS_SWITCH or a SUSPENSION?** | **Partly** | The distinction is intentional (`split_id` on suspend only **[S]**); telemetry evidence is indirect | **Deterministic first; LLM only on the ambiguous tail** |
| Assigning executions to families (clustering) | No | Similarity over symbols | **Deterministic** |
| **Naming the families** | **Yes** | Pure semantics | **LLM — and C4 says label text is not scored, so this is zero-risk** |
| **Describing a variant in words** | **Yes** | For the report | **LLM** |
| Counting frequency, effort, operators | No | Aggregation | **Deterministic** |
| **Turning a step sequence into a readable procedure** | **Yes** | Generation | **LLM — this is the prototype** |
| Scoring, metrics, evaluation | No | Must be reproducible | **Deterministic, always** |

**Rule that falls out of this table:** the LLM may produce *types, names and prose*. It may never produce *times, indices, counts or scores*.

---

## 2. Three concrete architectures

### H1 · Vocabulary Compiler — *offline, frozen, zero runtime LLM* — **ADOPT NOW**

```
normalise.py
   └─► extract_surfaces.py        deterministic
         emits the DISTINCT set of:
           (app_name, window_title_pattern, url_route, element_id_prefix)
         B: ~76 strings [A].  A: unknown, same order of magnitude [U]
              │
              ▼
   compile_vocabulary.py          ← THE ONLY LLM STEP.  Batched, ~10 calls.
         input : the distinct surface strings + frequency + co-occurring app
         output: vocabulary_<dataset>.json   (committed to git, human-audited)
              │
              ▼
   everything downstream reads the frozen JSON.  No LLM at runtime.
```

Output schema (one record per distinct surface):

```json
{
  "surface_id": "win:HR人事給与システム",
  "raw": "HR人事給与システム - Profile 1 - Microsoft Edge",
  "app": "Microsoft Edge",
  "gloss_en": "HR payroll system",
  "surface_type": "business_system",
  "role": "work_surface",
  "business_domain": "hr",
  "likely_process_hint": "payroll",
  "confidence": "high",
  "evidence": "Japanese title names an HR payroll system; served on a dedicated port",
  "compiler_version": "v1",
  "model": "<model-id>",
  "reviewed_by_human": true
}
```

Controlled vocabularies (enums, enforced by the decoder — **not** free text):
`surface_type ∈ {business_system, spreadsheet, document, procedure_reference, communication, terminal, os_utility, browser_chrome, unknown}`
`role ∈ {work_surface, reference_surface, incidental, noise}`

**Why this is the strongest candidate.** `role` is exactly the field the deterministic merge policy needs and cannot derive. A `reference_surface` excursion (opening `settai_keihi_kitei` — entertainment-expense rules — while working a claim) should be **merged into the surrounding execution**; a `work_surface` excursion should be a **boundary**. Hand-deriving that for 76 Japanese strings is hours of guesswork; the LLM does it in one pass and we audit it in fifteen minutes. It also gives the English glosses the report needs anyway.

**Properties:** runtime cost £0 · reproducible by construction (the artifact is frozen and diffable) · fully auditable · degrades to a hand-written file if the LLM is unavailable · transfers correctly (run the *compiler* on B, never reuse A's *vocabulary* — this is precisely the C6 transfer discipline).

### H2 · Candidate + LLM Judge on the ambiguous tail — **GATE BEHIND AN EXPERIMENT**

```
dwell/context segmenter ──► candidate boundaries + ambiguity score
                                   │
              ┌────────────────────┴────────────────────┐
              │ ambiguity < θ                           │ ambiguity ≥ θ  (top-N only)
              ▼                                          ▼
     deterministic rule decides                  LLM judge (cached, temp 0)
                                                  returns ONE enum + confidence
              └────────────────────┬────────────────────┘
                                   ▼
                    deterministic decoder + constraint solver
                    (monotone time, min duration, no illegal overlap,
                     max % of boundaries the LLM may flip)
                                   ▼
                             segments.jsonl
```

LLM contract — note it returns **no timestamps**:

```json
{
  "candidate_id": "ses_x#c0412",
  "decision": "SAME_EXECUTION | INTERRUPTION | PROCESS_SWITCH | NEW_EXECUTION | UNCERTAIN",
  "confidence": 0.0,
  "rationale": "<= 25 words",
  "resumes_block_id": "b0398 | null"
}
```

**Cost reality, from measured numbers.** If 10% of candidates are ambiguous: B ≈ **740 calls** (fine, minutes, cents). A ≈ **5,900 calls** ≈ 3.5M tokens (real money, hours of wall-clock under rate limits, and it must be re-run whenever the prompt changes). **Conclusion: affordable on the deliverable dataset, expensive on the validation dataset** — so validate on a *sample* of A and run the full judge only on B. That asymmetry is acceptable but must be stated in the report.

### H3 · Segment-then-Critic — **CHEAPER COUSIN OF H2; PREFER IT IF H2 IS GATED OUT**

```
deterministic segmenter ──► full segmentation
             ▼
   suspicion detector (deterministic):
     · duration in the extreme tails of the family's distribution
     · high internal heterogeneity (many surfaces, no dominant one)
     · label unstable under ±20% parameter perturbation
     · adjacent segments with identical labels separated by < merge window
             ▼
   LLM critic reviews ONLY flagged segments  →  MERGE_WITH_PREV | SPLIT_AT | RELABEL | KEEP
             ▼
   deterministic applier, with guardrails:
     · may alter at most K% of segments
     · may never produce a segment shorter than the observed minimum on A
     · every change logged with before/after for the work log (C15)
```

**Why H3 beats H2 under a seven-day budget:** its blast radius is bounded, it is trivially ablatable (skip the critic → you still have a complete system), the call count is an order of magnitude smaller, and a failed critic run degrades to *no change* rather than to a broken segmentation.

---

## 3. Ranking the levels the LLM could operate at

Your list omitted the level that wins. Adding it:

| Rank | Level | Calls (A / B) | Value | Verdict |
|---|---|---|---|---|
| **1** | **Vocabulary / surface-type** *(added)* | ~10 / ~5, **once** | Supplies the one thing determinism cannot derive; frozen artifact | **Adopt** |
| **2** | **Process-family** (name, description, variant prose) | ~30 / ~15 | High report value (C7, C9); **zero score risk** since label text is unscored (C4) | **Adopt** |
| **3** | **Execution** (procedure generation for the prototype) | ~50 on selected family | Step 3 deliverable; README explicitly permits an AI-agent form (C8) | **Adopt for prototype** |
| **4** | **Candidate boundary (ambiguous subset)** | ~5,900 / ~740 | Potentially real accuracy gain; highest cost and risk | **Gate on experiment** |
| **5** | **Compressed block** | ~7,400 / ~900 | Mostly redundant with levels 1 and 3 | **Skip** |
| **6** | **Raw event** | 162,000 / 20,477 | No semantic unit at this granularity; absurd cost | **Never** |

The value/cost curve is steeply decreasing and the top three are all **off the scored critical path**.

---

## 4. Does a graph add real value?

**Not for identity inference** — the previous review refuted connectivity-implies-execution, and nothing here revisits that. But a **typed, heterogeneous graph built *after* reconstruction** earns its place for a different reason: it turns C7's five operational questions into one-line queries and gives the report its figures.

**Nodes:** `Session`, `Operator` (`source.username_hash`), `Execution`, `ProcessFamily`, `Variant`, `Surface` (system/route/document, typed by H1), `Field` (`extensions.field_identity_v1.stable_key`), `Step`.

**Typed edges (all deterministic, all derived from reconstruction — none inferred by an LLM):**

| Edge | Meaning | Answers |
|---|---|---|
| `Operator –PERFORMED→ Execution` | who did it | "how many people" (C7) |
| `Execution –INSTANCE_OF→ ProcessFamily –HAS_VARIANT→ Variant` | classification | process inventory, variant counts |
| `Execution –USES→ Surface` (weight = dwell) | where the work happened | application count, cross-system transitions |
| `Execution –CONSULTED→ Surface` (role = reference) | lookup, not work | distinguishes reference excursions from switches |
| `Execution –TYPED_INTO→ Field` | data entry points | human decision points; determinism proxy |
| `Execution –PRECEDES→ Execution` (same session) | temporal order | handoff patterns, batching |
| `Execution –RESUMES→ Execution` | fragment stitching (M2b) | interruption recall |
| `Step –PART_OF→ Execution`, `Step –NEXT→ Step` | procedure structure | **feeds the prototype and makes PM4Py meaningful** |

**Implementation:** this is a star schema. `pandas` plus a dict of adjacency lists is enough; `networkx` only if we want its algorithms. **Do not introduce a graph database.** The value is in the *typing*, not the storage.

---

## 5. Reliability engineering — making the LLM usable without making it the truth

| Technique | Applies to | Why |
|---|---|---|
| **Enum-constrained structured output** (tool-use / JSON schema, not free text) | H1, H2, H3 | The decoder rejects anything off-enum. The model cannot invent a new category. |
| **`UNCERTAIN` is always a legal answer** | H2, H3 | Removes the pressure to guess. Uncertain ⇒ deterministic rule keeps control. |
| **The LLM never emits times, indices or counts** | all | It answers *about* a referenced block id; the deterministic layer owns all arithmetic. This eliminates the entire class of temporal-reasoning errors. |
| **Content-hash caching** (`sha256(prompt_template + payload)` → response, on disk, committed) | all | Makes re-runs byte-identical and free. **This is what makes an LLM component reproducible enough to sit in a graded pipeline.** |
| **Temperature 0, pinned model id, prompt file versioned in git** | all | C15 makes the git history a deliverable; prompt changes become visible. |
| **Self-consistency (3 samples, majority) only at level 1–2** | H1 | Cheap where call counts are in the dozens; unaffordable at level 4. |
| **Batching** (25 surfaces per call) | H1 | Turns ~250 calls into ~10. |
| **Blast-radius cap** (critic may change ≤ K% of segments) | H3 | Bounds the damage from a bad run. |
| **Two-tier prompts:** a domain-neutral system prompt + a dataset-specific payload | all | The system prompt is the only thing that transfers A→B. **No A process name may ever appear in a prompt** (C6). |
| **Every LLM output stored with its input** | all | Auditable; feeds the work log (C15). |

**On sensitive telemetry:** C14 explicitly permits LLM and translation tools, so this is not a contract violation. But H1 sends only *distinct UI strings* — no clipboard values (`raw_value_persisted: false` anyway **[A]**), no form contents, no screenshots. That is worth stating in the report as a deliberate design property under C9, not because the assignment demands it but because a client would.

---

## 6. Failure modes

| Failure | Realistic here? | Mitigation |
|---|---|---|
| **Hallucinated relationships** ("this resumes block 398" when 398 is unrelated) | Yes, at H2 | Decoder validates that the referenced block exists, precedes in time, and shares a compatible surface; reject otherwise |
| **Inconsistent decisions** across identical contexts | Yes | Content-hash cache makes identical contexts literally return the same answer |
| **Label drift** (same family named differently across sessions) | Yes, at level 2 | Name *clusters*, not segments — one call per cluster, so drift is structurally impossible |
| **Prompt sensitivity** | Yes | Version prompts in git; re-run the 150-call validation set on any prompt change and diff the agreement rate |
| **Context-window limits** | Low | Compressed blocks are ~40 tokens; a local window is ~600 |
| **Cost / wall-clock** | **Yes, at level 4 on Dataset A** | Ambiguity gating; sample-validate on A, full-run only on B; cache |
| **Temporal reasoning errors** | **Yes — this is what LLMs are worst at** | Structurally prevented: the model never sees or emits raw timestamps, only ordered block ids and pre-computed relative gaps |
| **Over-merging** (one giant execution) | Yes, at H3 | Guardrail: reject any merge producing a segment beyond the 99th percentile duration observed in A's GT |
| **Over-segmentation** | Yes, at H2 | The deterministic layer already over-segments; the LLM is only allowed to *merge or confirm*, never to introduce a boundary the candidate generator did not propose |
| **Silent dependency** (pipeline stops working without an API key) | Yes | H1's output is a committed file; the pipeline runs offline. H2/H3 are optional stages with a `--no-llm` flag that must stay green in the test suite |

---

## 7. Ablation and the decision rule

### Ablation ladder

| Arm | Configuration | Isolates |
|---|---|---|
| **A** | Deterministic only: dwell blocks + merge policy, surfaces typed by **hand-written** rules | The floor |
| **B** | A + **H1 vocabulary compiler** (LLM-typed surfaces, frozen) | **Value of semantics alone, with no runtime LLM** |
| **C** | B + **H3 critic** on flagged segments | Value of post-hoc correction |
| **D** | C + **H2 judge** on ambiguous candidates, incl. `INTERRUPTION`/`RESUMES` | Value of boundary-level reasoning + identity |

Report all four in the final document. **Arm B is the one I expect to carry most of the gain**, and it is the only arm with no runtime LLM at all.

### The control everyone forgets

Add **Arm A′: spend the same engineering hours adding one more deterministic feature** (e.g. form-submission detection, or `field_identity_v1` step tokens). If the LLM arm does not beat A′, the honest conclusion is that the LLM bought us nothing that equal effort elsewhere would not.

### When the LLM stays in the critical path

No universal thresholds. Five relative conditions, **all** of which must hold:

1. **Targeted gain:** measurable improvement in boundary F1 / segmental F1@IoU **on the flagged or ambiguous subset** — evaluating on the whole dataset dilutes the effect it is supposed to have.
2. **No collateral damage:** unflagged segments unchanged or improved; count ratio moves toward 1.0, not away.
3. **Stability:** ≥95% identical decisions across three runs at temperature 0 on the same inputs (with cache disabled for the test).
4. **Cost proportionality:** a full run on the deliverable dataset completes within an hour and costs less than a rounding error — measured, not assumed.
5. **Downstream impact:** the automation-candidate ranking either changes *and* becomes more stable under perturbation, or is unchanged. If the ranking is unchanged, the LLM is not earning its place in the *scored* path — move it to naming and reporting only.

If 1–4 hold but 5 fails, the correct action is **demote, not delete**: keep it at levels 1–3 where it is free and useful.

---

## 8. Does this help the Step 3 prototype?

**Yes — and this is the strongest argument for GenAI in the entire project.** The README lists acceptable tool forms including *"An AI agent (for example, something like Copilot given a set of procedure definitions)"* (C8). That phrasing describes almost exactly what a reconstruction pipeline produces: **procedure definitions**.

The prototype that follows naturally:

```
deterministic pipeline
   ├─ executions of the chosen family (from segments.jsonl)
   ├─ step sequence per execution      (M6 / field_identity_v1 / route transitions)
   ├─ dominant variant + branch points (deterministic)
   └─ screenshots for each step        (payload.file_reference)
              ▼
   LLM generation layer (one call per procedure, ~50 calls total)
              ▼
   ARTIFACT: a step-by-step SOP / checklist for that business process,
             with human-decision points marked as REQUIRES_HUMAN,
             plus a machine-readable workflow skeleton (JSON/YAML)
```

Three reasons this is the right prototype: it needs **no target system** (the localhost SPAs are unavailable to us **[A]**); it uses the 4,746 screenshots that are otherwise dead weight; and it automates work we can *observe being done by hand* in the data — Word files named `nyusha_checklist_shinsotsu_batch` and `keiyaku_kaijo_tetsuzuki` are literally onboarding checklists and contract-cancellation procedures being edited **[A]**. Generating them is not a toy; it is the thing.

The `REQUIRES_HUMAN` markers double as C9's "what manual work remains after deployment" — the honest answer falls out of the artifact instead of being asserted.

---

## 9. Hybrid vs. pure deterministic

| Dimension | Pure deterministic | **+ H1 (vocabulary)** | + H3 (critic) | + H2 (judge) |
|---|---|---|---|---|
| Expected accuracy | baseline | **likely meaningful gain** — supplies the merge policy's missing input | modest, bounded | unknown; highest ceiling |
| Implementation effort | — | **+3–4 h** | +6–8 h | +2 days |
| Explainability | high | **high** (frozen, diffable, human-reviewed file) | medium (rationale strings) | medium |
| Transfer A→B | good | **good** — recompile vocabulary on B; procedure transfers, content does not | good | unproven |
| Reproducibility | perfect | **perfect** (artifact frozen at build time) | good with cache | good with cache, fragile without |
| Cost | 0 | ~cents, once | low | **material on A** |
| Prototype value | low | medium | low | low |
| Risk | — | **very low** | low | medium |

**Reading:** H1 is nearly free and sits outside the runtime path entirely. H2 is the only one that could move the headline metric, and it is also the only one that could quietly break reproducibility and blow the time budget. That asymmetry is the whole recommendation.

---

# A. Best hybrid architecture

**Deterministic spine, with GenAI at three clearly bounded edges — and none of them in the scored runtime path.**

```
 ┌──────────────────────── DETERMINISTIC SPINE ────────────────────────┐
 │ normalise → surfaces → dwell blocks → merge policy → executions →    │
 │ clustering → typed graph → operational analysis → segments.jsonl     │
 └──────┬──────────────────────────┬──────────────────────┬────────────┘
        │ build time               │ post-hoc, optional   │ prototype
        ▼                          ▼                      ▼
  ① VOCABULARY COMPILER      ② FAMILY NAMER         ③ PROCEDURE GENERATOR
    ~10 calls, ONCE            ~30 calls              ~50 calls
    → vocabulary.json          → names + prose        → SOP + workflow skeleton
    (committed, audited)       (unscored by C4)       (the Step 3 deliverable)

                    ④ BOUNDARY CRITIC (H3)  —  OPTIONAL, GATED
                       flagged segments only · caps on blast radius
                       ablatable to zero with --no-llm
```

Total LLM calls in the adopted design: **fewer than 100 per dataset.** No agent framework, no tool loop, no multi-agent system, no LLM in the metric path.

# B. Smallest experiment to validate it

Three experiments, ~200 LLM calls total, roughly **half a day**, on **6 sampled sessions of Dataset A** — no bulk download.

**B1 · Vocabulary compiler sanity (≈10 calls, 1 h).** Extract A's distinct surfaces; compile; **a human spot-checks 20 records**. *Pass:* `role` (work vs. reference) is correct on ≥17/20 by human judgement. *This is the gate for adopting H1 at all,* and it needs no ground truth.

**B2 · Does semantic typing improve merging? (0 extra calls, 2 h).** Run Arm A vs. Arm B on the 6 sessions. *Pass:* Arm B improves boundary F1 or moves count ratio toward 1.0 without degrading the other. *This is the experiment that actually decides whether GenAI belongs in the pipeline.*

**B3 · Boundary-judge feasibility (≈150 calls, 2 h).** Sample 150 candidate boundaries stratified by ambiguity; derive the true answer from canonicalised GT; compare **LLM decision** vs. **deterministic rule** vs. **truth**. *Pass:* LLM agreement exceeds the deterministic rule's agreement on the high-ambiguity stratum, with ≥95% run-to-run stability. *Fail:* H2 and H3 are dropped; ① ② ③ remain.

Run B1 → B2 → B3 in that order, and stop at the first failure.

# C. If it works, what we build

1. **`compile_vocabulary.py`** + committed `vocabulary_a.json` / `vocabulary_b.json`, with a human-review column. Frozen artifacts, diffable in git.
2. **Merge policy consuming `role`** — reference-surface excursions merge, work-surface excursions cut. This is the concrete accuracy mechanism.
3. **`name_families.py`** — one call per cluster, producing names and one-paragraph descriptions for Step 2's report. Structurally drift-free because it names clusters, not segments.
4. **`critic.py` behind `--llm-critic`** (only if B3 passes), with cache, guardrails and full before/after logging.
5. **`generate_procedure.py`** — the Step 3 prototype: step sequence + screenshots → SOP document with `REQUIRES_HUMAN` markers + workflow skeleton JSON.
6. **The ablation table (A / A′ / B / C / D)** in the final report — which is itself a C9 deliverable and turns the negative results into content.

# D. If it fails, how the deterministic system proceeds

Nothing in the spine depends on an LLM, so failure is a **degradation, not a blocker**:

- **If B1 fails** (typing unreliable): replace `vocabulary.json` with a hand-written file. We lose a few hours to manual classification and some gloss quality; the pipeline is otherwise identical. Keep the LLM for naming and the prototype only.
- **If B2 fails** (typing does not improve merging): semantics are not the bottleneck. Promote the change-point / sensitivity work instead, and demote the LLM to naming, explanation and prototype generation.
- **If B3 fails** (judge no better than the rule): drop H2 and H3 entirely. **This is a reportable finding under C9 and C15**, not a loss — "we tested LLM boundary adjudication against a deterministic rule on 150 stratified cases and it did not beat it" is exactly the kind of evidenced risk assessment the brief says it is scoring.
- **If the API is unavailable on the day:** `--no-llm` runs the whole pipeline from committed artifacts. That flag must stay green in the test suite from day one.

The prototype survives every branch: procedure generation can fall back to a **template-filled** SOP built deterministically from the step sequence, with the LLM only improving the prose. The artifact still exists; it just reads less well.

---

**One closing caution.** Your instinct that GenAI will speed this up is right about *domain knowledge* and *artifact generation*, and wrong about *pipeline engineering*. The harness, the canonicaliser, the baselines and the metrics are still the bulk of the build, they are still deterministic, and no amount of GenAI removes them. Keep the LLM where it is cheap, frozen, auditable and outside the scored path — and the seven days stay achievable.
