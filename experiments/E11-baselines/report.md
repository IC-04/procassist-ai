# E11 — Phase 1 baseline scorecard

**Date** 2026-09-13 · **Phase** 1 · **Dataset** `dataset_a` · **Git SHA** see `config.json`

## Hypothesis

Establish the floor. What boundary and identity accuracy do trivial methods reach on Dataset
A, and — more importantly — **where do they fail?** No parameter is selected from these
numbers; the scorecard was produced once and not iterated on.

`README.md`'s FAQ says deciding what counts as "good enough" is part of the task. This
scorecard is that definition, and is therefore a graded deliverable rather than internal
scaffolding.

## Setup

| | |
|---|---|
| Sessions | 5 (seed 7) primary · 63 (all) robustness |
| Arms | `B0-single`, `B1-chunk`, `B2-gap`, `B3-random` (20 seeds), `B4-surface`, `B5-dwell` |
| Oracle arms | `B2-gap`, `B3-random` receive **k = the true execution count** |
| GT tiers | `clean` · `clean+repaired` (headline) · `all` |
| Conventions | fragment (headline) · canonical (lenient) |
| Domains | time (τ, calibrated) and event index (κ ∈ {1,2,5,10}) |
| IoU grid | 0.3 / 0.5 / 0.7 |
| Perception params | `min_events=3`, `min_ms=1500`, `max_lag=12` — **inherited from Phase 0's E01 on Dataset B, not re-tuned here** |

τ is calibrated from A's observed canonical execution durations (median 34.8 s over 63
sessions → grid {1000, 2000, 5250, 10500} ms). It is never hard-coded.

## Results — headline (63 sessions, `clean+repaired`, fragment convention, τ = 2,000 ms)

| arm | segs | ratio | **bF1** | bP | bR | segF1@.5 | WD | ARI | match | interrupt |
|---|---|---|---|---|---|---|---|---|---|---|
| B0-single | 63 | 0.04 | 0.000 | 0.000 | 0.000 | 0.000 | 0.462 | n/a | n/a | 0.796 |
| B1-chunk | 119 | 0.07 | 0.008 | 0.059 | 0.004 | 0.003 | 0.469 | 1.000 | 0.002 | 0.663 |
| B2-gap | 1,752 | 1.00 | 0.089 | 0.086 | 0.091 | 0.134 | 0.605 | 0.682 | 0.134 | 0.194 |
| B3-random | 1,752 | 1.00 | 0.109 | 0.109 | 0.110 | 0.320 | 0.626 | 0.362 | 0.320 | 0.155 |
| B4-surface | 8,827 | 5.04 | 0.247 | 0.153 | 0.639 | 0.186 | 0.859 | 0.770 | 0.562 | 0.398 |
| **B5-dwell** | 4,968 | 2.84 | **0.258** | 0.173 | 0.504 | **0.311** | 0.838 | 0.797 | 0.597 | 0.388 |

Five-session sample (τ = 2,250 ms): B0 0.000 · B1 0.000 · B2 0.084 · B3 0.099 · B4 0.268 ·
**B5 0.287**. Identical ordering — the conclusions do not depend on the sample.

## Findings

1. **`B1-chunk` = 0.008.** Chunks carry no business meaning. ADR-001 is now measured rather
   than asserted from the schema.
2. **`B2-gap` (0.089) is worse than `B3-random` (0.109) — while holding the oracle count.**
   The time-gap heuristic is not merely weak on Dataset A; it is anti-correlated with the
   truth. This independently confirms ADR-003, which previously rested only on Dataset B.
3. **`B5-dwell` is the best arm at 0.258**, ~2.4× chance, with recall 0.504 / precision 0.173
   at a count ratio of 2.84. It over-segments roughly threefold *and* still finds only half
   the boundaries — the two failures are simultaneous, not a precision/recall trade-off that
   a threshold could rebalance.
4. **`interruption_recall` must never be quoted alone.** `B0-single` scores 0.796 on it by
   emitting one segment per session, which trivially assigns every fragment the same label.
   Read it beside the count ratio or not at all.
5. **ARI is meaningless without `match_rate`.** `B1-chunk` posts ARI 1.000 at `match_rate`
   0.002 — two matched segments out of 1,752. `B5-dwell`'s ARI 0.797 at `match_rate` 0.597 is
   the only identity figure here worth anything, and it says the surface key is a genuinely
   strong signal for *which* process is running.

## Why the best baseline stops at 0.258

Measured separately (see `docs/phases/PHASE_1_REPORT.md` §8): at τ = 2 s only **60.4%** of
execution boundaries have *any* block boundary within tolerance, so 0.504 recall sits just
under a hard structural ceiling. Of the transitions that are missed, **98.4% involve no change
of screen at all** — the worker moves from one process to the next without leaving the page.
No threshold on a surface-comparison rule can recover those.

## Threats to validity

- `B2-gap` and `B3-random` are handed the true segment count, which no production method could
  know. They are *generous* floors; a method that fails to beat them has not earned anything.
- Labels for the boundary-only arms are the modal surface key, a documented floor rather than
  a labelling method. The identity column measures how much process identity the surface key
  carries, not how well any arm names processes.
- One session (`ses_20260701-152030-CHAITANYA0BCF`) has telemetry truncated 963 s short of its
  GT. It is retained — dropping it would be fitting the evaluation set. Excluding it moves the
  ceiling figures by under one point.
- Per-session spread is reported instead of leave-one-session-out, because none of these
  baselines fits a parameter, which makes LOSO degenerate.

## Reproduce

```bash
python3 experiments/E11-baselines/run.py                 # 5-session sample, seed 7
python3 experiments/E11-baselines/run.py --all-sessions  # all 63
```
