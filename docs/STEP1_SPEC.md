# STEP 1 — Business-Process Execution Inference
## 0. The objective, stated once

> Given a chronological stream of low-level desktop telemetry with no process labels, no case
> identifiers and no task boundaries, infer coherent **business-process execution intervals** —
> including executions whose boundaries fall **inside** an existing activity block — and assign
> **stable labels** so that repeated executions of the same process receive the same label.

Dataset A is the **laboratory**: it has ground truth, and every number we report comes from it.
Dataset B is the **client dataset**: the same frozen code runs on it and produces
`segments.jsonl`. Nothing dataset-specific crosses from A to B (ADR-010).

Step 1 is an **enabling capability, not the product.** It is finished when it is good enough to
support Steps 2 and 3, not when it is optimal.

---

## 1. The conceptual correction

The previous architecture treated the activity block as the atomic unit of reasoning, which in
practice made it the candidate space for business-process boundaries. Phase 1 measured the
consequence. The correction is recorded in **ADR-015**:

| | |
|---|---|
| **OLD** | activity block ≈ business-process boundary unit |
| **NEW** | activity block = activity / context / compression / identity **container**. A business-process execution boundary may occur **inside** a block. |

### What the measurement actually showed

Measured in Phase 1 over 63 A sessions (`docs/phases/PHASE_1_REPORT.md` §8):

| Quantity | Value |
|---|---|
| GT boundary points scored | 3,327 |
| falling strictly inside a block | 74.5% |
| median distance to nearest block edge | 1,040 ms |
| reachable within τ=1 s / 2 s / 5.25 s / 10.5 s | 47.3% / **59.9%** / 82.8% / 92.2% |

**This must not be read as "the representation can only achieve 60%."** It is the reachability
of **one candidate space** — block edges — under one decision rule. The events that would
express the missing boundaries are still present inside the blocks; nothing downstream reads
them. The distinction that governs every decision in this document:

| | Meaning | Response |
|---|---|---|
| **(A) representation loss** | information destroyed by normalisation or blocking and not recoverable from the block's own events | rebuild the layer that destroyed it |
| **(B) candidate-space limitation** | information present in the retained events but never surfaced as a boundary candidate | add a finer candidate layer |

Experiment **S-E2** exists to decide, per missed boundary, which of the two applies.
**Do not rebuild the perception layer on suspicion.** Do not invent additional information-loss
problems without measured evidence.

---

## 2. Architecture — Two Levels, One Gate

```
raw telemetry
   │
   ├─ 1. perception / normalisation            deterministic   normalise.py    [KEEP]
   │
   ├─ 2. activity blocks  (CONTAINERS)         deterministic   blocks.py       [KEEP]
   │        blocks retain access to their own events
   │
   ├─ 3. candidate boundary generation         deterministic   candidates.py   [NEW]
   │        block edges  ∪  intra-block event-level candidates
   │
   ├─ 4. candidate scoring                     deterministic   score.py        [NEW]
   │
   ├─ 5. ambiguity gate                        deterministic   gate.py         [NEW]
   │        confident → decided here;  uncertain tail → 6
   │
   ├─ 6. semantic adjudicator                  LLM (bounded)   adjudicate.py   [NEW, ablatable]
   │        sees a TEKG local-evidence window; returns boundary?/label/justification
   │
   ├─ 7. constrained global inference          deterministic   decoder.py      [NEW]
   │        DP / Viterbi-style pass under hard constraints
   │
   ├─ 8. execution labelling                   deterministic   label.py        [NEW]
   │
   └─ segments.jsonl
```

The TEKG (`tekg.py`) is **retained unchanged** in its existing role: it packages typed local
evidence for stage 6 and explains decisions afterwards. It is not an inference engine and
connected components are never executions (ADR-005, unchanged).

### Why the LLM sits at stage 6 and nowhere else

The LLM is **not the primary segmentation mechanism.** Stages 3–5 and 7 are deterministic,
reproducible, cheap, testable without an API key, and cannot hallucinate a boundary. The LLM is
given the residue that deterministic evidence cannot settle — which is the one place semantic
judgement is genuinely required — and its contribution is **measured by ablation** (S-E5). If
the ablation shows negligible value, it is removed and that is a legitimate result, reported.

