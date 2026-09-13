# PHASE_1_REPORT

**Date** 2026-09-13 · **Branch** `phase-0-setup` · **Python** 3.12.14 · **Time spent** ~2.5 h

> **Headline.** The harness works, the ground truth is clean, and the baselines are scored.
> The finding that matters is not a score: **41.6% of execution boundaries in Dataset A occur
> with no change of screen at all**, and 98.4% of the boundaries our deterministic perception
> layer cannot reach are exactly those. This is a measured ceiling on any method that only
> merges activity blocks, and it is the strongest evidence so far that the architecture's AI
> reasoning layer is aimed at the right problem.

---

## 1. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | 5 A sessions ingested; A-vs-B block comparison reported | **PASS** | §3. Sample fixed by seed 7. Risk R1 **does not fire** — A's blocks are *richer* than B's |
| 2 | Four GT artifacts written and schema-valid | **PASS** | `build/dataset_a/{gt_events,executions,executions_canonical}.jsonl`, `expected_boundaries.json`; 10,609 / 2,009 / 1,819 rows, 0 malformed |
| 3 | `docs/GT_DEFECT_REPORT.md` with real defect rates | **PASS** | Written, 63 sessions, all rates measured |
| 4 | Alignment target chosen and justified | **PASS** | §6 — decided on evidence, not assumption |
| 5 | Harness implemented, both domains, tiered, unit-tested | **PASS** | `procmine/evaluate.py`; 25 tests, every expected value hand-computed |
| 6 | Six baselines scored; scorecard written | **PASS** | §7, `experiments/E11-baselines/` |
| 7 | `make test` green; `PHASE_1_REPORT.md` written | **PASS** | 162 passed, 1 skipped |

**All seven PASS.**

## 2. GT canonicalisation summary

Implemented in `procmine/gt.py` under the repair rules frozen by ADR-011 **before** any
segmenter existed. Full detail in `docs/GT_DEFECT_REPORT.md`.

| | |
|---|---|
| Stream records | 10,609 |
| Manifest executions | 2,009 |
| **Canonical executions** | **1,819** |
| Tiers | `clean` 1,946 · `repaired` 63 · `disputed` **0** |
| Repair flags fired | `chunk_merge_applied` 63; all others **0** |
| Interrupted executions | **98 (5.4%)** |

**Two corrections found by measuring rather than assuming — both would have silently
destroyed the phenomenon under study:**

1. **Fragments are linked by `split_id`, not `case_id`.** Task 1.2 says to group by
   "`case_id` + `split_id`". In Dataset A, `case_id` is **unique per fragment**: a split
   execution's halves carry *different* case_ids (`PI-175009-002` phase 1, suspended, resumes
   as `PI-175009-003` phase 2). Grouping on `case_id` yields an interruption rate of
   **exactly zero**. The canonicaliser keys on `split_id`, falling back to `case_id`.
2. **The manifest alone cannot link an interruption.** It records `split_id` only on the
   phase-2 fragment; the suspended phase-1 side carries `null`. Only the stream's
   `process_suspended` names the link — 99 of 289 links come from the stream alone. This is
   the one place the two GT sources genuinely differ, and it vindicates
   `EVALUATION_PROTOCOL.md` §4's rule that the stream is authoritative for semantics.

**The two defects `DATA_SCHEMA.md` §3 warns about do not occur**: 0 duplicate
`process_started`, 0 unpaired `process_switched_out`. And manifest vs stream agree to **0 ms
on all 2,009 executions** — so the two sources are *not independent* and must never be cited
as cross-validation. They are one generator's state, serialised twice.

## 3. Dataset A statistics, and the A-vs-B block comparison (Task 1.1)

Sample: 5 sessions, `random.Random(7).sample(...)` over the 63 sorted session ids —
`ses_20260630-164418-MSI`, `ses_20260701-053720-SIDDHIGUPTAB00B`,
`ses_20260701-062250-Marcos`, `ses_20260701-093900-Marcos`,
`ses_20260701-152030-CHAITANYA0BCF`.

