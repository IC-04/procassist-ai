# S-E1 — GT metric correction

**Date** 2026-09-14 · **Dataset** `dataset_a`, all 63 sessions · **Git SHA** see `config.json`
**Blocks built with** the post-D-1/D-2 perception layer (commit `c9d1c05`)

> **Verdict: the ~60% block-edge reachability figure survives correction.** Recomputed on the
> scoreable canonical population at the unified τ grid it is **60.6%** at τ = 2 s, against the
> prior ad-hoc 59.9%. Nothing downstream needs re-planning on that account. What does need
> restating is the *provenance* of the prior figure and the denominator of the "no surface
> change" claim, where the brief's own expectation turns out to be measuring a third thing.

This experiment establishes the empirical baseline. It builds no algorithm: there is no
candidate generator, no scorer, no decoder and no LLM here.

---

## 0. Audit (STEP1_SPEC Task 1)

`procmine/` contains twelve modules: `normalise` (chunk dissolution, title/URL normalisation,
tab carry-forward), `blocks` (surface-keyed activity blocks, three passes plus late-title
attachment), `tekg` (eight typed edge classes, locality-bounded), `context` (reasoner payload,
ADR-006 enforcement), `schemas` (artifact validators), `cli` (perception build), `gt` (GT
canonicaliser), `evaluate` (the harness), `baselines` (B0–B5), and `emit_segments` /
`validate_segments` (the provisional Step 1 deliverable).

**`gt.py` conforms to ADR-011.** The five repair flags are implemented and partitioned exactly
as the ADR requires — `DETERMINISTIC = {chunk_merge_applied, duplicate_start_collapsed}` → tier
`repaired`; `DISPUTED = {unpaired_switch_out, manifest_stream_disagreement, zero_duration}` →
tier `disputed`. Both GT sources are retained on disagreement (`manifest_value` /
`stream_value`). The rules were committed in `5cc48c3`, before any segmenter existed.

**Where the `PHASE_1_REPORT.md` §8 numbers came from — stated plainly.** They were produced by
three throwaway scripts in a session scratchpad — `ceiling.py`, `why_missed.py`, `offset.py` —
**none of which was ever committed.** `git log --all` finds no such file in the history, and no
`experiments/` directory produces them: `E01-block-sweep` swept block thresholds and
`E11-baselines` scored baselines. Neither computed reachability. So the 47.3 / 59.9 / 82.8 /
92.2% figures, the "74.5% strictly inside a block" and the 1,040 ms median distance had **no
reproducible artifact behind them at all** — exactly the situation `EVALUATION_PROTOCOL.md` §9
rule 4 flags. This experiment is the first committed derivation of any of them.

---

## 1. Populations (a) — verified exactly, zero disagreements

| Population | expected (ADR-017) | measured | |
|---|---|---|---|
| raw manifest | 2,009 | 2,009 | OK |
| raw without `end_ts` | 257 | 257 | OK |
| canonical | 1,819 | 1,819 | OK |
| unscoreable (no usable interval) | 230 | 230 | OK |
| **scoreable canonical** | **1,589** | **1,589** | OK |
| interrupted (`n_fragments > 1`) | 98 | 98 | OK |
| tier `clean` | 1,756 | 1,756 | OK |
| tier `repaired` | 63 | 63 | OK |

**Disagreements: 0.** Nothing was adjusted.

The 1,589 scoreable canonical executions contain **1,752 fragments**, giving **3,504 boundary
points** at the fragment convention. Those are the denominators used throughout below, and the
reason they differ from the prior 3,327 is that the prior figure was computed over an unstated
population.

---

## 2. The unified τ grid (b)

**τ ∈ {1000, 2000, 5000, 10000} ms.** Both prior grids are superseded:
`PHASE_1_REPORT.md` used {1000, 2000, 5250, 10500}; `experiments/E11-baselines/config.json`
used {1000, 2250, 5500, 11250}.

Justification, from the scoreable canonical fragment durations (n = 1,752):

| | p10 | p50 | p90 | max |
|---|---|---|---|---|
| fragment duration | 23.2 s | **31.7 s** | 66.4 s | 1,144.8 s |

The grid spans **3.2% / 6.3% / 15.8% / 31.5%** of the median fragment. Three constraints fix
it. The floor is 1,000 ms because the GT annotation leads the telemetry by a systematic
≈ +820 ms (p50), so any τ below 1 s measures the annotation offset rather than the method
(`EVALUATION_PROTOCOL.md` §8). The ceiling is 10,000 ms because at ~32% of a median fragment a
tolerance begins to accept a boundary placed in a neighbouring fragment, at which point the
number stops discriminating. Between those, round decimal values are chosen over the previous
5,250/5,500 and 10,500/11,250 for one reason only: **the two prior grids were incompatible, so
no figure from either could be compared with the other.** A round grid makes every future
number quotable against every past one. The two prior grids bracket this one, so restating on
it moves figures by less than a point wherever the τ values nearly coincide — which is what
§3 shows.