`--no-llm` must remain a supported, tested execution mode at every stage of development.

---

## 3. Stage contracts

### 3.1 Perception and blocks — KEEP, two surgical fixes only

`normalise.py` and `blocks.py` are **not redesigned**. Two corrections, both evidence-backed:

| ID | Defect | Location | Fix |
|---|---|---|---|
| **D-1** | `_TITLE_STRIP` strips the Edge profile suffix but not the equivalent Chrome/other-browser suffix, so the same page can key as two surfaces | `normalise.py::_TITLE_STRIP` | generalise the browser-suffix pattern; keep it structural (a trailing ` - <browser name>` / ` - Profile N - <browser>` form), not an allow-list of browser names |
| **D-2** | `"Untitled"` in `NOISE_TITLE_HINTS` marks genuine Notepad work as noise | `blocks.py::NOISE_TITLE_HINTS` | remove the bare `"Untitled"` hint, or scope it to browser surfaces only |

Both fixes require a regression test and a before/after block-count comparison on A **and** B.
If either fix moves block counts by more than a few percent, say so in the report.

**Already-settled behaviour that must not be re-litigated** (each was tested against data):

- `L1` / `SYSTEM` events attach to the open block and can never open one (**ADR-012**).
- Browser tab is carried-forward state, scoped to an unchanged active app, seeded from `L2` only
  (**ADR-013**).
- Surface type is structural from the presence of a usable http(s) origin — no browser
  allow-list (**ADR-013**).
- `route_of` returns the hash route when present, else the URL path, **never** the origin
  (**ADR-013**).
- Self-referential `app_switch` events are **not** suppressed; 176 of 738 on B carry a different,
  meaningful window title (**ADR-014**).
- A missing title or URL is **missing information**, not a distinct surface state
  (`blocks.has_discriminator`, ADR-012).
- Chunks are dissolved and may never appear as a predicted boundary (**ADR-001**).

**New hard requirement:** every block must expose the event rows it contains, so stage 3 can
place a candidate between any two of them. If `blocks.jsonl` does not carry them, it must carry
a `(first_seq, last_seq)` span into the normalised event stream, and `candidates.py` must be
able to recover the rows deterministically from the same session load.

### 3.2 Candidate boundary generation — `procmine/candidates.py` (NEW)

Produces a candidate set **strictly finer** than block edges. It must be able to place a
boundary **between two events inside one block**.

```python
Candidate = dict  # written to build/<ds>/candidates.jsonl
{
  "session_id": "ses_...",
  "cand_id": "ses_...#c00412",
  "at_seq": 8123,            # boundary sits BEFORE this event index
  "at_ms": 1782931329501,
  "block_id": "ses_...#b0042",
  "kind": "block_edge" | "intra_block",
  "features": { ... },       # §3.2.1, all deterministic, all numeric or boolean
}

def generate(rows, blocks, cfg) -> list[Candidate]
```

Contract:

1. Every block edge is a candidate (the old candidate space is a strict subset).
2. Intra-block candidates are generated from event-level structure, not from a fixed stride.
3. Deterministic and reproducible; no randomness, no GT input.
4. The generator emits candidates; it does **not** decide. Scoring is stage 4.
5. Candidate density is a reported number. A generator that nominates every event is not a
   candidate generator — report `candidates / event` and `candidates / block`.

#### 3.2.1 Signals to featurise — hypotheses, not rules

Compute these as features. **Do not hard-code any of them as a boundary rule.** S-E3 establishes
which actually carry evidence on A.

- `event_type` of the event at and around the candidate
- `ms_since_last`, and the same normalised by the session's rolling median gap
- local event density / lull relative to the enclosing block
- `browser_navigation` present in a small window
- `app_switch` present in a small window
- window/surface change (including the sub-block case where the title changes)
- route change within the same origin
- origin/system change
- field identity change (`extensions.field_identity_v1`, optional — must degrade when absent)
- clipboard activity in a small window
- shortcut activity in a small window
- browser form input in a small window
- transition between interaction modes (typing → navigating → copying)
- position within the enclosing block (start / middle / end)

