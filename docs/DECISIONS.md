# DECISIONS — Architecture Decision Records

Append-only. An ADR is required to change anything in `ARCHITECTURE.md` or a `*_SPEC.md`.

**Format:** ID · Date · Status (`accepted` | `superseded by ADR-NNN`) · Context · Decision ·
Consequences · Evidence.

---

### ADR-001 · 2026-09-11 · accepted · Chunks are dissolved during normalisation
**Context** `DATA_SCHEMA.md` §1: chunks are fixed recording-time buckets with no business
meaning; `correlation.sequence_number` restarts per chunk.
**Decision** `normalise.load_session` merges all chunks of a session and rebuilds global order
from `timestamp_ms`. A chunk boundary may never appear as a predicted boundary.
**Consequences** Baseline `B1-chunk` exists solely to demonstrate that chunks are meaningless.
**Evidence** Schema, explicit.

### ADR-002 · 2026-09-12 · accepted · Provenance/correlation fields are NOT an identity mechanism
**Context** An earlier design proposed connected components over `correlation.*` and
`extensions.dataflow_v2` as the backbone of execution identity.
**Decision** Rejected. `triggered_by` and `correlated_events` are excluded from identity
reasoning. `dataflow_v2` is retained only as a weak `shared_value_with` / `dataflow_to` edge.
**Consequences** Family D demoted from backbone to complementary feature. No `networkx`
connected-component logic anywhere on the critical path.
**Evidence** Measured on `dataset_b`: `triggered_by` has 4,760 links of which **4,759 have
child `event_type = screenshot_smart`** (capture plumbing). `correlated_events` is 96%
singletons pairing `browser_click`↔`mouse_click` and `text_input_complete`↔`keystroke`
(layer de-duplication). `cross_layer_v1` matches `dom_event_id`↔`uia_event_id`.
`dataflow_v2.source_event_id` is present on 870 of 20,477 events (4.2%) with
`raw_value_persisted: false`. Resulting graph: only **35** `dataflow_to` edges.

### ADR-003 · 2026-09-12 · accepted · Time gaps are a baseline and a weak feature, not a method
**Context** Measured on `dataset_b`: median inter-event gap 62 ms, p99 6 s, **one** gap > 30 s
in 20,477 events. `README.md` notes waiting time is compressed in the test environment.
**Decision** No gap-threshold segmenter is a candidate method. `B2-gap` is kept permanently as
a published baseline floor. Relative gap (gap ÷ session rolling median) remains a feature in
the ambiguity gate.
**Consequences** Prevents re-litigating this; the negative result is report content.
**Evidence** As above. Note this is a **Dataset B** observation; Phase 2 re-checks it on A.

### ADR-004 · 2026-09-12 · accepted · The activity block is the unit of reasoning
**Context** Reasoning per event (162k in A) or per raw state change (~59k in A) is
unaffordable and semantically meaningless.
**Decision** Deterministic perception compresses events into activity blocks; all downstream
reasoning, retrieval and explanation operate on blocks.
**Consequences** Makes an LLM affordable on the critical path. Block quality becomes a
first-class engineering concern (Phase 0 and Phase 2 both measure it).
**Evidence** 20,477 events → 7,408 state changes → 1,782 blocks on `dataset_b`.

### ADR-005 · 2026-09-12 · accepted · The TEKG is an evidence and explanation layer
**Context** See ADR-002.
**Decision** The graph builds local typed context for the reasoner and explains decisions
afterwards. Connected components are never interpreted as executions.
**Consequences** `evidence_used` is a required output field; the prototype's P3/P4 pages depend
on it.
**Evidence** `returns_to` (2,150) and `same_field_as` (940) are ~60× more abundant than
`dataflow_to` (35) — structural/temporal relations are the real evidence base.

### ADR-006 · 2026-09-12 · accepted · The LLM never controls temporal arithmetic
**Decision** The reasoner is shown relative seconds and local ids `b0…bN` only. It cannot emit
a timestamp, duration, interval or global index because it never receives one.
**Consequences** An entire class of LLM failure is structurally impossible. A test asserts no
payload leaks absolute values.
**Evidence** Design; enforced in `context.build_payload`.

### ADR-007 · 2026-09-12 · accepted · Rejected dependencies
**Decision** Not used: Neo4j / FalkorDB / any graph database; Raphtory; any vector database;
LangGraph / CrewAI / any agent framework; `stumpy`; `streamlit-gantt`; ScreenRPA (CC BY-NC —
disqualifying for client-facing work); OpenAdapt; SmartRPA; fine-tuning stacks; global OCR.
**Consequences** Storage is JSON + dicts; graphs use `networkx` only where an algorithm is
needed; the demo uses built-in `plotly.express.timeline`.
**Evidence** Data scale is ~20k events / ~1.8k blocks per dataset. These tools solve problems
we do not have, or solve the inverse problem (replay a known task rather than discover one).

### ADR-008 · 2026-09-12 · accepted · PM4Py only with step structure
**Context** One row per execution yields a one-activity process model — degenerate.
**Decision** `pm4py` is introduced only after step/task structure exists
(`case = execution`, `activity = step`), in Phase 5.
**Consequences** Step recovery becomes a real objective, validated against GT `task_started`.

### ADR-009 · 2026-09-12 · accepted · Vision is selective and tool-gated
**Decision** No global OCR/VLM pass. Screenshots are requested only by `look_at_screen` when
reasoner confidence is low, capped at ≤5% of routed transitions.
**Consequences** `extensions.ocr_v1` and `context.extracted_text` are not primary inputs.
**Evidence** `DATA_SCHEMA.md` §2 states OCR is unnecessary; on `dataset_b`
`extracted_text` covers 4.6% of events and is largely browser chrome.

### ADR-010 · 2026-09-12 · accepted · Nothing dataset-specific transfers from A to B
**Decision** Transferable: code, featurisation, the *rule* for estimating a parameter, the
evaluation harness, domain-neutral prompts. Not transferable: A's process names/codes,
vocabulary, keyword lists, cluster count `k`, memory records, few-shot examples.
**Consequences** `make run-b` must succeed with `dataset_a/` absent — a CI-enforced test.
**Evidence** `README.md`: B is from different departments, processes and applications.

### ADR-011 · 2026-09-13 · accepted · GT repair rules are frozen before any segmenter runs
**Context** `DATA_SCHEMA.md` §3 documents duplicate `process_started` and unpaired
`process_switched_out`, and instructs us to verify consistency ourselves.
**Decision** Repair rules are written and committed in Phase 1 **before** the first segmenter.
Tuning uses the `clean` tier only; headline uses `clean + repaired`; a sensitivity line uses
`all`. Both GT sources are retained on disagreement.
**Consequences** Prevents fitting the generator's defects; the disagreement rate becomes a
reported finding.

