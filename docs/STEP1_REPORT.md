# Step 1 — reconstructing business-process executions from desktop telemetry

**Status: frozen.** Dataset B's `segments.jsonl` is the deliverable; every accuracy figure below
is measured on Dataset A against its ground truth, on the **scoreable canonical** population,
with its denominator stated. Step 2 and Step 3 are not started.

---

## 1. Headline

| | |
|---|---|
| boundary **F1 0.690** at τ=2 s | precision **0.680** · recall **0.702** |
| count ratio | **0.98** (B5-dwell: 2.83) |
| vs the strongest baseline | **2.67×** B5-dwell's 0.258, and not bought by segmenting more |
| recall against the **ceiling** | 0.702 of an achievable **0.900**, i.e. **78%** of what is reachable |

| τ | P | R | F1 | ceiling | R/ceiling |
|---|---|---|---|---|---|
| 1 s | 0.534 | 0.551 | 0.543 | 77.8% | 70.9% |
| **2 s** | **0.680** | **0.702** | **0.690** | **90.0%** | **77.9%** |
| 5 s | 0.729 | 0.752 | 0.740 | 98.7% | 76.2% |
| 10 s | 0.781 | 0.806 | 0.794 | 98.9% | 81.5% |

LOSO over all 63 A sessions, `--no-llm`. segmental F1@IoU 0.5 **0.768** · WindowDiff 0.470 ·
Pk 0.257 · per-session 0.683 ± 0.115. **Recall is never read against 100%**: 10% of GT
boundaries are not reachable from the candidate space at τ=2 s, and quoting 0.702/1.000 would
overstate the remaining headroom by a factor of three.

---

## 2. The reorientation that made the result possible

The project's first number was **59.9% reachability at τ=2 s**, and it was nearly read as a
representation ceiling — as evidence that normalisation had destroyed the information. It had
not. 59.9% was the reachability of the **block-edge candidate space**: the set of positions a
segmenter restricted to block boundaries could even nominate. S-E2 measured whether the
information survived, at event level and at field level, and found category (a) — *destroyed by
preprocessing* — to be **zero** on both. The information was present and unsurfaced (ADR-015:
a block is a container, not a boundary unit).

Adding an intra-block candidate layer took reachability to **88.0%** against a measured ceiling
of **90.0%** — 97.8% of what is achievable — at a candidate density of 0.165/event on A and
0.127/event on B. **Reachability is reported separately from segmentation quality and is never
an accuracy number** (EVALUATION_PROTOCOL §9).

**The concrete case.** `ses_20260630-121953`, a boundary placed **438 ms from truth**, strictly
*inside* a 60 s / 35-event Microsoft Excel block whose surface never changes — located from a
burst of *self-referential* `app_switch` events. Those events were nearly suppressed as
artifacts in Phase 0; ADR-014 kept them on measurement (suppression would have destroyed 176
genuine document boundaries), and they turned out to be the highest-mass intra-block signal.
No block-edge method can place this boundary at all.

---

## 3. Identity: representation → similarity → grouping

