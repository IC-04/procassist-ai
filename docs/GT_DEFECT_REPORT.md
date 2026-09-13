# GT_DEFECT_REPORT — Dataset A ground truth, measured

**Date** 2026-09-13 · **Phase** 1 (Task 1.3) · **Scope** all 63 sessions of `dataset_a`
**Produced by** `procmine/gt.py` under the repair rules frozen in ADR-011, before any
segmenter existed.

`DATA_SCHEMA.md` §3 warns qualitatively that `gt.jsonl` "sometimes emits the same
`process_started` twice in a row", that "`process_switched_out` does not always pair up", and
instructs us to "verify consistency yourself before relying on it." This document is that
verification, quantified. It is a deliverable in its own right: the ground truth is
**evidence, not truth** (`CLAUDE.md` §6), and the reader is entitled to know how good the
measuring instrument is before reading any accuracy number produced with it.

---

## 1. Corpus

| | |
|---|---|
| Sessions | 63 |
| GT stream records (`gt.jsonl`) | 10,609 |
| Manifest executions (`gt_manifest.json`) | 2,009 |
| Canonical executions after fragment grouping | **1,819** |
| Distinct process codes | 15 (A–O) |
| Domains | `hr` (5 codes), `finance` (5), `ops` (5) |
| Executions per session | min 24 · median 32 · max 44 |
| Distinct processes per session | min 8 · median 9 · max 13 |
| Operators | 12 distinct, across 6 departments |
| Operator profiles | `novice` 32 · `expert` 17 · `stressed` 14 sessions |

Stream record types: `clipboard_paste` 3,010 · `task_started` 2,009 · `process_started` 1,819 ·
`clipboard_copy` 1,766 · `process_switched_out` 1,590 · `process_resumed` 190 ·
`process_suspended` 99 · `run_config` 63 · `session_ended` 63.

---

## 2. The documented defects — measured

| Defect (`DATA_SCHEMA.md` §3) | Rate measured | Verdict |
|---|---|---|
| Duplicate `process_started` in a row | **0 / 1,819 (0.00%)** | **does not occur** |
| Unpaired `process_switched_out` | **0 / 1,590 (0.00%)** | **does not occur** |

Both warned-about defects are **absent from this distribution**. The repair rules
`duplicate_start_collapsed` and `unpaired_switch_out` are implemented, frozen and tested, but
never fire on Dataset A.

> The unpaired-switch figure is sensitive to how you count. A naive scan that does not treat
> `process_resumed` as re-opening an execution reports **159** false unpaired switch-outs. The
> correct reading is 0. This is worth stating because it is exactly the kind of artifact that
> would have been reported as a GT defect if the canonicaliser had been written carelessly.

### 2.1 Manifest vs stream disagreement — there is none

| | n | min | p50 | p90 | max | \|Δ\| > 1 s |
|---|---|---|---|---|---|---|
| start delta (stream − manifest) | 2,009 | 0 ms | 0 ms | 0 ms | 0 ms | **0** |
| end delta | 1,752 | 0 ms | 0 ms | 0 ms | 0 ms | **0** |

**Every matched execution agrees to the millisecond.** The `manifest_stream_disagreement`
flag never fires at any τ.

The honest reading: the two "independent" GT sources are **not independent**. They are two
serialisations of the same generator state. `EVALUATION_PROTOCOL.md` §4's provision to retain
both values on disagreement is therefore inert on this dataset — correct to have built, but
it buys nothing here, and it must not be cited as evidence that the GT has been
cross-validated. It has not; it has been checked for self-consistency and found consistent.

### 2.2 Where the sources genuinely differ: `split_id`

The one field where the two sources are **not** interchangeable:

| `split_id` supplied by | executions |
|---|---|
| manifest (phase-2 fragments) | 190 |
| **stream only** (`process_suspended`, phase-1 fragments) | **99** |
| absent (uninterrupted) | 1,720 |

The manifest records `split_id` **only on the phase-2 fragment**; the suspended phase-1
fragment carries `split_id: null`. Only the stream's `process_suspended` event names the link
for that side. **The manifest alone cannot reconstruct which fragments belong to the same
interrupted execution**, which is precisely why `EVALUATION_PROTOCOL.md` §4 makes the stream
authoritative for semantics. `gt.py` back-fills `split_id` from the stream and records the
provenance in `split_id_source`.

---

## 3. Fragmentation — the number that decides how central M2b is

Fragments are linked by `split_id`, **not** by `case_id`.

> Measured: `case_id` is **unique per fragment**. The two halves of a split execution carry
> *different* case_ids — e.g. `PI-175009-002` (phase 1, suspended) resumes as
> `PI-175009-003` (phase 2). Grouping on `case_id`, which the task description's phrasing
> invites, yields an interruption rate of **exactly zero** and would have silently erased the
> entire phenomenon under study.

| fragments per canonical execution | count |
|---|---|
| 1 | 1,721 |
| 2 | 26 |
| 3 | 52 |
| 4 | 20 |

**98 of 1,819 canonical executions are interrupted — 5.4%.**

The rate understates the difficulty, because interruption is temporally enormous:

| | interrupted executions |
|---|---|
| median **active** duration (sum of fragments) | 88.1 s |
| median **wall span** (first start → last end) | **491.1 s** |
| ratio | **5.6×** |

An interrupted execution occupies 5.6× its own working time in wall-clock terms, with other
processes interleaved in the gap. So 5.4% of executions contaminate a far larger share of the
timeline, and a segmenter that cannot stitch will mis-assign every interleaved neighbour too.

**Implication for M2b:** interruption is not a rare edge case to be deferred. It is rare *per
execution* but dominant *per unit of confusing timeline*. `interruption_recall`
(`EVALUATION_PROTOCOL.md` §3) is the metric that measures it, and §5's stitch-aware
convention is the one that will discriminate between methods.