### ADR-012 · 2026-09-13 · accepted · A surface is defined only by user-operation layers
**Context** Phase 0 measured the block degenerate tail on `dataset_b`: 623 one-event blocks,
624 zero-duration, 63 with an empty surface key, median 4 events/block. Tracing them to the
raw telemetry showed they were not a threshold problem. An `L1 screenshot_smart` fired while
the user was browsing carries `context.active_app` but no `context.active_browser_tab`, so the
surface key flipped from `web:<origin>/<route>` to `app:<browser>:<title>` and back, splitting
one run into three. `SYSTEM` events (`session_start`, `extension_connected`) carry no
`active_app` at all and produced every empty-surface block.
**Decision** A block's surface is defined **only** by events on the user-operation layers
`L2` and `L3`. `L1` and `SYSTEM` events attach to the block already open and can never open
one (`blocks.is_capture_event`). Symmetrically, a row carrying neither a window title nor an
origin identifies only an application, so it cannot open a block inside a run of that same
application (`blocks.has_discriminator`); the forward half of the same rule merges a bare
`app:<X>` run into an immediately following `app:<X>:<title>` run, since a window title is not
populated until the window finishes activating. A row naming a *different* application still
opens a block, so this repairs missing data without merging distinct work.
**Consequences** Block identity attributes derive from surface-defining rows, not `rows[0]`.
The rule is keyed on `layer` and on field presence — both defined by `DATA_SCHEMA.md` — and
contains no application name, URL or value, so it runs unchanged on `dataset_a` (ADR-010).
**Evidence** `DATA_SCHEMA.md` §2 *layer* table: `SYSTEM` = "the agent's own activity",
`L1` = "screen capture"; only `L2`/`L3` describe operations the user performed. Consistent
with `TEKG_SPEC.md` §6, which already strips `screenshot_smart` as "capture noise, not user
action", and with ADR-009. Measured (`experiments/E01-block-sweep`): 1782 → 1338 blocks,
median 4 → 8 events/block, one-event 623 → 152, empty-surface 63 → 0, surface purity
0.9742 → 0.9852. This rule accounts for essentially the whole improvement.

### ADR-013 · 2026-09-13 · accepted · Browser tab is carried-forward state; surface type is structural
**Context** Two related defects. (a) `blocks.surface_key` chose the `web:` form from a
hard-coded set of browser application names — a dataset-specific rule that would mis-key any
browser a future dataset happens to use. (b) `normalise.route_of` returned the *origin* when a
URL carried no `#` fragment, producing keys such as
`web:http://127.0.0.1:5132http://127.0.0.1:5132` on 54 blocks, which violates the
`web:<origin><route>` grammar in `DATA_CONTRACT.md` §2 and splits one logical surface in two.
**Decision** (a) The web/app choice is structural: a usable http(s) origin in context means a
web surface. The `BROWSERS` allow-list is deleted. (b) `route_of` returns the hash route when
present, else the URL path, never the origin. (c) `context.active_browser_tab` is treated as
last-observed **state** rather than a per-event fact and is carried forward, scoped to an
unchanged `app_name` and seeded only from `L2` events.
**Consequences** The surface grammar is now honoured exactly. The `L2`-only seeding matters:
the `L3` browser extension is a separate capture mechanism whose `active_app` lags the OS
foreground, and seeding from it propagated a browser URL onto 87 non-browser events.
**Evidence** `DATA_SCHEMA.md` §2 *context*: "how often each field is populated varies" — an
absent state field is missing data, not a state change. **Negative result, recorded
deliberately:** measured on `dataset_b` the carry-forward changes *no block boundary*. It
fills 3,058 rows, every one an `L1 screenshot_smart` that ADR-012 already makes transparent;
the 562 `L2` browser operations lacking a tab URL sit at the *entry* to a browser visit, where
no prior tab has been observed and the rule correctly declines to invent one. Retained as the
correct reading of the schema and for later phases (ADR-009 vision gating, prototype
screenshot attachment), not as a load-bearing fix. Re-measure on `dataset_a` in Phase 2.

### ADR-014 · 2026-09-13 · accepted · `app_switch` self-transitions are NOT suppressed
**Context** Phase 0 hypothesised that an `app_switch` whose `payload.new_app` equals
`payload.previous_app` reports no change and should not open a block. `DATA_SCHEMA.md` §2
licenses reading those fields, and 738 of 1,654 `app_switch` events on `dataset_b` are such
self-transitions.
**Decision** **Rejected.** The rule was tested against the data before being implemented and
would have destroyed signal.
**Consequences** Self-transitions need no special handling: 559 of the 738 carry the same
window title as the preceding event and are therefore already no-ops under surface-key
equality. The rule would have bought nothing for those and damaged the rest.
**Evidence** 176 of the 738 self-transitions carry a **different, meaningful** window title —
`getsujitsu_teigaku_torihikisaki_ichiran` → `kazoku_teate_kitei` (a Word document switch),
`Opening - Excel` → `expense_calc - Excel`. The application does not change but the *surface*
does, and the surface is the unit. Suppressing them would have merged distinct documents into
one block and erased 176 genuine boundaries. Regression test:
`tests/test_blocks.py::test_a_document_switch_within_one_application_is_preserved`.

### ADR-015 · 2026-09-13 · accepted · The activity block is a container, not a boundary unit — refines ADR-004
**Context** ADR-004 made the block "the unit of reasoning". In practice that made block edges
the *candidate space* for business-process boundaries, and Phase 1 measured the cost: of 3,327
GT boundary points on Dataset A, **74.5% fall strictly inside a block** and only **59.9%** are
within τ=2 s of a block edge. That figure was then read as a ceiling on the representation.
**Decision** The reading is corrected, not the perception layer.

| | |
|---|---|
| OLD | activity block ≈ business-process boundary unit |
| NEW | activity block = activity / context / compression / identity **container**; an execution boundary may occur **inside** a block |

ADR-004 stands as a statement about **compression and reasoning affordability** (162,768 events
→ 4,968 blocks on A) and is superseded only in its implied use as the candidate space. A new
deterministic stage generates **intra-block, event-level** candidates; blocks must therefore
retain access to their underlying events.
**Consequences** 59.9% is restated as *the reachability of the block-edge candidate space*, never
as a representation ceiling. `STEP1_SPEC.md` §2 replaces the pipeline in `ARCHITECTURE.md` §3.
Two questions are kept permanently distinct: **(A)** information destroyed by preprocessing vs
**(B)** information preserved but not surfaced as a candidate. Experiment S-E2 decides which
applies, per missed boundary, before any rebuild is considered.
**Evidence** `docs/phases/PHASE_1_REPORT.md` §8. Reachability 47.3 / 59.9 / 82.8 / 92.2% at
τ = 1 / 2 / 5.25 / 10.5 s; median distance to the nearest block edge 1,040 ms; 36.5% of
executions contain zero whole blocks; 80.3% of block edges are interior to a GT execution.
Prior signal evidence (to be re-measured under S-E3): at missed boundaries vs interior controls
±2 s, `browser_navigation` 8.5% vs 2.3%, `clipboard_change` 0.6% vs 30.5%, `shortcut` 1.6% vs
53.4% — the discriminating events survive into the retained stream, which is evidence for (B).