| metric | A (5 sessions) | B (15 sessions) |
|---|---|---|
| blocks | 363 | 1,338 |
| **median events/block** | **30** | 8 |
| mean events/block | 32.2 | 15.3 |
| median block duration | 6.7 s | 3.5 s |
| one-event blocks | **3.9%** | 11.4% |
| empty-surface blocks | 0 | 0 |
| blocks/session | 72.6 | 89.2 |
| distinct surfaces/session | 9.4 | 4.4 |
| web-surface share | 62.8% | 44.4% |
| noise-flagged blocks | 14.6% | 4.0% |

**Risk R1 does not fire.** `ARCHITECTURE.md` §7 anticipated that A's `window_title` values
might be generic, collapsing block quality. The opposite is true: A's titles are semantic
(`財務会計システム`, `HR人事給与システム`, `受発注在庫管理システム`), and A's blocks are
almost four times richer than B's by median event count. Phase 2 may proceed as planned.

Whole-dataset A (63 sessions): 162,768 events → 4,968 blocks, 32.8 events/block, 0
empty-surface. 15 process codes across `hr`/`finance`/`ops`, 12 operators, 6 departments,
median 32 executions and 9 distinct processes per session.

## 4. Two generic defects surfaced by A — recorded, deliberately not fixed

Both are pre-existing implementation defects in Phase 0 heuristics, exposed because A uses
Chrome where B uses Edge. **Neither was fixed during Phase 1**, because changing the
perception layer mid-phase would invalidate the A-vs-B comparison above and the frozen
baseline scorecard.

| ID | Defect | Evidence | Impact on Phase 1 |
|---|---|---|---|
| **D-A1** | `normalise._TITLE_STRIP` strips Edge's `- Profile N - Microsoft␣Edge` but not Chrome's `- Google Chrome`, so A's titles retain browser chrome | A's top titles are `財務会計システム - Google Chrome`; B's are `財務会計システム` | none — `web:` surfaces key on origin+route, and the suffix is constant so it never fragments |
| **D-A2** | `blocks.NOISE_TITLE_HINTS` contains `"Untitled"`, which matches Notepad's default document title | 52 A blocks (14.3%) flagged `is_noise`, vs 4.0% in B | none — no Phase 1 metric consumes `is_noise` |

`NOISE_TITLE_HINTS` is a hard-coded English/browser-specific seed list and is the last
remaining dataset-specific rule in the perception layer. **Recommendation for Phase 2:** fix
D-A1 generically (strip a trailing ` - <app_name>` suffix using the app name already in
context, which is dataset-agnostic) and replace D-A2's list with a structural noise test.
Both require re-running the Phase 0 block statistics and the E11 scorecard.

## 5. Parameter-selection evidence

**Exactly one parameter was selected from Dataset A in Phase 1: the tolerance grid τ.** It is
calibrated, not assumed (Task 1.5 forbids hard-coding ±2 s):

```
median canonical execution duration = 34.8 s   (p10 23.9 s, p90 77.5 s; n=1,819)
tau grid = {3%, 6%, 15%, 30%} of the median, rounded to 250 ms
         = {1000, 2000, 5250, 10500} ms
```

`evaluate.calibrate_tau` derives this from the data and is unit-tested to prove a 100 s median
cannot produce the same grid as a 10 s one. On the 5-session sample the median is 37.1 s and
the grid becomes `{1000, 2250, 5500, 11250}` — the calibration tracks the sample, as intended.

**Everything else is inherited from the generic specification, not fitted to A:**
`min_events=3`, `min_ms=1500`, `max_lag=12`, `window=5` all come from Phase 0's E01 sweep on
Dataset B and were **not** re-tuned here. κ ∈ {1,2,5,10} events and IoU ∈ {0.3,0.5,0.7} are
taken verbatim from `EVALUATION_PROTOCOL.md` §2. No parameter was chosen to improve any
baseline's score; the scorecard was produced once and not iterated on.