---

## 4. Duration and task structure

Canonical execution duration:

| | p10 | p50 | p90 | max |
|---|---|---|---|---|
| active duration | 23.9 s | **34.8 s** | 77.5 s | 1,144.8 s |
| wall span | — | 34.8 s | 94.6 s | 1,144.8 s |

This median of 34.8 s is what calibrates the evaluation tolerance grid τ (Task 1.5) — τ is
expressed as a fraction of it rather than assumed.

**Tasks per execution: p50 = 1, p90 = 1, max = 1.** There are exactly 2,009 `task_started`
records for 2,009 manifest executions — a strict 1:1 mapping.

> **This is a significant negative finding for Phase 5.** ADR-008 defers `pm4py` until step
> structure exists, on the grounds that "one row per execution yields a one-activity process
> model — degenerate." Dataset A's ground truth contains **no sub-execution step structure at
> all**: `task_started` is a synonym for the execution, not a decomposition of it. Step
> recovery therefore cannot be validated against A's GT, and ADR-008's precondition is not
> satisfied by this data. Phase 5 must either derive steps from telemetry and validate them
> some other way, or drop the step-level process map.

`variant` — documented in `DATA_SCHEMA.md` §4 as "the handling pattern used in that
execution" — is **null for 1,147 of 2,009 executions (57.1%)**. Present values: `std` 339,
`reg` 332, `exc` 116, `adj` 75. Variant-level analysis in Phase 5 can therefore be validated
on at most 43% of executions.

---

## 5. Chunk continuation

| | count |
|---|---|
| `continues_from_prev = true` | 63 |
| `continues_to_next = true` | 63 |

Exactly one of each per session — the execution straddling the session's chunk boundary.
These 63 executions receive the deterministic repair flag `chunk_merge_applied` and form the
entire `repaired` tier.

This is the measurement that justifies ADR-001: a chunk boundary cuts a real execution in
half in **every single session**. Treating chunks as business boundaries would inject 63
guaranteed false boundaries.

---

## 6. Confidence tiers (EVALUATION_PROTOCOL §4)

| Tier | Executions | Share |
|---|---|---|
| `clean` | 1,946 | 96.9% |
| `repaired` (`chunk_merge_applied`) | 63 | 3.1% |
| `disputed` | **0** | 0.0% |

With no disputed records, the tier-1 / tier-3 sensitivity line that
`EVALUATION_PROTOCOL.md` §4 asks for is **degenerate on Dataset A**: `clean+repaired` and
`all` are the same set. Reported for completeness; it carries no information here.

---

## 7. `expected_boundaries` — semantics (Task 1.4 evidence)

3,698 entries across 63 sessions.

| type | count |
|---|---|
| `process_started` | 1,819 |
| `process_switched_out` | 1,590 |
| `process_resumed` | 190 |
| `process_suspended` | 99 |

Cross-checked against the canonicalised execution endpoints:

| check | result |
|---|---|
| entries matching an execution **start** exactly | 2,218 |
| entries matching an execution **end** exactly | 1,480 |
| entries within 1 s but not exact | **0** |
| entries matching nothing | **0** |
| **exact coverage** | **100.00%** |
| converse: execution starts present in `expected_boundaries` | 2,009 / 2,009 (100%) |
| converse: execution ends present | 1,689 / 1,752 (96.4%) |

`expected_boundaries` **is** the union of execution start and end timestamps — the same
information in a flatter form, not a second opinion. The 63 missing ends are exactly the
session-final executions, which the stream closes with `session_ended` rather than an explicit
switch-out. Using execution intervals as the alignment target is therefore strictly more
complete, and additionally carries `process_code`, which boundary entries do not.

---

## 8. A defect the GT does *not* document: telemetry truncation

Not a ground-truth defect but a GT-versus-telemetry one, found while validating alignment.

`ses_20260701-152030-CHAITANYA0BCF` has a GT span of **1,496 s** but a telemetry span of
**569 s**. Forty of its 59 GT endpoints — the last **963 s** of annotated work — lie after the
final recorded event. No method operating on telemetry can recover them.

Across all 63 sessions:

| | |
|---|---|
| sessions with GT endpoints outside the telemetry span | **1 / 63** |
| GT endpoints outside telemetry | **40 / 3,761 (1.06%)** |
| telemetry-span ÷ GT-span, p05 / p50 / p75 | 1.02 / 1.05 / 1.13 |
| sessions with ratio < 0.9 | **1** |

Every other session records *more* wall time than its GT spans. The defect is confined to one
session and is **reported, not repaired**: dropping it would be fitting the evaluation set to
make our numbers look better. It is flagged so that any per-session outlier in the scorecard
can be attributed rather than explained away.

> It happened to fall inside the seed-7 five-session sample, where it contributes
> disproportionately to the tail of the boundary-distance distribution. This is the clearest
> argument for reporting the 63-session figures alongside the 5-session ones.

---

## 9. Summary for the reader of any accuracy number

1. The GT is **internally consistent to the millisecond**; the two sources never disagree.
2. The two defects `DATA_SCHEMA.md` warns about **do not occur** here.
3. The GT's real weaknesses are **omissions**, not contradictions: no step structure
   (`task_started` is 1:1 with executions), `variant` missing on 57% of executions, and
   `split_id` recorded on only one side of each interruption.
4. **5.4%** of executions are interrupted, but they span **5.6×** their own working time.
5. One session's telemetry is truncated against its GT; 1.06% of endpoints are unobservable.
6. There are **no disputed records**, so the tiered sensitivity analysis is degenerate on A.