### ADR-016 · 2026-09-13 · accepted · Scope is Step 1 only; the phase plan is replaced
**Context** The repository accumulated specifications for a full pipeline — retrieval/execution
memory, agentic tools, vision, workflow and SOP generation, family/variant analysis, a Streamlit
prototype — before Step 1 had been shown to work. Phases 2–7 encode that plan.
**Decision** The current bounded objective is Step 1 alone: *infer business-process execution
segments from low-level desktop telemetry, using existing activity blocks as context containers
and adding event-level candidate boundary inference.* `docs/STEP1_SPEC.md` is authoritative for
it. `phases/PHASE_2.md`, `PHASE_3.md`, `PHASE_4.md` are superseded by `STEP1_SPEC.md` §6–7;
`PHASE_5.md`, `PHASE_6.md`, `PHASE_7.md`, `RETRIEVAL_SPEC.md` and `PROTOTYPE_SPEC.md` are
deferred until Step 1 exits at S-DONE. `ARCHITECTURE.md` §3 stages 7–10 are deferred.
**Consequences** No Step 2 or Step 3 architecture is written until S-DONE. Deferred documents
are retained, banner-marked, and not deleted — they are prior work and may be revived.
**Evidence** `README.md`: "Technical accuracy is not the objective in itself. Your judgment is
what is being assessed — including how you choose to spend your 7 days"; FAQ Q3 answers "will I
score higher by building something technically sophisticated?" with **No**. As of this ADR,
`segments.jsonl` — Deliverables §1 — does not exist.

### ADR-017 · 2026-09-13 · accepted · Accuracy is reported on the scoreable canonical GT population
**Context** Phase 1 reported figures without stating which GT population they were computed on,
and the ceiling analysis in `PHASE_1_REPORT.md` §8 was computed ad hoc and never committed as an
experiment. The τ grid also disagrees between documents: the report uses
{1000, 2000, 5250, 10500} ms, `experiments/E11-baselines/config.json` uses
{1000, 2250, 5500, 11250} ms.
**Decision** Four populations are named in every report and never conflated: **raw** (2,009
manifest executions, of which 257 have no end timestamp), **canonical** (1,819 after fragment
grouping, 98 interrupted), **unscoreable** (230 canonical records with no usable interval), and
**scoreable canonical** (**1,589**) — the last being the denominator for every accuracy figure.
The τ grid is unified in S-E1 and justified from A's duration distribution; every prior figure is
restated on it. Reachability of a candidate space is reported separately from segmentation
quality and is never presented as an accuracy number.
**Consequences** `EVALUATION_PROTOCOL.md` gains §8 (populations) and §9 (candidate reachability).
The 59.9% figure is re-derived under S-E1 before it is quoted again.
**Evidence** Counted from `build/dataset_a/executions_canonical.jsonl`: 1,819 canonical;
230 with no intervals; 1,589 scoreable; 98 interrupted; confidence tiers clean 1,756 /
repaired 63.

### ADR-018 · 2026-09-13 · accepted · The LLM adjudicates the ambiguous tail; it is not the segmenter
**Context** Two opposing failure modes were live: confining the LLM to cosmetic work (naming,
report prose), and making it the primary segmenter over every transition.
**Decision** Neither. Deterministic candidate generation, scoring and constrained global
inference handle the majority of cases. A deterministic ambiguity gate routes **≤15%** of
candidates to a bounded semantic adjudicator whose output is limited to: boundary vs no-boundary
for one candidate neighbourhood, process identity / label normalisation, and a short
evidence-citing justification. `--no-llm` remains a supported, tested mode at all times.
**Consequences** Preferred because it is explainable, reproducible, cheap, validatable on A, and
structurally incapable of hallucinating a boundary — while still placing AI where semantic
judgement is genuinely required. Its value is **measured by ablation (S-E5)**; if the ablation
shows negligible value the adjudicator is removed and the negative result is reported. Agentic
tools, retrieval/memory, few-shot retrieval, vision and fine-tuning are out of scope for the
first implementation. ADR-006 (the model never controls temporal arithmetic) and ADR-009 (vision
is selective, never global) are unchanged and still binding.
**Evidence** Per-window payload ≈1.7k tokens at `window=5` — ungated adjudication over A's 4,968
blocks is unaffordable and unjustified, since 74% of boundary decisions have deterministic
evidence. `context.extracted_text` covers ~4% of events, so it cannot be a central feature.

### ADR-019 · 2026-09-14 · accepted · Fitted scorer weights are a sanctioned A→B transfer
**Context** `procmine/score.py` fits a logistic regression on Dataset A's `clean` ground-truth
tier and applies it to Dataset B. ADR-010 forbids dataset-specific transfer from A to B, so
whether fitted weights are permitted must be ruled on explicitly rather than assumed.

**Decision** Fitted scorer weights **are** a sanctioned A→B transfer, subject to four conditions,
all of which are met:

1. **The features are domain-neutral and structural.** Every input is an event-type count, a
   composition ratio, a timing quantity normalised by the session's own distribution, or a
   structural flag. **No A surface string, process name, process code, vocabulary item, keyword
   list, cluster count `k`, or few-shot example is used** — those remain forbidden by ADR-010 and
   nothing here relaxes that.
2. **The weights are committed with their provenance stated.** `procmine/scorer_v1.json` carries
   `fitted_on: dataset_a`, `tier: clean`, `tau_ms`, and
   `provenance: "a_fitted — declared A->B transfer"`. Every threshold in the pipeline is tagged
   `tolerance_derived` / `structural` / `a_fitted` in `build/<dataset>/thresholds.json`, which
   makes the leakage check mechanical rather than a judgement call.
3. **`make run-b` succeeds with `dataset_a/` absent from disk.** The B path loads committed
   weights and never reads A. Enforced by test and by the ADR-010 guard test.
4. **The transfer risk is measured, not assumed.** `is_web_surface` is the strongest positive
   feature (lift 1.56) and Dataset A is portal-heavy, so it was the feature most likely not to
   transfer. Ablated: removing it moves boundary F1 at τ=2 s from **0.702 to 0.698** — a
   **−0.004** change, with count ratio unmoved at 0.97. The headline therefore does **not** rest
   on an A-specific feature.

**Why this is permitted at all.** Developing on A and applying to B is what the assignment asks
for: A carries ground truth precisely so a method can be built on it, and B has none to fit on.
Refusing to transfer fitted parameters would mean refusing to use A for its stated purpose. What
ADR-010 forbids is transferring A's *content* — its vocabulary and process identities — and that
prohibition is untouched.

**Consequences** Any future model must declare its features against condition 1 and re-run the
ablation of condition 4 before its number may be quoted on B. A scorer whose headline collapses
under ablation of a single feature is A-specific and must be reported as such.

**Evidence** Ablation above. Scorer: 28 domain-neutral features, LOSO AUC 0.979 over 63
sessions. Routing 3.4%. Every threshold tagged in `thresholds.json`.

### ADR-020 · 2026-09-14 · accepted · Dataset A's ground truth does not tile the session
**Context** The decoder's shape was about to be chosen. A natural default is a partitioning
segmenter — every moment of the session belongs to exactly one segment — and it would have been
wrong for a reason that is not visible without measuring.