## 6. Alignment target (Task 1.4) — decided on evidence

`expected_boundaries` contains 3,698 entries across 63 sessions. Cross-checked against the
canonicalised execution endpoints:

| check | result |
|---|---|
| entries matching an execution start or end **exactly** | 3,698 / 3,698 = **100.00%** |
| entries needing even 1 s tolerance | 0 |
| entries matching nothing | 0 |
| execution **starts** present in `expected_boundaries` | 2,009 / 2,009 (100%) |
| execution **ends** present | 1,689 / 1,752 (96.4%) |

**`expected_boundaries` is exactly the union of execution start and end timestamps** — the
same information flattened, not a second opinion. So the Task 1.4 fork does not exist: both
candidates are the same target.

**Decision: align on `executions[].start_ts/end_ts`.** Justification — it is *strictly more
complete* (it includes the 63 session-final ends that `expected_boundaries` omits, because the
stream closes those with `session_ended` rather than an explicit switch-out) and it carries
`process_code`, which the boundary list does not and which the label-consistency metrics
require. `expected_boundaries` is retained verbatim as `expected_boundaries.json` and used as
a cross-check.

## 7. Baseline definitions and scorecard

| ID | Definition | Oracle? |
|---|---|---|
| `B0-single` | one segment per session | — |
| `B1-chunk` | one segment per chunk | — |
| `B2-gap` | top-k largest inter-event gaps | **k = true count** |
| `B3-random` | random boundaries, 20 seeds | **count-matched** |
| `B4-surface` | boundary at every context-state change | — |
| `B5-dwell` | activity blocks after excursion absorption | — |

Labels for boundary-only arms are the modal surface key of the segment — a documented floor
for label consistency, not a labelling method.

**Headline: tier `clean+repaired`, fragment convention, τ = 2,000 ms, 63 sessions.**

| arm | segs | count ratio | **bF1** | bP | bR | segF1@.5 | WD | ARI | match | interrupt |
|---|---|---|---|---|---|---|---|---|---|---|
| B0-single | 63 | 0.04 | 0.000 | 0.000 | 0.000 | 0.000 | 0.462 | n/a | n/a | 0.796 |
| B1-chunk | 119 | 0.07 | 0.008 | 0.059 | 0.004 | 0.003 | 0.469 | 1.000 | 0.002 | 0.663 |
| B2-gap *(oracle k)* | 1,752 | 1.00 | 0.089 | 0.086 | 0.091 | 0.134 | 0.605 | 0.682 | 0.134 | 0.194 |
| B3-random *(oracle k)* | 1,752 | 1.00 | 0.109 | 0.109 | 0.110 | 0.320 | 0.626 | 0.362 | 0.320 | 0.155 |
| B4-surface | 8,827 | 5.04 | 0.247 | 0.153 | 0.639 | 0.186 | 0.859 | 0.770 | 0.562 | 0.398 |
| **B5-dwell** | 4,968 | 2.84 | **0.258** | 0.173 | 0.504 | **0.311** | 0.838 | 0.797 | 0.597 | 0.388 |

Five-session sample (τ = 2,250 ms): B0 0.000 · B1 0.000 · B2 0.084 · B3 0.099 · B4 0.268 ·
**B5 0.287**. The ordering is identical, so the conclusions do not depend on the sample.

Per-session boundary F1 spread, 63 sessions (mean ± sd over sessions × seeds):

| arm | mean | sd | min | max |
|---|---|---|---|---|
| B0-single | 0.000 | 0.000 | 0.000 | 0.000 |
| B1-chunk | 0.007 | 0.019 | 0.000 | 0.083 |
| B2-gap | 0.089 | 0.040 | 0.000 | 0.179 |
| B3-random | 0.108 | 0.053 | 0.000 | 0.321 |
| B4-surface | 0.237 | 0.087 | 0.000 | 0.433 |
| **B5-dwell** | **0.252** | 0.094 | 0.000 | 0.417 |

