# S-E3 — intra-block candidate reachability

**Date** 2026-09-14 · **Dataset** `dataset_a`, all 63 sessions · **Git SHA** see `config.json`
**Population and τ grid** from `experiments/SE1-gt-metric-correction/`, not recomputed.
**Runtime** 24.1 s.

> **GATE-2 verdict, one sentence: PROCEED — at τ = 2 s the candidate space reaches 88.0% of GT
> boundaries against an achievable ceiling of 90.0%, i.e. 97.8% of ceiling, at a density of
> 0.165 candidates per event, so all three gate criteria are met with margin.**

Builds no scorer, gate, decoder or LLM. The generator emits; it does not decide.

---

## 1. Reachability against the ceiling

n = 3,504 boundary points (1,752 fragments of 1,589 scoreable canonical executions, tiers
`clean + repaired`).

| τ | block-edge only | **candidates** | ceiling | **ceiling-adjusted** |
|---|---|---|---|---|
| 1,000 ms | 48.2% | **77.2%** | 77.8% | **99.3%** |
| **2,000 ms** | 60.6% | **88.0%** | 90.0% | **97.8%** |
| 5,000 ms | 76.9% | **92.2%** | 98.7% | 93.4% |
| 10,000 ms | 92.4% | **98.7%** | 98.9% | 99.8% |

The ceiling is the share of boundaries with at least one retained event within τ — a candidate
can only be placed at an event, so nothing above this line is reachable by any event-level
generator. **Ceiling-adjusted reachability is the headline**; absolute reachability alone is
uninterpretable without it.

At τ = 1 s and τ = 2 s the generator is within 0.7 and 2.2 points of everything that is
*possible*. The block-edge arm gains **+27.4 points** at τ = 2 s from the intra-block layer.

The weakest cell is τ = 5 s at 93.4% of ceiling: between 2 s and 5 s the ceiling jumps from
90.0% to 98.7% because sparsely-covered boundaries acquire a distant event, and the generator
does not nominate at those quiet positions. That is a real gap, and it is the honest limit of
this generator — but τ = 5 s is 16% of a median fragment (31.7 s), a tolerance loose enough that
a hit there says little about boundary placement.

## 2. Candidate density — mandatory, not optional

| | dataset_a | dataset_b |
|---|---|---|
| candidates | 26,860 | 2,608 |
| events | 162,768 | 20,477 |
| **per event** | **0.1650** | **0.1274** |
| per block | 5.42 | 5.05 |
| block-edge / intra-block | 5,020 / 21,840 | 1,353 / 1,255 |

Both are comfortably inside the 0.30 gate. Reachability bought by nominating every event would
be density 1.0 and not a result; this is a sixth of that.

## 3. Per-session spread (τ = 2 s)

mean **87.5%**, sd **12.7**, range **[27.8%, 98.4%]**, n = 63.

The 27.8% floor is `ses_20260701-152030-CHAITANYA0BCF`, the one session whose GT runs 963 s past
the end of its telemetry (S-E1 §5). Its boundaries are unreachable in principle, so it drags the
minimum without indicating a generator fault. It is retained rather than excluded — dropping it
would be fitting the evaluation set.

## 4. Recovery of S-E2's missed boundaries — the most diagnostic table

Of the 1,381 boundaries the block-edge space missed at τ = 2 s, how many does the candidate set
now reach?

| S-E2 category | reached / total | % | S-E2's prediction |
|---|---|---|---|
| **(b)** preserved inside a block | **858 / 892** | **96.2%** | recoverable — **confirmed** |
| **(c)** absorbed micro-excursion | **125 / 126** | **99.2%** | recoverable — **confirmed** |
| (d) ambiguous — no evidence | 7 / 14 | 50.0% | the honest residue |
| **(e)** GT/telemetry mismatch | **0 / 349** | **0.0%** | unreachable in principle — **confirmed** |

This is as clean a confirmation as the design allows. S-E2 predicted (b) and (c) were
candidate-space limitations and (e) was not recoverable at all; the generator recovers 96–99% of
the first two and, correctly, **exactly zero** of (e). The 349 (e) boundaries are the entire
difference between 100% and the 90.0% ceiling.

Notably **(c) is recovered without touching absorption.** S-E2 showed absorption costs 126
boundaries; the intra-block layer recovers 125 of them because the events the excursion was
made of are still in the block. Whether to change absorption remains a scoring question, not a
generation one — and this result removes most of the reason to.

## 5. Contingency — features × (boundary / non-boundary)

Computed over **candidates**, at τ = 2 s. Both tables are produced because fitting a scorer on
the missed-only population would mis-rank the easy majority.

### 5.1 All boundaries (this is the table a scorer should be fitted on)

6,034 boundary candidates vs 20,826 non-boundary.

| feature | boundary % | non-boundary % | lift |
|---|---|---|---|
| `is_web_surface` | 83.1% | 53.1% | **1.56** |
| `app_switch_self_at` | 67.8% | 45.9% | **1.48** |
| `app_switch_at` | 78.9% | 70.1% | 1.13 |
| `app_switch_w` | 92.2% | 85.7% | 1.08 |
| `large_relative_gap` | 25.8% | 28.2% | 0.91 |
| `mode_transition` | 54.7% | 66.7% | 0.82 |
| `mouse_scroll_w` | 1.2% | 31.9% | **0.04** |
| `mouse_click_w` | 1.7% | 54.5% | **0.03** |
| `browser_click_w` | 1.3% | 47.1% | **0.03** |
| `keystroke_w` | 1.0% | 48.6% | **0.02** |
| `shortcut_w` | 0.3% | 43.2% | **0.01** |