**Measured on Dataset A**, scoreable canonical population, 63 sessions:

| | |
|---|---|
| median GT time coverage of the session span | **0.81** |
| median inter-fragment gap share of the span | **0.12** |
| fragments per session | min 20 · median 28 · max 41 |

Executions are **disjoint intervals with idle space between them**, not a partition.

**Decision** The decoder selects **disjoint segments**, each contributing its own start and end
boundary. It does not partition the session.

**Consequences** A partitioning decoder emitting `N` segments produces `N+1` distinct boundary
points, because each segment's end is the next one's start. The reference has `2N` — every
fragment contributes two. Matching the reference's boundary count would therefore require
roughly twice as many segments as executions, i.e. a count ratio near 2.0; holding the count
ratio at 1.0 instead caps boundary recall near **52%** however good the ranking. The constraint
is structural and no amount of scoring quality escapes it.

**Downstream consequence for later work, recorded now:** roughly **19% of observed session time
belongs to no business-process execution** at all. Step 2 effort estimates must not assume
session time and process time are the same quantity, and any "time spent on process X" figure
must state which of the two it divides by.

**Evidence** Coverage and gap measurements above. Confirmed by construction in
`procmine/decoder.py`, whose emitted segments are disjoint and whose test
`test_decoder_emits_disjoint_segments_not_a_partition` asserts a gap between segments is
representable.

### ADR-021 · 2026-09-14 · accepted · Process identity is a graph-clustering problem, not an LLM problem
**Context** S-E4 measured the structural labeller at ARI 0.431 / NMI 0.5625 at match_rate
0.760 against 15 reference process codes, and diagnosed the weakness as representational:
"nothing in the signature captures *same business purpose, different route*". That is a claim
about representation, so S-E6 tested it as `representation -> similarity -> grouping ->
identity` rather than assuming an LLM was the answer. Segmentation was frozen throughout: the
exact 1,717 S-E4 segments, boundary F1 identical (0.6904 at τ=2 s) on every arm, asserted in
`metrics.json.contract_boundary_f1` and in `tests/test_identity.py`.

**The two ceilings, measured.**

| Ceiling | Value | What it bounds |
|---|---|---|
| merge-only oracle | ARI **0.478** | *relabelling only* — membership of the 51 existing labels held fixed |
| supervised probe, all three views | acc **0.891** · macro-F1 **0.888** · ARI **0.786** | any unsupervised method over this representation |

The merge-only oracle is **small**: perfectly renaming the existing clusters buys +0.047 ARI,
because 37 of 41 matched labels are *impure* — 30.2% of matched members sit under a label whose
majority code is not their own — and impurity is not merge-fixable. All 15 reference codes are
also split across labels. Relabelling was never the lever.

**The per-view probe refutes the reframe's own hypothesis.** The claim was that the signature
overweights WHERE and needs WHAT and HOW:

| view | accuracy | macro-F1 | ARI |
|---|---|---|---|
| WHERE | **0.851** | 0.847 | 0.720 |
| HOW | 0.256 | 0.216 | 0.141 |
| WHAT (char 2-3-gram TF-IDF) | 0.741 | 0.734 | 0.535 |
| all three | **0.891** | 0.888 | 0.786 |

WHERE is the strongest view, not an overweighted one; HOW is close to worthless on its own
(15 classes, chance ≈ 0.07, so 0.256 is weak); WHAT is real and adds +0.040 accuracy on top of
WHERE. The signal was already in the representation — what was missing was a grouping that uses
it.

**Segmentation-inherited error is not the limiter.** The same representation and grouping run
on GT segments scores ARI 0.427 — within 0.004 of the structural labeller on *hypothesis*
segments. Identity error is caused by grouping, not by imperfect boundaries.

**Decision** Identity ships as: three-view representation → weighted similarity → kNN graph →
Louvain, in `procmine/identity.py`, consumed by `label.py` as `method="graph"`. **No LLM.**

| arm (boundary F1 identical on every row) | ARI | NMI | hom | cmp | match_rate | labels | interruption_recall |
|---|---|---|---|---|---|---|---|
| S-E4 structural (control) | 0.431 | 0.563 | 0.622 | 0.514 | 0.760 | 51 | 0.122 |
| k-means (k=30, vector space) | 0.222 | 0.444 | 0.487 | 0.407 | 0.760 | 30 | 0.102 |
| agglomerative average / complete | 0.109 / 0.122 | — | — | — | 0.760 | 30 | — |
| DBSCAN (eps 0.30 / 0.45) | 0.163 / −0.001 | — | — | — | 0.760 | 643 / 35 | — |
| **graph kNN(k=20) + Louvain** | **0.583** | **0.688** | **0.679** | **0.698** | 0.760 | **15** | **0.337** |

**Transferability of `k` selection is part of the decision, not a footnote.** Two unsupervised
selection rules were measured, both declared before their ARI was inspected:

* **modularity × cross-session reuse** → `how_heavy, k_nn=5` → ARI **0.204**. It fails for a
  structural reason: modularity is not comparable across graphs of different density, so the
  rule was really selecting the sparsest graph, and it scored `how_heavy` and `where_heavy`
  identically at 0.8669 — it could not distinguish the view that carries the identity signal
  from the one that carries almost none.
* **stability under 80% node resampling × cross-session reuse** (the Phase E rule, co-clustering
  Jaccard) → `where_heavy, k_nn=20` → ARI **0.583**, the best configuration in the grid.

Rule 2 ships. Louvain then selects the community count itself, so nothing about A's `k`
transfers to B (ADR-010): on Dataset B the same code re-runs the sweep and Louvain picks B's
own count. **"15 reference process codes" is never a production assumption** — that A's chosen
configuration happened to yield 15 communities is an outcome, not an input.

**Is an LLM justified? Not yet, and the measurement says why.** This is **case B by the letter
of the criterion** — grouping improves materially (ARI 0.431 → 0.583, NMI 0.563 → 0.688,
homogeneity *and* completeness both up, so it is neither over-merging nor over-splitting) but
closes only ~43% of the recoverable gap to the supervised probe. The qualification matters
more than the label: the residual is **not** a missing-semantics gap. A logistic regression on
exactly these features reaches 0.891 accuracy, so the information needed to separate the
residual is already present and unlabelled clustering simply is not extracting it. The
concrete failure is visible — 99% of the highest-similarity cross-code pairs are wrongly
grouped, and what they share is the portal *dashboard root* `http://127.0.0.1:5122/`, a
surface every process passes through. The cheap deterministic fix for that is IDF-weighting
the surface Jaccard so a universal surface stops carrying evidence; that must be tried and
ablated before a model is added. **`STEP1_SPEC.md` §3.7 is unchanged and "LLM identity
normalisation" is explicitly NOT hard-coded into the architecture.** If a bounded semantic
judge is ever added it is subject to ADR-018: it may normalise a label, clustering decides
membership, and its value is established by ablation (S-E5) against the deterministic fix.