Every arm has sessions where it scores 0.000, and `B5-dwell`'s sd (0.094) is more than a third
of its mean. Per-session variance is large; any future claim of improvement must clear it.

### What the scorecard actually says

1. **`B1-chunk` scores 0.008.** Chunks are meaningless as business boundaries — ADR-001 is now
   measured, not merely asserted. Combined with the GT finding that a chunk boundary cuts a
   real execution in **every one of the 63 sessions**, treating chunks as boundaries would
   inject 63 guaranteed errors.
2. **`B2-gap` (0.089) is *worse than random* (0.109) — while holding the oracle count.** This
   is a strong, independent confirmation of ADR-003 on Dataset A, which previously rested only
   on Dataset B. The time-gap heuristic is not a weak method here; it is actively
   anti-correlated with the truth. It stays published as a floor.
3. **`B5-dwell` is the best arm at 0.258**, only 2.4× chance. Its profile is recall 0.504 /
   precision 0.173 at a count ratio of 2.84 — it **over-segments by ~3×** and still finds only
   half the boundaries. That combination is the Phase 1 result that matters, and §8 explains it.
4. **`interruption_recall` is not usable as a headline.** `B0-single` scores **0.796** on it by
   emitting one segment per session, which trivially gives every fragment the same label. The
   metric is only meaningful read *alongside* the count ratio, and that caveat belongs
   wherever it is quoted.
5. **Identity looks strong but is carried by `match_rate`.** `B5-dwell` reaches ARI 0.797 — but
   at `match_rate` 0.597, i.e. over the 60% of references it matched at all. `B1-chunk` posts
   ARI 1.000 at `match_rate` 0.002 — two matched segments. This is exactly why
   `EVALUATION_PROTOCOL.md` §3 forbids reporting ARI without `match_rate`.

## 8. Error analysis — the representational ceiling

Measured over all 63 sessions (and again excluding the one truncated session; the numbers move
by <1 point, so the truncation is not driving them).

**Can block boundaries express execution boundaries at all?**

| | all 63 | excl. truncated session |
|---|---|---|
| GT boundaries | 3,327 | 3,283 |
| falling **strictly inside** a block | 74.5% | **75.2%** |
| median distance to nearest block boundary | 1,040 ms | 1,033 ms |
| **reachable within τ=1,000 ms** | 47.3% | 47.6% |
| **reachable within τ=2,000 ms** | 59.9% | **60.4%** |
| reachable within τ=5,250 ms | 82.8% | 83.5% |
| reachable within τ=10,500 ms | 92.2% | 93.1% |
| block boundaries **interior to** a GT execution | 80.3% | 80.3% |
| executions containing **zero whole blocks** | — | **36.5%** |

So `B5-dwell`'s measured recall of 0.504 sits just under a hard ceiling of **0.604** at
τ = 2 s. No amount of merging blocks can exceed it, because 40% of the target boundaries have
no block boundary within tolerance.

**Why are they unreachable?** Classifying all 1,663 execution-to-execution transitions:

| | same surface | surface changes |
|---|---|---|
| reachable within 2 s | 576 | 395 |
| **missed** | **681** | 11 |

> **Of the missed boundaries, 98.4% occur with no change of screen whatsoever.**
> Every one of them is a change of *process code*: the worker finishes process H and begins
> process C without leaving the page — typically on the portal root, e.g.
> `web:http://127.0.0.1:5122/`.

These are not timing artifacts. For a missed boundary, the distance forward to the *next*
block boundary is median **5.3 s**, p75 15.5 s, p90 32.7 s — only 1.3% are within 3 s. The
worker genuinely continues on the same surface for several seconds into the new execution.

There is also a systematic **+820 ms lead**: the GT annotation precedes the corresponding
telemetry, with the nearest raw event +173 ms and the nearest block boundary +822 ms after the
GT timestamp (p50). This is why τ ≥ 1 s is required for any figure to be meaningful, and it
is a calibration fact worth carrying into Phase 4's decoder.

