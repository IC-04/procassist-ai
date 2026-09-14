# S-E6 — the identity ceiling, and which grouping method is justified

**Question.** S-E4 left identity as the weakest part of Step 1: ARI 0.431 / NMI 0.5625 at
match_rate 0.760, 51 predicted labels against 15 reference process codes, and the diagnosis
*"nothing in the current signature captures same business purpose, different route."* That is
a claim about **representation**, so identity is tested here as

    REPRESENTATION -> SIMILARITY -> GROUPING -> IDENTITY

and whether an LLM is justified is decided at the end, by measurement. **No LLM was used.**

**Contract (G-A0).** Every arm operates on the exact frozen S-E4 segmentation — 1,717
hypothesis segments, reproduced by `build_frozen.py` and verified at boundary F1 **0.6904**
(τ=2 s) and count ratio **0.98**, identical to S-E4. No arm adds, deletes, moves or merges a
boundary. `metrics.json.contract_boundary_f1.identical_on_every_arm` is `true`, and
`tests/test_identity.py::test_grouping_cannot_move_a_boundary` asserts the property directly.
Every metric comes from `evaluate.evaluate_all` (and through it `identity_scores`,
`matched_identity`, `interruption_recall`); none is reimplemented.

---

## G-A1 — the three-view representation audit

| view | dimensionality | sparsity | coverage |
|---|---|---|---|
| **WHERE** | 116 surfaces · 31 routes · 825 surface bigrams | 0.978 | **1.00** |
| **HOW** | 20 dense features | 0.230 (15.4/20 non-zero) | **1.00** |
| **WHAT** | char 2-3-gram TF-IDF, mean 188 chars of evidence per execution | sparse | **1.00** |

WHAT uses **character n-grams, not words**: Dataset A's titles are Japanese
(財務会計システム) and Dataset B's are romanised, and no tokeniser covering both is available
without a new dependency.

**One thing the spec asked for is absent, and it is recorded rather than worked around.**
`context.extracted_text` is not exposed by `normalise.flatten_event`'s flat record, and
`normalise.py` is not modifiable in this phase. WHAT is therefore built from window titles,
element labels, element ids and field keys only. Its coverage is 1.00 regardless, so nothing
in the analysis below rests on the missing field.

### Three executions, rendered in all three views

| | ex. 1 `ses_20260630-121953` | ex. 2 `ses_20260701-072319` | ex. 3 `ses_20260701-172430` |
|---|---|---|---|
| **WHERE** | Terminal → Notepad → Notepad(SETUP.md) → `web:5122/` → Excel → Excel | `web:5124/social-insurance` → Notepad | `5124/payroll-items` → `5123/social-insurance` → PowerPoint → `5123/social-insurance` → `5122/dashboard` → `5123/dashboard` |
| routes | `/` | `/social-insurance` | `/dashboard`, `/payroll-items`, `/social-insurance` |
| **HOW** | typing .138 · pointing .000 · nav .517 · 24.5 ev/min | typing .276 · pointing .103 · nav .138 · 59.8 ev/min | typing .049 · pointing .115 · nav .557 · form .016 · 56.3 ev/min · revisit .167 |
| **WHAT** | `Theme M1 — Mixed Multi-Domain (HR / Finance / Ops)`, `SETUP.md`, `Untitled` | `受発注在庫管理システム`, `Untitled` | `受発注在庫管理システム`, `調整内容・差異原因を入力してください…`, `btn-pi-register`, `pi-note`, `財務会計システム` |

Example 1 is a setup execution and looks nothing like a business process; examples 2 and 3
show what WHAT contributes that WHERE cannot — `btn-pi-register` / `pi-note` name the *object
being manipulated*, not the page it sits on.

---

## G-A2 — the similarity

    S = w_where·sim_where + w_how·sim_how + w_what·sim_what + w_seq·sim_sequence

