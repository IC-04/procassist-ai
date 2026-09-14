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

**S-E8.** On B, **0 of 943** consecutive segment pairs share a label, so the frozen system emits no
consecutive same-process executions. A cannot test the case either (0 of 1,689). Recorded as a
limitation; nothing was changed to chase it.