Prior evidence from the G1 analysis, comparing missed GT boundaries against interior control
points sampled ±2 s away. **These are prior hypotheses to be re-measured, not settled facts,**
and they were computed on the uncorrected GT population:

| Signal | near missed boundary | interior control | direction |
|---|---|---|---|
| `browser_navigation` | 8.5% | 2.3% | enriched ≈3.7× |
| `app_switch` | 71.0% | 46.2% | enriched ≈1.5× |
| `browser_click` | 4.3% | 28.4% | depleted |
| `clipboard_change` | 0.6% | 30.5% | strongly depleted |
| `shortcut` | 1.6% | 53.4% | strongly depleted |

Depletion is evidence too: a signal that is strongly *absent* at boundaries is a useful negative
feature.

### 3.3 Candidate scoring — `procmine/score.py` (NEW)

A transparent, inspectable score per candidate in `[0, 1]`.

- Start with a **weighted linear combination of the features**, weights fitted or hand-set from
  S-E3's contingency evidence. Nothing heavier unless a lighter thing has been shown to fail.
- If a learned scorer is used, it must be trained **only on the `clean` GT tier**, evaluated
  leave-one-session-out, and must not receive any GT field as an input feature.
- The score must be explainable: the top contributing features per candidate are written out and
  are what the adjudicator and the final report cite.

### 3.4 Ambiguity gate — `procmine/gate.py` (NEW)

```python
def route(candidates_scored, cfg) -> list[dict]
# per candidate: {"route": "rule" | "llm", "rule_decision": bool, "ambiguity": float}
```

- Confident-boundary and confident-no-boundary bands are decided deterministically.
- Only the uncertain middle band routes to stage 6.
- **Target routing fraction ≤ 15% of candidates.** Report the histogram every run. If routing
  exceeds 40%, the gate is too weak — fix the gate before spending on calls.
- The gate must be able to run in `--no-llm` mode, in which every routed candidate falls back to
  its deterministic `rule_decision`.

Note the Phase 1 warning that still applies: the gate **cannot** simply route "surface changed"
transitions — those are the easy ones. Its discriminator must work on same-surface transitions.

### 3.5 Semantic adjudicator — `procmine/adjudicate.py` (NEW, LLM, bounded, ablatable)

Bounded to exactly three jobs:

1. **boundary / no-boundary** for one candidate, given its local neighbourhood;
2. **process identity** — a normalised label for the segment being opened or continued;
3. a **concise justification** naming the evidence it used.

Input is the existing TEKG local-evidence window (`context.local_evidence`,
`context.build_payload`) extended to carry the candidate's own top features. The existing
constraints are retained verbatim and are non-negotiable:

- the model never sees or emits a timestamp, duration, interval, absolute index or `block_id`
  (ADR-006, enforced structurally in `context.py`, asserted in `tests/test_context.py`);
- structured output via `pydantic` + `instructor`, enum-constrained;
- content-hash cache committed to git, so every experiment replays without an API key;
- persistent failure returns `UNCERTAIN` and the pipeline completes;
- the prompt is versioned in `procmine/prompts/` and must be domain-neutral (ADR-010).

Deliberately **out of scope for the first implementation**: agentic tool use, `expand_window`,
`similar_executions`, retrieval/execution memory, few-shot retrieval, screenshots/vision,
fine-tuning. Screenshots may become relevant for adjudication later; they are **not** a
dependency now, and `context.extracted_text` (~4% coverage) is **not** a central feature
(ADR-009 unchanged).

**Ablation is mandatory (S-E5).** If the LLM arm does not beat the deterministic arm on the
ambiguous stratum, it is removed from the critical path and the finding is written up.

### 3.6 Constrained global inference — `procmine/decoder.py` (NEW)

A dynamic-programming / Viterbi-style pass over the scored, gated candidates, choosing the
globally best segmentation subject to **hard constraints (rejections, not penalties)**:

- chronological ordering; segments within a session ordered and non-overlapping;
- no zero-length segment;
- no segment below the duration floor observed in A's scoreable canonical executions
  (Phase 1 measured median canonical duration 34.8 s, p10 23.9 s — recompute on the corrected
  population before using it);
- an upper bound on segment duration only where A's distribution justifies one;
- label consistency within a segment;
- interruption / resumption handled only where evidence supports it; a resumption must reference
  a genuinely open earlier execution, otherwise it is demoted.