weighted Jaccard over surfaces / routes / origins / bigrams; cosine over the z-scored HOW
vector; cosine over char-n-gram TF-IDF; `rapidfuzz` normalised Levenshtein similarity over the
surface-visit shape. Dense 1,717 × 1,717 (≈2.9 M pairs), computed **once**; every graph below
is a slice of it. Five declared weightings, no search, no tuning against ARI. Reference process
codes never enter the similarity.

| weighting | mean S | p50 | p95 | p99 |
|---|---|---|---|---|
| uniform | 0.111 | 0.076 | 0.315 | 0.481 |
| where_heavy | 0.109 | 0.077 | 0.324 | 0.493 |
| what_heavy | 0.114 | 0.087 | 0.289 | 0.437 |
| how_heavy | 0.129 | 0.068 | **0.431** | 0.579 |
| balanced | 0.113 | 0.081 | 0.310 | 0.469 |

---

## G-A3 — the two ceilings, and a third diagnostic

### (3a) Merge-only oracle — it is SMALL

| | |
|---|---|
| ARI after perfect relabelling | **0.478** (from 0.431) |
| NMI | 0.558 · homogeneity 0.553 · completeness 0.563 |
| reference codes split across labels | **15 of 15** |
| predicted labels that are IMPURE | **37 of 41** |
| matched members under a wrong-majority label | **30.2%** |

**Bounds relabelling only**; membership is held fixed. Re-clustering arms are *not* bounded by
it and may legitimately exceed it — the winning arm does. Perfectly renaming the existing 51
clusters buys **+0.047 ARI**, because the clusters are impure and impurity is not
merge-fixable. Relabelling was never the lever, so an "LLM merges the labels" design was
bounded at 0.478 before it was written.

### (3b) Supervised probe — the decisive measurement (DIAGNOSTIC ONLY, never runs on B)

Logistic regression, LOSO by session, on the frozen representation. An upper bound on any
unsupervised method over it.

| view | accuracy | macro-F1 | ARI |
|---|---|---|---|
| **WHERE** | **0.851** | 0.847 | 0.720 |
| HOW | 0.256 | 0.216 | 0.141 |
| WHAT | 0.741 | 0.734 | 0.535 |
| **all three** | **0.891** | **0.888** | **0.786** |

*(15 classes, n = 1,332; chance accuracy ≈ 0.07.)*

**This refutes the reframe's own hypothesis.** WHERE is the *strongest* view, not an
overweighted one. HOW — the view the reframe proposed as the missing ingredient — is close to
worthless on its own. WHAT is real and adds +0.040 accuracy on top of WHERE. The identity
signal was already in the representation; the problem was never that the features are
location-bound.

### (3c) Segmentation-inherited error (DIAGNOSTIC ONLY, never shipped)

The same representation and grouping run on **GT segments** instead of hypothesis segments:
ARI **0.427** (NMI 0.625, 27 clusters, match_rate 1.00 by construction) — within **0.004** of
the structural labeller on hypothesis segments. **Identity error is caused by grouping, not by
imperfect segmentation.** Perfect boundaries would not have fixed it.

---

## G-A4 / G-A5 — the arms

Boundary F1 is identical on every row (0.6904 @ τ=2 s; 0.5428 / 0.6904 / 0.7404 / 0.7937 over
the τ grid) — the column is shown to prove it. Match rate is identical on every row (0.760) for
the same reason. **Ceiling rows are ceilings, not arms.**