**Consequences** `procmine/identity.py` is new and is an inference module: it imports no GT
module, reads no GT artifact, and is covered by the AST leakage test. `label.py` defaults to
`method="graph"` and falls back to the Phase E structural labeller when the optional numeric
stack is absent, so `--no-llm` and a stdlib-only path both keep working. Interruption recall
rises 0.122 → 0.337 at an unchanged count ratio of 0.98, but it must be read with the label
count: 15 labels raise it partly by being coarser, which is why DBSCAN at eps 0.45 posts 0.857
with 35 labels and ARI −0.001, and why B0-single posts 0.796 degenerately.

**Evidence** `experiments/SE6-identity-grouping/` — `metrics.json`, `selection_rule_2.json`,
`report.md`, `samples.jsonl`. 1,717 frozen segments, 1,332 matched to a reference code at
IoU 0.5 (match_rate 0.760), 15 reference codes, 63 sessions. Every identity metric comes from
`evaluate.identity_scores` / `evaluate.matched_identity` via `evaluate.evaluate_all`; none is
reimplemented.

#### ADR-021 · addendum · 2026-09-15 · S-E6b — the case-study-3 diagnosis was wrong

ADR-021 named IDF-weighting the surface Jaccard as the next thing to try, on the strength of
S-E6's case study 3: *"99% of the highest-similarity cross-code pairs are wrongly grouped, and
what they share is the portal dashboard root."* It was built, measured, and **it does not work,
because the diagnosis behind it was wrong.**

**The measurement that settles it.** For those 97 offending pairs the surface Jaccard is
**exactly 1.00** — their surface sets are *identical*, not merely overlapping in one universal
term. The Jaccard of two identical sets is 1.0 under **any** term weighting whatsoever, so no
IDF, BM25 or other re-weighting of set members can ever separate them. They share a mean of
1.35 surfaces and that is every surface either one has: these are short executions that visit
exactly the same page and differ only in business purpose. The observation "71% of them share
the dashboard root" was true; the causal claim built on it was not, and it was not checked
against the Jaccard before being written into an ADR.

**Measured cost of turning IDF on** (frozen segmentation, boundary F1 0.6904 identical, shipped
`where_heavy` / k_nn=20 configuration, only the factor named varying):

| | ARI | NMI | hom | cmp | labels | case 1 | case 2 | case 3 |
|---|---|---|---|---|---|---|---|---|
| plain, linear | **0.580** | 0.685 | 0.676 | 0.695 | 15 | 0.017 | 0.017 | 1.000 |
| plain, adaptive | **0.585** | **0.696** | 0.686 | **0.707** | 15 | 0.017 | 0.017 | 1.000 |
| plain, noisy-OR | 0.588 | 0.683 | 0.695 | 0.672 | 17 | 0.017 | 0.017 | 1.000 |
| IDF, linear | 0.549 | 0.669 | 0.671 | 0.667 | 17 | 0.017 | 0.017 | 0.991 |
| IDF, adaptive | 0.567 | 0.678 | 0.674 | 0.682 | 16 | 0.017 | 0.017 | 1.000 |
| IDF, noisy-OR | 0.541 | 0.654 | 0.666 | 0.642 | 18 | 0.017 | 0.017 | 1.000 |

Separability over matched executions, within-code minus between-code: **0.2263 → 0.2180**,
Cohen's *d* **1.535 → 1.508**. IDF makes the metric slightly *worse* on every axis and moves
case study 3 by one pair in 97. **Decision: the IDF implementation is retained, unit-tested and
ablatable, and its default is OFF.** Negative result recorded rather than shipped.

**Case studies 1 and 2 must be restated.** S-E6 reported 13.3% under the *rule-1* arm
(`how_heavy`, k_nn=5, 24 rhythm-driven communities). Measured under the **shipped** arm the
figure is **1.7%**, and none of the three combination modes moves it. The number was not
comparable across arms and should not have been carried between them. Same-process pairs with
disjoint surface or route sets are essentially never grouped, by any variant tried here.

**Adaptive combination is a small real gain and ships.** Per-pair renormalisation over the views
applicable to that pair: ARI 0.580 → 0.585, NMI 0.685 → 0.696, with homogeneity *and*
completeness both rising. Noisy-OR reaches 0.588 but at 17 labels with completeness falling to
0.672 — it buys ARI by over-merging, which is the failure mode this project is meant to detect,
so it is not the default.