## 9. What Phase 1 taught us about the representation

The question was whether activity blocks are a suitable substrate for reconstructing business
executions. The measured answer is **yes for compression and identity, no for boundaries on
their own** — and the failure is precisely the one the architecture predicted.

1. **Compression works, and better on A than on B.** 162,768 events → 4,968 blocks, 32.8
   events/block. The reasoning unit is affordable (ADR-004 holds).
2. **Blocks carry real process identity.** ARI 0.797 between surface keys and true process
   codes on matched segments is far above chance. The surface key is a strong feature for
   *what* is happening.
3. **Blocks do not nest inside executions.** 75% of execution boundaries fall inside a block;
   36.5% of executions contain no whole block; 80% of block boundaries are interior to an
   execution. Blocks and executions are **overlapping segmentations of the same timeline at
   similar granularity**, not a clean hierarchy. Any decoder that assumes "execution = a run of
   whole blocks" inherits a 60% recall ceiling.
4. **The residual is exactly the contextual-reasoning problem.** `ARCHITECTURE.md` §2 claims
   the hard part "is not 'where does the application change' — that is string comparison."
   Phase 1 measures that claim: string comparison on surfaces reaches 0.258 boundary F1, and
   98.4% of what it misses is a process switch with no surface change. Those transitions are
   invisible to *any* deterministic surface rule, at any threshold. They are visible only to
   something that can reason about whether a new case has begun on the same screen — which is
   what `NEW_EXECUTION` vs `SAME_EXECUTION` in `AI_REASONING_SPEC.md` §3 is for.

**Consequence for Phase 2–4, stated as a constraint rather than a redesign.** The ambiguity
gate cannot simply route "surface changed" transitions — those are the *easy* ones. It must
route same-surface transitions, which are 1,257 of 1,663 (75.6%). Routing all of them is
unaffordable, so the gate needs a discriminator other than surface change. Phase 4's decoder
must also be able to place a boundary *inside* a block, or the 60% ceiling stands. **This is
reported at G1 for a decision; nothing in the architecture has been changed.**

## 10. Dataset-generalisation concerns

- **A and B share the same three portal system names** (`財務会計システム`, `HR人事給与システム`,
  `受発注在庫管理システム`) on different ports (A: 5122–5124, B: 5132–5134), despite
  `README.md` stating B comes from different departments with different applications. Anything
  that looks like it transfers between A and B may be transferring because the *simulator* is
  shared, not because the method generalises. ADR-010's prohibition is now more important, not
  less.
- **A has ~4× B's per-session process diversity** (9.4 vs 4.4 distinct surfaces/session) and a
  very different event mix (`app_switch` 31.1% in A vs 8.1% in B). A parameter tuned on either
  dataset should be expected to move on the other.
- **No B accuracy figure exists or can exist** (`EVALUATION_PROTOCOL.md` §7). Nothing in this
  report was computed on B except the Phase 0 block statistics quoted for comparison.

## 11. Findings that weaken Phase 0 assumptions

| Phase 0 position | Phase 1 evidence | Status |
|---|---|---|
| Risk R1: A's titles may be generic, collapsing block quality | A's blocks are **richer** than B's (median 30 vs 8 events) | **Retired** |
| ADR-003: gaps are a weak feature (measured on B) | `B2-gap` scores **below random** on A even with oracle k | **Strengthened** |
| ADR-001: chunks are meaningless (asserted from schema) | `B1-chunk` = 0.008; a chunk cuts a real execution in all 63 sessions | **Strengthened** |
| ADR-004: the block is the unit of reasoning | Holds for compression and identity, but blocks **cannot express 40%** of boundaries | **Qualified — see §9** |
| ADR-008: `pm4py` once step structure exists | A's GT has **no step structure**: `task_started` is 1:1 with executions (2,009 / 2,009) | **Precondition unmet** |
| ADR-012/013 (Phase 0 perception rules) | Ran unmodified on A; 0 empty-surface blocks, 0 contract violations | **Confirmed** |