| arm | ARI | NMI | hom | cmp | match_rate | labels | ratio | reuse | sess/label | intR | runtime | det. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S-E4 structural (control) | 0.431 | 0.563 | 0.622 | 0.514 | 0.760 | 51 | 0.98 | 0.902 | 15.1 | 0.122 | 89 s | ✓ |
| k-means (k=30, vector space) | 0.222 | 0.444 | 0.487 | 0.407 | 0.760 | 30 | 0.98 | 1.000 | — | 0.102 | 2 s | ✓ |
| agglomerative average (k=30) | 0.109 | 0.254 | 0.250 | 0.258 | 0.760 | 30 | 0.98 | 0.900 | — | 0.174 | <1 s | ✓ |
| agglomerative complete (k=30) | 0.122 | 0.285 | 0.300 | 0.272 | 0.760 | 30 | 0.98 | 1.000 | — | 0.092 | <1 s | ✓ |
| DBSCAN (eps 0.30) | 0.163 | 0.536 | 0.729 | 0.424 | 0.760 | 643 | 0.98 | 0.087 | — | 0.071 | <1 s | ✓ |
| DBSCAN (eps 0.45) | −0.001 | 0.027 | 0.015 | 0.266 | 0.760 | 35 | 0.98 | 0.143 | — | **0.857** | <1 s | ✓ |
| graph kNN(k=5, rule-1 config) + Louvain | 0.204 | 0.407 | 0.425 | 0.390 | 0.760 | 24 | 0.98 | 1.000 | — | 0.102 | 5 s | ✓ |
| graph mutual-kNN(k=5) + Louvain | 0.168 | 0.519 | 0.670 | 0.423 | 0.760 | 190 | 0.98 | 0.474 | — | 0.061 | 4 s | ✓ |
| graph threshold(p99.5) + components | 0.001 | 0.220 | 0.164 | 0.336 | 0.760 | 253 | 0.98 | 0.142 | — | 0.490 | 2 s | ✓ |
| graph threshold(p99.5) + Louvain | 0.225 | 0.487 | 0.577 | 0.421 | 0.760 | 275 | 0.98 | 0.211 | — | 0.041 | 2 s | ✓ |
| spectral (k=30, precomputed affinity) | 0.172 | 0.354 | 0.386 | 0.327 | 0.760 | 30 | 0.98 | 1.000 | — | 0.092 | 6 s | ✓ |
| **graph kNN(k=20, where_heavy) + Louvain — rule 2** | **0.583** | **0.688** | **0.679** | **0.698** | 0.760 | **15** | 0.98 | **1.000** | 34.7 | **0.337** | 14 s | ✓ |
| *— ceiling: merge-only oracle (relabelling only)* | *0.478* | *0.558* | *0.553* | *0.563* | *0.760* | *≤41* | — | — | — | — | — | — |
| *— ceiling: supervised probe, all views (diagnostic)* | *0.786* | — | — | — | *0.760* | *15* | — | — | — | — | — | — |
| *— diagnostic: same method on GT segments* | *0.427* | *0.625* | *0.656* | *0.598* | *1.00* | *27* | — | — | — | — | — | — |

Reading the table honestly:

* **Homogeneity and completeness both rise** for the winning arm (0.622→0.679 and 0.514→0.698).
  ARI alone cannot separate over-merging from over-splitting; here neither is happening.
* **DBSCAN at eps 0.45 posts interruption_recall 0.857 with ARI −0.001.** That is the
  degenerate mode, identical in kind to B0-single's 0.796 — 35 labels with one swallowing
  almost everything. It is why interruption_recall is never quoted without the label count.
  The winning arm's 0.337 is also partly mechanical (15 labels vs 51), and is stated as such.
* **DBSCAN is structurally unsuited here** and was not tuned beyond two settings: one global
  `eps` cannot fit both a 300-execution routine and a rare one, and at eps 0.30 it marks 585 of
  1,717 executions as noise while producing 643 labels with 8.7% cross-session reuse.
* **k-means runs on the explicit vector space, not on S**, because S is a weighted sum of
  similarities and is not a proper metric. This is stated wherever its result appears.

### The graphs

| graph | nodes | edges | density | degree min/p50/mean/max | isolates | components |
|---|---|---|---|---|---|---|
| kNN k=5 | 1,717 | 5,953 | 0.0040 | 5 / 6 / 6.9 / 21 | 0 | 2 |
| mutual-kNN k=5 | 1,717 | 2,632 | 0.0018 | 0 / 3 / 3.1 / 5 | 89 | 164 |
| threshold S>0.637 (p99.5) | 1,717 | 7,366 | 0.0050 | 0 / 6 / 8.6 / 48 | 210 | 253 |