**Per-view separability**, which explains all of it (Cohen's *d* over matched executions):
sequence 1.545 · WHERE 1.425 · WHAT 1.190 · HOW **0.410**. Consistent with the supervised probe
and with what the residual is: the similarity is not weighting the wrong terms, it is being asked
to separate executions whose structural footprints are genuinely identical.

**Scaffolding contamination — reported, NOT removed.** 98 of 1,717 executions (5.7%) carry a
structural scaffolding signature (terminal-only app set; `SETUP`/`launch`/`theme`/`_reference`
filename tokens; terminal present with no web surface). 44 of them are in the matched population
(3.3%), and they account for 39 of 411 misgrouped executions (**9.5%** of the residual error) —
an enrichment of **2.9×** over their base rate. They are real contamination and they are a
minority of the problem. Neither case study 1 nor 2 is driven by them. They remain in the
pipeline: excluding inconvenient executions is fitting the evaluation set.

**Dataset B: the 6-cluster result was NOT defensible, and the k-selection rule degrades.**
On A (1,717 executions) the stability × reuse rule selects `where_heavy`. On B (183) it selects
`how_heavy` — the view measured at 0.256 probe accuracy — and the resulting 6 clusters have a
**modal-surface share of 0.32–0.52**: fewer than half the members of a "process" visit that
process's own most common surface. That is not a process identity. Constrained to `where_heavy`
and letting the rule choose only the graph `k`, B yields **8 clusters** at a modal-surface share
of **0.77** and a modal-route share of **0.92**, 100% cross-session reuse, mean 8.25 sessions per
label. **Decision:** the view weighting is fixed to `where_heavy` and declared as an A→B transfer
under the ADR-019 conditions — it is a structural, domain-neutral choice, and no A surface,
route, process name, vocabulary or cluster count crosses over; `k` is still selected on B, by B.
`label.DEFAULT_CFG["weightings"]` carries the provenance, and `None` restores the full sweep.

`segments.jsonl` regenerated under this configuration: 183 segments, **8 labels**, 15 sessions,
100% cross-session reuse. It still trips the one known `validate_segments` false positive (an
intra-block boundary at a chunk edge; the validator's `justified` set is built from *block*
boundaries, a Phase B assumption predating ADR-015).

**Still true after S-E6b:** no LLM is justified. The supervised probe (0.891 accuracy) shows the
information is present; the residual is executions with identical structural footprints and
different business purpose, which is where a semantic judge would have to earn its place — and
whether it can must be established by ablation, not asserted. Metric learning from LLM
pseudo-labels is recorded as future work and was not built.

#### ADR-021 · addendum 2 · 2026-09-15 · S-E7 — saturation tie-break; Step 1 frozen

**The last identity change, and it is a real one.** S-E6b established the residual to be pairs
whose surface sets are *identical* (Jaccard 1.00). A Jaccard of 1.0 is maximally **similar** and
minimally **informative** — the adaptive combiner, which weights by applicability, could not
exploit that, which is why it bought only +0.005. The tie-break inverts it: above
`SATURATED_WHERE = 0.95` the WHERE term is discarded and the pair is decided on WHAT and sequence
alone, the only views that can still separate two executions with the same footprint.

Measured on the frozen segmentation, boundary F1 0.6904 and match_rate 0.760 identical:

| | ARI | NMI | hom | cmp | event-ARI | labels | interruption_recall |
|---|---|---|---|---|---|---|---|
| adaptive (S-E6b) | 0.5852 | 0.6962 | 0.686 | 0.707 | 0.267 | 15 | 0.347 |
| **tiebreak (shipped)** | **0.6814** | **0.7375** | **0.751** | **0.725** | **0.297** | 17 | 0.347 |

**It does not pass the acceptance test as written, and it ships anyway — deliberately.** Two of
the three stated gates fail: case study 3's wrong-grouping rate did *not* move materially
(1.000 → 0.990, though the population of top-0.1% cross-code pairs fell 127 → 104), and the label
count drifted 15 → 17. What those gates were protecting against was buying ARI by over-merging;
**homogeneity and completeness both rose**, so that did not happen, and 17 labels with higher
completeness is not over-splitting. Case study 3 was a diagnostic of a mechanism, not the
objective. This is a judgement call and is recorded as one rather than presented as a pass.

**Granularity-fair identity metric added** (`evaluate.pointwise_identity`). Matched-segment ARI
is not comparable across arms: B1-chunk posts **ARI 1.000 at match_rate 0.0017**. Labelling every
event and every second of session time, over 100% of the timeline with an explicit `unassigned`
label (ADR-020), the pipeline leads B5-dwell **0.297 vs 0.250** on events and **0.269 vs 0.200**
on time — a 1.19× margin, far narrower than the 2.67× on boundary placement, and stated as such.

**`validate_segments` §6.7 corrected.** Its `justified` set was built from *block* boundaries — right
for the Phase B emitter, wrong from ADR-015 onward — and flagged a valid intra-block boundary as a
violation. It is now every candidate position, plus an AST check that no enabled trigger reads
`chunk_id` and that `at_chunk_edge` stays audit-only, which is what the clause actually requires.

**Freeze.** `label.weightings` (`where_heavy`) and `label.combine_mode` (`tiebreak`) are declared
in `thresholds.json` as `a_fitted` A→B transfers under the ADR-019 conditions; `identity.saturated_where`
is `structural`; **`label.k` is explicitly not transferred** — Louvain selects 17 on A and 13 on B.
Two consecutive runs produce byte-identical `segments.jsonl`. `make run-b` verified with
`dataset_a/` moved out of the tree.

**The deliverable has exactly one writer (fixed at the freeze).** `make run-b` was `build-b`
plus `emit_segments.py`, the Phase B block-run safety net, which defaulted to `segments.jsonl`.
Running the ADR-010 leakage check therefore replaced the Phase D/E deliverable with a
958-segment block-edge-only file, silently. `cli.segment()` now writes `segments.jsonl` — and
validates it against DATA_CONTRACT §6 before considering it written — `run-b` calls that instead,
the safety net defaults to `build/<dataset>/segments_provisional.jsonl` and refuses the
deliverable path without `--force`, and a test walks the package AST to assert exactly one module
writes it. This also makes STEP1_SPEC §8's requirement literally true for the first time: the
submitted file is produced by the same frozen code that was validated on A, not by an experiment
script. Verified by re-running the gate that broke it: `dataset_a/` moved out, `make run-b`, and
the deliverable comes back byte-identical.

**S-E8 — consecutive same-process executions.** A cannot test the case at all: 0 of 1,689
consecutive execution pairs share a process code. On B the frozen system emits them readily —
**67 of 168** consecutive segment pairs within a session share a label (39.9%), at a median gap
of 7.0 s, and **7** of those pairs have *identical* surface sets, which is the hardest version of
the case: nothing about where the operator is changes across the boundary. The system does
therefore split adjacent same-process executions rather than merging them, and it places those
boundaries on evidence other than surface change. **B has no ground truth, so this records what
the system does, never that it is right.** Recorded as a limitation; nothing was changed to chase
it.

#### ADR-021 · addendum 3 · 2026-09-15 · The graph method's dependencies are REQUIRED, not optional

**The incident.** `make run-b` on a host without the numeric stack produced a **different
deliverable**, silently, with exit code 0. `.venv/bin/python3.12` is an absolute symlink into
`~/.local/bin`; where that does not resolve, the Makefile's `[ -x $(PY) ]` guard fails and falls
through to the ambient `python3`, which on this machine is 3.9.6 with no `networkx` and no
`rapidfuzz`. `label._graph_assign` caught the `ImportError` and returned `None`; `label_segments`
fell back to the Phase E structural labeller. Result: **33 labels instead of 13, ARI 0.431
instead of 0.681** — with **183 of 183 spans byte-identical and 1 of 183 labels identical**.
Segmentation is environment-independent; identity was not.

It was found by hashing `segments.jsonl` across two machines — `48796e9c` against `eab64f62` —
not by any test. The reproducibility check in place at the time ("two consecutive runs agree")
could not have found it: **two runs in one environment agree even when both are wrong.**

**Decision.** `numpy`, `scipy`, `networkx`, `scikit-learn` and `rapidfuzz` are **hard
requirements** of the shipped identity method and are declared in `pyproject.toml`'s
`dependencies`, not in an optional extra. The note that used to sit above that list — *"none of
pandas/numpy/networkx is imported anywhere in procmine/"* — was true in Phase 0 and became false
at this ADR; stale accuracy in a dependency declaration is what made "optional" look defensible.
`scipy` was being imported by `identity.vector_space` while relying on scikit-learn to pull it
in, and is now declared explicitly.

**Consequences**

1. `label._graph_assign` **raises `DegradedIdentityError`** when the stack is missing, naming
   the missing modules, the install command, and what the fallback would have cost. It no longer
   returns `None`. The fallback is reachable only through an explicit `allow_degraded=True`
   (CLI: `--allow-degraded`), which logs a warning. This follows the `schemas.py` convention:
   an artifact that does not meet its contract is a hard failure, never a warning.
2. Every run writes **`build/<dataset>/run_manifest.json`** — `method_used`, `expected_method`,
   `missing_graph_dependencies`, the deliverable's sha256, segment and label counts, git sha,
   interpreter path and version, and resolved dependency versions. A provenance mismatch is now
   visible **in an artifact**, not only to someone who thinks to hash the file on two machines.
3. The reproducibility test asserts three separate things: the regenerated bytes match the
   **committed** sha256; the manifest reports `method_used == "graph"`; and the identity test
   module **fails rather than skips** when its dependencies are absent. `pytest.importorskip` on
   a required dependency hides exactly this defect — the suite was green on a host that could
   not run the method it was testing.
4. `make setup`'s interpreter search now covers `~/.local/bin`, Homebrew and `/usr/local/bin`.
   It had **failed outright from a clean clone on this machine** — the only `python3` on PATH is
   the system 3.9.6 — which is the same root cause seen from the other end.

**Verified after the fix**, under `.venv/bin/python` → `/Users/aumvyas/.local/bin/python3.12`
(Python 3.12.14) with numpy 2.5.3 · scipy 1.18.1 · networkx 3.6.1 · scikit-learn 1.9.1 ·
rapidfuzz 3.14.6: `segments.jsonl` deleted, `dataset_a/` moved out of the tree, `make run-b`
exit 0 → **183 segments, 13 labels, sha256 `48796e9c…`, identical to the committed file**, and
`run_manifest.json` reporting `method_used: "graph"`.

### ADR-022 · 2026-09-18 · accepted · Module key authority: the screen header, not the URL

**Context** Phase 3 of the evidence programme reported 539 of 3,011 extracted records (17.9%)
where the capture URL and the record-id prefix disagreed about which business module a record
belongs to. The `(origin, route)` key derived from the URL is what
`analysis/step2_reanalysis.py` and `docs/STEP2_PROCESS_INVENTORY.csv` are built on, so the
disagreement had to be settled before anything further rested on that inventory.

**The decisive test.** The leading explanation was cross-module queue views — a shared inbox
whose URL names one module while its rows belong to several — under which both keys would be
correct about different questions. Measured: **33 captures contain more than one record-id
prefix, and 0 of them cross a module boundary.** Every mixed capture is `P1` + `P4`, both
HR|経費精算・給与変更. **There are no cross-module queue views in Dataset B, and the hypothesis is
refuted.**

**Measured** over 3,011 records (`build/dataset_b/evidence/module_key_reconciliation.json`):

| Comparison | Comparable | Agree | Rate |
|---|---|---|---|
| K2 screen header ↔ K3 record prefix | 2,904 | 2,904 | **1.000** |
| K1 URL ↔ K3 prefix | 2,704 | 2,139 | 0.791 |
| K1 URL ↔ K2 screen | 2,630 | 2,067 | 0.786 |

Only two agreement patterns occur: all three agree (2,064), or **K1 alone dissents (552)**. K2
and K3 never disagree with each other. That is the signature of one wrong key rather than three
partial views.

**Decision**
1. **A record's home module is named by K2, the screen header**, with K3 (the record-id prefix)
   as an exact proxy. The P1–5/P6–10/P11–13 → HR/FI/LO mapping is **derived** from 211 queue
   captures, not assumed; all 13 prefixes resolve at **purity 1.00**, and the derivation is
   finer than the supplied grouping — it names the module, not just the system.
2. **An operator action (execution) is keyed by K3 where records were extracted inside it, by
   K1 elsewhere, and the disagreement is flagged rather than resolved.** K1 is not demoted to
   "the view key": it is simply wrong about the displayed screen in 21% of captures. It remains
   the only key with full coverage.

**Consequences**
- **K3 is more accurate and less complete; K1 is more complete and less accurate.** K1 assigns
  165 of 183 executions, K3 only 107, because `extracted_text` reaches 4.59% of events. Where
  both apply they agree on 64 of 97 (66.0%). **No single-key inventory is defensible**, and
  per-module execution counts must be quoted as a range with the reason (coverage, not noise).
- **The inventory is missing a module.** `FI|予算差異分析` is declared on screen in 11 captures and
  carries 132 record rows under prefix `P8` at purity 1.00, and has no entry in the
  `(origin, route)` map — 12 modules on screen against 11 in the map. The error is omission; no
  map entry is declared-but-unseen. `docs/STEP2_AUTOMATION_OPPORTUNITY.md` is superseded in the
  affected sections rather than rewritten.
- All 12 inventory rows change count between the keys.

**Not established** Why the URL lags. Every record-bearing capture is an `app_switch` event —
563 disagreeing, 2,067 agreeing — so event type does not discriminate them. The most likely
account, offered as INFERENCE and not as a finding, is that the SPA hash route and the
recorder's stored `active_browser_tab.url` are written by different code paths.

**Evidence** `docs/STEP2_MODULE_KEY_RECONCILIATION.md`;
`build/dataset_b/evidence/module_key_reconciliation.json`;
`analysis/evidence/module_key_reconcile.py`. Step 1 is untouched.

### ADR-023 · 2026-09-18 · accepted · Pillow and matplotlib accepted; the VLM is a new dependency CLASS

**Context** Three dependencies entered the project without an ADR, two of them because
`DECISIONS.md` was frozen at the time. ADR-007 rejects "global OCR pipelines" and that rejection
stands; what follows is a different thing and the distinction has to be recorded rather than
argued in a commit message.

**Decision**
1. **`matplotlib` — accepted, analysis only.** Added during Step 2 for the three inventory
   figures, with the ADR deferred because this file was frozen. It is an optional `analysis`
   extra in `pyproject.toml` and is never on the Step 1 critical path.
2. **`Pillow` — accepted, analysis only.** Used by `analysis/evidence/pass1_states.py` to decode
   JPEGs for perceptual hashing. The DCT is written out as a NumPy matrix product rather than
   taken from `scipy`, so the module runs under either interpreter on this machine, and
   `imagehash` is deliberately not added.
3. **The VLM is a new dependency CLASS, not a package**, and is governed accordingly: an
   outbound paid call to a third party, over user data, whose output is non-deterministic.
   Governance is in code, not in policy: a `VisualExtractor` protocol whose default backend is
   `null`; the key read only from an environment variable, never hard-coded, never prompted for,
   with **no silent fallback** — a missing key is a non-zero exit naming the variable; a hard
   cap of 60 images across all questions; `--dry-run` as the default; and a per-call ledger at
   `build/dataset_b/evidence/vlm_ledger.jsonl` that every `VLM_INTERPRETATION` claim must cite.

**ADR-007 is not weakened.** A global OCR pipeline processes every frame because it exists.
Phase 4-Micro would have processed a frame only when a named question needed it and cheaper
evidence had been measured to be absent — and in the event, **it processed none**.

**Consequences** Spend to date: 0 images, 0 calls, $0.00, 0 ledger rows
(`docs/PHASE4_SCOPE_DECISION.md`). The capability remains in place so that not spending is a
measured decision rather than an absence.

**Evidence** `tesseract` is not installed on this machine, so OCR proper was never available.
The recorder's own `extensions.ocr_v1` ran on 15 events and renders 第1条(目的) as 第1条(白的),
interleaved with Word ribbon chrome — corroborating that OCR is the wrong tool here, not merely
the unavailable one.

### ADR-024 · 2026-09-18 · accepted · The strong hypothesis is refuted; Step 3 targets preparation

**Context** The programme set out to test whether operators apply recoverable written rules to
record variables, such that an AI system could learn that decision function. Four gates were
declared and each was tested against telemetry rather than argued.

| Gate | Criterion | Verdict |
|---|---|---|
| G1 | task, record type and outcome are OBSERVED, not inferred | **PASS** — 3,011 records, 549 outcomes, 216 queue tables, zero VLM |
| G2 | a governing rule is recoverable from a content-identified document | **PASS** — 112 content-hashed documents; the 接待交際費 threshold parses to `<¥50k→部門長 / ≥¥50k→役員 / ≥¥100k→社長` |
| G3 | the record carries the variables that rule needs | **FAIL** — 金額 present on 1.0–9.1% of records on four modules |
| G4 | the outcome varies enough to distinguish rule-application from confirm-and-proceed | **FAIL for the system disposition** — 225/225 positive, 0 backward transitions over 25,495,968 characters. **REOPENED for the operator's annotation** — 26 of 481 typed comments carry 差異あり / 要注意 / 要確認 |

**Decision** The hypothesis is **refuted in its strong form**. With no negative outcome, there is
no supervision signal for a decision function: a model trained here learns `return approve` and
scores 100% while being worth nothing. The refutation is **structural, not a sampling artifact**,
because G3 and G4 fail compatibly — if the deciding variable is absent from 91–99% of records,
the operator is not deciding from the record.

**What survives** H3, SUPPORTED in 10 of 11 modules at rates 0.66–1.00 against a permutation
null, most p < 0.001: operators open a governing document before disposing, far above chance.
Step 3's target is therefore **prepare-and-present** — assemble the record, surface the governing
document, pre-fill the templated comment, flag incomplete fields — **and the human decides**.

**And AI does not yet earn its place inside it.** On the one non-trivial sub-task, governing-
document retrieval, a deterministic `(module, record type) → document` lookup reaches **64.2%**
(95% Wilson CI 56.2–71.5%) against 5.4% random, on n=148 labelled pairs over 17 document labels.
A learned retriever would have to exceed **71.5%** before this evidence could tell it apart from
the table. **The recommendation is the lookup table plus a good UI, instrumented so the residual
decides later.**

**Consequences** `docs/STEP2_AUTOMATION_OPPORTUNITY.md` §12 is superseded in place. The target
module is `FI|請求書承認・経費精算` — the only module whose operator annotation varies (19 差異あり vs
36 差異なし) and which carries 金額 on 87.1% of records. The system may not decide, cannot detect
errors, and cannot be evaluated against rejection behaviour even though the UI supports 差戻し —
a branch that never occurred in this capture window.

**The strongest reason this may still be wrong** H3 measures sequence, not causation. If the
document-open is procedural or habitual, surfacing it faster saves keystrokes and changes
nothing. No amount of Dataset B can settle that; it needs an operator interview or an A/B test
with the document suppressed.

**Evidence** `docs/STEP2_HYPOTHESIS_VERIFICATION.md`; `docs/STEP3_TARGET_REFRAME.md`;
`build/dataset_b/evidence/{hypothesis_tests,outcome_variance_sweep,retrieval_feasibility}.json`.

---

### ADR-025 · 2026-09-19 · accepted · ProcAssist: three queues, four statuses, no scores

**Context** ADR-024 settled the target as prepare-and-present with a deterministic lookup. This
ADR records the decisions taken while building it that a reader could otherwise mistake for
arbitrary choices.

**Three queues, not one.** Dataset B contains exactly **one** parsed `threshold` rule
(接待交際費規程 第２条) and it is keyed on 費目. Three screens are therefore needed to show the
engine's full behaviour honestly: `M05 :5133/payroll-items` (P6 invoices — **MISS**, no
regulation governs an invoice amount), `M01 :5132/payroll-items` (P1 接待交際費 with 金額 —
**OK/FLAG**) and `M07 :5133/leave-applications` (P9 — **REQUIRES_REVIEW**, because that screen
has no 金額 column at all). M07 is not padding: it is where the regulation is demonstrably
read — operators type 「規程確認のうえ承認」 there, and the captured Word document carrying 第２条
has that sentence in its body. No P1 or P6 record lacks 金額, so REQUIRES_REVIEW is unreachable
without it, and fabricating a gap was not an option.

