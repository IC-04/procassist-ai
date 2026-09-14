# S-E6b — the fixes ADR-021 proposed, measured

Segmentation frozen: 1,717 S-E4 segments, boundary F1 **0.6904** @ τ=2 s and match_rate
**0.760** identical on every arm (`metrics.json.contract_boundary_f1` → `true`). No LLM.

## The headline: the main fix does not work, because the diagnosis was wrong

ADR-021 named IDF-weighting as the next step, on S-E6's case study 3: *"99% of the
highest-similarity cross-code pairs are wrongly grouped, and what they share is the portal
dashboard root."* The observation was true — 71% of them do share it. The mechanism inferred
from it was not.

| the 97 offending cross-process pairs | |
|---|---|
| mean surface Jaccard, plain | **1.00** |
| mean surface Jaccard, IDF-weighted | **1.00** |
| mean shared surfaces | 1.35 |
| mean similarity, plain → IDF | 0.9108 → 0.9093 |

**Their surface sets are identical.** Jaccard = 1.0 means set equality, and the Jaccard of two
identical sets is 1.0 under *any* term weighting — IDF, BM25 or otherwise. These are short
executions that visit exactly the same page and differ only in business purpose. No
re-weighting of set members could ever have separated them, and one check of the Jaccard before
writing the ADR would have shown it.

## Task 1 + 2 — the ablation

Shipped configuration (`where_heavy`, k_nn=20) held fixed; only the named factor varies.

| arm | ARI | NMI | hom | cmp | labels | case 1 | case 2 | case 3 |
|---|---|---|---|---|---|---|---|---|
| plain, linear (control) | 0.580 | 0.685 | 0.676 | 0.695 | 15 | 0.017 | 0.017 | 1.000 |
| **plain, adaptive** | **0.585** | **0.696** | 0.686 | **0.707** | 15 | 0.017 | 0.017 | 1.000 |
| plain, noisy-OR | 0.588 | 0.683 | 0.695 | 0.672 | 17 | 0.017 | 0.017 | 1.000 |
| IDF, linear | 0.549 | 0.669 | 0.671 | 0.667 | 17 | 0.017 | 0.017 | 0.991 |
| IDF, adaptive | 0.567 | 0.678 | 0.674 | 0.682 | 16 | 0.017 | 0.017 | 1.000 |
| IDF, noisy-OR | 0.541 | 0.654 | 0.666 | 0.642 | 18 | 0.017 | 0.017 | 1.000 |

Separability over matched executions (within-code minus between-code): **0.2263 → 0.2180**,
Cohen's *d* **1.535 → 1.508**. **IDF is worse on every axis.** Retained, unit-tested, ablatable,
**default OFF**.

**Adaptive combination ships**: +0.005 ARI, +0.011 NMI, homogeneity *and* completeness both up.
Small and real. Noisy-OR reaches 0.588 but at 17 labels with completeness falling to 0.672 — it
buys ARI by over-merging, the failure mode this project exists to catch.

**Case studies 1 and 2 must be restated.** S-E6's 13.3% was measured under the *rule-1* arm
(`how_heavy`, k_nn=5, 24 rhythm-driven communities), not the shipped one. Under the shipped arm
it is **1.7%**, and no combination mode moves it. A case-study rate is only comparable within one
arm; that number should not have been carried across them.

**Per-view separability explains all of it** (Cohen's *d*): sequence 1.545 · WHERE 1.425 ·
WHAT 1.190 · HOW **0.410**. The similarity is not weighting the wrong terms — it is being asked
to separate executions whose structural footprints are genuinely identical.

## Task 3 — scaffolding contamination (reported, NOT removed)

Detector is structural — terminal-only app set, `SETUP`/`launch`/`theme`/`_reference` filename
tokens, terminal present with no web surface — and uses no A process name.

| | |
|---|---|
| flagged executions | **98 / 1,717 (5.7%)** |
| flagged in the matched population | 44 / 1,332 (3.3%) |
| share of residual misgrouping | **39 / 411 (9.5%)** |
| enrichment over base rate | **2.9×** |
| case-1 pairs touching scaffolding | 0 / 60 |
| case-2 pairs touching scaffolding | 0 / 60 |

Real contamination, meaningfully enriched in the errors, and **a minority of the problem**.
Neither case study 1 nor 2 is driven by it. It stays in the pipeline: excluding inconvenient
executions is fitting the evaluation set.

## Task 4 — Dataset B: 6 clusters was not defensible

The selection rule picks `where_heavy` on A's 1,717 executions and **`how_heavy` on B's 183** —
the view the supervised probe measured at 0.256 accuracy. **The rule degrades at a tenth of A's
data.** B has no ground truth, so the test is internal consistency:

| B configuration | clusters | largest share | reuse | modal-surface share | modal-route share |
|---|---|---|---|---|---|
| `how_heavy`/linear/k20 (the old selection) | **6** | 0.31 | 0.83 | **0.32–0.52** | 0.44–0.63 |
| `where_heavy`/linear/k5 | 11 | 0.169 | 0.91 | **0.813** | 0.871 |
| `where_heavy`/linear/k10 | 9 | 0.169 | 1.00 | 0.772 | 0.821 |
| **`where_heavy`/linear/k20 (shipped)** | **8** | 0.180 | **1.00** | **0.765** | **0.918** |

Under the 6-cluster result, *fewer than half* the members of a "process" visit that process's
own most common surface. That is not a process identity. **The view weighting is now fixed to
`where_heavy`**, declared as an A→B transfer under the ADR-019 conditions — structural and
domain-neutral, with no A surface, route, process name, vocabulary or cluster count crossing
over — and `k` is still selected on B, by B.

`segments.jsonl` regenerated and committed: **183 segments, 8 labels, 15 sessions**, 100%
cross-session reuse, mean 8.25 sessions per label. It still trips the one known
`validate_segments` false positive (an intra-block boundary at a chunk edge; the validator's
`justified` set is built from *block* boundaries, a Phase B assumption predating ADR-015).

## Task 5 — not done

Conditional on 60 minutes remaining; not reached. No dependency was added, and the brief's own
prior — that a corpus of code identifiers and filenames favours char n-grams over a sentence
encoder — remains untested and open.

## Where this leaves identity

The residual is **executions with identical structural footprints and different business
purpose**. IDF cannot touch it, adaptive combination cannot touch it, and the supervised probe
(0.891 accuracy) proves the discriminating information is nonetheless present in the features.
That is precisely the place a semantic judge would have to earn its keep — and whether it can
must be established by ablation, not asserted. **No LLM is justified on the evidence available.**
Metric learning from LLM pseudo-labels is recorded as future work and was not built.