The thresholded graph shatters — 253 components, 210 isolates — because similarity is not
uniformly scaled across processes. That is exactly the assumption kNN does not make, and it is
why connected-components is the trivial baseline it looks like (ARI 0.001).

---

## Hyperparameter discipline — and a rule that failed

Two unsupervised selection rules were run, each declared **before** its ARI was inspected.

| rule | selects | measured ARI |
|---|---|---|
| modularity × cross-session reuse | `how_heavy`, k_nn=5, 24 communities | **0.204** |
| stability(80% resampling, co-cluster Jaccard) × cross-session reuse | `where_heavy`, k_nn=20, **15** communities | **0.583** |

Rule 1 failed for a structural reason, not a tuning accident: **modularity is not comparable
across graphs of different density.** Sparser graphs score higher almost mechanically, so rule 1
was really selecting "the sparsest graph" — and it scored `how_heavy` and `where_heavy`
*identically* at 0.8669, unable to distinguish the view the probe shows carries the signal from
the one that carries almost none. Rule 2 is the Phase E rule (`label.choose_k`) applied to a
self-selecting-`k` method, and it lands on the best configuration in the grid.

The GT-informed sweep, shown as a **development analysis and not as an unsupervised selection**,
confirms rule 2 chose the optimum:

| weighting | k_nn | communities | ARI | NMI | hom | cmp |
|---|---|---|---|---|---|---|
| where_heavy | 10 | 22 | 0.583 | 0.674 | 0.701 | 0.650 |
| **where_heavy** | **20** | **15** | **0.583** | **0.688** | 0.679 | 0.698 |
| balanced | 10 | 22 | 0.573 | 0.695 | 0.723 | 0.668 |
| balanced | 20 | 17 | 0.546 | 0.687 | 0.686 | 0.688 |
| uniform | 20 | 18 | 0.502 | 0.679 | 0.690 | 0.669 |

**"15 reference process codes" is never a production assumption.** That A's selected
configuration yields 15 communities is an *outcome*. On Dataset B the same code re-runs the
sweep and Louvain selects B's own count — measured, it picks **6** (below).

---

## G-A5 — inspecting the graph

Under the **rule-1** configuration (`how_heavy`, k_nn=5) the five largest communities are
mixed bags of every reference code — c0 spans F/A/E/H/K/O, c1 spans A/F/G/L/B/O — with the
single exception of **c3 (size 130, 47 sessions)**, which is 56 × `M` and 54 × `C`, both
driven by `/leave-applications` with `btn-la-approve` and `la-note` as its dominant WHAT
tokens, and a distinctive `仕入先への依頼内容または保留理由を入力してください…` prompt appearing in 70
members. c3 is the one place the graph is genuinely discovering *"same business purpose,
different route"* — its members reach that purpose through three different origins
(`:5122`, `:5124`, `:5123`) and it still holds together. Everywhere else, rule 1's graph is
re-finding **interaction rhythm** (`rate_events_per_min` 125–201 across communities), which the
probe says is nearly uninformative — which is precisely why rule 1 scores 0.204.

The most important *difference* inside those communities is the one that gives the answer:
they share portal surfaces while their business objects differ. Which is the next case study.

---

## Five case studies

1. **Same process, different route.** 60 same-code pairs with *disjoint* route sets:
   **13.3% grouped together.** Example — code `H`, one execution at
   `web:5122/` + `Microsoft Excel:m1_reference`, another at
   `Google Chrome:受発注在庫管理システム` + `Google Chrome:財務会計システム` + `Notepad:launch_m1.ps1`,
   similarity 0.269, different communities. This is the failure S-E4 named, and it is still the
   failure: when the route set does not overlap at all, the surface Jaccard contributes nothing
   and the sequence similarity is comparing different shapes.