Identity was treated as a representation problem, not as "structural labels, then an LLM merge".
Three named views — **WHERE** (surface/route/origin footprint and visit shape), **HOW**
(interaction profile, normalised per event), **WHAT** (character 2-3-gram TF-IDF over titles,
element labels, element ids and field keys; character n-grams because A's titles are Japanese and
B's romanised). Grouping is a kNN graph over a weighted similarity, with **Louvain selecting its
own community count**.

| | ARI | NMI | homogeneity | completeness | labels |
|---|---|---|---|---|---|
| S-E4 structural labeller | 0.431 | 0.563 | 0.622 | 0.514 | 51 |
| graph kNN + Louvain (S-E6) | 0.583 | 0.688 | 0.679 | 0.698 | **15** |
| **+ saturation tie-break (shipped)** | **0.681** | **0.738** | **0.751** | **0.725** | 17 |

All at match_rate **0.760** and boundary F1 **0.690**, unchanged. **Homogeneity and completeness
both rise at every step**, so the gain is not over-merging — ARI alone cannot tell those apart,
which is why all four are always reported. On A the method self-selects **15 communities against
15 true process codes**; that is an outcome, never an input, and on B it selects its own count.

---

## 4. The B5 ARI question, head on

B5-dwell posts **ARI 0.797** against our 0.681 and it is not better at identity. Matched-segment
ARI is not comparable across arms, for two reasons that compound: it is computed only over the
references an arm *matched* (B5: 59.7% of them; us: 76.0%), and it rewards over-segmentation,
because short fragments sit inside a single surface and are trivially label-pure. The reductio is
in the table: **B1-chunk posts matched ARI 1.000 at match_rate 0.0017.**

So Step 1 adds a **granularity-fair metric** (`evaluate.pointwise_identity`): every event — and
separately every second of session time — takes the label of its containing segment, scored
against GT process codes over **100% of the timeline**. Points in no segment carry an explicit
`unassigned` label on both sides rather than being dropped, because ADR-020 measured that ~19% of
session time belongs to no execution.

| arm | matched ARI | match_rate | **event ARI** | **time ARI** | count ratio | labels |
|---|---|---|---|---|---|---|
| **pipeline (shipped)** | 0.681 | 0.760 | **0.297** | — | **0.98** | 17 |
| pipeline (pre-tie-break) | 0.585 | 0.760 | 0.267 | 0.269 | 0.98 | 15 |
| S-E4 structural | 0.431 | 0.760 | 0.182 | 0.184 | 0.98 | 51 |
| B5-dwell | **0.797** | 0.597 | 0.250 | 0.200 | 2.83 | 130 |
| B4-surface | 0.770 | 0.562 | 0.244 | 0.162 | 5.03 | 140 |
| B2-gap | 0.682 | 0.134 | 0.119 | 0.103 | 1.00 | 72 |
| B3-random | 0.362 | 0.320 | 0.121 | 0.080 | 1.00 | 56 |
| B1-chunk | **1.000** | **0.0017** | 0.005 | −0.006 | 0.07 | 32 |
| B0-single | — | — | 0.003 | −0.008 | 0.04 | 16 |

**The fair comparison is the event/time one**, and it puts the pipeline ahead — 0.297 vs 0.250 on
events, 0.269 vs 0.200 on time. Two honest qualifications: the margin on identity (**1.19×**) is
far narrower than the 2.67× on boundary placement, and B5 achieves its 0.250 with **130 labels at
count ratio 2.83**, which is not a usable process inventory. B5's event homogeneity (0.451) even
exceeds our pre-tie-break 0.418 — its fragments are pure — while its completeness (0.359 vs
0.427) shows what that purity costs.

---

## 5. Why there is no LLM

An LLM was **sized three times against a measured ceiling and rejected three times on evidence.**

| what an LLM was proposed for | ceiling, measured | verdict |
|---|---|---|
| merging/renaming identity labels | merge-only oracle **ARI 0.478** | below the **0.583** clustering already achieves — bounded before it was written |
| adjudicating ambiguous boundaries | oracle **+0.026 F1** at the *full* 15% gate budget (+0.004 at the actual 3.4%) | perfect adjudication of the entire budget is worth 2.6 points |
| supplying missing semantics for identity | supervised probe **0.891 accuracy / ARI 0.786** on the same features | the information is *present*, not missing |

The third is decisive. A logistic regression over exactly the features the clusterer sees
recovers the reference process code at 0.891 accuracy, so the residual is not a semantics gap
that a language model could fill — it is an unsupervised-objective gap. `--no-llm` is the shipped
path and is tested end to end.

**The identified next step, scoped and deliberately not built:** metric learning from LLM
pseudo-labels — use a bounded LLM to label a sample of *pairs* as same/different process, fit the
view weighting to that signal, and ablate it against the current unsupervised rule. That places
the model where the measurement says the gap is (the objective, not the representation). It is
out of scope for Step 1 and is recorded rather than half-built.

---

## 6. The residual, named as a finding

S-E6b set out to fix the largest identity defect and instead falsified the mechanism behind it.
The offending cross-process pairs have a surface **Jaccard of exactly 1.00** — *identical*
surface sets, a mean of 1.35 shared surfaces and that is every surface either one has. No term
re-weighting can separate identical sets, and IDF measurably made things worse (separability
Cohen's *d* 1.535 → 1.508; ARI −0.031). It is implemented, tested, ablatable and **off**.

The tie-break that ships attacks the same pairs from the other side: where WHERE is saturated it
carries no information, so it is discarded and the pair is decided on WHAT and sequence. That
bought +0.096 ARI — the largest single identity gain in the project — and still leaves the
top-similarity cross-process pairs co-clustered.

**The finding: executions with identical structural footprints and different business purpose are
observationally equivalent at the UI-event level.** Two operators opening the same page, typing
into the same fields, for two different business reasons, emit the same events. That is a limit
of desktop telemetry, not a defect in the method, and no amount of clustering removes it.

---

## 7. Limitations — stated, not buried

- **Interruption stitching 0.337** (from 0.122), at count ratio 0.98 and 17 labels. There is no
  resumption model; fragments of one suspended execution share a label only by resemblance. Read
  it with the label count: coarser labels raise it mechanically, which is why DBSCAN at eps 0.45
  posts 0.857 with ARI −0.001, and B0-single posts 0.796 degenerately.
- **Residual decomposition.** Of 411 misgrouped matched executions, roughly **145 are
  probe-hard** (the supervised probe misses them too — genuinely ambiguous) and roughly **266 are
  clustering-specific headroom** a better unsupervised objective could still reach.
- **Scaffolding left in deliberately.** 98/1,717 executions (5.7%) carry setup/launch/theme
  signatures; 44 are in the matched population and they account for 9.5% of the residual error —
  a **2.9× enrichment**. They stay: excluding inconvenient executions is fitting the evaluation
  set.
- **One truncated session** whose GT extends far beyond its telemetry scores F1 0.022 and is in
  the mean. Reported as that session, never as a dataset-wide failure.
- **The +176 ms annotation lead.** GT leads the nearest retained event by ≈176 ms (p50). Any
  τ below 1 s is measuring the annotation offset, not the method. The separate ≈820 ms
  GT-to-block-edge distance is a property of the candidate space under measurement and must never
  be used as a correction.
- **Rare-process behaviour is untestable on A.** All 15 reference codes appear ≥ 14 times among
  the 1,332 matched executions.
- **Consecutive same-process executions are untestable on A** — 0 of 1,689 consecutive pairs
  share a code. On B the frozen system emits them readily: **67 of 168** consecutive segment
  pairs share a label (39.9%, median gap 7.0 s), **7** of them with identical surface sets. So
  the system does split adjacent same-process executions rather than merging them — but B has no
  ground truth, so that is an observation, not a validation (S-E8).
- **Dataset B is unvalidated throughout.** It has no ground truth; every B figure below is
  internal consistency, never accuracy.
- **Every identity figure lives at match_rate 0.760** and none of it generalises to the unmatched
  24%.

---

## 8. Populations and denominators

| population | n | use |
|---|---|---|
| raw manifest executions | 2,009 | 257 have no end timestamp |
| canonical (grouped by `split_id`) | 1,819 | of which **98 interrupted** (5.4%) |
| **unscoreable** | **230** | excluded, reported as an exclusion |
| **scoreable canonical** | **1,589** | **the denominator for every accuracy figure** |

→ 1,752 fragments → **3,504 boundary points**. Confidence tiers: clean 1,756 / repaired 63 /
disputed 0. **Candidate-space quality is reported separately from segmentation quality** and is
never presented as accuracy (EVALUATION_PROTOCOL §9).

---

## 9. The method — and what it caught

**Every gate measured a ceiling before anything was built.** That discipline caught **five**
denominator or mechanism errors, two of them in my own recommendations:

1. **The 59.9% "representation ceiling"** was the reachability of the block-edge candidate space.
   Treating it as representation loss would have triggered a rewrite of working perception code.
2. **The S-E2 ceiling of 74.7%** was `100 − 25.3`, a share-of-missed used as a share-of-all.
   Recomputed directly: **90.0% at τ=2 s**, and τ-dependent.
3. **The "+820 ms annotation lead"** conflated GT-to-event (176 ms) with GT-to-block-edge
   (820 ms). Correcting for the second would have been circular — it is the thing under
   measurement.
4. **The Phase G oracle sizing** counted *candidates* in a *boundary*-level confusion matrix. At
   1.72 candidates per boundary it reported +0.08 F1; recomputed in boundaries it is **+0.004**.
   The only one of the five that would have changed a build decision.
5. **The IDF mechanism in ADR-021** — my own. "They share the dashboard root" was a true
   observation promoted to a causal mechanism without checking the Jaccard, which is 1.00.

**Three times, measuring the ceiling first prevented building something that could not have
paid:** the LLM label-merger (bounded at 0.478, below what clustering already reached), the LLM
boundary adjudicator (+0.026 F1 for the entire gate budget), and IDF weighting (mathematically
incapable of moving identical sets). Each is recorded as a negative result with its number.

The same discipline produced the deliberate non-optimisations: block thresholds were not tuned to
a suggested 60–80 blocks/session; `mode_transition` was demoted to feature-only despite costing
1.9 points of reachability, because a trigger firing on 77.7% of intra-block positions is not
discriminating; and B was never tuned to resemble A.

---

## 10. Dataset B output — no accuracy claims

`segments.jsonl`, produced by the frozen code with no B-specific branch: `make run-b` is
`build-b` + `segment-b`, and `cli.segment()` is the **single** writer of the deliverable, which
it validates against `DATA_CONTRACT.md` §6 before the file is considered written. `make run-b`
succeeds with `dataset_a/` absent from disk (verified by moving it out of the tree), and two
consecutive runs produce byte-identical output.

Until the freeze this was not true, and it bit: `run-b` ended in the Phase B block-run safety
net, which defaulted to the same path, so running the leakage check silently replaced the
Phase D/E deliverable with a 958-segment block-edge-only file. The safety net now writes to
`build/<dataset>/segments_provisional.jsonl` and refuses the deliverable path without `--force`;
a test asserts that exactly one module in the package writes it.

| | |
|---|---|
| segments | **183** across **15** sessions |
| labels | **13**, self-selected on B by Louvain (A's count never transfers) |
| cross-session reuse | 11 of 13 labels used in more than one session (0.846), mean 6.2 sessions/label |
| largest label | 14.8% of segments |
| mean modal-surface share | **0.840** |
| mean modal-route share | **0.859** |

The last two are the internal-consistency check that caught a real error: an earlier
configuration produced 6 labels whose members mostly did *not* share their own cluster's modal
surface (0.32–0.52). That is not a process identity, and it was rejected on those grounds rather
than on a score. **These are consistency figures. B has no ground truth and none of this is an
accuracy claim.**

---

## 11. Freeze

Every similarity weight, clustering hyperparameter, graph `k` and seed is pinned and declared in
`build/<dataset>/thresholds.json` (2 `tolerance_derived` · 7 `structural` · 7 `a_fitted`). The
`where_heavy` view weighting and the tie-break rule are the identity-stage **A→B transfers**,
declared under the ADR-019 conditions: structural and domain-neutral, with no A surface, route,
origin, process name, vocabulary item or cluster count crossing over. **`k` is not transferred** —
Louvain selects it on B, from B.

Contract tests: identity grouping cannot move a boundary; grouping is deterministic under a fixed
seed; two runs are byte-identical; no inference module reads a GT artifact (AST, over *every*
inference module, with a test that fails if a new module is added unclassified); the generator has
no chunk-derived trigger; `--no-llm` green end to end. Suite: 300 tests.

Experiments: `E01` · `E11` · `SE1` · `SE2` · `SE3` · `SE4` · `SE6` · `SE6b` · `SE8`.
Decisions: ADR-001 … ADR-021 and its addenda.

**Step 1 ends here.**