Deliberately **not** in scope: a process-mining engine, `pm4py`, SOP/step discovery. **ADR-008's
precondition is unmet** — A's `task_started` is 1:1 with executions (2,009 / 2,009) and provides
no internal step structure. Do not add `pm4py` because it sounds appropriate.

### 3.7 Labelling — `procmine/label.py` (NEW)

The label must represent inferred **business-process identity**, not the current app or window.

- Derive a structural signature per segment: surface-key sequence, route/path set, origin set,
  interaction profile (typing / navigation / clipboard / form-input mix), window-title evidence.
- Cluster signatures so that repeated executions of the same process receive the same string.
- **Labels must be stable across sessions** — this is half of what the assignment scores.
- `k` is chosen by stability on the dataset being processed. A's `k` never transfers to B
  (ADR-010).
- The adjudicator may **normalise** a label; clustering decides membership.

**No GT leakage, absolutely.** `process_code`, `case_id`, `variant`, `family_name`, `split_id`,
`phase`, `task_id` and `expected_boundaries` are evaluation-only. No inference module may import
`gt.py` or read any `build/dataset_a/gt_*` or `executions*` artifact. Add a test that asserts
this by import inspection.

---

## 4. Output contract

`segments.jsonl` is unchanged and remains governed by `DATA_CONTRACT.md` §6: exactly four keys,
`session_id` the exact session directory name, ISO-8601 UTC `Z` second precision, `start < end`,
ordered and non-overlapping within a session, stable labels, no boundary placed because of a
chunk edge.

```json
{"session_id": "ses_...", "start": "2026-07-01T18:32:32Z", "end": "2026-07-01T18:35:41Z", "label": "payroll_item_processing"}
```

The output must support: multiple executions per session; **boundaries interior to existing
blocks**; interruption/suspension/resumption where identifiable; repeated labels; and no reliance
on recording-chunk boundaries.

`segments_rich.jsonl` (same rows plus `exec_uid`, `confidence`, `evidence`, `fragments`,
`candidate_ids`) is written for internal inspection and is **never submitted**.

The timestamp/index representation must stay compatible with the existing evaluation harness
(`evaluate.py` works in `(start_ms, end_ms)` intervals and converts to the event-index domain).

---

## 5. Evaluation

The protocol lives in `EVALUATION_PROTOCOL.md` and is **not duplicated here**. Step 1 adds two
requirements to it, now recorded there as §8 and §9:

1. **GT population accounting is mandatory.** Every reported number states which population it
   was computed on. The populations are fixed and measured:

   | Population | n | Definition |
   |---|---|---|
   | raw manifest executions | 2,009 | `gt_manifest.json` rows |
   | raw with no end timestamp | 257 | of the above |
   | canonical executions | 1,819 | after fragment grouping by `split_id` |
   | of which interrupted | 98 (5.4%) | `n_fragments > 1` |
   | **unscoreable** | **230** | canonical records with no usable interval |
   | **scoreable canonical** | **1,589** | the denominator for every accuracy figure |
   | confidence tiers | clean 1,756 / repaired 63 | ADR-011 tiering |

2. **Candidate reachability is reported separately from segmentation quality** and is never
   presented as an accuracy figure.

Required measurements for Step 1:

| # | Measure | Note |
|---|---|---|
| 1–3 | boundary precision, recall, F1 | at τ ∈ {1, 2, 5, 10} s; never quote one τ |
| 4 | segmental F1 @ IoU, WindowDiff, Pk | existing harness |
| 5 | **candidate-set reachability** | candidate space only — not an accuracy number |
| 6 | count ratio / over-segmentation | B5-dwell's 2.84 is the number to beat |
| 7 | per-session variability | LOSO spread, not just the mean |
| 8 | performance on interrupted executions | `interruption_recall`, always read with count ratio |
| 9 | repeated-process performance | A cannot test this; see S-E6 |
| 10 | runtime, LLM call count, cost | measured, not estimated |

