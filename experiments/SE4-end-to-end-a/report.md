# S-E4 — full Dataset A validation of the deterministic Step 1 pipeline

**Date** 2026-09-14 · **Dataset** `dataset_a`, all 63 sessions · **Mode** `--no-llm`
**Population** scoreable canonical (1,589 executions → 1,752 fragments → **3,504 boundary
points**), tiers `clean + repaired` · **Runtime** 265 s (LOSO scoring dominates)
`procmine/evaluate.py` and `procmine/baselines.py` reused unchanged; no metric reimplemented.

> **Headline: boundary F1 0.690 at τ = 2 s (P 0.680 / R 0.702) with count ratio 0.98 — 2.67× the
> best baseline, at an operating point that makes no bet on over- or under-segmenting.**
> Recall 0.702 read against the **90.0% ceiling** is 78% of what is achievable, not 70% of 100%.

---

## 1. Boundary accuracy (measures 1–3)

Leave-one-session-out. Fitting on all of A and scoring A would be optimistic; these are the
honest numbers.

| τ | precision | recall | **F1** | ceiling | recall / ceiling |
|---|---|---|---|---|---|
| 1,000 ms | 0.534 | 0.551 | 0.543 | 77.8% | 70.9% |
| **2,000 ms** | **0.680** | **0.702** | **0.690** | **90.0%** | **77.9%** |
| 5,000 ms | 0.729 | 0.752 | 0.740 | 98.7% | 76.2% |
| 10,000 ms | 0.781 | 0.806 | 0.794 | 98.9% | 81.5% |

**Operating point:** percentile calibration · `lambda_per_segment` 1.40 · `min_duration_ms`
19,000 · gate bands 0.80/0.94. Chosen for count ratio ≈ 1.0, not maximum F1.

## 2. Segmental, ordinal and identity measures (4, 6, 8, 9)

| | value | read with |
|---|---|---|
| segmental F1 @ IoU 0.3 / 0.5 / 0.7 | — / **0.7679** / — | count ratio 0.98 |
| WindowDiff | 0.4698 | lower is better |
| Pk | 0.2567 | lower is better |
| **count ratio** | **0.98** | 1,717 hypothesis vs 1,752 reference segments |
| ARI | **0.4307** | **match_rate 0.7603** |
| NMI | 0.5625 | match_rate 0.7603 |
| interruption_recall | **0.1224** | **count ratio 0.98** |

**`interruption_recall` 0.1224 is quoted only beside its count ratio, and must be.** `B0-single`
scores **0.796** on the same metric by emitting one segment per session — every fragment of an
interrupted execution trivially lands in the same segment, at count ratio 0.04. Our 0.1224 at
ratio 0.98 and its 0.796 at ratio 0.04 are not comparable numbers; the metric rewards
under-segmentation and is uninterpretable alone. Stitching interrupted executions is genuinely
weak here and §8 says so plainly.

**ARI 0.4307 is reported only with `match_rate` 0.7603**: identity is scored over the 76% of
reference segments that were matched at IoU ≥ 0.5, not over all of them.

## 3. Labelling stability

| | |
|---|---|
| segments → labels | 1,717 → **51** |
| labels used in more than one session | **46 / 51 = 90.2%** |
| segments under a cross-session label | 1,711 / 1,717 (99.7%) |
| mean sessions per label | **15.1** of 63 |

`k` is selected per dataset by stability × cross-session reuse; A's `k` never transfers (ADR-010).
Dataset B independently selects 33 labels from its own data.

**Oracle-k vs unknown-k.** The figures above are **unknown-k** — `k` chosen with no reference to
ground truth, which is the only setting that can run on B. As an evaluation-only reference, A's
ground truth contains 15 process codes; the pipeline selects 51, roughly 3.4× finer. Some of that
is genuine (one process visiting materially different surface shapes splits), some is
over-fragmentation. The gap is the honest measure of how far identity inference is from the
reference, and it is why ARI sits at 0.43 rather than higher.

## 4. Baseline comparison (same population, same grid)

