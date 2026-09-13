# Adversarial Review of the Solution-Space Analysis
## Re-evaluated from first principles, with `DATA_SCHEMA.md` and `README.md` as the contract

**Date:** 2026-09-12 · **Reviews:** *From Survey to Engineering Decision* (2026-09-11)
**Method:** the README and `DATA_SCHEMA.md` are treated as authoritative. Dataset A was **not** downloaded or inspected. Dataset B was inspected only where a check could settle a question cheaply and without A. Every claim below carries an evidence tag.

**Evidence tags used throughout**

| Tag | Meaning |
|---|---|
| **[A]** | Directly verified from Dataset B by inspection |
| **[S]** | Stated or directly implied by `README.md` / `DATA_SCHEMA.md` |
| **[H]** | Hypothesis, not yet validated |
| **[R]** | Engineering recommendation (a judgement, not a fact) |
| **[U]** | Unknown until Dataset A is actually inspected |

---

## 0. The headline correction

My previous document named the provenance/correlation hypothesis as *"the largest unexamined asset in the dataset"*, made it Milestone 0, and wrote that if `dataflow_v2` encodes copy→paste provenance then *"Family D becomes the backbone of the whole solution."*

**That prioritisation was wrong, and it was checkable on Dataset B without Dataset A.** I checked it for this review:

| Field | What it actually is **[A]** | Business-process value |
|---|---|---|
| `correlation.triggered_by` | 4,760 links, of which **4,759 have child `event_type = screenshot_smart`**. Parents are clicks, scrolls, shortcuts, keystrokes. It means *"this screenshot was captured because of that action."* | **None.** Pure capture plumbing. |
| `correlation.correlated_events` | 1,997 events, 96% singleton lists. Pair types: `browser_click`↔`mouse_click` (1,891), `text_input_complete`↔`keystroke` (605), `browser_form_input`↔`mouse_click` (28). It is **same-physical-action deduplication across layers L2/L3.** | **None.** One physical click logged twice. |
| `extensions.cross_layer_v1` | Fields `dom_event_id`, `uia_event_id`, `match_reason`, `timestamp_delta_ms`; observed `match_reason: "none"`. Same-action matching between DOM and UI-Automation layers. | **None.** |
| `extensions.dataflow_v2` | 1,759 events. Keys: `operation` (`paste`, `clipboard_change`), `content_type`, `normalized_value_hashes` (`{hash, namespace, entropy_bucket}`), `raw_value_persisted: false`, and **`source_event_id` on only 870 events**. | **Real but thin.** Genuine copy→paste lineage on **870 links ≈ 4.2% of events**. Values are hashed, not stored. |
| `extensions.field_identity_v1` | `field_label_hash` + `stable_key` on 2,415 events. A stable identifier for *which form field* was typed into. | **Real, but it is step identity, not case identity.** |

**So three of the four fields I cited are instrumentation plumbing with no business meaning, and the fourth covers 4.2% of events with hashed values.** The claim "connected component = business execution" was never tested, and the graph I proposed building would have been ~85% composed of screenshot-capture edges and layer-deduplication edges — edges that link an event to *itself in another representation*.

This is the exact failure the review was commissioned to find: I reasoned from **field names** to **semantics**, then let that inference set the project's first milestone. Two further aggravating factors: `extensions` is documented in `DATA_SCHEMA.md` only as `"extensions": {}` with **no description at all** **[S]**, so none of these namespaces are part of the contract; and `correlated_events` does not appear in the schema's `correlation` table either (which lists only `sequence_number`, `chunk_id`, `triggered_by`, `ms_since_last_event`) **[S]**.

What survives: `dataflow_v2.normalized_value_hashes` and `field_identity_v1.stable_key` are genuine signals, but they are **weak complementary features with a different mechanism than the one I proposed** (value-hash matching and field identity, not graph connectivity). Section 6 develops this properly.

---

## 1. Assignment Contract

Reconstructed from `README.md` and `DATA_SCHEMA.md`. Where the previous analysis used my terminology, the mapping is given explicitly.

| # | Requirement | Source | Engineering implication |
|---|---|---|---|
| C1 | **Goal is ROI, not accuracy.** "Produce a proposal that maximizes the client's ROI, and demonstrate it with something that actually runs." "Technical accuracy is not the objective in itself." | README, *Goal* | Segmentation quality is instrumental. Effort spent past "good enough for the ranking to be stable" is negative-return. |
| C2 | **Step 1 = segment the event stream into individual executions of business processes.** | README, *Step 1* | The unit of output is an **execution**, not a task and not a process family. |
| C3 | **Output is `segments.jsonl`: one JSON object per line with `session_id`, `start`, `end`, `label` (ISO-8601 UTC).** | README, *Deliverables* | Four flat fields. No case id, no nesting, no fragment link. A discontinuous execution cannot be expressed natively. |
| C4 | **Evaluated on (a) boundary correctness and (b) label consistency** — "the label text itself is not evaluated… What is evaluated is whether the boundaries between units of work are correct, and whether the same process consistently receives the same label." | README, *Deliverables* | Two independent metrics. Never report one number. Label *semantics* are worth zero to the scorer (but not to the report — see C9). |
| C5 | **No accuracy threshold is given; defining "good enough" is part of the task.** | README, *FAQ* | The evaluation design is itself a graded deliverable, not internal scaffolding. |
| C6 | **Dataset A is for building and validating the approach; Dataset B is the production data to analyse.** B has different departments, processes and applications; "an approach that works well on Dataset A will not necessarily transfer." | README, *Provided Data*; SCHEMA §6 | A is a **method-validation instrument**, not a training set for content. Transfer discipline is a first-class requirement. |
| C7 | **Step 2 = analyse B: what processes, how often, how much time, how many people, and are there different handling patterns within the same process. Then propose automation candidates in priority order with reasoning.** | README, *Step 2* | Five specific operational questions must be answerable from `segments.jsonl` plus the raw log. "How many people" needs a person proxy. |
| C8 | **Step 3 = build the automation tool(s); form is free** (AI agent, workflow definition, deterministic script, desktop app, web app, or other). Scope and count are our decision and "that decision is itself part of the ROI question." | README, *Step 3* | The prototype must be argued for, not just built. Breadth-vs-depth is scored. |
| C9 | **Report must explain: why that process and scope; why that implementation form (incl. why alternatives were rejected); what manual work remains and realistic impact; anticipated risks with the evidence that led to anticipating them.** | README, *Step 3* | Risks must be **evidenced from the logs**. This makes negative findings (e.g. §0 above) directly valuable report content. |
| C10 | **Judge candidates comparatively, not on absolute time** — "waiting time within each operation is shorter than in real production use." | README, *Notes* | Durations are ordinal. No annual-hours-saved claim is defensible. |
| C11 | **`text_input_complete` is unreliable; reconstruct from `keystroke` or `clipboard_change` if needed.** | README, *Notes*; SCHEMA *Caveats* | Do not use it as a feature without validation. |
| C12 | **Chunks are fixed recording-time buckets with no business meaning; a session may span several.** | README; SCHEMA §1 | Chunk boundaries must be dissolved during normalisation and must never appear as predicted boundaries. |
| C13 | **Ground truth is imperfect: `gt.jsonl` sometimes emits the same `process_started` twice; `process_switched_out` does not always pair with a start. "Verify consistency yourself."** | SCHEMA §3 | A GT canonicalisation step is mandated by the schema, not optional. |
| C14 | **Japanese content; translation tools and LLMs are explicitly permitted.** | README, *Notes*; SCHEMA §5 | **There is no stated privacy restriction in the assignment.** Any privacy argument I make is client-realism for the report (C9), not a contract constraint. I previously blurred this. |
| C15 | **Git history and a work log (including failures and generative-AI use) are graded deliverables.** | README, *Deliverables* | Negative experimental results must be recorded, not discarded. This changes experiment economics: a failed experiment still produces a deliverable. |
| C16 | **Incompleteness is survivable if reasoned** — "Record in your work log why you did not." | README, *FAQ* | Favour a complete-but-simple chain over a sophisticated-but-unfinished one. |
| C17 | **Screenshots resolve via `payload.file_reference.filename`; a missing image is "no capture available", not a pipeline error.** | SCHEMA §2 | Robustness requirement, explicitly stated. |
| C18 | **`context.extracted_text` is "present on roughly 4% of events"**, and OCR is explicitly *not* required: "you do not have to run OCR on the images to get at screen content." | SCHEMA §2 | The schema itself deprioritises the vision path. My previous rejection of OCR/VLM was right in direction but was justified from B statistics when it could have been justified from the contract. |