---

## 3. Block-edge candidate reachability (c)

**This measures the candidate space, not a segmenter** (`EVALUATION_PROTOCOL.md` §9 rule 1).
It is an upper bound on recall for methods restricted to block edges, and nothing else. It is
never an accuracy figure.

Scoreable canonical population, tiers `clean + repaired`, all 63 sessions:

| | all 63 | excl. truncated session | prior (ad hoc) |
|---|---|---|---|
| boundary points | **3,504** | 3,450 | 3,327 |
| τ = 1,000 ms | **48.2%** | 48.6% | 47.3% |
| **τ = 2,000 ms** | **60.6%** | **61.1%** | **59.9%** |
| τ = 5,000 ms | **76.9%** | 77.7% | 82.8% *(at 5,250 ms)* |
| τ = 10,000 ms | **92.4%** | 93.3% | 92.2% *(at 10,500 ms)* |
| strictly inside a block | **74.1%** | 74.8% | 74.5% |
| median distance to nearest edge | **1,026 ms** | 1,023 ms | 1,040 ms |

**The ~60% figure holds: 60.6% against 59.9%, a difference of 0.7 points.** The STOP condition
("differs by more than a few points") is not triggered. The 74.5% → 74.1% and 1,040 → 1,026 ms
figures also survive. The only column that moves materially is τ = 5 s, and that is because the
prior number was measured at 5,250 ms, not 5,000 — a grid artefact, not a correction.

Per confidence tier:

| tier | points | 1 s | 2 s | 5 s | 10 s |
|---|---|---|---|---|---|
| `clean` | 3,374 | 47.9% | **60.3%** | 76.7% | 92.3% |
| `repaired` | 130 | 56.2% | **68.5%** | 83.8% | 94.6% |

The `repaired` tier is slightly *more* reachable, which is expected: those 63 records are the
chunk-continuation executions, whose endpoints sit at session extremities where a block edge is
nearly always present. It is a 130-point sample and carries no weight.

**Candidate density** (`EVALUATION_PROTOCOL.md` §9 rule 3 — reachability without density is not
a result): 9,674 block-edge candidates over 162,768 events and 4,957 blocks =
**0.059 candidates per event, 1.95 per block.** This is the comparison arm that any intra-block
candidate generator must beat *at a stated density*; buying reachability by nominating every
event would be 1.0 per event and not a result.

---

## 4. The "no surface change" denominator (d) — three readings, not two

The brief expected two readings, 98.4% and ≈69.8%, differing by denominator. Measured, there
are **three**, and the difference is not the one assumed:

| # | reading | measured | prior |
|---|---|---|---|
| 1 | of **missed execution-to-execution transitions** | **700 / 711 = 98.5%** | 681/692 = 98.4% |
| 2 | of **missed boundary points** | **1,347 / 1,381 = 97.5%** | — |
| 3 | of **all boundary points** (unconditioned) | **2,566 / 3,504 = 73.2%** | ≈69.8% |

Reading 1 reproduces the prior 98.4% almost exactly. Reading 3 is the family the ≈69.8%
belongs to; the residual gap is explained by the prior having used the uncorrected 3,327-point
population and pre-D-1/D-2 blocks.

**The distinction is therefore conditioning, not granularity.** Readings 1 and 2 are both
*conditioned on the boundary having been missed*, and they agree with each other (98.5% vs
97.5%) whether you count transitions or points. Reading 3 is unconditioned — it is simply "how
often does a GT boundary fall where the screen does not change", which is a different question.
Quoting 98.5% against 73.2% as though they were the same statistic on different denominators
would be wrong in both directions.

The substantive finding is unchanged and now rests on a committed derivation: **when a block
edge fails to reach a GT boundary, it is almost always because the worker changed process
without changing screen.**

---

## 5. The one truncated session (e)

**`ses_20260701-152030-CHAITANYA0BCF`.** Its GT spans 1,496 s while its telemetry spans 569 s;
the last ~963 s of annotated work has no recorded events. It is **one session of 63** and is
reported as that, never as a dataset-wide algorithmic failure.