**`document_id` is a capture-window content hash, not a document identity.** 15 distinct
`document_id`s carry the same 第２条 text under 5 different Word window titles. The regulation
name is the identity that means something; the id says which capture the excerpt came from.
`doc_type_ja` on those rows is screen text, not a document type, and is not surfaced.

**FLAG means the clause is ambiguous, not that we disagree with the operator.** 第２条's tiers
overlap: ¥135,181 satisfies both `5万円以上：役員承認` and `10万円以上：社長承認`. We report two
matching tiers as FLAG rather than applying a most-specific-wins convention the document never
states. Exactly one matching tier is OK. 12 of 120 records on the HR queue reach FLAG.

**Four statuses, no confidence score.** A score invites trading the statuses apart ("0.7 OK")
when three of them mean *stop and look* and only one means *the rule held*.

**Dependencies** `fastapi`, `uvicorn`, `pydantic`, `jinja2` — four, as sanctioned. Definition
files are **TOML via stdlib `tomllib`**, not YAML: YAML would have meant PyYAML, a fifth. The
HTTP tests call the ASGI app through a 50-line stdlib caller rather than
`fastapi.testclient`, which requires httpx, also a fifth.

**Consequences** `build/dataset_b/evidence/*` is read-only to `procassist/`, asserted by test.
The tool never operates a host control; `tests/test_procassist_panel_invariants.py` enforces
that by reading `panel/panel.js`. Every suggestion and every human response is written to
`build/procassist/audit.sqlite3`, hash-chained — that residual is what decides later whether a
model is warranted, and nothing here presumes the answer.