`EVALUATION_PROTOCOL.md` §4's tiered sensitivity analysis is **degenerate on Dataset A**:
there are no `disputed` records, so `clean+repaired` and `all` are identical sets.

## 12. Reproducibility

- `experiments/E11-baselines/` follows `EXPERIMENT_PROTOCOL.md` §1: `config.json`,
  `metrics.json`, `samples.jsonl`, `report.md`, plus the committed `run.py`.
- Sample selection, `B3-random`, and every metric are seeded and deterministic. The experiment
  was run three times during development (after an artifact-path change and after a spread-
  statistic fix). **Every arm mean reproduced exactly on every run**, at both sample sizes:

  | run | B0 | B1 | B2 | B3 | B4 | B5 |
  |---|---|---|---|---|---|---|
  | 5 sessions × 3 runs | 0.000 | 0.000 | 0.084 | 0.099 | 0.268 | 0.287 |
  | 63 sessions × 3 runs | 0.000 | 0.008 | 0.089 | 0.109 | 0.247 | 0.258 |

  The only figure that ever moved was the `B3-random` spread, which is how the mixed-units bug
  in §13 was detected; it now reproduces at 0.108 ± 0.053.
- GT artifacts are written to `build/dataset_a/` (gitignored) per `DATA_CONTRACT.md` §5, so
  dataset-A-derived ground truth never enters version control.
- `metrics.json` retains the full `evaluate_all` output for seed 0 and for the headline
  combination on every seed; storing per-session detail for all 20 random seeds across 6
  tier×convention combinations produced a 44 MB file with no added information. The trimming
  is recorded in the file's own `_note`.

## 13. What did not work

- **My first canonicaliser reported 0 interrupted executions**, because it grouped on
  `case_id` as the task description's phrasing suggests. The number was implausible against
  `DATA_SCHEMA.md`'s description of suspend/resume, which is what prompted checking the raw
  manifest and finding that case_ids differ across fragments. Had I trusted the output, the
  interruption phenomenon would have been reported as non-existent.
- **My first GT-defect scan reported 159 unpaired `process_switched_out`.** That scan did not
  treat `process_resumed` as re-opening an execution. The correct count is 0. Both numbers are
  in `GT_DEFECT_REPORT.md` §2 because the wrong one is the trap a careless canonicaliser falls
  into.
- **My first artifact layout committed dataset-A-derived GT** into `experiments/` and produced
  a 44 MB `metrics.json`. Both fixed before the first Phase 1 commit.
- **I introduced an inconsistency in the spread statistic** when trimming `metrics.json` —
  mixing per-session values for seed 0 with pooled values for seeds 1–19. Caught by noticing
  the `B3-random` spread changed between two runs whose arm means were identical, and fixed by
  retaining per-session detail for the headline combination on every seed.

## 14. Recommendation

**READY FOR G2.**

All seven acceptance criteria pass. The harness is built and unit-tested, the GT is
canonicalised under frozen rules with its defects quantified, six baselines are scored, and
the alignment target is decided on evidence.

Two things should be settled at the G2 review before Phase 2 proceeds:

1. **The 60% boundary ceiling (§8–9).** The ambiguity gate and the decoder must be designed
   knowing that 40% of target boundaries are not expressible from block boundaries, and that
   the gate's obvious discriminator — "did the surface change?" — selects the wrong 24%.
2. **Defects D-A1 and D-A2 (§4).** Both are generic; fixing them changes block statistics and
   requires re-running E01 and E11. Better done deliberately at the start of Phase 2 than
   opportunistically now.

`ADR-008`'s precondition is unmet (§11) and Phase 5 should be re-planned accordingly, but that
is not a G2 blocker.

**Stopped at gate G1. Phase 2 not started.**