Baselines `B0-single`, `B1-chunk`, `B2-gap`, `B3-random`, `B4-surface`, `B5-dwell` are retained
permanently and re-scored on the corrected population. For reference, the existing 5-session
scorecard (τ=2.25 s): B0 0.000 · B1 0.008 · B2 0.089 · B3 0.109 · B4 0.247 · **B5 0.258**
(recall 0.504, precision 0.173, count ratio 2.84).

**Never report a single F1 without its precision, recall, count ratio, tolerance and operating
point.**

---

## 6. Experiments — Exactly Six, Each With a Decision It Changes

Every experiment produces `experiments/<exp_id>/{config,metrics,samples,report}` per
`EXPERIMENT_PROTOCOL.md`. **No result is reported from console scrollback.** The Phase 1 ceiling
analysis was computed ad hoc and never committed as an experiment — that is precisely the defect
S-E1 exists to repair.

### S-E1 — GT metric correction
Recompute block-edge reachability on the **scoreable canonical** population (n=1,589), per tier,
with exact denominators recorded. Unify the τ grid — the Phase 1 report used
{1000, 2000, 5250, 10500} ms while `experiments/E11-baselines/config.json` used
{1000, 2250, 5500, 11250} ms; pick one, justify it from A's duration distribution, and restate
every prior figure on it. Re-derive the 59.9% figure and state whether it holds.
**Also verify:** the report's "98.4% of missed boundaries have no surface change" is computed
over 1,663 execution-to-execution transitions (681 of 692 missed), not over the 3,327 boundary
points; an independent recomputation over all boundary points gave ≈69.8%. Both may be correct on
their own denominators — state the denominator wherever the figure appears.
**Also:** one A session has GT extending far beyond the telemetry duration. Report it as a single
identified session, never as a dataset-wide algorithmic failure.
**Decision it changes:** whether any subsequent number needs restating.
**Cost:** ~1 h.

### S-E2 — Miss attribution
For the missed boundaries, classify each into exactly one of:
(a) information destroyed by preprocessing; (b) information preserved inside blocks but not
surfaced as a candidate; (c) absorbed micro-excursion (`blocks._absorb`, the `A|x|A → A` rule);
(d) ambiguous — no visible surface change and no discriminating event; (e) telemetry/GT mismatch
(lead/lag, truncation, unscoreable record).
Phase 1 measured a systematic **+820 ms lead** of GT over telemetry — category (e) must account
for it explicitly rather than absorbing it into (d).
**Decision it changes:** a large (a) fraction means the perception layer must be rebuilt and
**S-E3 does not run yet**. A large (b)+(c) fraction confirms the candidate-layer plan.
**Cost:** ~1 h.

### S-E3 — Intra-block candidate reachability  ← **the decisive experiment**
Implement the simplest event-level candidate generator (§3.2) and measure reachability at
τ ∈ {1, 2, 5, 10} s against block-edge-only reachability, on the same corrected population.
Report candidate density alongside — reachability bought by nominating every event is not a
result. Also produce the feature × (boundary / non-boundary) contingency table that
parameterises the scorer.
**Decision gate — engineering judgement, not a statistical criterion:**

| Outcome | Action |
|---|---|
| reachability in the high 80s or better, at sane density | proceed with this architecture |
| roughly < 75% | **STOP.** Investigate representation loss before adding any intelligence. Do not proceed to S-E4. |
| in between | proceed, but report the ceiling honestly and cap effort on stages 6–7 |

**Cost:** ~2 h. **Nothing downstream is built before this returns.**

### S-E4 — Minimal end-to-end Step 1
Run stages 3→4→5(rule-only)→7→8 on A. Measure actual segmentation quality against all six
baselines, tiered, with LOSO spread and ±20% parameter perturbation.
**Decision it changes:** whether the deterministic system is already sufficient to ship.
**Cost:** ~3 h.

### S-E5 — LLM ablation
Two arms over a frozen stratified candidate sample: deterministic-only vs deterministic +
bounded adjudication. Report per stratum (easy / ambiguous / same-surface / interruption), not
just overall — an overall average dilutes exactly the effect being measured. Report routing
fraction, cost, latency and run-to-run stability at temperature 0.
**Decision it changes:** the LLM stays on the critical path, or it is removed and an ADR records
why. A clean negative result is a deliverable.
**Cost:** ~2 h.