| arm | F1@1s | **F1@2s** | F1@5s | F1@10s | P@2s | R@2s | ratio | ARI | match |
|---|---|---|---|---|---|---|---|---|---|
| B0-single | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.04 | n/a | n/a |
| B1-chunk | — | 0.008 | — | — | 0.059 | 0.004 | 0.07 | 1.000 | 0.002 |
| B2-gap *(oracle k)* | — | 0.089 | — | — | 0.086 | 0.091 | 1.00 | 0.682 | 0.134 |
| B3-random *(oracle k)* | — | 0.109 | — | — | 0.109 | 0.110 | 1.00 | 0.362 | 0.320 |
| B4-surface | — | 0.247 | — | — | 0.153 | 0.639 | 5.03 | 0.770 | 0.562 |
| B5-dwell | — | 0.258 | — | — | 0.173 | 0.504 | 2.83 | 0.797 | 0.597 |
| **S-E4 pipeline** | **0.543** | **0.690** | **0.740** | **0.794** | **0.680** | **0.702** | **0.98** | 0.431 | 0.760 |

**2.67× B5-dwell at τ = 2 s**, and the improvement is not bought by segmenting more: B5-dwell
runs at count ratio 2.83 with precision 0.173, the pipeline at 0.98 with precision 0.680.

`B1-chunk`'s ARI of 1.000 at `match_rate` 0.002 is the standing illustration of why ARI without
`match_rate` is meaningless — it matched two segments.

## 5. Candidate-space quality — NOT segmentation quality

Reported separately, per `EVALUATION_PROTOCOL.md` §9. **This is an upper bound on recall for a
method restricted to this candidate space, and nothing else. It is never an accuracy figure.**

| τ | reachability | density |
|---|---|---|
| 1 s | 77.2% | **0.165 candidates/event** |
| 2 s | **88.0%** | **5.42 candidates/block** |
| 5 s | 92.2% | |
| 10 s | 98.7% | |

The segmenter converts 88.0% reachability into 70.2% recall at τ = 2 s — it uses 80% of what the
candidate space makes available.

## 6. Per-session variability and threshold perturbation (measure 7)

Per-session boundary F1 at τ = 2 s: **mean 0.683, sd 0.115, min 0.022, max 0.807** over 63
sessions. The 0.022 floor is `ses_20260701-152030-CHAITANYA0BCF`, whose GT runs 963 s past the
end of its telemetry (S-E1 §5) — retained, because excluding it would be fitting the evaluation
set.

±20% on every threshold:

| perturbation | F1@2s | count ratio |
|---|---|---|
| baseline | **0.690** | 0.98 |
| `lambda_per_segment` ×0.8 | 0.659 | 1.13 |
| `lambda_per_segment` ×1.2 | 0.666 | 0.65 |
| `min_duration_ms` ×0.8 | 0.688 | 1.00 |
| `min_duration_ms` ×1.2 | 0.686 | 0.94 |

λ is the sensitive knob — ±20% costs ~3 F1 points and moves the count ratio from 1.13 to 0.65.
The duration floor is nearly inert (±0.004 F1), which is worth knowing: it is doing structural
work (suppressing candidate clusters) rather than tuning the result.

## 7. Why AUC is 0.979 but F1 is 0.690 — the denominators

A reviewer will ask, so the two numbers are stated with what they are computed over.

| | AUC | boundary F1 |
|---|---|---|
| population | **26,860 candidates** | **3,504 GT boundary points** |
| positive definition | candidate within 2,000 ms of any GT boundary | GT boundary matched one-to-one within τ |
| positives | 6,034 | 3,504 |

**They are different questions on different units.** AUC asks "does the scorer rank
boundary-adjacent candidates above the rest?" — and it does, almost perfectly. F1 asks "did the
decoder place the right number of boundaries in the right places?"

Three things convert the first into the second, and each costs:

1. **Candidate clustering.** 6,034 positive candidates cover 3,504 boundary points — **1.72
   candidates per true boundary**. Only one can be used; the surplus are either suppressed by
   the duration floor or emitted as false positives.
2. **The reachability ceiling.** 12% of boundary points have no candidate within τ at all, so
   0.88 is the hard recall cap before ranking matters.
3. **Pairing under constraints.** The decoder does not select boundaries independently — it
   selects *segments*, so a start and an end must both be right and ≥ 19 s apart. A perfectly
   ranked boundary whose partner is missing cannot be emitted.

Measured confusion at τ = 2 s: TP 2,334 · FP 1,100 · FN 993. The 1,100 false positives are
predominantly the surplus members of candidate clusters — the direct arithmetic consequence of
point 1.

## 8. A boundary placed strictly INSIDE a block — the ADR-015 evidence