### 5.2 Missed-only (for comparison with S-E2)

2,287 boundary candidates vs 20,826 non-boundary.

| feature | boundary % | non-boundary % | lift |
|---|---|---|---|
| `app_switch_self_at` | 83.2% | 45.9% | **1.81** |
| `app_switch_at` | 95.9% | 70.1% | 1.37 |
| `is_web_surface` | 62.0% | 53.1% | 1.17 |
| `browser_click_w` | 0.0% | 47.1% | **0.00** |
| `mouse_click_w` | 0.2% | 54.5% | **0.00** |
| `shortcut_w` | 0.3% | 43.2% | **0.01** |

**The two tables disagree in exactly the way the brief anticipated.** `app_switch_self_at` lifts
1.48 over all boundaries but 1.81 over missed-only; `is_web_surface` 1.56 vs 1.17. A scorer
fitted on the missed-only population would over-weight the self-switch and under-weight the
surface signal, mis-ranking the 60.6% of boundaries the block-edge space already handles. §5.1
is the table to fit on.

**The dominant evidence is negative.** `shortcut_w` at lift 0.01, `keystroke_w` 0.02,
`browser_click_w` and `mouse_click_w` 0.03 are far stronger discriminators than anything
positive. A boundary is characterised by the near-total **absence** of pointing, typing and
transactional activity in its window — a lull, not an event. This is why generation deliberately
did not use them: they are the scorer's most valuable input, and using them to suppress
candidates would have destroyed boundaries irrecoverably.

## 6. Arms measured

| arm | τ=2 s | ceiling-adj | density | note |
|---|---|---|---|---|
| **`candidates`** (shipped) | **88.0%** | **97.8%** | **0.1650** | `mode_transition` featurised, not a trigger |
| `candidates_with_mode_transition` | 89.9% | 99.8% | 0.2717 | +1.9 pts for +65% density; **0.3299/event on dataset_b**, over the gate |
| `candidates_no_dedup` | 88.0% | 97.8% | 0.3769 | STEP1_SPEC §3.2 contract 3 read literally |

Two design decisions, both settled by measurement rather than judgement:

**Deduplication.** Self-referential `app_switch` events arrive in bursts with a p50 inter-arrival
of **55 ms**, so nominating each one separately proposes the same boundary hypothesis dozens of
times. Collapsing a burst to its first member costs at most 250 ms of position — a quarter of
the tightest tolerance in the grid. Measured, it costs **0.0 points** of reachability at every τ
and saves **56%** of density. The literal reading of contract 3 ("a candidate at *every*
self-referential `app_switch`") is therefore in direct tension with the density gate, and the
measurement resolves it: dedup buys a large density saving for nothing. Set `dedup_ms=0` to
restore the literal behaviour.

**`mode_transition` is featurised but does not trigger.** It fires on 77.7% of intra-block
positions — typing → pointing happens constantly. With it, density is 0.272/event on A and
**0.330/event on B, over the gate**; without it, 0.165 and 0.127. It costs 1.9 points at τ = 2 s
(99.8% → 97.8% of ceiling). A trigger that nominates on three quarters of all positions is the
gate's own definition of indiscriminate, so it is demoted to a feature — which §3.2.1 requires
anyway.

## 7. GATE-2

| criterion | required | measured | |
|---|---|---|---|
| absolute reachability @ τ=2 s | ≥ 84% | **88.0%** | pass |
| ceiling-adjusted | ≥ ~93% | **97.8%** | pass |
| density | ≤ ~0.30 /event | **0.165** (A), 0.127 (B) | pass |

**PROCEED.** Not "proceed with a declared ceiling" — the generator is within 2.2 points of
everything achievable at the tolerance that matters.

One limit to carry forward honestly: **the ceiling itself is 90.0% at τ = 2 s**, so 9.96% of GT
boundaries (the 349 category-(e) records) can never be recovered from telemetry, whatever is
built downstream. Any end-to-end recall figure should be read against 90.0%, not 100%.

**Stopped at GATE-2.** No scoring, decoding or LLM work in this session.

## 8. Threats to validity

- Reachability is an upper bound on what a scorer could achieve, not an achievement. 26,860
  candidates contain 6,034 that are near a boundary; the other 20,826 are the scorer's problem.
- The ceiling assumes a candidate can be placed at any event. A generator restricted to *typed*
  triggers, as this one is, could in principle fall short of it for reasons other than
  telemetry coverage — the τ = 5 s cell (93.4% of ceiling) is where that shows.
- Per-session sd is 12.7 points. The mean is not the experience of every session.
- Features are hypotheses. Lift is measured on Dataset A only and must be re-measured before any
  of it is relied on for Dataset B (ADR-010).

## Reproduce

```bash
python3 -m procmine.cli --dataset dataset_a --no-windows   # writes candidates.jsonl
python3 experiments/SE3-candidate-reachability/run.py
pytest tests/test_candidates.py -q
```