### S-E6 — Same-process edge case
A cannot test consecutive executions of the same process: **0 of 1,689 consecutive execution
pairs share a process code.** So `NEW_EXECUTION` (same process twice in a row) is untestable on
A and any machinery for it is unvalidated. Inspect Dataset B — and any other available source —
for evidence that consecutive same-identity executions occur, and record what the system does
when they do.
**Decision it changes:** whether a same-process-repetition mechanism is justified at all. It is
**not** a licence to expand the architecture.
**Cost:** ~45 min.

**STOP after these six** unless a result exposes a concrete correctness problem. In particular,
do not run further block-hyperparameter sweeps: `experiments/E01-block-sweep` is closed, and
S-E1/S-E2 explain why the headline number is insensitive to those parameters.

---

## 7. Implementation order

Strictly sequential. Each step ends with a committed artifact and `make test` green.

| # | Do | Gate |
|---|---|---|
| **1** | **Emit `segments.jsonl` for Dataset B from the current blocks.** Imperfect and honest. The required deliverable currently does not exist; this converts the repository from unsubmittable to submittable, and everything after is improvement. | file exists and passes the validator |
| **2** | Fixes D-1 and D-2 + regression tests + before/after block counts on A and B | tests green, deltas reported |
| **3** | **S-E1** GT metric correction; restate prior figures | committed experiment dir |
| **4** | **S-E2** miss attribution | (a)-fraction decides whether to continue |
| **5** | `candidates.py` + **S-E3** | **hard gate — see the table in §6** |
| **6** | `score.py` + `gate.py` + `decoder.py` + `label.py`, `--no-llm` end to end | |
| **7** | **S-E4** end-to-end evaluation vs baselines | |
| **8** | `adjudicate.py` + **S-E5** ablation | keep or remove the LLM; write the ADR either way |
| **9** | **S-E6**; re-emit `segments.jsonl` for B with the frozen pipeline; leakage check | S-DONE |

Steps 1–4 are cheap and mostly measurement. Step 5 is the decision point. Do not begin step 6
before step 5 returns.

---

## 8. Definition of done for Step 1

- [ ] `segments.jsonl` exists for Dataset B at the repository root and passes the validator in
      `DATA_CONTRACT.md` §6 (exact session names, ISO-8601 `Z`, four keys, ordered,
      non-overlapping, no chunk-derived boundary).
- [ ] The same frozen code produced it that was validated on A — no B-specific branch, no manual
      edit. `make run-b` succeeds with `dataset_a/` absent from disk (ADR-010, CI-enforced).
- [ ] Boundary precision / recall / F1 at all four τ, segmental F1, count ratio, per-session
      spread and interruption recall are reported on A against all six baselines, on the
      **scoreable canonical** population, with every denominator stated.
- [ ] Candidate reachability is reported separately, with candidate density, and is never
      presented as an accuracy number.
- [ ] The system **measurably** beats `B5-dwell` (boundary F1 0.258 at count ratio 2.84) — or
      the report states plainly that it does not and why.
- [ ] Boundaries interior to blocks are demonstrably produced; a concrete example is quoted.
- [ ] Labels are stable across sessions; identity is reported as ARI/NMI **with `match_rate`**.
- [ ] S-E1 … S-E6 are committed experiment directories with `report.md`.
- [ ] The LLM's contribution is quantified by ablation — kept with a number, or removed with an
      ADR.
- [ ] No inference module reads any GT artifact; asserted by test.
- [ ] `make test` green, including the `--no-llm` path.
- [ ] `docs/WORK_LOG.md` updated, including failures and generative-AI use.

When this list is complete, **STOP**, and only then design Step 2.

---

## 9. Non-goals for this specification

Not designed here, not implemented here, not to be started before S-DONE:

Step 2 analysis · Step 3 automation · automation-candidate selection · Playwright or any
actuation · an automation agent · workflow induction · SOP/step generation · a dashboard ·
retrieval or process memory · a vector database · a graph database · an agent framework ·
fine-tuning · a global OCR/VLM pass · a generalized process-mining platform · any rewrite of
`normalise.py` or `blocks.py` beyond D-1 and D-2 · further block-hyperparameter optimisation ·
additional documentation hierarchy.