#### ADR-025 · addendum · 2026-09-19 · Band semantics, and the one declared knob

**Superseding ADR-025's FLAG rule.** ADR-025 reported ¥135,181 as `FLAG` on the grounds that
第２条's tiers overlap and the clause therefore selects no authority. That is true of the
string and wrong about the domain: tiered Japanese approval-authority clauses of this form are
read as **bands**, `5万円以上` meaning 5万〜10万, most specific tier winning. The engine now
applies `MOST_SPECIFIC_TIER` and the applicable authority for ¥135,181 is 社長承認, full stop.
The literal overlap survives as an `INF` note on the check, not as the verdict.

**What a FLAG now means** is that the authority the clause requires exceeds the **declared
ceiling** of the queue the record sits in. Each definition file carries an `[authority]` block
with `ladder_ja` (quoted from the clause — OBSERVED) and `ceiling_ja` with its own `basis`.

**The ceiling is the one policy knob in the system, and on the HR queue it is `INF`.** We
measured before declaring it: of 8 distinct 接待交際費 settlements observed on
`:5132/#/payroll-items`, 5 fall in the 役員承認 band (60,936–98,018円) and 3 in the 社長承認
band (118,189 / 123,224 / 135,181円), and **no observed field separates them** — all 23
接待交際費 records are 種別 調整, `exception_marker` false, `badge_ja` null. Where a settlement
clerk's authority stops is therefore the client's question, not the corpus's. It is one line of
TOML, the panel renders its `[INF]` tag, and 11 OK / 12 FLAG out of 120 follows from it.
M07's ceiling is weakly OBSERVED instead (n=2, both in the 部門長承認 band) and never fires,
because that screen has no 金額 column.

**Consequences** A reviewer must not read the OK/FLAG split as a measurement. Everything else
on the panel is; this is not, and it says so on screen.