2. **Same process, different application/surface.** 60 same-code pairs with disjoint *surface*
   sets: **13.3% grouped together.** The same mechanism — the two surviving signals (WHAT and
   HOW) are not weighted heavily enough to carry the pair alone.
3. **Different processes that look structurally similar.** 100 cross-code pairs above the
   99.9th similarity percentile: **99% wrongly grouped.** What they share is
   `web:http://127.0.0.1:5122/` — the portal **dashboard root**, a surface every one of the 15
   processes passes through. This is the single largest concrete defect, and it has a cheap
   deterministic fix: IDF-weight the surface Jaccard so a universal surface stops counting as
   evidence.
4. **Fragments of one interrupted execution.** 97 interrupted executions had more than one
   fragment matched to a hypothesis segment. Under the winning arm, **33.7%** have all their
   fragments under one label (`interruption_recall` 0.337, up from 0.122, at an unchanged count
   ratio of 0.98 and with 15 labels rather than 51 — part of the rise is that coarseness).
   Example success: `ses_20260630-121953`, code `B`, two fragments, both in community 12.
   Example failure: `ses_20260630-124826`, code `K`, two fragments, communities 5 and 19 —
   the decoder has no resumption model, so the two halves are only ever grouped by resemblance.
5. **Rare process / small cluster.** **There is none.** All 15 reference codes appear ≥ 14
   times among the 1,332 matched executions, so Dataset A cannot test rare-process behaviour at
   all. Reported as a limit of the dataset, not answered by picking the smallest cluster and
   calling it rare.

---

## Transfer to Dataset B

`label.py` now defaults to `method="graph"`. Running the full deterministic chain on
`dataset_b` (`--segment --no-llm`, `dataset_a/` untouched), the same code re-runs its own
configuration sweep and Louvain selects **6** communities over 183 segments in 15 sessions —
100% cross-session reuse, mean 7.8 sessions per label, against 33 labels under the structural
labeller. **B has no ground truth and this is not validated.** 6 labels for 183 segments is
coarse and may be over-merging on a tenth of A's data; it is reported as an observation, and
B's output is deliberately not tuned to resemble A's.

**One consequence to raise rather than act on:** the committed `segments.jsonl` was emitted
under the previous default (33 labels). Changing the shipped deliverable is outside this
experiment's scope, so it was left alone and the divergence is flagged.

---

## Decision

**CASE B, by the letter of the criterion — but the qualification matters more than the label.**
Graph clustering improves identity materially (ARI 0.431 → 0.583, NMI 0.563 → 0.688, with
homogeneity *and* completeness both rising, at byte-identical boundary F1) yet closes only
~43% of the recoverable gap to the supervised probe — so a residual remains. That residual is
**not** a missing-semantics gap: a logistic regression on exactly these features reaches 0.891
accuracy, so the information is present and unsupervised clustering simply is not extracting
it, and the concrete defect is a shared portal dashboard root rather than an unreadable
business meaning. **An LLM is therefore not justified yet**, `STEP1_SPEC.md` §3.7 is unchanged,
"LLM identity normalisation" is explicitly not hard-coded, and the next thing to try is
IDF-weighting the surface Jaccard — deterministic, free, and aimed directly at the 99% failure
in case study 3.

Recorded as **ADR-021**.

## What would change this conclusion

* An IDF-weighted surface Jaccard that does *not* move case study 3's 99% — that would say the
  shared-surface diagnosis is wrong and the residual really is semantic.
* A per-view probe on **Dataset B**'s domain showing WHAT dominant rather than WHERE; A is
  portal-heavy and that is the transfer risk in this representation, exactly as
  `is_web_surface` was for the scorer (ADR-019).
* Any evidence that the 1,332-of-1,752 matched population is unrepresentative — every identity
  figure here lives at match_rate 0.760 and none of them generalises to the unmatched 24%.