The reorientation from "block = boundary unit" to "block = container" (ADR-015) rests on the
claim that execution boundaries occur inside blocks. Here is one the pipeline found:

```
session   ses_20260630-121953-LAPTOP-R36BQBTE
boundary  1782822073232
block     #b0005   app:Microsoft Excel:m1_reference
          span 1782822017210 – 1782822077149  (59.9 s, 35 events)
          the boundary sits 56.0 s into the block, 3.9 s before it ends
distance to the nearest GT boundary: 438 ms
segment label: process__p00
```

surrounding events:

| Δ to boundary | event_type | app |
|---|---|---|
| −140 ms | `screenshot_smart` | Microsoft Excel |
| −112 ms | `app_switch` | Microsoft Excel |
| −54 ms | `app_switch` | Microsoft Excel |
| **0 ms** | **`app_switch`** | Microsoft Excel |
| +68 ms | `app_switch` | Microsoft Excel |
| +113 ms | `app_switch` | Microsoft Excel |

The surface never changes — it is Excel on the same workbook throughout a 60-second block — so
**no block edge exists here and no block-edge method could ever place this boundary.** What marks
it is a burst of *self-referential* `app_switch` events, exactly the signal S-E2 measured at 71%
of missed boundaries and which ADR-014 preserved by declining to suppress them. The pipeline
places the boundary 438 ms from the truth.

## 9. Sizing Phase G on the precision axis

Phase D characterised the routed population by how many true boundaries it *contains* — the
recall axis — and called it discouraging. Redone on precision: what would perfect adjudication
of every routed candidate be worth?

**Counted in GT boundaries and emitted boundary points, never in candidates.** The obvious
version of this calculation counts candidates in the routed band and adds them to a
boundary-level confusion matrix; with 1.72 candidates per boundary that overstates the gain
several-fold. The first version of this table did exactly that and reported +0.08 F1 at 3.4%
routing. Corrected:

| routing | n routed | recoverable FN | removable FP | **oracle F1** | Δ vs 0.690 |
|---|---|---|---|---|---|
| 3.4% (current) | 913 | 9 | 19 | **0.694** | **+0.004** |
| 5.0% | 1,343 | 15 | 33 | **0.697** | +0.006 |
| 10.0% | 2,686 | 31 | 93 | **0.706** | +0.016 |
| 15.0% (full budget) | 4,029 | 38 | 170 | **0.716** | **+0.025** |

**Perfect adjudication of the entire 15% gate budget is worth +0.025 F1.** A real LLM would
achieve some fraction of that. The recommendation is therefore explicit: **Phase G should be a
compressed demonstration, not a full experiment** — enough to show the adjudicator works and is
ablatable (ADR-018), not a programme aimed at the headline number.

## 10. Where the system still fails

Honestly, and in one place rather than scattered.

**Interruption stitching barely works.** `interruption_recall` is 0.1224: of 98 interrupted
canonical executions, the pipeline assigns all fragments the same label in about one in eight.
The decoder has no resumption model at all — it selects disjoint segments and the labeller
clusters them independently, so a suspended-and-resumed execution is reconstructed as two
segments that only share a label if their surface shapes happen to cluster together. This is the
single largest unaddressed gap, it is measured rather than hidden, and it is not fixable by
tuning: it needs the resumption logic STEP1_SPEC §3.6 describes and this decoder does not
implement.

**Identity is ~3.4× too fine.** 51 labels against 15 reference process codes, ARI 0.43 at
match_rate 0.76. The signature is structural — surface shape, routes, interaction profile — and
two executions of one process that visit different screens split apart. Nothing in the current
signature captures "same business purpose, different route".

**Tight tolerance is weak.** F1 falls from 0.690 at τ = 2 s to 0.543 at τ = 1 s, and recall to
70.9% of a 77.8% ceiling. Sub-second placement is not something this pipeline does; the +176 ms
annotation lead is a floor on how precise it could ever look.

**One session is near-total failure.** F1 0.022 on `ses_20260701-152030`. That is a data defect
(GT running past the telemetry), not a method defect, but it is in the mean and the sd of 0.115
is largely it.

**And the honest limit on all of it:** every number here is Dataset A. The pipeline's behaviour
on B is self-consistent and rule-transferable but **unvalidated**, and no amount of A accuracy
changes that.

## Reproduce

```bash
python3 -m procmine.gt --dataset dataset_a
python3 experiments/SE4-end-to-end-a/run.py
```