### Terminology mapping (assignment → my previous document)

| Assignment term (source) | My term | Note |
|---|---|---|
| *execution* (`gt_manifest.executions[]`) | "unit of work", "segment" | Same thing. Use **execution** from now on. |
| *process* / `code` / `family_name` | "process family" | Same. Use **process family**. |
| *process_variant* / `variant` | "variant" | Same. |
| *task* (`task_started`, `task_id`, `action`, `entity`) | **absent from my decomposition** | **A real omission.** See §4. |
| *process_switched_out* | folded into "interleaving" | Distinct from suspension. See §4. |
| *process_suspended* / *process_resumed* / `split_id` / `phase` | "interruption/resumption" | Same, but the schema gives it explicit machinery I ignored. |
| `expected_boundaries` (gt_manifest) | mentioned in the survey, **dropped** in the solution doc | **A real omission.** Likely the intended scoring target. See §7. |

---

## 2. A/B schema parity matrix

Derived from `DATA_SCHEMA.md` alone, except where marked **[A]**. No Dataset A inspection was performed.

| Field / signal | In A (schema) | In B (schema) | GT-only | Sparse? | Semantic meaning | Segmentation | Identity | Switch/interleave | Variant |
|---|---|---|---|---|---|---|---|---|---|
| `timestamp_ms` / `timestamp_iso` | ✔ | ✔ | | no | UTC event time | **High** (ordering; gaps as a feature) | low | medium | low |
| `session_id` | ✔ | ✔ | | no | recording session | boundary prior at edges only | scoping | — | — |
| `correlation.chunk_id` / `sequence_number` | ✔ | ✔ | | no | recording bucket + within-chunk index | **must be dissolved** (C12) | — | — | — |
| `correlation.ms_since_last_event` | ✔ | ✔ | | no | inter-event gap | **feature, not threshold** (§7) | low | medium | low |
| `correlation.triggered_by` | ✔ | ✔ | | no | *capture causality* — 4,759/4,760 parent→screenshot **[A]** | none | **none** | none | none |
| `correlation.correlated_events` | **not in schema** | present **[A]** | | no | L2↔L3 same-action dedup **[A]** | none | **none** | none | none |
| `layer` / `event_type` | ✔ | ✔ | | no | event taxonomy | **High** (rhythm features) | medium | medium | medium |
| `context.active_app` (`app_name`, `process_name`, `window_title`) | ✔ | ✔ | | "how often populated varies" **[S]**; 99.4% in B **[A]** | foreground application + title | **Highest available** | **High** | **High** | medium |
| `context.active_browser_tab` (URL, title) | ✔ | ✔ | | varies **[S]**; 46.5% in B **[A]** | browser context | **High** when present | **High** | **High** | medium |
| `context.open_apps` / `visible_windows` | ✔ | ✔ | | varies | ambient state | low–medium | low | medium | low |
| `context.extracted_text` | ✔ | ✔ | | **~4%** **[S]**; 4.6% and largely browser chrome in B **[A]** | screen text | low | low–medium | low | medium |
| `context.active_monitor` | ✔ | ✔ | | no | display info | none | none | none | none |
| `payload.keystroke` (`key`, `character`, `modifiers`, `target_field`) | ✔ | ✔ | | no | typing | medium (rhythm) | low | low | medium |
| `payload.browser_click.element.attributes` (`id`, `class`, `placeholder`…) | ✔ | ✔ | | mostly null except `id`/`placeholder` in B **[A]** | clicked DOM element | **High** | **High** | medium | **High** |
| `payload.app_switch` (`new_app`/`previous_app`) | ✔ | ✔ | | no | foreground change | **High** — but 80% are Edge→Edge in B **[A]** | medium | **High** | low |
| `clipboard_change` payload | ✔ | ✔ | | `text_content` **null**, only `text_length` **[A]** | clipboard transition | low | **low** (no content) | medium | low |
| `text_input_complete` | ✔ | ✔ | | **unreliable** **[S]**; 0.4% in B **[A]** | finalised text entry | avoid | avoid | avoid | avoid |
| `screenshot_smart` + `file_reference` | ✔ | ✔ | | chunk may have none **[S]**; 23.2% in B **[A]** | screen capture | low directly | medium (via content) | low | medium |
| `extensions.uia_v2` | **not in schema** | 9,289 events **[A]** | | | UI-Automation tree **[H]** | **[U]** potentially high | **[U]** | **[U]** | **[U]** |
| `extensions.dom_v2` | **not in schema** | 2,726 **[A]** | | | DOM snapshot **[H]** | **[U]** | **[U]** | **[U]** | **[U]** |
| `extensions.dataflow_v2` | **not in schema** | 1,759; `source_event_id` on 870 **[A]** | | 4.2% of events | copy→paste lineage, **hashed values** **[A]** | weak | **weak-positive** | weak | low |
| `extensions.field_identity_v1` | **not in schema** | 2,415 **[A]** | | | stable per-field key (hashed) **[A]** | medium | low (step, not case) | low | **medium-high** |
| `extensions.cross_layer_v1` | **not in schema** | 2,726 **[A]** | | | DOM↔UIA same-action match **[A]** | none | none | none | none |
| `extensions.capture_quality_v1` | **not in schema** | 12,127 **[A]** | | | capture quality/coverage class **[A]** | **useful as a confidence weight** | — | — | — |
| `extensions.ocr_v1` | **not in schema** | 15 **[A]** | | negligible | OCR output | none | none | none | none |
| `source.username_hash` | ✔ **[S]** | ✔; 4 distinct in B **[A]** | | no | **person proxy** | — | — | — | — |
| `manifest.firebase_uid` / `machine_id` | ✔ (manifest) | 4 / 4 distinct **[A]** | | no | account / machine | — | — | — | — |
| **`gt.jsonl`**: `process_started`, `process_switched_out`, `process_suspended`, `process_resumed`, `task_started`, `clipboard_copy/paste`, `session_ended`; `current_process`, `process_variant`, `ts_utc` | ✔ | ✘ | **GT-only** | imperfect **[S]** | chronological annotation stream | **target** | **target** | **target** | **target** |
| **`gt_manifest.json`**: `processes[].code/family_name/domain`, `executions[].{variant, case_id, start_ts, end_ts, apps, phase, seq, continues_from_prev, continues_to_next}`, `expected_boundaries` | ✔ | ✘ | **GT-only** | | per-session summary | **target** | **target** | **target** | **target** |

**Three parity conclusions.**