Every headline number above is given twice, with and without it. Removing it moves reachability
by **+0.5 points** at τ = 2 s (60.6% → 61.1%) and leaves every other conclusion unchanged. It
is **retained** in the headline figures: excluding it would be fitting the evaluation set.

---

## 6. Baselines re-scored (f)

**Run on all 63 sessions, not the 5-session sample.** `E11-baselines` defaulted to 5 sessions
(seed 7) and offered `--all-sessions`; S-E1 uses all 63 unconditionally, because the corrected
population is defined over all 63 and because the 5-session sample happens to contain the one
truncated session, which over-weights it fivefold.

Reference: 1,752 fragments from 1,589 scoreable canonical executions, tiers `clean + repaired`,
fragment convention, τ = 2,000 ms.

| arm | segs | count ratio | bF1@2s | P | R | segF1@.5 | ARI | match | prior (5-sess, τ=2.25 s) |
|---|---|---|---|---|---|---|---|---|---|
| B0-single | 63 | 0.04 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 |
| B1-chunk | 119 | 0.07 | 0.008 | 0.059 | 0.004 | 0.003 | 1.000 | 0.002 | 0.008 |
| B2-gap *(oracle k)* | 1,752 | 1.00 | 0.089 | 0.086 | 0.091 | 0.134 | 0.682 | 0.134 | 0.089 |
| B3-random *(oracle k)* | 1,752 | 1.00 | 0.109 | 0.109 | 0.110 | 0.320 | 0.362 | 0.320 | 0.109 |
| B4-surface | 8,816 | 5.03 | 0.247 | 0.153 | 0.639 | 0.186 | 0.770 | 0.562 | 0.247 |
| **B5-dwell** | **4,957** | **2.83** | **0.258** | 0.173 | 0.504 | 0.312 | 0.797 | 0.597 | 0.258 |

**Every arm reproduces its prior value to three decimals.** That is worth stating explicitly:
the population correction, the grid unification and the D-1/D-2 fixes together moved the
baseline scorecard by nothing measurable. The reason is that `E11-baselines` had already, in
effect, been scoring against the scoreable population — it filtered `executions.jsonl` to rows
carrying both a start and an end, which is the same 1,752 fragments — it simply never named the
population it was using. The correction makes the denominator explicit rather than changing it.

`B5-dwell` across the unified grid: **0.147 / 0.258 / 0.381 / 0.469** at 1 / 2 / 5 / 10 s
(excluding the truncated session; n_ref 1,725 over 62 sessions).

---

## 7. What this invalidates, and what survives

**Survives, now with a committed derivation:**
- block-edge reachability ≈ 60% at τ = 2 s (60.6%, was 59.9%)
- 74.1% of GT boundaries fall strictly inside a block (was 74.5%)
- median distance to the nearest block edge ≈ 1 s (1,026 ms, was 1,040 ms)
- "when a block edge misses, the screen did not change" at 98.5% of missed transitions
- the entire baseline scorecard, unchanged to three decimals

**Invalidated or requiring restatement:**
- **Any reachability figure quoted without its population and grid.** The prior numbers were
  computed on an unstated population by uncommitted scripts. They happen to have been close to
  correct; that was not knowable before this experiment.
- **τ = 5 s reachability: 82.8% → 76.9%.** The prior figure was measured at 5,250 ms. This is a
  grid artefact, but 82.8% must not be quoted again.
- **The framing "98.4% vs ≈69.8% — both correct on their own denominators."** They are not two
  denominators for one statistic; they are two different statistics (§4). Three readings are
  given above and each must be named when quoted.
- **`PHASE_1_REPORT.md` §8's characterisation of ~60% as "a ceiling on the representation."**
  ADR-015 already corrected this: it is the reachability of the **block-edge candidate space**,
  and S-E1 measures it as such, with density stated alongside.

## 8. Threats to validity

- Reachability was computed with post-D-1/D-2 blocks; the prior figure used pre-fix blocks. The
  fixes moved A's block count by −0.2% (4,968 → 4,957), so the comparison is dominated by the
  population and grid correction, not by the fixes.
- `B2-gap` and `B3-random` hold the true segment count. They are generous floors, not methods.
- The `repaired` tier is 130 boundary points; its per-tier row is descriptive only.
- Reachability is an upper bound on recall for a block-edge-restricted method. It says nothing
  about whether any method achieves it — `B5-dwell` reaches 0.504 recall against the 60.6%
  bound, so roughly a fifth of the reachable boundaries are not actually recovered.

## Reproduce

```bash
python3 -m procmine.gt --dataset dataset_a          # writes build/dataset_a/ GT artifacts
python3 experiments/SE1-gt-metric-correction/run.py
```