1. **Every field the schema guarantees exists in both A and B.** The contract-level signal set is identical; only ground truth differs **[S]**. This is reassuring for transfer of *mechanism*.
2. **Every field my previous analysis leaned on hardest — `extensions.*` and `correlated_events` — is outside the schema contract.** Their presence in A is **[U]** and their stability across agent versions is unknown (B's manifests report `agent_version 1.1.1`). **Any component that depends on them needs a documented fallback.**
3. **The schema explicitly warns that context-field population "varies"** **[S]**. B's 99.4% `active_app` coverage is **[A]** for B and **[U]** for A. The single most load-bearing assumption in my previous document — that window titles are richly informative — is unverified for A.

---

## 3. Evidence-level audit of the previous document

### What was right, and why it survives

| Claim | Tag | Verdict |
|---|---|---|
| Build the evaluation harness before the first model | **[R]** | **Keep.** Strengthened by C5 — the evaluation design is itself graded. |
| Evaluate identity on ground-truth segments, decoupled from boundary quality | **[R]** | **Keep — best idea in the document.** Directly mirrors C4's two independent criteria. |
| Report GT results in clean/repaired/disputed tiers | **[R]** | **Keep in principle**, specific rules revised (§8). Mandated by C13. |
| Leakage checklist; B pipeline must run with A artifacts absent | **[R]** | **Keep.** Direct expression of C6. |
| Report boundary metrics as a tolerance curve, not one number | **[R]** | **Keep**, extended to event-index tolerance (§7). |
| Count ratio (predicted ÷ true) as a standing diagnostic | **[R]** | **Keep.** Cheap and hard to fool. |
| Ranking stability under parameter perturbation | **[R]** | **Keep** — arguably the highest-value honesty artifact for C9. |
| PM4Py is not a segmentation tool | **[S]** | **Keep**, but its downstream role was under-specified (§10). |
| Reject ScreenRPA (CC BY-NC licence) | **[S]** | **Keep.** Licence is dispositive for client-facing work. |
| Reject OpenAdapt / SmartRPA as dependencies (cannot ingest this format; solve the inverse problem) | **[R]** | **Keep.** |
| B's semantic channel is rich: 57 titles, 19 URLs, clean port→system map | **[A]** | **Keep as a B-fact.** Does not generalise (§3, next table). |
| Idle gaps are near-absent in B (p99 = 6 s; one gap > 30 s) | **[A]** | **Keep as a B-fact**; the *conclusion* drawn from it was wrong (§7). |
| Clipboard carries no content | **[A]** | **Keep**, now with the mechanism: `raw_value_persisted: false` **[A]**. |

### What was overconfident or wrong

| Claim in the previous document | Actual status | Correction |
|---|---|---|
| "`dataflow_v2` … could be the backbone"; provenance = Milestone 0 and "first concrete artifact" | Was **[H]** presented with **[R]**-level force | **Refuted for `triggered_by`/`correlated_events`/`cross_layer_v1`; downgraded to a weak complementary feature for `dataflow_v2`** (§0, §6). |
| "Idle-gap segmentation is **dead on arrival**" | **[A]** for B as a *threshold rule*; overgeneralised | Gaps are a poor rule and a **legitimate weak feature / boundary prior**. Also **[U]** for A (§7). |
| "The sparse-semantics problem is largely not our problem" | **[A]** for B, **[U]** for A | Restate as: *B's* semantics are rich; A's are unverified and the schema warns population varies (§2). |
| "Reject OCR/VLM" justified by B's richness | Right direction, wrong justification, and too absolute | Justify from C18 (the schema says OCR is unnecessary) and re-frame as **selective/conditional**, not rejected (§9). |
| M1/M2/M3 decomposition | Incomplete | Missing tasks, switching-vs-suspension distinction, family/variant separation, `expected_boundaries` (§4). |
| "Prefer the manifest over the stream" on disagreement | **[R]** with no justification | Neither dominates; they represent different things (§8). |
| "Quantile thresholds transfer" | **[R]**, asserted | Quantile normalisation is not domain-invariance. Requires a sensitivity argument (§9 transfer). |
| Success criteria "count ratio ∈ [0.7, 1.4] and F1 > 0.6" | Invented | No basis existed. Replace with **relative** criteria (beats baseline; curve has a plateau) (§12). |
| "4 machines = 4 people" | **[A]** for machines; the right field was unused | `source.username_hash` is the schema-documented person proxy; in B it is **4 distinct, matching 4 machine_ids and 4 firebase_uids** **[A]**. Corroborated, but state the assumption. |
| Effort estimates (E0 "1–2 h"; M1 "6–8 h") | Optimistic | A GT loader against an imperfect, two-source, three-level annotation format over 63 sessions is a day, not an afternoon. |
| Tolerances of ±1/2/5 s | Assumed | Must also be expressed in **event index**, and calibrated to observed execution duration on A (§7). |

**The distinction the review asked for:** of everything above, only the three `correlation`/`cross_layer` fields are cases where *we now have evidence the idea is bad*. Everything else in the "overconfident" column is a case where *we do not yet have evidence the idea is good* — which is a reason to test, not to drop.

---

## 4. Revised problem decomposition

The previous M1/M2/M3 is retained but was **incomplete**, and it did not match the vocabulary the ground truth actually encodes **[S]**.

| Component | Definition | GT evidence in schema | Previously? |
|---|---|---|---|
| **M1 · Boundary detection** | Where does an execution start and end | `executions[].start_ts/end_ts`, `expected_boundaries` | ✔ |
| **M2a · Process switching** | Worker moves from process X to process Y | `process_switched_out {from, to}` | folded into M2 |
| **M2b · Suspension / resumption** | One execution occupies *multiple* phases | `process_suspended {from, to, split_id}`, `process_resumed {process_code, split_id, phase}`, `executions[].phase/seq` | folded into M2 |
| **M2c · Chunk continuity** | An execution spans a recording bucket | `continues_from_prev` / `continues_to_next` | mentioned, not modelled |
| **M3 · Execution identity** | Which fragments constitute one execution | `case_id`, `split_id` | ✔ |
| **M4 · Process-family assignment** | Which family an execution belongs to — **this is the `label` field of C3** | `code`, `family_name`, `domain` | conflated with M3 |
| **M5 · Variant discovery** | Handling pattern within a family | `process_variant`, `executions[].variant` | present, underweighted |
| **M6 · Task / step structure** | Ordered steps inside an execution | `task_started {task_id, action, entity}` | **absent — a real omission** |
| **M7 · Operational analysis** | C7's five questions | — | present |
| **M8 · Automation prioritisation** | C7/C9 | — | present |

**Why M6 matters and why omitting it was a mistake.** `task_started` carries `action` and `entity` **[S]**. That is an activity vocabulary *given to us* on Dataset A. It supplies three things my previous document did not have: (i) a second, finer evaluation target that can validate the abstraction layer independently of segmentation; (ii) sub-execution boundary evidence for M1; and (iii) — decisively for §10 — an activity dimension that makes downstream process mining meaningful rather than degenerate.

**Why M2a ≠ M2b matters.** The schema emits `split_id` on suspension but not on switching **[S]**, which strongly implies the generator distinguishes *"I will come back to this"* from *"I am done with this for now."* Conflating them means a method that correctly detects a switch is scored identically to one that correctly detects a suspension, and the `phase`-linked fragments of one execution are treated as two executions. Given C4 scores label consistency, **getting M2b wrong directly costs label-consistency score** — fragments of one execution would receive the right family label anyway, so the cost is on M1/M3, not M4. This is worth knowing: **M2b errors are cheaper than they look under the assignment's stated criteria.**

**Coupling, revised.** M1↔M2b↔M3 remain tightly coupled. **M4 is more separable than I claimed** and is also *the only thing in `segments.jsonl` besides times* — C4 says the label text is not evaluated, only its consistency, so M4 is a clustering problem with no naming requirement. M5, M6, M7, M8 are downstream and separable. **M6 can be evaluated on A completely independently of M1**, which makes it a cheap, high-information experiment nobody was planning to run.

---

## 5. Re-ranked solution families

Classification per the review's requested scheme. **Nothing is eliminated except where evidence — not absence of evidence — justifies it.**

### Family A · Dwell / context-state segmentation → **Promising primary candidate (conditional on A)**
1. **Solves:** M1, partially M2a. 2. **Assumes:** `active_app.window_title` and/or browser URL are populated and discriminative — schema says population "varies" **[S]**; 99.4% in B **[A]**; **[U]** in A. 3. **Evidence for:** B's 57-title / 19-URL vocabulary **[A]**; SWISH and Shen et al. reached 70–80% on titles alone \[survey §4.3]. 4. **Invalidated by:** generic titles in A, or an irreducible over-segmentation rate (7,408 state changes / 20,477 events in B **[A]**). 5. **Validating experiment:** P0-3. 6. **Interruptions:** partially, via an excursion-merge rule. 7. **A→B:** good — mechanism is vocabulary-free. 8. **Needs A labels:** only for tuning and evaluation. 9. **Cost:** low. 10. **Prototype:** yes — most explainable. 11. **When:** **now.**

### Family B · Change-point detection → **Useful baseline and insurance**
1. **Solves:** M1. 2. **Assumes:** a numeric featurisation carries the signal. 3. **Evidence for:** applies when titles fail; `ruptures` API verified (`rpt.Pelt(model="rbf").fit(signal).predict(pen=…)`, signal `(n_samples, n_dims)`). 4. **Invalidated by:** a narrow penalty plateau (⇒ untransferable). 5. **Experiment:** P1-2 (penalty-curve *shape*). 6. **Interruptions:** no. 7. **A→B:** poor for the penalty, good for the featurisation. 8. **Needs A labels:** yes, for calibration. 9. **Cost:** low–medium. 10. **Prototype:** neutral. 11. **When:** **later** — but promote to primary immediately if A's titles turn out generic. This is the hedge against the biggest **[U]**.

### Family C · Motif / sequence discovery → **Useful for M4/M5, not for M1**
1. **Solves:** M4 and M5 well; M1 only incidentally. 2. **Assumes:** executions are near-contiguous and recur with stable structure. 3. **Evidence for:** it is the mechanism behind family/variant discovery in the literature. 4. **Invalidated by:** low coverage under interleaving — the documented failure mode of the flagship method \[survey L2]. 5. **Experiment:** P1-4 (coverage first). 6. **Interruptions:** poorly. 7. **A→B:** procedure transfers, motifs must not. 8. **Needs A labels:** for evaluation only. 9. **Cost:** medium. 10. **Prototype:** yes — a motif *is* a displayable procedure, which matters for the prototype options in §11. 11. **When:** **after M1 works.** *Reclassified from "segmentation candidate" to "family/variant + procedure-extraction tool", which is where its real value lies.*

### Family D · Provenance / correlation graph → **Complementary signal only; demoted**
1. **Solves:** would have solved M3. 2. **Assumes:** links carry business meaning — **largely false** **[A]** (§0, §6). 3. **Evidence against:** `triggered_by` is 99.98% screenshot capture; `correlated_events` is layer dedup; `cross_layer_v1` is same-action matching **[A]**. 4. **Residual value:** `dataflow_v2.normalized_value_hashes` (870 source-linked events, hashed) and `field_identity_v1.stable_key` **[A]**. 5. **Experiment:** P1-5, reformulated as *value-hash co-occurrence*, not connectivity. 6. **Interruptions:** would have handled natively — the loss of this is the main cost of the correction. 7. **A→B:** **[U]** — non-contract fields. 8. **Needs A labels:** for validation. 9. **Cost:** low. 10. **Prototype:** minor. 11. **When:** **only if P0 shows M3 is hard and M1 alone is insufficient.**

### Family E · Hybrid → **Conditional candidate**
Unchanged in structure but its premise weakened: the hybrid was A + D, and D is demoted. The surviving hybrid is **A (boundaries) + C (family/variant) + weak features from B/D**. **When:** only after P0 and P1 establish which components earn their place. Complexity is a real cost against C16.

### Family F · LLM → **Reclassified into four distinct roles (see §9)**
Previously evaluated as a clustering competitor and judged on ARI. That was the wrong test for three of its four possible roles.

### Newly added

### Family G · Task/step-anchored segmentation → **Promising, previously missing**
1. **Solves:** M6, and supplies boundary evidence for M1. 2. **Idea:** learn what a *step* looks like (field-identity keys, form submissions, navigation events), then treat executions as runs of steps. 3. **Evidence for:** `task_started {task_id, action, entity}` exists in A's GT **[S]**; `field_identity_v1.stable_key` gives a language-independent step token **[A]**. 4. **Invalidated by:** task boundaries not being recoverable from telemetry. 5. **Experiment:** P1-6. 6. **A→B:** good — step tokens are hashed and vocabulary-free. 7. **Needs A labels:** yes, for validation (`task_id`). 8. **Cost:** medium. 9. **Prototype:** **high** — steps are what a procedure document or an automation script is made of. 10. **When:** **P1**, and promote if M1 alone under-performs.

### Summary ranking

| Rank | Family | Role | Implement |
|---|---|---|---|
| 1 | **A · Dwell/context** | M1 primary | Now |
| 2 | **Baseline set** (single-segment, gap-threshold, chunk-boundary, random) | floor/ceiling for C5 | Now |
| 3 | **G · Task/step anchoring** | M6 + M1 support | P1 |
| 4 | **C · Motif/sequence** | M4/M5 + procedure extraction | P1 |
| 5 | **B · Change-point** | M1 insurance if A's titles are generic | P1 (gated) |
| 6 | **F · LLM (naming/explanation layers)** | M4 naming, C9 reporting | P1, non-critical path |
| 7 | **D · Value-hash / field-identity features** | weak M3 features | P2 |
| 8 | **E · Hybrid** | integration | P2 |

---

## 6. Adversarial analysis of the provenance hypothesis

Kept as its own section because the review asked for it and because it is where the previous document was most wrong.

**What the schema says.** `DATA_SCHEMA.md` documents exactly one linking field: `correlation.triggered_by` — *"The `event_id` of the event that triggered this one"* **[S]**. `correlated_events`, `dataflow_v2` and `cross_layer_v1` are **not in the schema at all** **[S]**. So the contract offers one causal field, and its wording is about *event triggering*, not business relationship.

**What B shows [A].** `triggered_by`: 4,759 of 4,760 children are `screenshot_smart` — it is the capture trigger. `correlated_events`: 96% singletons, pairing `browser_click`↔`mouse_click` and `text_input_complete`↔`keystroke` — the same physical action seen at two layers. `cross_layer_v1`: `dom_event_id`/`uia_event_id` with `match_reason` — same-action matching.

**Answering the review's questions directly.**

- *Event-layer, causal, UI, lineage, or business?* — `triggered_by`, `correlated_events`, `cross_layer_v1` are **event-layer/UI**. `dataflow_v2` is **data lineage**. **None is business-process.**
- *Could a link cross a process boundary?* — For `dataflow_v2`, **yes, trivially**: copy a value in one process, paste it in another. That is the normal case in back-office work, not an edge case.
- *Could executions share a source event?* — Yes. One copied template value pasted into many executions creates a hub.
- *Could one execution have disconnected components?* — Yes: `dataflow_v2` covers 4.2% of events **[A]**, so most executions will have no link at all.
- *Could instrumentation create false connections?* — Yes, and it demonstrably does: an unfiltered graph would be dominated by screenshot-trigger and layer-dedup edges linking an event to *itself*.
- *Does connectivity imply identity?* — **No.** This was the unexamined leap.
- *Repeated values / hubs?* — `normalized_value_hashes` carries an `entropy_bucket` **[A]**, which is exactly the field needed to down-weight low-entropy (common) values. A robust formulation would use it.

**What a defensible formulation would require.** Typed edges (never mix capture-trigger with data-lineage); direction (source→sink); confidence weights (entropy bucket, temporal distance); temporal constraints (reject links spanning more than a plausible execution duration, calibrated on A); hub detection and pruning by degree; and — critically — **validation against A's `case_id` before use**, measuring *link containment* (fraction of links whose endpoints share a `case_id`) against a permutation baseline.

**Minimum experiment (P2-1).** On A: build only the `dataflow_v2` source→sink edges; compute containment against `case_id`; compare to a time-matched random baseline. **Kill criterion:** containment not materially above baseline, or coverage below ~10% of executions. **Continue criterion:** containment high *and* coverage meaningful — then use as a *feature* (a boundary veto), never as the primary mechanism.

**Honest assessment:** given 4.2% event coverage and hashed values, even a successful outcome yields a weak feature. **This is now a P2, not a P0.**

---

## 7. Segmentation assumptions, re-examined

### Time gaps
Previous claim: *"dead on arrival."* **Overstated.**
- **[A]** On B, gaps are useless as a *threshold rule*: median 62 ms, p99 6 s, one gap > 30 s in 20,477 events.
- **[U]** On A: 63 sessions and ~162,000 events **[S]**. If A's sessions are longer in wall-clock, the gap distribution may differ materially. The compression caveat (C10) is about *within-operation waiting*, which does not strictly imply the absence of *between-execution* pauses.
- **[R]** Correct disposition: **retain `ms_since_last_event` as a weak feature and a boundary prior; retire the gap-threshold rule as a candidate; keep the gap-threshold segmenter permanently as a published baseline** — C5 makes baselines a deliverable, and C15 makes the negative result itself reportable.
- **[R]** Use *relative* gap (gap ÷ rolling median within the session), which is robust to compression and to A/B rate differences, rather than absolute milliseconds.

### Dwell / context-state
- **[A]** On B, raw state change over-segments ~an order of magnitude (one change per 2.8 events; 464 blocks in an 11-minute session).
- **[R]** This is a **merge/suppression** problem, and the merge policy is where the engineering is. That conclusion survives.
- **[R]** Dwell should **not** be treated as a finished method but as a **candidate-boundary generator** whose proposals are scored by other evidence (gap magnitude, app change vs. tab change, form submission, navigation, step tokens). That reframing — generator + scorer, rather than rule — keeps the door open to a learned scorer on A while remaining explainable.

### Change-point detection
- **[R]** Judge it by the **shape of its penalty curve**, not its peak. A wide plateau means transferable; a narrow peak means a number tuned to A. Unchanged, and still the cheapest transfer diagnostic available.
- **[R]** Add the featurisation choice as an explicit ablation: event-type histogram vs. context-state one-hot vs. both.

### Not a binary decision
The right output of P0 is not "family A wins" but **a ranked set of boundary-evidence sources with measured individual contributions** — which is what makes the later scorer (or the later report) defensible.

---

## 8. Ground-truth canonicalisation, re-examined

**What the schema says each source is [S]:** `gt.jsonl` is *"a chronological annotation stream"* recording *"when each business process started and ended"*, with `run_config`, per-event `current_process` and `process_variant`, and `ts_utc`. `gt_manifest.json` is *"a per-session summary of the business processes it contains"*, with `executions[]` carrying explicit `start_ts`/`end_ts`, and a top-level **`expected_boundaries`**.

**Correction to my previous rule.** I wrote "prefer the manifest" with no justification. The defensible position: **they are not competing measurements of the same thing.**
- The **stream** is primary for *semantics and sequence*: switch vs. suspend, `split_id`, `phase`, task structure, variant at each moment.
- The **manifest** is primary for *interval extents and the scoring target*: it is the only source with explicit `start_ts`/`end_ts` per execution, and `expected_boundaries` is almost certainly the artifact the scorer derives from **[H]**.
- **Disagreement is data, not noise**, and the disagreement rate is itself a reportable finding under C9/C13.

**Revised policy**

| Class | Rule | Reversible? |
|---|---|---|
| **Untouched** | `process_code`, `case_id`, `variant`, `ts_utc`, `task_id` — never altered | n/a |
| **Deterministic repair** | Dissolve chunk continuity (`continues_from_prev/next`) into single intervals; normalise timestamps to a single UTC representation; rebuild global ordering across chunks | ✔ flagged |
| **Deterministic repair** | Collapse consecutive duplicate `process_started` with identical `(code, case_id)` and no intervening annotation (C13 names this defect explicitly) | ✔ flagged |
| **Marked disputed** | `process_switched_out` with no matching open process; manifest/stream interval disagreement beyond tolerance; zero or negative duration | ✔ retained with both values |
| **Never repaired** | Overlapping executions of different families — this is genuine interleaving, which is the phenomenon under study | n/a |

**Tuning vs. reporting split (new, and important).** Tune on **clean** executions only. Report the headline on **clean + deterministically repaired**. Report a sensitivity line on **all including disputed**. Tuning on disputed records risks fitting the generator's defects — a subtle form of the overfitting C6 warns about.

**Rules are frozen before results are seen.** Write and commit the canonicalisation module before running any segmenter; C15's git history makes that ordering visible and auditable.

---

## 9. Evaluation, screenshots, LLMs, and transfer

### 9a. Evaluation framework

| Metric | Role | Justification against the contract |
|---|---|---|
| **Boundary F1 at tolerance τ, reported as a curve** | **Report** | Directly measures C4(a). Tolerances must be given in **both** seconds **and event index** — B's event rate varies 62 ms to 6 s between events **[A]**, so a fixed second-tolerance is not a fixed difficulty. **Calibrate τ to A's observed execution-duration distribution** (P0-1), not to my previously invented ±1/2/5 s. |
| **Segmental F1 @ IoU {0.25, 0.5}** | **Report** | The only metric matching our output shape (labelled intervals). Penalises over- and under-segmentation symmetrically. |
| **Count ratio** | **Diagnostic** | Instantly exposes the failure F1 hides. |
| **WindowDiff** | **Report (secondary)** | Corrects Pk's asymmetry. Use **event index** as the atomic unit. |
| **Pk** | **Diagnostic only** | Report beside WindowDiff to show the difference; never alone. |
| **Boundary similarity (`segeval`)** | **Diagnostic** | Its real value is inter-coder agreement machinery — usable to quantify manifest-vs-stream disagreement (§8). |
| **ARI / NMI on matched segments** | **Report** | Measures C4(b). Must be reported **with the match rate**; ARI over three matched segments is meaningless. |
| **ARI on ground-truth segments** | **Tuning + diagnostic** | Isolates M4 from M1 entirely. |
| **Interruption recall** (fragments of one `case_id`/`split_id` receiving the same label) | **Report** | The only metric that measures M2b. |
| **Task-level F1 against `task_started`** | **Diagnostic** | New. Validates M6/the abstraction layer independently of M1. |
| **Ranking stability under ±20% perturbation** | **Report** | Serves C9 directly; the strongest honesty signal available. |
| **Variant accuracy** | **Deprioritised** | Report variant *counts and examples*, not accuracy \[survey L13]. |

**On `expected_boundaries`** — my previous document dropped it. It should be the **primary alignment target** if its semantics match our output, and P0-1 must inspect it first. If the scorer derives from it, evaluating against anything else is evaluating against the wrong thing.

**Discontinuous executions.** Report under two conventions side by side — fragment-level (strict) as headline, plus interruption recall as the diagnostic — and state the convention explicitly, since the scorer's convention is unknown \[survey L4].

### 9b. Screenshots / OCR / VLM — re-evaluated

The previous rejection inferred *"23% screenshots + rich titles ⇒ unnecessary"*. That is a non-sequitur, as the review says. The defensible position rests on three legs instead:

1. **Contract:** `DATA_SCHEMA.md` states screen text is available via `context.extracted_text` and *"you do not have to run OCR on the images"* **[S]** (C18). The assignment explicitly de-prioritises the vision path.
2. **Cost:** 4,746 images in B alone; A is ~8× larger by events **[S]**. CPU-only VLM inference over that is days, against a seven-day budget (C16).
3. **Marginal value is unmeasured** — and *that* is the honest gap. B's `extracted_text` is 4.6% populated and largely browser chrome **[A]**, which tells us the *text* channel is weak; it tells us nothing about the *image* channel.

**Revised disposition: conditional and selective, not rejected.**
- **[R]** Structured-telemetry-first. No global OCR/VLM pass.
- **[R]** Define a **marginal-value experiment (P2-2)**: take the executions where structured signals are *ambiguous* (context state uninformative, or two candidate labels within a small margin), sample ~30, have a VLM label their screenshots, and measure whether ambiguity resolves. **If ambiguous cases are <5% of executions, the ceiling on total gain is <5% and the branch closes on arithmetic alone.** That is a two-hour experiment with a decisive outcome.
- **[R]** Screenshots may matter more for **A** than for B if A's applications are desktop-native with generic titles **[U]** — this is the same hedge as Family B.
- **[R]** Privacy is a **report-level risk argument under C9**, not an assignment constraint: C14 explicitly permits LLM use. Say so honestly rather than dressing a cost decision as a compliance decision.

### 9c. LLM — four distinct roles, judged separately

My previous framing (LLM vs. clustering, judged on ARI) tested one role and implicitly dismissed three.

| Role | Value under the contract | Verdict |
|---|---|---|
| **Clustering mechanism** (assign executions to families) | C4 says label *text* is not evaluated, only consistency. An LLM brings label-drift risk across 15 sessions and non-determinism. | **Do not use.** Cheap clustering is better suited and reproducible. |
| **Semantic naming layer** (name the discovered clusters) | High for C7 and the report: management cannot act on `cluster_7`. Zero risk to the score, since naming is post-hoc and does not alter cluster membership. | **Use.** Cheap, safe, clearly valuable. |
| **Explanation layer** (why these events are one execution; what this process does) | High for C9 — the report must explain reasoning and evidence. | **Use.** |
| **Prototype-generation layer** (draft the procedure document / checklist / script skeleton from a discovered execution) | Potentially the core of the Step 3 prototype (§11), since C8 explicitly allows an AI-agent form. | **Candidate — evaluate in P1.** |

**Architecture must not depend on an LLM.** Roles 2–4 are additive layers; removing them degrades the report, not the pipeline. That is the right dependency direction under C16.

### 9d. A→B transfer, re-examined

**On "quantile thresholds transfer" — the review's scepticism is correct.** Quantile normalisation maps to a common *rank* scale but assumes the distributions are comparable in shape and that the same rank means the same thing. If A's executions are longer or its event rate differs, the 60th percentile of dwell is a different object. Quantiles reduce scale sensitivity; they do not confer domain invariance.

**Four-way classification:**

| Class | Contents | Justification |
|---|---|---|
| **1 · Fixed rules learned from A** | The *form* of the segmenter; the featurisation; the evidence sources and their ordering; the evaluation harness | Structural, vocabulary-free |
| **2 · Unsupervised adaptation on B** | Vocabulary (titles, routes, systems); cluster count; variant structure | B's content must come from B |
| **3 · Parameters re-estimated on B** | Dwell threshold, merge window, change-point penalty — re-estimated from **B's own distributions**, with the estimation *rule* fixed on A | The rule transfers, the value does not |
| **4 · Must NOT transfer** | A's process names, codes, `family_name` strings; A-derived keyword lists; A's `k`; any prompt naming A's processes | Direct leakage (C6) |

**Stronger discipline than quantiles [R]:** prefer parameters whose **sensitivity curve is flat** over parameters whose optimum is sharp — measured on A (P1-2), applied to B. A flat parameter is transferable *by evidence*; a quantile-expressed one is transferable *by assertion*. And keep the mechanical test: **the B pipeline must run with A's artifacts absent from disk.**

**What may legitimately be claimed about B:** the mechanism was validated on A; it was applied unchanged with parameters re-estimated on B; here is its output, its internal consistency, and the stability of its conclusions under perturbation. **No accuracy figure on B.**

### 9e. Choosing `k` on B

My previous "silhouette" suggestion was thin. Better, in priority order **[R]**:
1. **Stability under resampling** — cluster repeated bootstrap subsamples of B's executions and measure label agreement; choose the `k` whose partition is most reproducible. Stability is a better proxy for "real structure" than compactness.
2. **Minimum support** — a family must recur at least *n* times across at least two sessions to be called a process rather than an incident.
3. **Semantic coherence** — do members share a system/route signature a human would accept.
4. **Downstream usefulness** — does the choice change the automation ranking (§9a's stability metric).
5. Silhouette only as a tiebreak.

**Report the oracle-`k` experiment on A separately from the unknown-`k` experiment.** Oracle-`k` measures whether the *representation* separates families; unknown-`k` measures what we can actually do on B. Conflating them inflates the apparent result.

---

## 10. Libraries, re-examined

The review's challenge to PM4Py is correct and changes its status.

| Library | Previous verdict | Revised verdict |
|---|---|---|
| **PM4Py** | "Stage G only, one row per segment" | **The previous formulation was degenerate.** One row per execution gives a one-activity process model — worthless. **PM4Py becomes meaningful only if we reconstruct M6**: `case = execution`, `activity = step` (from context state, `field_identity_v1.stable_key`, or route transitions). Then DFGs, variant analysis and conformance checking all become genuinely useful for C7 ("different handling patterns within the same process") and for the report's visuals. **Status: useful component, conditional on M6.** |
| **`segeval`** | Definitely reuse | **Keep.** Still the highest value-per-hour reuse. Also supplies inter-coder agreement for §8. |
| **`ruptures`** | Definitely reuse | **Keep, conditional on Family B being needed.** Useful component, not core. |
| **`scikit-learn`** | Definitely reuse | **Keep** — clustering, ARI/NMI, bootstrap stability. Core. |
| **`rapidfuzz`** | Definitely reuse | **Keep** — sequence distance. Note we could implement edit distance ourselves in 20 lines; `rapidfuzz` is a speed convenience, not a capability. Honest classification: **useful component, easily replaceable.** |
| **`networkx`** | Core for Family D | **Demoted to optional** — with Family D reduced to hash co-occurrence, a dict of sets suffices. **Unnecessary dependency unless P2-1 succeeds.** |
| **`stumpy`** | Optional | **Still optional, and probably unnecessary**: our sequences are categorical, and matrix profile is built for continuous signals. Sequential pattern mining is the better fit. **Do not add.** |
| **PrefixSpan / SPMF** | Optional | **Promote to P1** given Family C's reclassification toward M4/M5 and procedure extraction. Prefer `prefixspan` (pure Python) over SPMF (JVM) for a seven-day budget. |
| **`pandas`** | Core | **Keep.** |
| Japanese NLP / OCR / VLM | Rejected | **Conditional** — see §9b. Not installed now. |

**Principle applied:** a library earns its place by solving a *core* problem or removing a *real* implementation risk. `networkx` and `stumpy` currently do neither.

---

## 11. Automation layer and prototype

### 11a. Measured / Derived / Assumed / Unknown

| Quantity (C7) | Class | Note |
|---|---|---|
| Which processes occur | **Derived** | From `segments.jsonl` labels; inherits all M1/M4 error |
| How often each occurs | **Derived** | Count per session; extrapolation beyond the sample is **Assumed** |
| How much time each consumes | **Derived, ordinal only** | C10 forbids absolute claims |
| **How many people** | **Derived** | `source.username_hash` — 4 distinct in B **[A]**, corroborated by 4 `machine_id` and 4 `firebase_uid` **[A]**. State the one-account-one-person assumption explicitly. |
| Different handling patterns (variants) | **Derived** | M5; low confidence \[survey L13] |
| Application count / cross-app transitions | **Measured** | Note 80% of B's app switches are Edge→Edge **[A]** — report tab switches and app switches separately or the number misleads |
| Repetition / stereotypy | **Derived** | Mean pairwise sequence similarity within a family — a direct automatability proxy |
| Human decision points | **Derived, weak** | Free-text fields are evidence of judgement (e.g. B's `#pi-note` textarea, placeholder *"enter processing details / confirmation comment"* **[A]**) |
| Determinism / data availability | **Derived, weak** | `dataflow_v2` coverage is 4.2% **[A]** — too thin to carry this |
| Exception rate | **Unknown** | `browser_error` count (38 in B **[A]**) is a proxy at best |
| Integration feasibility | **Assumed** | Requires knowing whether target systems expose APIs |
| ROI in currency | **Unknown** | Volumes, wages, error costs absent. **Do not compute.** |

### 11b. Prototype

C8 leaves the form open and says the scope decision is itself part of the ROI answer; C9 requires justifying the form *and* why alternatives were rejected. The binding constraint is that **the target systems are localhost SPAs we do not have** **[A]** — so anything that actuates them requires building a mock, which C9 would then require us to disclose.

Ranked by *demonstrating the core contribution* rather than by ease:

| Rank | Prototype | Demonstrates | Concern |
|---|---|---|---|
| **1** | **Procedure/SOP generator**: from discovered executions of one family, emit the step-by-step procedure (steps from M6, screenshots as illustrations) | The whole chain — segmentation → identity → step structure → a usable artifact. Needs **no target system**. Uses the 4,746 screenshots we otherwise discard. Directly mirrors work we can *see* being done by hand in B (Word files named `nyusha_checklist_shinsotsu_batch`, `keiyaku_kaijo_tetsuzuki`) **[A]** | Is it "automation"? Argue it as work *elimination* — the document is the deliverable a human currently produces |
| **2** | **Executable workflow skeleton**: emit a runnable script/workflow definition for the dominant variant, with human-decision points explicitly marked as stubs | Closest to C8's "deterministic script" / "workflow definition". Marked stubs honestly encode C9's "what manual work remains" | Cannot be executed without a target |
| **3** | **Automation candidate recommender** | Step 2's output made interactive | Analysis, not automation |
| **4** | **Mock end-to-end automation** (build a stand-in for one route, drive with Playwright) | Most visually convincing | Expensive; the automation is against our own mock, which weakens rather than strengthens the claim |
| **5** | **Live monitoring assistant** | Least aligned with the brief | Weakest demonstration |

**[R]** Decide after Milestone equivalent to P1, not now. But note that options 1 and 2 both depend on **M6 (step structure)** — which is further evidence that the omission of M6 from the previous decomposition was the most consequential structural error in it.

---

## 12. Experiment plan and decision tree

### Decision tree

```
P0-1  Inspect A's GT structure (schema-guided, minimal read)
      ├─ expected_boundaries aligns with our output shape
      │     → it becomes the primary alignment target
      └─ it does not → align on executions[].start_ts/end_ts; record why

P0-2  Baseline suite on A (single-segment / chunk / gap-threshold / random)
      → establishes the floor and ceiling that C5 requires us to define

P0-3  Is context state informative on A?
      ├─ YES → Family A is the M1 primary; Family B becomes optional insurance
      └─ NO  → Family A collapses; PROMOTE Family B to primary immediately,
               and re-open screenshots (§9b) since A would then be title-poor

P0-4  Is identity learnable on GT segments (oracle-k)?
      ├─ ARI high → M4 is separable and cheap; spend the budget on M1
      └─ ARI low  → representation is wrong; fix abstraction before segmentation
                    (no amount of M1 work will produce consistent labels)

P1-1  Does task structure (M6) recover against task_started?
      ├─ YES → enables PM4Py downstream AND prototype options 1–2
      └─ NO  → prototype shifts toward option 3; PM4Py stays degenerate

P1-2  Penalty/threshold sensitivity curves
      ├─ flat plateau → parameter is transferable by evidence
      └─ sharp peak   → do not transfer; re-estimate on B and say so

P1-4  Motif coverage of A's executions
      ├─ ≥ threshold → use for family/variant discovery and procedure extraction
      └─ below       → auxiliary evidence only (NOT discarded)

P2-1  dataflow_v2 value-hash containment vs. case_id
      ├─ above baseline & useful coverage → weak boundary-veto feature
      └─ otherwise → close the branch, record the negative result (C15)

P2-2  VLM marginal value on ambiguous executions only
      ├─ ambiguous cases < 5% of executions → close on arithmetic
      └─ otherwise → selective visual reasoning on that subset only
```

### Prioritised plan

**P0 — before any architecture decision. Requires A.**

| # | Hypothesis | Data | A? | GT? | Method | Metric | Artifact | Effort | Decision | Kill criterion |
|---|---|---|---|---|---|---|---|---|---|---|
| **P0-1** | A's GT can be canonicalised into executions + fragments + tasks, and `expected_boundaries` is the alignment target | A | **Yes** | Yes | Read `gt.jsonl` + `gt_manifest.json` for **a sample of ~5 sessions first**, not all 63 | duplicate-start rate; unpaired switch-out rate; manifest-vs-stream disagreement rate; fragments per `case_id` | `gt_canonical` module + a defect report | **1 day** | Everything | — |
| **P0-2** | Trivial baselines bound the problem | A | Yes | Yes | single-segment, one-per-chunk, gap-threshold, random-matched-count | full metric suite | baseline scorecard (a C5 deliverable) | 0.5 d | Defines "good enough" | — |
| **P0-3** | Context state is informative on A | A | Yes | Yes | Family A across a dwell sweep | boundary F1 curve, count ratio, segmental F1@IoU | sweep plot | 0.5 d | Family A in/out; whether B is promoted | No dwell value beats P0-2's best baseline |
| **P0-4** | Identity is learnable from GT segments (oracle-`k`) | A | Yes | Yes | featurise true executions; cluster; ARI vs `process_code` | ARI / NMI | ARI table | 0.5 d | Whether M4 is cheap | ARI near chance ⇒ fix representation first |

**P0 total ≈ 2.5 days, and it selects the architecture.**

**P1 — strongly useful**

| # | Hypothesis | A? | Effort | Decision enabled |
|---|---|---|---|---|
| **P1-1** | Steps recoverable against `task_started` | Yes | 0.5 d | PM4Py downstream; prototype options 1–2 |
| **P1-2** | Key parameters have flat sensitivity curves | Yes | 0.5 d | What may transfer to B |
| **P1-3** | Combining evidence sources beats the best single source | Yes | 0.5 d | Whether the hybrid earns its complexity |
| **P1-4** | Motifs cover a useful fraction of executions | Yes | 0.5 d | Family C's role in M4/M5 |
| **P1-5** | LLM naming produces stable, human-acceptable family names | No (B ok) | 0.5 d | Report quality; prototype option 1 |
| **P1-6** | End-to-end run on B produces a schema-valid `segments.jsonl` | No | 0.5 d | **Ships the required deliverable early** |

**P2 — only if P0/P1 indicate value**

| # | Hypothesis | Effort | Kill criterion |
|---|---|---|---|
| **P2-1** | `dataflow_v2` hash containment respects `case_id` | 0.5 d | Containment ≈ baseline, or <10% execution coverage |
| **P2-2** | Screenshots resolve ambiguous executions | 0.5 d | Ambiguous cases <5% of executions |
| **P2-3** | Change-point detection beats dwell where dwell is weak | 0.5 d | No region where it wins |

**Note on C15:** every kill criterion above produces a documented negative result, which is itself a graded deliverable. No P-experiment is wasted effort.

---

## 13. What changed

**KEEP** — evaluation-harness-first; identity evaluated on GT segments; GT reporting tiers; leakage checklist and the "runs without A on disk" test; tolerance *curves* not single numbers; count ratio; ranking stability; PM4Py is not a segmenter; ScreenRPA/OpenAdapt/SmartRPA rejected; B's semantics are rich (as a B-fact); clipboard has no content.

**MODIFY** — *"idle gaps are dead"* → gaps are a weak feature and a permanent baseline, and A is unknown. *"Sparse semantics is not our problem"* → true for B, unverified for A, and the schema warns population varies. *"Prefer the manifest"* → the two GT sources represent different things; disagreement is a reportable finding. *"Quantile thresholds transfer"* → prefer parameters with measured flat sensitivity. *"PM4Py at Stage G, one row per segment"* → degenerate; PM4Py earns its place only with M6 step structure. *"LLM vs clustering on ARI"* → four separate roles, three of which that test does not address. *Invented success thresholds* → replaced with relative criteria. *"4 machines = 4 people"* → use `source.username_hash` (4 distinct, corroborated).

**DEFER** — provenance features (P2-1); screenshots/VLM (P2-2, selective); change-point detection (P1/P2, promoted immediately if P0-3 fails); hybrid integration; prototype form (decide after P1).

**DROP** — only where evidence justifies it: `correlation.triggered_by`, `correlation.correlated_events` and `extensions.cross_layer_v1` as execution-identity signals (**refuted [A]**); connected-component-equals-execution as a formulation (**unsound**); `networkx` and `stumpy` as dependencies (**unnecessary**); the gap-*threshold* as a candidate *method* (retained as a baseline).

**NEW** — the Assignment Contract as the reference document; M2a/M2b/M2c and **M6 (task/step structure)** added to the decomposition; Family G (task/step anchoring); `expected_boundaries` restored as the likely alignment target; task-level F1 as a new diagnostic; tuning-vs-reporting GT split; stability-based `k` selection; oracle-`k` vs unknown-`k` separated; the four LLM roles; the marginal-value experiment design for screenshots; PM4Py's conditional promotion.

**The distinction the review insisted on.** *Evidence it is bad*: the three correlation/cross-layer fields, and connected-component identity. *No evidence it is good yet*: screenshots, VLMs, change-point detection, motifs, hybrids, `dataflow_v2` — all retained, all gated.

---

## 14. Risk register

| # | Risk | Evidence | Severity | Mitigation |
|---|---|---|---|---|
| R1 | **A's window titles are generic**, collapsing Family A | Schema says population "varies" **[S]**; B is rich **[A]**; A is **[U]** | **High** | P0-3 tests it on day 1; Family B is the pre-planned hedge |
| R2 | `extensions.*` absent or different in A | Not in the schema contract **[S]** | Medium | No component may depend on them without a fallback (now true after the demotion) |
| R3 | GT canonicalisation consumes more than a day | Two sources, three levels, documented defects **[S]** | Medium | Start with ~5 sessions; expand only if stable |
| R4 | Over-segmentation proves irreducible | 1 state change / 2.8 events in B **[A]** | Medium | P0-2's baselines bound what is achievable and make the finding reportable |
| R5 | Parameters tuned on A do not transfer | Survey L7 | **High** | Flat-sensitivity preference (P1-2); re-estimate on B; claim nothing about B's accuracy |
| R6 | Time spent on M1 crowds out Steps 2–3 | C1, C16 | **High** | Ship `segments.jsonl` for B at P1-6, early and imperfect |
| R7 | Prototype has no target system | Localhost SPAs unavailable **[A]** | Medium | Prefer prototypes needing no target (§11b options 1–2) |
| R8 | LLM label drift across sessions | Survey; non-determinism | Low (after demotion) | LLM confined to naming/explanation; clustering stays deterministic |
| R9 | Sample size too small for B's operational claims | 15 sessions, ~3.2 h total **[A]** | Medium | Report counts with explicit sampling caveats; never annualise |
| R10 | Screenshot volume tempts an expensive detour | 4,746 in B **[A]**; A ~8× larger **[S]** | Medium | P2-2's arithmetic kill criterion closes it fast |

---

## 15. The first engineering task, and the artifact it produces

**Task.** Build the **normalisation + ground-truth canonicalisation + evaluation harness** — in that order, in one module, over **a sample of ~5 Dataset A sessions**, before any segmenter exists.

**Why this and not the provenance dump I previously proposed.** The provenance question is now answered for three of its four fields and demoted to P2 for the fourth. The harness, by contrast, is required by every P0 experiment, is mandated in substance by C13 ("verify consistency yourself") and C5 ("deciding what counts as good enough is part of the task"), and is the one artifact whose value does not depend on any experimental outcome. It is also the only way to avoid the failure the survey documented in the literature — four papers, four incompatible metrics — happening inside our own repository.

**Why a 5-session sample and not all 63.** It exercises every code path — multi-chunk sessions, duplicate starts, unpaired switch-outs, suspended executions — at a fraction of the cost, and defers bulk processing until the loader is known to be correct. This respects the instruction not to spend compute on A for schema discovery: we are reading A for *values we cannot get anywhere else* (defect rates, duration distributions, fragment counts), not to learn the schema.

**Concrete artifact — four files plus one report:**

1. `normalise.py` — chunks → one ordered event table per session; chunk boundaries dissolved (C12); `extensions.*` flattened into named columns **with every one optional**.
2. `gt_canonical.py` — `gt.jsonl` + `gt_manifest.json` → three tables: `gt_events`, `executions` (with `repair_flags`, `confidence`, and both sources' values retained on disagreement), and `executions_canonical` (fragments grouped by `case_id`/`split_id`, `intervals[]`). Canonicalisation rules **committed before any segmenter runs** (C15 makes the ordering auditable).
3. `evaluate.py` — boundary F1 at τ in **both** seconds and event index; segmental F1@IoU; WindowDiff and Pk (via `segeval`); count ratio; ARI/NMI with match rate; interruption recall; tier-1/2/3 reporting.
4. `baselines.py` — single-segment, one-per-chunk, gap-threshold, random-matched-count.
5. **`GT_DEFECT_REPORT.md`** — duplicate-start rate, unpaired switch-out rate, manifest-vs-stream disagreement rate, fragments per canonical execution, execution-duration distribution, tasks per execution.

**Success.** The four baselines score end to end; the tolerance curve is calibrated to A's observed execution durations rather than to an assumed ±2 s; and the defect report answers, with numbers, what C13 only warns about qualitatively.

**Decision it enables.** All of P0. And the defect report is, on its own, publishable evidence for C9 — a documented account of what the ground truth actually contains, which is the kind of finding the brief says it is looking for.
