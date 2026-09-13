# From Survey to Engineering Decision
## Solution-space analysis for inferring business-process executions from desktop operation logs

**Date:** 2026-09-11 · **Status:** pre-architecture analysis. No architecture is selected, no automation target is chosen, no production code is written.
**Inputs:** the v2 literature survey (terminology and conclusions preserved), `DATA_SCHEMA.md`, `README.md`, and **a direct reconnaissance of Dataset B performed for this document**.

---

## 0. Read this first: the reconnaissance changed the problem

Before writing this analysis I inspected the actual data in the project folder. Two things must be stated up front.

**(a) Dataset A is not present.** The folder contains `dataset_b` (15 sessions, 20 chunks, 20,477 events, 4,746 screenshots), `README.md` and `DATA_SCHEMA.md`. There is no `dataset_a`, therefore no ground truth. Everything in **Part 7** (ground-truth alignment) and every Dataset-A measurement in **Part 6** is *designed against the documented schema and cannot yet be verified*. Getting `dataset_a` onto disk is the single highest-priority unblocking action; it gates Milestones 2 onward.

**(b) The measurements below are from Dataset B only.** Dataset B is distribution-shifted from A by construction. These numbers describe the *deliverable* dataset, which is the right place to ground engineering decisions about what will actually be shipped — but they must not be assumed to hold for A.

### Measured facts (Dataset B, all 20,477 events)

| Measurement | Value | Engineering consequence |
|---|---|---|
| Total events / sessions / chunks | 20,477 / 15 / 20 | Tiny. Whole dataset fits in memory; every experiment is seconds, not minutes. |
| Session duration | **7.2–16.4 min**, ~3.2 h total across all 15 | These are short scripted recordings, not working days. "A session is one continuous recording from the beginning to the end of an employee's work session" is true but the session is ~11 minutes. |
| Distinct machines | **4** (`CHAITANYA0BCF`, `SIDDHIGUPTAB00B`, `NEELA9BAF`, `LAPTOP-76QMG9DE`) | "How many people" has a concrete, if assumption-laden, answer: 4 machine identities over 15 sessions. |
| Inter-event gap, median / p95 / p99 | **62 ms / 2.7 s / 6.0 s** | — |
| Gaps > 30 s in the entire dataset | **1** | **Idle-gap segmentation is dead on arrival.** There is no idle time to cut on. The brief's "waiting time is compressed" caveat has this as its concrete consequence. |
| `context.active_app` populated | **99.4%** | Application context is effectively universal. |
| `context.active_browser_tab` populated | **46.5%** | URL context on nearly half of all events. |
| `context.extracted_text` populated | **4.6%** | Matches the spec's ~4% — but see below, it is mostly worthless. |
| Distinct window titles (whole dataset) | **57** | The semantic vocabulary is tiny and enumerable. |
| Distinct browser URLs | **19** | Likewise. |
| `screenshot_smart` events | 4,759 (**23.2%**) | Screenshots are *not* sparse in B. 4,746 JPEGs on disk. |
| `clipboard_change` events | 872 (4.3%) | — |
| `clipboard.text_content` | **`null` on every event** (only `text_length` recorded) | **Clipboard carries no content.** The survey's open question Q13 — do clipboard values supply a surrogate case identifier — is answered *no* for this channel. |
| `text_input_complete` | 77 events (0.4%) | The spec's warning is moot: there is almost nothing there to misuse. |
| `app_switch` events | 1,654 (8.1%), of which **1,322 are Edge→Edge** | "Frequent application switching" is mostly *within-browser* context switching. True cross-application switches number ~330 in the whole dataset. |
| `extensions` namespaces (undocumented in `DATA_SCHEMA.md`) | `capture_quality_v1` 12,127 · `uia_v2` **9,289** · `cross_layer_v1` 2,726 · `dom_v2` 2,726 · `field_identity_v1` 2,415 · `dataflow_v2` **1,759** · `ocr_v1` 15 | **The largest unexamined asset in the dataset.** `uia_v2` is a UI-Automation tree; `dataflow_v2` plausibly carries copy→paste provenance; `cross_layer_v1` plausibly links L2 and L3 events. |
| `correlation.triggered_by` / `correlated_events` | 4,760 / **1,997** events | Explicit event-linking fields already present in the log. |

### What the semantic channel actually looks like

Window titles name the business system directly, and the file names are meaningful:

```
3190  HR人事給与システム - Profile 1 - Microsoft Edge          (HR payroll system)
2483  財務会計システム - Profile 1 - Microsoft Edge             (financial accounting system)
2012  受発注在庫管理システム - Profile 1 - Microsoft Edge        (order / inventory management)
 605  expense_calc - Excel
 573  budget_analysis - Excel
 559  keiyaku_kaijo_tetsuzuki - Compatibility Mode - Word      (contract cancellation procedure)
 537  nyusha_checklist_shinsotsu_batch - Word                  (new-graduate onboarding checklist)
 331  settai_keihi_kitei - Word                                (entertainment expense rules)
```

URLs are SPA hash routes that name the business function, served from three localhost ports:

```
port 5132 ↔ HR人事給与システム   (3,728 events)      routes: #/payroll-items, #/onboarding,
port 5133 ↔ 財務会計システム      (2,982 events)              #/resident-tax, #/leave-applications,
port 5134 ↔ 受発注在庫管理システム (2,321 events)              #/social-insurance, #/dashboard
```

The port→system mapping is near-clean: off-diagonal counts are 28–83 against diagonals of 2,321–3,728. **Port number is effectively a system/department label.**

DOM attributes are mostly `null`, but `id`, `placeholder` and `css_selector` are populated and semantic — e.g. `id="pi-note"`, `placeholder="処理内容・確認コメントを入力してください…"` ("enter processing details / confirmation comment"), `css_selector="#pi-note"`. Element-ID prefixes appear namespaced by route (`pi-` ↔ payroll-items).

By contrast, `extracted_text` is largely browser chrome: *"For quick access, place your favorites here on the favorites bar"*, *"Translate page from Japanese?"*, PowerShell banners. Source is `tree_walk`. **It is 4.6% of events and most of that 4.6% is noise.**

### The three conclusions that follow

1. **The "sparse semantics" problem that dominates the literature is largely not our problem.** The survey's family A3 assumed the semantic channel was 4% screen text. In Dataset B the semantic channel is `window_title` (99.4%) + URL route (46.5%) + element ID, over a vocabulary of 57 titles and 19 URLs. This is *rich*. It means the vision-language and OCR branch of the literature — the most technically glamorous part — is very likely unnecessary here, and should be rejected early rather than explored.

2. **The hard problem is boundary detection without idle gaps, plus interleaving.** With a p99 gap of 6 seconds and exactly one gap over 30 seconds, every time-threshold heuristic in the literature is inapplicable. And a naive "cut whenever `(app, title, route)` changes" rule produces **7,408 state changes across 20,477 events — one per 2.8 events, 464 blocks in a single 11-minute session.** That is over-segmentation by roughly an order of magnitude against any plausible number of true executions.

3. **Execution identity may have a real signal we have not looked at.** `correlation.correlated_events` (1,997 events), `correlation.triggered_by` (4,760) and `extensions.dataflow_v2` (1,759) are explicit linking structures. If `dataflow_v2` records copy→paste provenance, it is the closest thing to a case identifier this telemetry will ever offer, and it is worth one hour of inspection before any modelling decision is made. **This is Milestone 0.**

---

# PART 1 — The engineering problem as a pipeline

Nine stages. The point of separating them is that they fail independently and can be evaluated independently — which is what makes the Part 5 experiment matrix possible.

### Stage A — Event normalisation

| | |
|---|---|
| **Input** | `events.jsonl` across all chunks of a session; `manifest.json` |
| **Output** | One flat, time-ordered table per session: `(session_id, ts_ms, ts_iso, layer, event_type, app_name, process_name, window_title, url, route, element_id, element_label, chunk_id, seq_no, ms_since_last, triggered_by, correlated_events, ext_*)` |
| **Information available** | Everything; this stage is lossless flattening |
| **Information missing** | Nothing — this is the one stage with no inference |
| **Nature** | **Deterministic** |
| **Existing tools** | None specific. `pandas` + `json`. |
| **Build ourselves** | Yes, entirely. ~100 lines. |

Non-obvious requirements: chunk boundaries must be *dissolved*, not preserved (`sequence_number` restarts per chunk, so a global order must be rebuilt from `timestamp_ms`); events must be sorted within session across chunks; and `extensions.*` namespaces must be flattened into named columns rather than left as opaque JSON, or Stage D loses its best signal.

### Stage B — Event abstraction / representation

| | |
|---|---|
| **Input** | Normalised event table |
| **Output** | An *action alphabet*: each event mapped to a compact symbol, plus a **context state** `(app, system, route, document)` |
| **Information available** | app_name, window_title, URL route, element id/label, event_type |
| **Information missing** | The business activity name. This is the abstraction gap. |
| **Nature** | **Deterministic given a vocabulary**, which is derived statistically |
| **Existing tools** | Conceptually: event abstraction in process mining \[survey §4.1]. Practically: **none consume this input.** |
| **Build ourselves** | Yes. The vocabulary is 57 titles / 19 URLs — a lookup table, not a model. |

This is where the reconnaissance pays off most. In the general literature this stage needs supervised learning \[Tax et al.] or clustering. Here it is closer to parsing: `port → system`, `hash route → function`, `window title regex → document`, `element id prefix → form region`. **Do not model what you can parse.**

### Stage C — Execution boundary detection

| | |
|---|---|
| **Input** | Abstracted event stream with context state |
| **Output** | Candidate boundary positions (or dwell blocks) |
| **Information available** | Context-state transitions, event-type rhythm, route changes, document opens, form submissions |
| **Information missing** | Any marker of business-process start/end |
| **Nature** | **Heuristic or statistical**; possibly ML with Dataset-A labels |
| **Existing tools** | `ruptures` for change-point detection (needs a numeric signal); `stumpy` for motif discovery. Neither consumes the log. |
| **Build ourselves** | The featurisation and the smoothing/merging policy. The detector itself can be borrowed. |

The measured over-segmentation (1 state change per 2.8 events) means the real work here is **not detecting changes — it is suppressing them.** The engineering question is the merge rule, not the split rule.

### Stage D — Execution identity / grouping

| | |
|---|---|
| **Input** | Candidate segments |
| **Output** | Assignment of segments to executions; stitching of interrupted-and-resumed fragments |
| **Information available** | `correlation.correlated_events`, `triggered_by`, `extensions.dataflow_v2`, route continuity, document continuity |
| **Information missing** | Case identifiers (no clipboard content; no visible case numbers confirmed yet) |
| **Nature** | **Heuristic + graph**, possibly statistical |
| **Existing tools** | Correlation mining \[survey §4.1] assumes structured attribute-rich logs — **does not apply as implemented**. |
| **Build ourselves** | Yes. This is one of the two genuinely project-specific stages. |

### Stage E — Process-family and variant discovery

| | |
|---|---|
| **Input** | Executions as symbol sequences |
| **Output** | Cluster label per execution (the `label` field of `segments.jsonl`), plus within-cluster variants |
| **Information available** | Symbol sequences; system/route composition; duration |
| **Information missing** | Whether a difference is a business branch or operator habit \[survey L13] |
| **Nature** | **Statistical (clustering)**, evaluable on A |
| **Existing tools** | `scikit-learn` clustering; `rapidfuzz`/`Levenshtein` for sequence distance; trace clustering literature (no usable implementation for this input) |
| **Build ourselves** | Feature construction and the distance function. Clustering itself is reused. |

### Stage F — Semantic enrichment

| | |
|---|---|
| **Input** | Clusters, with representative segments |
| **Output** | Human-meaningful names, Japanese→English glosses |
| **Information available** | Window titles, routes, element labels, document filenames |
| **Information missing** | Nothing critical — this stage is now cheap |
| **Nature** | **LLM-assisted**, over *aggregates* not raw events |
| **Existing tools** | Any LLM; Japanese tokenisers if needed (probably not) |
| **Build ourselves** | A prompt over cluster summaries. Hours, not days. |

The survey treated this as a hard problem. Given 57 titles and 19 routes, it is a translation task over a fixed vocabulary. **Cost: near zero. Do it last, and do not let it drive the architecture.**

### Stage G — Operational analysis

| | |
|---|---|
| **Input** | `segments.jsonl` for Dataset B |
| **Output** | Frequency, relative effort share, machine/operator counts, per-family variant counts, transition statistics |
| **Information available** | Everything in the segments plus session metadata |
| **Information missing** | Business volumes, wage rates, error costs \[survey C2] |
| **Nature** | **Deterministic** aggregation |
| **Existing tools** | **This is where PM4Py finally becomes usable** — once segments have labels, `(session, label, start, end)` is a legitimate event log with a case notion. |
| **Build ourselves** | The aggregation; PM4Py for process maps if a visual is wanted. |

### Stage H — Automation candidate prioritisation

| | |
|---|---|
| **Input** | Operational analysis + feasibility evidence from the logs |
| **Output** | Ranked, evidenced candidate list with explicit assumption ledger |
| **Information available** | Frequency, effort share, application count, cross-app transitions, route determinism, form-field counts, branch counts |
| **Information missing** | Volumes, costs, API availability, governance constraints \[survey §4.7] |
| **Nature** | **Deterministic scoring over declared weights** |
| **Existing tools** | The structure of Gomez & Castillo's suitability index \[survey §4.7] is reusable *as a structure*, not as code |
| **Build ourselves** | The scorecard and, critically, the assumption ledger |

### Stage I — Prototype execution

| | |
|---|---|
| **Input** | One selected candidate |
| **Output** | Something that runs |
| **Information available** | The target systems are localhost SPAs on ports 5132–5134 — **but we do not have them** |
| **Information missing** | The running target application |
| **Nature** | Engineering |
| **Existing tools** | Playwright / RPA Framework, *if* a target exists |
| **Build ourselves** | Most likely a log-driven or mock-driven demonstration; see Milestone 6 |

**Coupling summary:** A→B is strictly sequential and cheap. C and D are tightly coupled (you cannot stitch what you have not split, and a bad split makes stitching impossible). E depends on C+D but its *failure modes are independent* — good segments can still cluster badly. F, G, H are downstream and near-independent. I is independent of everything except H's output.

---

# PART 2 — Build vs. reuse matrix

Verified by inspecting documentation and, where reachable, repository contents during this analysis.

| Capability | Tool | What it actually implements | Input expected | Output | Licence | Maturity | Consumes our raw data? | Adaptation required | Still to implement | Risk | **7-day verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Process discovery, conformance, process maps | **PM4Py** | Alpha/inductive/heuristics miners, conformance checking, DFG, performance analysis, XES/CSV I/O | pandas DataFrame with `case:concept:name`, `concept:name`, `time:timestamp` via `format_dataframe` | Petri nets, process trees, DFGs, statistics | open source | Mature, company-backed, published | **No.** It has no concept of keystrokes, window titles, or unlabelled streams | Feed it *our* output: one row per segment, `case = session or execution`, `activity = label` | Everything upstream of it | Low — but **high risk of misuse**: reaching for it at Stage C is a category error | **Reuse at Stage G only.** ~1 hour. |
| Change-point detection | **`ruptures`** | Pelt, BinSeg, Window, DynP over cost models (`l1`,`l2`,`rbf`); `rpt.Pelt(model=...).fit(signal).predict(pen=...)`; signal is `(n_samples, n_dims)` float array | **Numeric matrix** | Array of change-point indices | BSD-2 | Mature | **No** — our signal is categorical | Build a numeric encoding: sliding-window histograms over the action alphabet, or one-hot context state; `rbf` cost handles non-Euclidean structure reasonably | Featurisation, penalty selection, post-hoc merging | Medium — penalty `pen` must be tuned, and tuning on A is a transfer risk \[survey L7] | **Reuse at Stage C.** ~3 hours to first result. |
| Segmentation scoring | **`segeval`** | `pk()`, `window_diff()`, `boundary_similarity()`, `segmentation_similarity()`, boundary-edit-distance measures, inter-coder agreement (Fleiss' π/κ) | Segmentations as *masses* (segment lengths) or boundary strings | Tolerance-aware error scores | see repo | Stable, documented, from ACL work | **No** — needs our segments converted to masses over a common unit | Define the atomic unit (event index vs. time bin) and convert both reference and hypothesis to masses | The conversion; label-aware scoring (segeval scores boundaries only) | Low | **Reuse at evaluation.** ~2 hours. The single highest value-per-hour reuse in this table. |
| Motif-based segmentation | **TimeSeriesInRPM** | Two Jupyter notebooks reproducing word2vec + time-series motif segmentation; bundles Leno-format example logs | Leno-format UI logs (CSV) | Experiment result CSVs | MIT | Research artifact: ~20 commits, 0 stars | **No** | Would require converting our log into Leno's UI-log format, which loses our richest fields | Effectively a reimplementation | Medium | **Read as a reference, do not depend on it.** Worth 30 minutes of reading the notebook; not worth integrating. |
| Unsupervised segmentation + typing | **Rebmann & van der Aa** (Univ. Mannheim GitLab) | Companion code to CAiSE 2023: keyword chunking, contextual relatedness, DenStream clustering | Interaction event streams in their schema | Tasks + type clusters | not stated on landing page | University research artifact | **No** | Schema conversion, plus their method **explicitly cannot handle interleaved tasks** \[survey L3] — which is our central condition | — | High — unverified licence, and the documented limitation targets our exact case | **Reuse the *method design*, not the code.** Their two-part evaluation structure (boundary quality separate from cluster quality) is the best thing to copy. |
| Desktop telemetry capture | **ActivityWatch** | Window/app watchers, AFK detection, local REST API, **manual rule-based categorisation** | Live desktop | Time buckets, category reports | MPL-2.0 | Mature, widely used | **No** — it is a collector; we already have collected data | None useful | — | — | **Reject as a dependency.** Valuable only as evidence that the industry solves categorisation by hand-written rules — which supports a rule-based Stage B. |
| Screen-based task mining | **ScreenRPA (RPA-US)** | UI recording, eye tracking, feature extraction, decision discovery, Graphviz visualisation | Its own capture format + screenshots | UI logs, visualisations | **CC BY-NC** | 6 stars, 982 commits, v1.0.2 (2025) | **No** | Heavy | — | High: **the non-commercial licence is disqualifying for a client-facing deliverable** | **Reject.** |
| Demonstration→replay automation | **OpenAdapt** | Records screenshots/actions/accessibility data; embeds demonstrations; conditions or fine-tunes VLMs to replay | Its own live recorder | Replayable automation | MIT | 1.6k stars, actively maintained (v1.2.4, Jun 2026) | **No** — it records its own data and cannot ingest ours | Would require writing an adapter into its schema and a target app to replay against | — | High: solves the *inverse* problem (replay a known task), not discovery | **Reject as a dependency.** Possibly relevant as a Stage-I reference if a live target existed. It does not. |
| UI-log → software robot | **SmartRPA** | Records UI logs, analyses variants, reactively synthesises executable robots | Its own recorder format | Executable robots | see repo | Peer-reviewed (Comp. in Industry 2022, SoftwareX 2025) | **No** | Requires its recorder *and* an actuatable target application | — | High | **Reject as a dependency.** Cite as precedent for what a Stage-I prototype would look like with a live system. |
| Sequence distance / alignment | **`rapidfuzz`**, `python-Levenshtein`, `difflib` | Fast edit distance, partial ratio, alignment | Strings / sequences | Distances | MIT | Mature | **Yes**, once events are mapped to symbols | Map alphabet to single characters or use token lists | The alphabet | Low | **Reuse at Stage E.** ~1 hour. |
| Clustering | **`scikit-learn`** | Agglomerative (with `metric='precomputed'`), DBSCAN, HDBSCAN, silhouette, ARI, NMI | Feature matrix or precomputed distance matrix | Labels | BSD | Mature | Yes, after featurisation | None | Feature/distance design | Low | **Reuse at Stage E and for evaluation metrics (ARI/NMI).** |
| Motif discovery | **`stumpy`** | `stump` (1-D matrix profile), `mstump` (multi-dimensional), `motifs` | numpy arrays; `stump` is 1-D, `mstump` takes dimensions as rows | Matrix profile, motif indices | 3-Clause BSD | Mature | **No** — needs numeric series | Same featurisation problem as `ruptures` | — | Medium: designed for continuous signals, not categorical streams | **Optional, Stage C/E.** Only if the `ruptures` route shows promise and motifs are needed for identity. |
| Sequential pattern mining | `prefixspan` (PyPI), SPMF via wrapper | Frequent/closed sequential patterns, gap constraints | Lists of sequences | Frequent patterns | varies | Thin (prefixspan) / mature but Java (SPMF) | Yes, after symbolisation | Symbolisation | — | Medium: SPMF needs a JVM; prefixspan is lightly maintained | **Optional.** This is the CloFast-equivalent of Leno et al. Defer until Stage C works. |
| Japanese tokenisation | `fugashi`+`unidic-lite`, `SudachiPy`, `janome` | Morphological analysis | Japanese text | Tokens, readings, POS | MIT/Apache | Mature | Yes | pip install | — | Low | **Probably unnecessary.** With 57 titles and 19 routes, a hand-built glossary of ~30 terms beats a tokeniser. Revisit only if Dataset A's vocabulary is large. |
| Japanese OCR | `manga-ocr`, PaddleOCR (`japan`), Tesseract `jpn` | Image→text | Images | Text | Apache/MIT | Mature | Yes (screenshots are on disk) | Model download; GPU helpful | — | Medium: 4,746 images, slow on CPU | **Reject for now.** `extracted_text` already exists and is mostly chrome noise; window titles and URLs carry the same information more cheaply. Revisit only if Stage B fails on A. |
| Vision-language screen labelling | VLMs per \[survey §4.6] | Activity descriptions from screenshots; ~0.75 cosine similarity to human labels | One screenshot per event | Text descriptions | varies | Research-stage | Yes technically | Significant | — | High cost, modest accuracy, and **it answers a question we can already answer from window titles** | **Reject.** This is the most attractive-looking and least justified option in the whole space. |
| Browser/UI automation (Stage I) | **Playwright**, Selenium, `rpaframework` | Drive a browser or desktop app | A running target | Actions | Apache/MIT | Mature | N/A | N/A | N/A | **The target systems do not exist for us** | **Conditional.** Only usable if the prototype includes a mock target we build ourselves. |

**Summary of reuse decisions.** Definitely reuse: `segeval`, `ruptures`, `scikit-learn`, `rapidfuzz`, `pandas`, and PM4Py *at Stage G only*. Definitely do not build from scratch: change-point detection, edit distance, clustering, segmentation metrics, cluster-comparison metrics. Definitely reject: ScreenRPA (licence), OpenAdapt, SmartRPA, OCR, VLM labelling.

---

# PART 3 — The true missing middle

The hypothesis in the brief was:

```
raw desktop telemetry → business execution reconstruction → standard process mining
```

**That shape is right, but the contents of the middle box are not what the survey predicted.** The survey, reasoning from the literature, expected the middle to be dominated by *semantic enrichment* (the A3 problem: how do you extract meaning from 4% screen text?). The reconnaissance says otherwise.

### What the middle is NOT

**Not semantic enrichment.** With 57 distinct window titles, 19 URLs, a clean port→system mapping and semantic element IDs, meaning is available by *parsing*, not inference. The expensive machinery the literature built for this — OCR, VLMs, supervised abstraction — solves a problem we do not have. (Caveat: verified on B only; A may be worse.)

**Not event abstraction in the process-mining sense.** `vanzelst2021abstraction`'s taxonomy assumes you must learn a mapping from low-level events to activities. Here the mapping is a lookup table over an enumerable vocabulary.

**Not trace clustering.** Once executions exist as symbol sequences, grouping them is a solved problem with mature tooling (`scikit-learn` + `rapidfuzz`). It is downstream, cheap, and its failure modes are independent.

### What the middle actually IS

Three coupled sub-problems, in dependency order:

**M1 — Boundary detection under zero idle time.** Every heuristic in the literature that uses a time gap is inapplicable: p99 gap is 6 s, and there is exactly one gap over 30 s in 20,477 events. Simultaneously, the obvious alternative — cut on context-state change — over-segments by roughly an order of magnitude (7,408 changes; 464 blocks in one 11-minute session). **The engineering problem is a merge/suppression policy, not a detection policy.** No existing tool provides this because no existing tool knows what a business process boundary looks like.

**M2 — Interleaving resolution and fragment stitching.** The storyline of a single session shows the real pattern: work in `#/payroll-items`, switch to a Word procedure document, return to `#/payroll-items`, glance at 財務会計システム, return. Whether that is one execution with reference lookups, or two interleaved executions, is exactly the question \[survey L1–L3] says nobody has solved. The output schema makes it worse: `segments.jsonl` has four flat fields and cannot express "this execution has two disjoint intervals" \[survey L6].

**M3 — Execution identity without a case identifier.** Clipboard content is `null`, so the obvious surrogate is gone. What remains unexamined: `correlation.correlated_events` (1,997), `correlation.triggered_by` (4,760), `extensions.dataflow_v2` (1,759). If `dataflow_v2` is copy→paste provenance, M3 partly collapses into a graph-connectivity problem. **This is the single highest-information unexamined question in the project.**

### Coupling analysis — what must be solved together, what can be separated

| Pair | Coupled? | Why |
|---|---|---|
| M1 ↔ M2 | **Tightly coupled.** | You cannot stitch fragments you failed to split, and an over-segmented stream makes stitching combinatorially hard. They must be designed as one mechanism with two parameters (split sensitivity, merge aggressiveness). |
| M1 ↔ M3 | **Coupled, and exploitable.** | If provenance links exist, they are *evidence for* boundaries: two events joined by a dataflow link are very likely in the same execution. Identity can inform boundaries, not just follow them. This inverts the usual pipeline order and is worth testing. |
| M2 ↔ M3 | **Tightly coupled.** | Stitching a resumed fragment to its original *is* an identity decision. |
| M1/M2/M3 ↔ Stage E (clustering) | **Separable.** | Clustering quality can be measured independently by feeding it *ground-truth* segments from Dataset A. This is an important experimental lever: it lets us find out whether identity is even learnable before we have working boundaries. |
| Middle ↔ Stage G (PM4Py, analysis) | **Fully separable.** | Once `(session, label, start, end)` exists, downstream is standard. |
| Middle ↔ Stage F (naming) | **Fully separable.** | Cosmetic and late. |

**The practical consequence:** build a harness that can evaluate Stage E on ground-truth segments *before* Stage C works. That single decision decouples the two hardest risks and is why Milestone 1 below is what it is.

---

# PART 4 — Candidate solution families

Six families, qualitatively different. None is selected.

---
## Family A — Dwell-block segmentation on context state

**1. Core idea.** Define a *context state* `(app, system, route, document)`. Emit a boundary where the state changes and the new state persists for at least `d` events or `t` milliseconds. Merge blocks separated by short excursions back into the parent.
**2. Event representation.** A tuple of categorical fields; no vectorisation.
**3. Boundaries.** State change + dwell threshold + excursion-merge rule.
**4. Grouping.** By the dominant state of the block (e.g. all `#/payroll-items` blocks share a label).
**5. Interruptions.** Handled explicitly by the excursion-merge rule: `A → B(short) → A` collapses to one `A` block. This is the family's main strength.
**6. Variants.** Sub-clustering within a label by the sequence of sub-states visited.
**7. Sparse text/screenshots.** Not used at all.
**8. If semantics absent.** Degrades to app-only segmentation and collapses. Fully dependent on titles/URLs being informative.
**9. Cost.** Trivial — seconds over the whole dataset.
**10. Explainability.** **Highest of any family.** Every boundary traces to a named state change a human can read.
**11. Dataset-A dependence.** Only for tuning `d`/`t` and evaluating. The mechanism is label-free.
**12. Transfer to B.** Excellent *if* the parameters are expressed in domain-agnostic units (events, or quantiles of the observed dwell distribution) rather than absolute seconds tuned on A.
**13. Reuse.** `pandas` only.
**14. Build.** The state definition and the merge policy. ~150 lines.
**15. Failure modes.** (i) Over-segmentation if excursions are frequent — **we have measured that they are**; (ii) under-segmentation when two consecutive executions of the *same* process occur back-to-back in the same route, which this family cannot split at all; (iii) collapse if A's window titles are generic.
**16. Validating evidence.** On Dataset A: boundary recall/precision against ground truth at a fixed tolerance, plus the count ratio (predicted executions ÷ true executions). Failure signature: count ratio ≫1 (excursions) or the inability to split consecutive same-route executions (count ratio <1 with high boundary recall on transitions only).

---
## Family B — Change-point detection on a windowed feature signal

**1. Core idea.** Convert the event stream into a numeric multivariate signal — sliding-window histograms over event types, apps, routes and element-ID prefixes — and run offline change-point detection.
**2. Event representation.** Window-level feature vector (counts/rates), not per-event.
**3. Boundaries.** `ruptures` Pelt with `rbf` cost; penalty `pen` controls granularity.
**4. Grouping.** Separate step (Family C or E machinery).
**5. Interruptions.** Poorly. A short excursion is a genuine distributional change and will be flagged. Needs the same merge policy as Family A bolted on.
**6. Variants.** Not addressed.
**7. Sparse text/screenshots.** Not used.
**8. If semantics absent.** Degrades gracefully — event-type rhythm alone still carries signal. **This is the family's distinguishing strength: it is the most robust to bad window titles.**
**9. Cost.** Seconds to a minute.
**10. Explainability.** Moderate. A boundary is "the feature distribution changed"; you can show which features moved, but it is less legible than Family A.
**11. Dataset-A dependence.** Penalty selection must be tuned on A — **and this is a genuine transfer risk** \[survey L7]. Mitigate by expressing the penalty relative to signal variance rather than as an absolute.
**12. Transfer to B.** Moderate. The featurisation transfers; the penalty may not.
**13. Reuse.** `ruptures` (verified API: `rpt.Pelt(model="rbf", min_size=..., jump=...).fit(signal).predict(pen=...)`, signal shape `(n_samples, n_dims)`).
**14. Build.** Windowing and featurisation; penalty calibration protocol.
**15. Failure modes.** (i) Penalty tuned on A transfers badly to B; (ii) window size trades boundary precision against detectability; (iii) flags UI noise (the "Turn off extensions in developer mode" dialogs we observed) as change points.
**16. Validating evidence.** Sweep `pen` on Dataset A and plot the boundary-F1/WindowDiff curve. If the curve is flat-topped and wide, the method is robust and transfer risk is low. If it is a narrow peak, **the family should be rejected on transfer grounds regardless of its peak score.** That single plot is one of the most informative experiments in the whole matrix.

---
## Family C — Sequence/motif-based discovery

**1. Core idea.** Symbolise events into an alphabet, then find repeated subsequences (motifs); treat motif occurrences as execution instances.
**2. Event representation.** A single symbol per event, from `(event_type, route/app)`.
**3. Boundaries.** Implied by motif extent.
**4. Grouping.** Free — occurrences of the same motif are the same process by construction. **This is the family's elegance: boundaries and identity fall out together.**
**5. Interruptions.** Badly. A motif interrupted mid-way does not match. Gapped pattern mining (CloFast-style, per Leno et al.) mitigates but does not solve.
**6. Variants.** Naturally — different motifs in the same family.
**7. Sparse text/screenshots.** Not used.
**8. If semantics absent.** Survives, if the action rhythm differs between processes.
**9. Cost.** Moderate; `stumpy.stump` is fast but requires numeric encoding; sequential pattern mining scales with alphabet and support threshold.
**10. Explainability.** Good — a motif is a literal displayable pattern.
**11. Dataset-A dependence.** Support/length thresholds tuned on A.
**12. Transfer to B.** Moderate. Motifs themselves are domain-specific and **must not be carried from A to B** — only the discovery procedure transfers.
**13. Reuse.** `stumpy`, `prefixspan`; TimeSeriesInRPM as a readable reference.
**14. Build.** Symbolisation, threshold policy, occurrence-to-segment conversion.
**15. Failure modes.** (i) **The documented failure mode of the flagship method** \[survey L2] — motif approaches assume consecutive, non-overlapping, non-shared executions, exactly what we do not have; (ii) an over-coarse alphabet makes everything one motif; (iii) coverage gaps — events belonging to no motif have no segment, but `segments.jsonl` may need full coverage.
**16. Validating evidence.** Measure *coverage* first: what fraction of Dataset A's ground-truth executions are matched by any discovered motif. If coverage is low (<50%), reject early — this is a cheap, decisive test.

---
## Family D — Correlation / provenance-based reconstruction

**1. Core idea.** Build a graph over events using the *explicit* linking fields already in the log — `correlation.triggered_by`, `correlation.correlated_events`, `extensions.dataflow_v2`, `extensions.cross_layer_v1` — and take connected components (or densely-connected communities) as executions.
**2. Event representation.** Graph nodes with typed edges.
**3. Boundaries.** Emergent: the time span of a component.
**4. Grouping.** By component signature (which systems/routes it touches).
**5. Interruptions.** **Handled naturally and correctly.** A component is not required to be contiguous in time — which is precisely what a suspended-and-resumed execution is. No other family gets this for free.
**6. Variants.** By component topology.
**7. Sparse text/screenshots.** Not needed.
**8. If semantics absent.** Still works — this is a structural method.
**9. Cost.** Trivial (`networkx`).
**10. Explainability.** **Excellent and defensible**: "these events are one execution because the system itself recorded that this paste came from that copy."
**11. Dataset-A dependence.** Minimal — near parameter-free.
**12. Transfer to B.** **Best of any family**, provided the same fields are populated in both datasets (verified present in B; *unverified in A*).
**13. Reuse.** `networkx`.
**14. Build.** Field interpretation and component-merging rules.
**15. Failure modes.** (i) **The fields may not mean what we hope** — `dataflow_v2` on only 1,759 of 20,477 events (8.6%) means coverage is partial at best; (ii) components may be too small (fragments) or too large (one giant component across a whole session); (iii) the fields may be absent or differently populated in Dataset A.
**16. Validating evidence.** Inspect the actual contents of these fields (Milestone 0), then measure: what fraction of ground-truth executions in A contain at least one intra-execution link, and how often a link *crosses* a true execution boundary. **If links respect ground-truth boundaries, this family becomes the backbone of the solution. If they cross freely, it is dead.** This is a one-hour experiment with an enormous decision payoff.

---
## Family E — Hybrid: anchored blocks + provenance stitching + clustering identity

**1. Core idea.** Layer the above deliberately: Family A produces candidate blocks; Family D's links stitch blocks into executions across interruptions; Family C/E machinery clusters the stitched executions into labelled families.
**2. Event representation.** Context state per event + graph edges.
**3. Boundaries.** Family A, with the merge policy informed by Family D's links (a link spanning a candidate boundary is evidence against that boundary).
**4. Grouping.** Clustering over sequence + composition features.
**5. Interruptions.** By design — this is the family built specifically around M2.
**6. Variants.** Sub-clusters within a family label.
**7. Sparse text/screenshots.** Only for Stage F naming.
**8. If semantics absent.** Degrades to Family B + D.
**9. Cost.** Still trivial at this data scale.
**10. Explainability.** Good — each decision layer is separately inspectable.
**11. Dataset-A dependence.** Moderate: two or three thresholds.
**12. Transfer to B.** Good if thresholds are quantile-based.
**13. Reuse.** `pandas`, `networkx`, `scikit-learn`, `rapidfuzz`.
**14. Build.** The layering and the evidence-combination rule.
**15. Failure modes.** (i) Complexity: three coupled components mean three sets of parameters and harder attribution of failure; (ii) if D's links are worthless, this degenerates to Family A with extra steps and wasted days.
**16. Validating evidence.** Only worth building *after* A and D have been independently measured. Ablation is the evaluation: measure A alone, D alone, then A+D, and confirm the combination beats both.

---
## Family F — LLM-assisted labelling over compressed block summaries

**1. Core idea.** Do *not* give an LLM raw events. Compress each candidate block into a short structured summary (system, route, documents touched, action counts, duration, form fields), then use an LLM to (a) name it and (b) judge whether adjacent blocks belong to the same execution.
**2. Event representation.** A ~50-token text summary per block.
**3. Boundaries.** LLM as *adjudicator* on candidate boundaries proposed by another family, not as generator.
**4. Grouping.** LLM assigns a canonical label from an evolving label set.
**5. Interruptions.** The LLM can be asked directly whether block *k* resumes block *j*.
**6. Variants.** Descriptive, in natural language.
**7. Sparse text/screenshots.** The Japanese titles and routes are exactly what an LLM handles well — no tokeniser or OCR needed.
**8. If semantics absent.** Collapses entirely. This family is *purely* a semantics play.
**9. Cost.** ~500–3,000 LLM calls for Dataset B depending on block count; minutes and a few dollars. Non-trivial but affordable.
**10. Explainability.** Moderate and *fragile* — the reasoning is post-hoc and not reproducible run to run.
**11. Dataset-A dependence.** Can be evaluated on A, but **prompt-tuning on A is a subtle leakage channel** \[survey L7]: a prompt that enumerates A's process names will not transfer and is arguably cheating.
**12. Transfer to B.** Good in principle — this is the one family that genuinely handles an unseen vocabulary zero-shot — **provided the prompt never names A's processes.**
**13. Reuse.** Any LLM API.
**14. Build.** The summarisation schema, the label-consistency mechanism (the hard part: keeping the same process mapped to the same label across 15 sessions), and determinism controls.
**15. Failure modes.** (i) **Label drift** — the same process gets different names in different sessions, which fails the assignment's explicit consistency criterion; (ii) non-determinism undermines reproducibility; (iii) cost/latency if applied per-event rather than per-block; (iv) it looks impressive and can hide a weak segmenter underneath.
**16. Validating evidence.** On Dataset A: feed *ground-truth* segments, ask for labels, and measure cluster agreement (ARI/NMI) against true process codes. This isolates labelling quality from segmentation quality completely, and costs almost nothing. **If an LLM cannot consistently label ground-truth segments, it certainly cannot label inferred ones.**

---
### Family comparison at a glance

| | A Dwell | B Change-point | C Motif | D Provenance | E Hybrid | F LLM |
|---|---|---|---|---|---|---|
| Solves M1 (boundaries) | ✔ | ✔ | partial | partial | ✔ | adjudicates only |
| Solves M2 (interleaving) | partial | ✘ | ✘ | **✔** | ✔ | partial |
| Solves M3 (identity) | weak | ✘ | ✔ | **✔** | ✔ | ✔ |
| Needs informative titles | **✔ critically** | ✘ | ✘ | ✘ | partial | **✔ critically** |
| Parameter-free | ✘ | ✘ | ✘ | **✔** | ✘ | ✘ |
| Transfer risk to B | low | **high** | high | **lowest** | medium | medium |
| Days to first result | 0.5 | 0.5 | 1.5 | 0.5 | 2 | 1 |

---

# PART 5 — Minimum experimental matrix

Designed for **maximum information per engineering hour**, not maximum sophistication. The ordering matters: E0–E2 are cheap and can each kill a whole family.

Note the deliberate asymmetry: several experiments are designed so that a *negative* result is as decisive as a positive one. Effort figures assume the normalisation layer (Milestone 0) already exists.

| # | Hypothesis | Features | Method | Output | Metric | Success | If it fails | Effort |
|---|---|---|---|---|---|---|---|---|
| **E0** | The explicit linking fields (`triggered_by`, `correlated_events`, `dataflow_v2`, `cross_layer_v1`) encode real intra-execution relationships | those four fields | Dump and read 50 examples; then, on A, measure how often a link stays inside one ground-truth execution vs. crosses a boundary | A note plus one number: *link containment rate* | fraction of links entirely within one true execution | >0.9 containment with >30% execution coverage ⇒ Family D is the backbone | If containment ≈ random, **reject Family D immediately** and the middle collapses to M1+M2 only | **1–2 h** |
| **E1** | Idle gaps carry no boundary information | `ms_since_last_event` | Rank all gaps; take the top-*k* as boundaries for *k* = true execution count | boundary F1 at ±2 s and ±5 s tolerance | — | F1 > 0.3 would be surprising and would resurrect time-based methods | Expected to fail (measured p99 = 6 s on B). **Its value is as a documented baseline floor in the report** | **1 h** |
| **E2** | Context-state change over-segments; a dwell threshold fixes it | `(app, system, route, document)` | Family A, sweeping dwell threshold *d* ∈ {1,2,3,5,8,13,21} events | boundary F1 curve, count ratio (predicted÷true) | boundary F1 + WindowDiff via `segeval` | A *d* exists where count ratio ∈ [0.7, 1.4] and F1 > 0.6 | If no *d* works, boundaries are not a function of context state alone ⇒ Family A is insufficient and Family B/D become necessary | **3 h** |
| **E3** | Identity is learnable independently of boundaries | ground-truth segments from A | Featurise each true execution (route histogram, app set, symbol sequence); cluster with agglomerative + `rapidfuzz` distance; also try `k` = true family count | ARI / NMI vs. true `process_code` | ARI | ARI > 0.6 ⇒ the identity half is solved and can be decoupled | If ARI is low even on *perfect* segments, **no amount of segmentation work will produce usable labels** — a critical early warning | **3 h** |
| **E4** | An LLM can label ground-truth segments consistently | block summaries of true executions | Family F over ground-truth segments only | cluster labels | ARI / NMI vs. true `process_code`; plus label-consistency across sessions | Beats E3's ARI by a clear margin | If it does not beat cheap clustering, **reject Family F** — it adds cost, non-determinism and no accuracy | **3 h** (after E3) |
| **E5** | Change-point detection is robust to penalty choice | sliding-window histograms (window ∈ {25, 50, 100} events) | `ruptures` Pelt/`rbf`, sweep `pen` | boundary F1 vs. `pen` curve | shape of the curve, not its peak | A wide plateau ⇒ low transfer risk ⇒ Family B viable for B | A narrow peak ⇒ **reject Family B on transfer grounds even if its peak beats everything else** | **4 h** |
| **E6** | Motifs cover a useful fraction of executions | symbolised stream | Sequential pattern mining; measure coverage before anything else | coverage % of true executions matched | coverage | >50% coverage | <50% ⇒ **reject Family C**; consistent with the documented failure mode of the flagship method under interleaving \[survey L2] | **4 h** |
| **E7** | Provenance links improve a dwell segmenter (ablation) | E2 output + E0 links | Family E: veto boundaries crossed by a link; stitch blocks sharing links | boundary F1, count ratio, and a *fragment-stitching* measure | F1 and interruption recall | A+D beats both A alone and D alone | If no gain, **drop the hybrid** and ship the simpler family | **4 h**, only if E0 and E2 both pass |
| **E8** | Results are stable across sessions, not driven by one | best configuration so far | Leave-one-session-out over A | per-session metric spread | std. dev. / IQR across held-out sessions | Spread small relative to the A-vs-B gap we expect | High variance ⇒ any single number reported for A is unreliable and must be reported as a distribution | **2 h** |

**Total: ~25 engineering hours** for the full matrix, of which **E0+E1+E2+E3 ≈ 8 hours decides the architecture.** That is the core claim of this section: eight hours of experiment eliminates or confirms four of six families.

**Sequencing rule.** Run E0 first — it is the cheapest and has the highest variance in outcome. Run E1 and E2 next (same harness). Run E3 in parallel with E2 if two people are working, since it needs only ground truth and shares no code. E4–E7 are conditional on the results above. E8 is a reporting-integrity step, not a discovery step.

---

# PART 6 — Data audit

Some of this is **already done for Dataset B** (§0). What follows marks each diagnostic as **[DONE-B]**, **[TODO-A]**, or **[TODO-both]**, states the question it answers, the artifact to produce, and — crucially — how it changes an engineering decision.

| # | Diagnostic | Status | Question answered | Artifact | Decision it changes |
|---|---|---|---|---|---|
| 1 | Event-type distribution | **[DONE-B]** | What is actually in the stream? | Bar chart + table by `layer` and `event_type` | B found: keystrokes 22.8%, screenshots 23.2%, app_switch 8.1%. **Screenshots are not rare** — but also not needed. Confirms the alphabet for symbolisation. |
| 2 | Inter-event gap distribution | **[DONE-B]** | Is there idle time to segment on? | Log-scale histogram + quantile table | **Decisive: no.** p99 = 6 s, one gap > 30 s. Kills all time-threshold heuristics; mandates E1 as a documented floor rather than a candidate. |
| 3 | Application-switch frequency and *type* | **[DONE-B]** | Is switching cross-app or within-app? | Transition matrix | 1,322/1,654 switches are Edge→Edge. **Reframes "application switching" as route switching**; tells us to build the context state around route, not app. |
| 4 | Window-title informativeness | **[DONE-B]** | Are titles generic or semantic? | Distinct-count + top-*n* table + entropy | 57 distinct, directly naming business systems. **This is why Stage B is parsing, not modelling.** Must be re-run on A — if A's titles are generic, Family A collapses. |
| 5 | Browser URL/DOM informativeness | **[DONE-B]** | Do routes name business functions? | Route inventory; port×system cross-tab; element-ID prefix inventory | 19 URLs, 6 routes, clean port→system map, semantic IDs (`pi-note`). **Route becomes the primary context dimension.** |
| 6 | Clipboard informativeness | **[DONE-B]** | Is there a surrogate case key? | Payload schema dump + distinct-value count | **`text_content` is null.** Answers survey Q13 negatively for this channel; removes an entire hoped-for mechanism. |
| 7 | Sparse screen-text distribution *and quality* | **[DONE-B]** | Is `extracted_text` worth parsing? | Population rate + 20 random samples | 4.6% populated, mostly browser chrome and translate prompts. **Deprioritise; do not build an OCR/VLM path.** |
| 8 | Screenshot distribution | **[DONE-B]** | How many, and do they add anything titles do not? | Count per chunk; sample 10 against their titles | 4,746 images. Given titles/routes, marginal value is low. **Reject the VLM branch unless A is title-poor.** |
| 9 | Execution duration distribution | **[TODO-A]** | How long is a unit of work? | Histogram of `end_ts - start_ts` from `gt_manifest.json` | Sets the dwell threshold *d* prior and the `min_size` for `ruptures`. Without it, E2's sweep range is guesswork. |
| 10 | Interruption/resumption frequency | **[TODO-A]** | Is interleaving rare or pervasive? | Count of `process_suspended`/`process_resumed`; distribution of `split_id`; fraction of executions with `continues_from_prev`/`continues_to_next` | **The single most decision-relevant Dataset-A number.** If <10% of executions are split, Family A alone may suffice and Family D is optional. If >30%, M2 is the project and Family D/E is mandatory. |
| 11 | Applications per execution | **[TODO-A]** | Is an execution single-app or cross-app? | Histogram over `executions[].apps` | Determines whether app/route composition is a usable identity feature (Stage E). |
| 12 | Repeated application/route sequences | **[TODO-both]** | Is there motif structure at all? | Top-*n* n-grams over the route symbol stream | Gates E6. If the top n-grams are dominated by one pattern, motif discovery will collapse to a single cluster. |
| 13 | Shared actions between process families | **[TODO-A]** | Does the condition the literature cannot handle actually occur? | Confusion matrix of symbol → process family; count of symbols appearing in >1 family | Directly tests survey L1. High sharing ⇒ pure-sequence methods (Family C) are doomed and structural methods (D) become essential. |
| 14 | Process / variant / task granularity | **[TODO-A]** | What is "one unit"? | Counts of families, executions, tasks; executions per family; variants per family | **Settles the label-granularity decision** (survey L12) that silently determines every score. Must be decided explicitly and recorded. |
| 15 | Duplicate and malformed GT records | **[TODO-A]** | How bad is the ground truth? | Count of consecutive duplicate `process_started`; unpaired `process_switched_out`; `gt.jsonl` vs. `gt_manifest.json` disagreements | Determines the repair policy (Part 7) and sets a ceiling on achievable measured accuracy. |
| 16 | Non-business activity | **[DONE-B, TODO-A]** | How much is not work? | Time share by app/route outside business systems | B: Slack in 3 sessions, PowerShell, "Turn off extensions" dialogs. Decides whether `segments.jsonl` must tile the session or may leave gaps. |
| 17 | Surrogate case identifiers | **[PARTIAL]** | Is there any per-case key? | Regex sweep for ID-like tokens across titles, URLs, form values, DOM labels; plus E0's link analysis | Clipboard: **no**. Still to check: form input values, `field_identity_v1`, `dataflow_v2`. **This is the open question with the largest remaining payoff.** |

**Two additional diagnostics not in the original list but warranted by what we found:**

| 18 | `extensions.*` namespace inventory | **[TODO-both]** | What is in the undocumented namespaces (`uia_v2`, `dataflow_v2`, `cross_layer_v1`, `field_identity_v1`)? | Schema dump: keys, population rates, 10 samples each | **Highest information-per-hour diagnostic available.** `DATA_SCHEMA.md` documents `extensions` as empty; it is not. `uia_v2` alone is on 9,289 events. |
| 19 | Context-state change rate and block-length distribution | **[DONE-B]** | How badly does the naive segmenter over-segment? | Block-count per session; block-length histogram | 464 blocks in one 11-min session. **Quantifies the merge problem** and sets the sweep range for E2. |

---

# PART 7 — Ground-truth alignment

**Caveat: Dataset A is not on disk.** The following is designed against `DATA_SCHEMA.md` and must be validated the moment A is available. Every claim below is a *specification to verify*, not an observation.

### What the schema says exists

Two sources, which may disagree:

- **`gt.jsonl`** — a chronological annotation stream. Events: `run_config` (first line: `operator`, `operator_dept`, `machine_id`), `process_started` (`process_code`, `process_name`, `case_id`), `process_switched_out` (`from`, `to`), `process_suspended` (`from`, `to`, `split_id`), `process_resumed` (`process_code`, `split_id`, `phase`), `task_started` (`task_id`, `action`, `entity`), `clipboard_copy`/`clipboard_paste` (`content_preview`, `target_app`), `session_ended` (`total_tasks`, `duration_seconds`). Every line also carries `current_process` and `process_variant`. Timestamps are in **`ts_utc`**, not `timestamp_iso`.
- **`gt_manifest.json`** — a per-session summary: `processes[]` with `code`, `family_name`, `domain`, and `executions[]` each with `code`, `variant`, `case_id`, `start_ts`, `end_ts`, `apps[]`, `phase`, `seq`, `continues_from_prev`, `continues_to_next`; plus a top-level `expected_boundaries[]`.

### What a process execution *is*

The schema answers this more clearly than the survey could: **an execution is one entry in `gt_manifest.json → processes[].executions[]`**, identified by `(code, case_id, seq)`, spanning `start_ts` to `end_ts`, with a `variant`.

But three complications must be resolved before any metric is computed:

1. **`phase` and `split_id` imply an execution may occupy multiple intervals.** An execution with `phase=1` and `phase=2` entries is *one* business execution in *two* disjoint time spans. The manifest appears to list them as separate execution entries linked by `case_id`/`split_id`.
2. **`continues_from_prev` / `continues_to_next`** mark chunk-crossing, which is a *recording* artifact and must be dissolved — merge such entries before evaluating, or the evaluation punishes correct behaviour.
3. **The hierarchy is three-deep**: family (`code`) → execution (`case_id`, `seq`) → task (`task_id`). The assignment's `label` field maps to *family*, and `start`/`end` map to *execution*. Task-level records are a bonus signal for boundary sub-structure, not the target.

### Proposed internal representation

Two normalised tables, plus a derived one. Deliberately **additive**: nothing is deleted, every repair is recorded as a flag.

```
executions.parquet
  session_id, exec_uid, process_code, family_name, domain,
  case_id, variant, seq, phase, split_id,
  start_ts_utc, end_ts_utc, apps[],
  continues_from_prev, continues_to_next,
  source            ∈ {manifest, stream, both}
  repair_flags[]    ∈ {duplicate_start_collapsed, unpaired_switch_out,
                       manifest_stream_disagreement, chunk_merge_applied,
                       zero_duration, overlapping_sibling}
  confidence        ∈ {clean, repaired, disputed}

gt_events.parquet
  session_id, ts_utc, gt_event_type, process_code, case_id,
  variant, split_id, phase, task_id, action, entity,
  current_process, raw_line_no

executions_canonical.parquet     -- derived, for evaluation
  session_id, canonical_exec_id, process_code, variant,
  intervals[]     -- list of (start, end); length > 1 ⇒ interrupted
  n_fragments, total_duration_s, wall_span_s
```

`canonical_exec_id` groups fragments of one business execution (by `case_id` + `split_id`). **`intervals[]` is the representation the assignment's flat output schema cannot express** — which is exactly why we need it internally, and why Part 8 must define how a flat prediction is scored against it.

### Handling the known defects without silently fixing labels

The governing principle: **every repair is a recorded, reversible hypothesis, and every headline metric is reported on all three of the tiers below.**

| Defect | Detection | Policy | Recorded as |
|---|---|---|---|
| Consecutive duplicate `process_started` | same `process_code`+`case_id`, no intervening event | collapse to the first | `duplicate_start_collapsed` |
| `process_switched_out` with no matching start | switch-out whose `from` is not the open process | keep the record, do not synthesise a start | `unpaired_switch_out`, confidence `disputed` |
| `gt.jsonl` vs `gt_manifest.json` disagreement | interval mismatch beyond tolerance | **prefer the manifest** (it is the explicitly summarised artifact), record both | `manifest_stream_disagreement` |
| Chunk-crossing fragments | `continues_to_next`/`continues_from_prev` | merge into one interval | `chunk_merge_applied` |
| Zero- or negative-duration executions | `end_ts <= start_ts` | exclude from boundary scoring, keep in counts | `zero_duration` |
| Overlapping executions of the same family | interval intersection | keep both; this is genuine interleaving, not a defect | `overlapping_sibling` |

**Report every metric on three tiers:**
- **Tier 1 — clean only:** executions with no repair flags. The conservative number.
- **Tier 2 — clean + repaired:** the headline number.
- **Tier 3 — all, including disputed:** the pessimistic number.

If Tier 1 and Tier 3 diverge sharply, that divergence *is* a finding about the ground truth and belongs in the final report. This is the honest alternative to quietly cleaning labels until the score improves — and it directly addresses survey L16 (nobody studies ground-truth reliability in this field).

**One discipline to adopt now:** the repair rules must be written **before** any segmentation results are seen. Writing them afterwards, having watched which repairs help the score, is the exact failure mode the survey warns about.

---

# PART 8 — Evaluation design

The assignment says boundaries must be correct and the same process must get the same label. Those are two different measurements and must never be collapsed into one number.

### A. Boundary quality

Our output is a set of **labelled time intervals**; the reference is a set of labelled intervals, some of which are **discontinuous**. Neither text segmentation nor video action segmentation handles exactly this, so metrics must be chosen deliberately.

| Metric | Applicability here | Verdict |
|---|---|---|
| **Boundary F1 at tolerance τ** | Match predicted to reference boundary *points* within ±τ; report at τ ∈ {1 s, 2 s, 5 s} | **Primary.** Directly interpretable, tolerance is explicit, and it degrades gracefully. Report the whole τ-curve, never a single τ. |
| **WindowDiff** | Requires a linear sequence of atomic units; obtainable by binning the session into fixed time bins or using event index as the unit | **Secondary, and worth the effort.** It corrects Pk's asymmetric penalty and near-miss over-penalisation \[survey §4.4]. Use event index as the atomic unit — time bins distort when event rate varies. |
| **Pk** | Same input form | **Report only alongside WindowDiff**, and only to show the difference. Using Pk alone reproduces a known defect. |
| **Boundary similarity / boundary edit distance** (`segeval`) | Models near-misses as explicit edit operations | **Worth one experiment.** Its real value is that `segeval` also provides inter-coder agreement, which is how we could quantify the ground truth's own reliability. |
| **Segmental F1 @ IoU** | Matches predicted *intervals* to reference intervals above an overlap threshold — the closest convention to our output shape \[survey §4.4] | **Primary alongside boundary F1.** Report at IoU ∈ {0.25, 0.5}. This is the metric that penalises both over- and under-segmentation correctly. |
| **Count ratio** (predicted ÷ true executions) | Trivial | **Always report.** A single number that instantly reveals over- or under-segmentation, and the one most likely to be misleadingly hidden by F1. |

### B. Execution identity quality

Measured **independently of boundaries** by evaluating on ground-truth segments (experiment E3). Metrics: **ARI** (primary — chance-corrected, handles unequal cluster counts), **NMI** (secondary), plus **cluster count vs. true family count**. Homogeneity and completeness separately are worth reporting because they distinguish "merged two families" from "split one family".

### C. Process-family clustering quality on *inferred* segments

The composite measurement, and the one that corresponds to what the external evaluator will actually score. Since predicted and true segments do not align one-to-one, use a **matched-segment protocol**: (i) match predicted to true intervals at IoU ≥ 0.5; (ii) compute ARI over matched pairs only; (iii) report match rate separately. Reporting ARI without the match rate is meaningless — a method that finds three perfect segments and misses ninety would score 1.0.

### D. Variant quality

Deliberately **deprioritised**. Within a correctly identified family, measure ARI of predicted sub-clusters against `variant`. But given survey L13 (nobody can distinguish a genuine branch from operator habit), the honest position is to report variant *counts* and *examples* rather than variant accuracy, and to say so.

### E. Downstream stability

The metric that actually matters for Steps 2 and 3, and the one nobody in the literature reports. **Perturb the segmenter's parameters by ±20% and measure whether the automation-priority ranking changes.** If the top-3 ranked processes are stable under perturbation, the operational conclusions are robust to segmentation error; if they reshuffle, the ranking is an artifact and must be reported as such. This is cheap and is the strongest honesty signal available in the final report.

### The interruption problem: how to score a split execution

This is where standard metrics break, and it needs an explicit decision. Three scoring conventions, to be computed and reported side by side:

1. **Fragment-level (strict).** Each reference fragment is a separate target interval. A method that never stitches can still score well on boundaries; it will score poorly on identity because its fragments carry separate labels.
2. **Canonical-execution level (lenient).** Union the reference fragments into one canonical execution; credit a prediction if it covers the union. Rewards stitching, but a method that merges an interruption *and everything inside it* is over-credited.
3. **Stitch-aware (the informative one).** Score boundaries at fragment level, but *additionally* measure **interruption recall**: of reference executions with `n_fragments > 1`, what fraction did the method assign the *same label* to all fragments? This isolates M2 as its own measurable quantity.

**Recommendation: report (1) as the headline, (3) as the diagnostic, and state the convention explicitly.** Since the external scorer's convention is unknown \[survey L4], reporting under more than one convention is both honest and defensive — it means our number cannot be dismissed as convention-shopping.

**Practical note on `segments.jsonl`:** if a split execution must be emitted as two lines sharing a label, say so in the report and justify it. If instead it is emitted as one long interval swallowing the interruption, that is also defensible — but the two choices score very differently under conventions (1) and (2), so pick one, document it, and measure both.

---

# PART 9 — Transfer to Dataset B

The survey's validation asymmetry is the governing constraint: measurement is possible only where the content does not matter. Dataset A's process vocabulary must never appear in any artifact that touches B.

### What may legitimately transfer

| Layer | Transfers? | Justification |
|---|---|---|
| **Normalisation code** (Stage A) | **Yes, fully** | Schema-level, department-agnostic. |
| **Abstraction *procedure*** (Stage B) — "derive context state from app + title + URL route + element id" | **Yes** | It is a rule for *how* to build a vocabulary, not a vocabulary. |
| **Abstraction *vocabulary*** — the actual titles, routes, systems | **No. Never.** | This is the leakage channel. B's systems are different by construction. |
| **Boundary mechanism** (dwell rule, change-point detector, graph rule) | **Yes** | Structural. |
| **Absolute thresholds** tuned on A (e.g. "d = 5 events", "pen = 12") | **Risky** | The strongest transfer risk in the project \[survey L7]. |
| **Quantile-expressed thresholds** ("d = the 60th percentile of observed dwell length *in this dataset*") | **Yes** | Self-calibrating. **This is the single most important design discipline for transfer.** |
| **Clustering procedure and distance function** | **Yes** | Structural. |
| **Number of clusters `k`** from A | **No** | B has different departments and a different number of processes. Must be selected on B by an internal criterion (silhouette, stability under resampling). |
| **Evaluation harness** | **Yes** — but it produces no numbers on B | Useful for internal consistency checks only. |
| **LLM prompts** | **Only if process-agnostic** | A prompt listing A's process names is leakage dressed as engineering. |

### Six transfer mechanisms, and what each legitimately licenses

**1. Zero-shot representation transfer.** Apply A-validated *code* with self-calibrating parameters to B; discover B's vocabulary from B.
*Claimable:* "the mechanism was validated on A and applied unchanged to B." *Not claimable:* any accuracy figure on B.

**2. Unsupervised clustering on B.** Cluster B's inferred executions with `k` chosen by an internal criterion.
*Claimable:* internal cluster quality (silhouette), stability under resampling, and the qualitative coherence of clusters when inspected. *Not claimable:* correctness.

**3. Template discovery.** Extract recurring route/document templates from B itself and use them as anchors.
*Claimable:* "these patterns recur N times in B." Purely descriptive and fully defensible — this is the most honest mechanism available.

**4. Domain-adaptive thresholds.** Re-estimate every threshold from B's own distributions; carry over only the *rule* for estimating them.
*Claimable:* robustness. This is what makes mechanism 1 credible and should be treated as mandatory, not optional.

**5. Weak semantic matching.** Use language-level similarity (e.g. route name ↔ document name) to group B's executions without any A vocabulary.
*Claimable:* semantic coherence. **Risk:** it is easy to smuggle A knowledge in through hand-written keyword lists. Any keyword list must be derived from B or from generic business vocabulary, and its provenance stated.

**6. No-transfer discovery.** Run a fully independent discovery pass on B, using A only to validate that the *method class* works at all.
*Claimable:* the cleanest position, and the easiest to defend in the report. *Cost:* forgoes everything learned on A beyond method selection.

### Leakage checklist (to be enforced mechanically)

Practical safeguard: **the B pipeline should be runnable with the A artifacts absent from disk.** If it crashes without them, something leaked.

- [ ] No A process names, codes, or `family_name` strings appear in B-facing code, config, or prompts.
- [ ] No A-derived keyword or regex list is applied to B unless independently justified.
- [ ] Every numeric threshold used on B is either a constant justified on first principles or re-estimated from B.
- [ ] `k` for clustering on B is selected by an internal criterion, and the selection curve is reported.
- [ ] Any LLM prompt is shown in full in the report, so leakage is auditable.
- [ ] The report states which of the six mechanisms was used and what it therefore claims.

### What to say about B in the report

The defensible formulation: *"Our segmentation mechanism achieves X on Dataset A under metric M at tolerance τ. Dataset B is drawn from different departments and applications; we therefore make no accuracy claim on B. What we report for B is the mechanism's output, its internal consistency, and the stability of its conclusions under parameter perturbation."* Anything stronger is the failure mode the survey identifies as most likely to damage credibility \[survey C1].

---

# PART 10 — Automation opportunity layer

"Frequent" is not "automatable" — the field that defined this problem says so explicitly, and says automatability has no formal definition \[survey §4.7, L14].

### Opportunity record

One per discovered process family. The column that matters most is the last one.

| Dimension | Computable from our data? | How | Confidence |
|---|---|---|---|
| Frequency (executions per session / per hour) | **Yes** | Count from `segments.jsonl` | High, conditional on segmentation |
| Cumulative effort share | **Yes** | Σ duration ÷ Σ session duration | **Relative only** — waiting time is compressed by design |
| Number of people | **Partly** | Distinct `machine_id` / `username_hash` touching the family. B has 4 machines | Medium — assumes one machine ≈ one person |
| Application count | **Yes** | Distinct apps per execution | High |
| Cross-application transitions | **Yes** | Count app/system changes within an execution. Note: in B most switches are within-browser | High |
| Repetition / stereotypy | **Yes** | Mean pairwise sequence similarity of executions within a family | High — and a *direct* automatability proxy |
| Variability | **Yes** | Number of sub-clusters; entropy of route sequences | Medium \[L13] |
| Exception rate | **Partly** | Executions deviating from the dominant variant; `browser_error` events (38 in B) | Low |
| Human decision points | **Weakly** | Free-text form fields (e.g. `#pi-note`, a textarea with a "enter comment" placeholder) are strong evidence of human judgement | Medium — **and this is the most valuable feasibility signal available** |
| Data availability / determinism | **Partly** | Fraction of inputs traceable to a prior copy or a visible field vs. typed *de novo* — `dataflow_v2` is exactly this signal if it means what we hope | Medium, pending E0 |
| Integration feasibility | **No** | Requires knowing whether the target systems expose APIs | **External assumption — must be declared** |
| Compliance / privacy sensitivity | **Partly** | Personal-data routes (`#/payroll-items`, `#/social-insurance`, `#/resident-tax`) are self-evidently sensitive | Medium |
| Prototype feasibility | **No** | Depends on what we can actually stand up in the remaining days | Engineering judgement |
| **ROI in currency** | **No** | Needs volumes, wage rates, error costs — none present | **Do not compute. Declare as unavailable.** |

### Structure to borrow (not code)

Gomez & Castillo's four-module shape \[survey §4.7] is directly reusable *as a structure*: taxonomy → multi-criteria suitability index → tool-tier selection → ROI. Two things to copy deliberately:

1. **The explicit gate.** They use a suitability threshold to stop low-scoring processes progressing. An explicit gate is more defensible than a ranked list with no cut-off.
2. **The disclaimer.** Their authors state the instrument is not empirically calibrated. Saying the same thing about our weights is not weakness; it is the difference between a scorecard and a fabricated number.

Wanner et al. supply criteria beyond frequency. Neither offers usable code.

### Recommended form of the artifact

A table with **three explicitly separated column groups**, so a reader can see instantly which numbers are evidence and which are assumption:

- **Measured** — computed from `segments.jsonl` and the raw log, with the metric definition attached.
- **Derived** — computed with a stated modelling assumption (e.g. "one machine = one person").
- **Assumed** — imported from outside the data, each with an owner and a sensitivity note.

Plus a **sensitivity analysis**: vary the weights by ±20% (and vary the segmentation parameters, per Part 8E) and report whether the top-3 ranking is stable. A ranking that survives perturbation is a finding; one that does not must be reported as unstable.

---

# PART 11 — What to build first

Not a seven-day plan — a dependency-ordered sequence of decision-enabling artifacts. Effort is one engineer's focused hours.

### Milestone 0 — The reconnaissance notebook and the `extensions` dump
**Artifact.** A single notebook producing: (a) the Dataset-B statistics in §0, re-run reproducibly; (b) **a full schema dump of `extensions.uia_v2`, `dataflow_v2`, `cross_layer_v1`, `field_identity_v1` with 10 samples each**; (c) the same statistics for Dataset A once it lands.
**Why it matters.** `DATA_SCHEMA.md` documents `extensions` as empty. It is not — `uia_v2` is on 9,289 events and `dataflow_v2` on 1,759. If `dataflow_v2` is copy→paste provenance, **Family D becomes the backbone of the whole solution and several other families become unnecessary.** No other hour of work has this variance in outcome.
**Dependencies.** None for B. **Dataset A must be obtained** — this is the critical-path blocker.
**Effort.** 2–3 h. **Success.** We can state in one sentence what each namespace contains and whether it links events. **Decision enabled.** Whether Family D is in or out — which changes the entire architecture.

### Milestone 1 — Normalisation layer + ground-truth loader + evaluation harness
**Artifact.** `normalise.py` (chunks → one event table per session), `gt_loader.py` (producing the three tables in Part 7 with repair flags), `evaluate.py` (boundary F1 at τ, segmental F1@IoU, WindowDiff via `segeval`, count ratio, ARI/NMI, tier-1/2/3 reporting).
**Why it matters.** Every subsequent experiment is a thin script on top of this. **Building the evaluator before the first model is the highest-leverage ordering decision in the project** — it makes every later result comparable and prevents the "four papers, four metrics" problem \[survey L4] from happening inside our own repo.
**Dependencies.** M0; Dataset A on disk.
**Effort.** 6–8 h. **Success.** A random segmenter and a single-segment-per-session segmenter both score, producing sane floor/ceiling numbers. **Decision enabled.** All of them.

### Milestone 2 — The first end-to-end baseline (Family A at one setting)
**Artifact.** `segments.jsonl` for Dataset A from a dwell-block segmenter, with a scorecard.
**Why it matters.** Produces the first real number and makes the problem concrete. It is also the baseline everything else must beat.
**Dependencies.** M1.
**Effort.** 3–4 h. **Success.** It runs end to end and scores; the number itself does not matter yet. **Decision enabled.** Whether the harness is trustworthy.

### Milestone 3 — The experiment that can invalidate the baseline (E1 + E2 sweep + E3)
**Artifact.** Three plots: boundary-F1 vs. dwell threshold; count ratio vs. threshold; identity ARI on ground-truth segments. Plus the E1 gap-baseline floor.
**Why it matters.** **This is where the architecture is actually decided.** E2 tells us whether context state can produce boundaries at all. E3 tells us — independently of any segmentation — whether identity is learnable. A low E3 ARI is the most important early warning available: it means no segmentation improvement will produce usable labels.
**Dependencies.** M2.
**Effort.** 6 h. **Success.** Either a dwell threshold with count ratio ∈ [0.7, 1.4] and F1 > 0.6, or a clear demonstration that none exists. **Both outcomes are wins.** **Decision enabled.** Family A in or out; whether Family B/D are necessary.

### Milestone 4 — The first useful process-discovery result on A
**Artifact.** A table of discovered families on Dataset A: count, mean duration, apps, example route sequences — next to the true families.
**Why it matters.** First evidence that the pipeline produces something a human would recognise as business work. It is also the first artifact suitable for the final report.
**Dependencies.** M3 plus whichever of E0/E5/E6 survived.
**Effort.** 4 h. **Success.** A reader who knows the domain would accept most of the discovered families as real.
**Decision enabled.** Whether to invest in Family E (hybrid) or freeze the mechanism and move to B.

### Milestone 5 — The first Dataset-B result
**Artifact.** `segments.jsonl` for Dataset B — **the actual required deliverable** — plus the operational analysis (frequency, effort share, machines, variants) and a leakage-checklist sign-off.
**Why it matters.** This is what gets submitted. Producing it *early and badly* is far better than producing it late and well, because it converts every remaining hour into refinement of a shippable artifact rather than a race to first output.
**Dependencies.** M4; the leakage checklist from Part 9.
**Effort.** 4 h (mechanism is unchanged; the work is re-estimating thresholds on B and selecting `k`).
**Success.** A schema-valid `segments.jsonl` — exact `session_id` directory names, ISO-8601 UTC with `Z`, one JSON object per line — and a stability check under ±20% parameter perturbation.
**Decision enabled.** Everything downstream is now refinement, not risk.

### Milestone 6 — Automation opportunity artifact
**Artifact.** The opportunity table from Part 10 with its three column groups, the explicit gate, the assumption ledger, and the ranking-stability result.
**Why it matters.** This is Step 2's deliverable and the input to Step 3's scope decision. The assumption ledger is what separates a credible proposal from an optimistic one — which the brief says explicitly it is scoring.
**Dependencies.** M5. **Effort.** 4 h.
**Success.** Every number traces to either a measurement, a stated derivation, or a declared assumption. **Decision enabled.** Which process the prototype targets.

### Milestone 7 — The smallest credible prototype
**Artifact.** Deliberately left open until M6, but the constraint is known now and should shape expectations: **the target systems (localhost SPAs on ports 5132–5134) are not available to us.** Three honest options:
- **(a)** A tool that consumes logs and produces an artifact a human would otherwise make by hand — e.g. generating the procedure document or the checklist we can see being edited in Word (`nyusha_checklist_shinsotsu_batch`, `keiyaku_kaijo_tetsuzuki`). This needs no target system and is fully demonstrable.
- **(b)** A mock target: rebuild a minimal stand-in for one route and drive it with Playwright. Honest if labelled as a mock; expensive.
- **(c)** A detector/assistant rather than an actuator: something that watches a log and flags the repetitive step. Weakest as a demonstration.
**Why it matters.** The brief asks for something that *works*. Defining what "works" means when the target is unreachable is itself part of the answer, and should be argued explicitly rather than finessed.
**Effort.** 8–12 h. **Decision enabled.** None — this is the terminal deliverable.

**Critical path.** M0 (blocked on obtaining Dataset A) → M1 → M2 → M3 → M4 → M5 → M6 → M7. The only parallelisable work is E3 (identity on ground-truth segments), which needs M1 but not M2, and Stage F naming, which can be done any time after M4.

---

# PART 12 — Decision matrix

| Approach | Data requirements | Existing code reuse | Impl. effort | Interleaving | Interruptions | Sparse semantics | Dataset-B shift | Explainability | Eval difficulty | Prototype compat. | Major risk | **Information gained by testing** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A · Dwell blocks** | titles/routes informative | pandas only | **Low** (0.5 d) | partial | partial (excursion merge) | **fails without titles** | **good** (quantile thresholds) | **Highest** | Low | High | Over-segmentation; collapses if A's titles are generic | **High** — cheap, and its failure mode is diagnostic |
| **B · Change-point** | numeric featurisation | `ruptures` | Low-Med (0.5–1 d) | ✘ | ✘ | **robust** | **poor** (penalty transfer) | Moderate | Low | Medium | Narrow penalty plateau ⇒ untransferable | **High** — the penalty-curve shape decides transferability in one plot |
| **C · Motif / sequence** | stable repeated patterns | `stumpy`, `prefixspan` | Med-High (1.5 d) | ✘ | ✘ | robust | medium | Good | Medium | Medium | The documented failure mode under interleaving \[L2]; coverage gaps | **Medium** — one coverage number settles it cheaply |
| **D · Provenance graph** | link fields meaningful | `networkx` | **Low** (0.5 d) | **✔** | **✔ natively** | **independent** | **best** | **Excellent** | Low | High | The fields may not mean what we hope; 8.6% coverage | **Highest variance** — could be the backbone or dead in one hour |
| **E · Hybrid A+D+cluster** | both above | pandas, networkx, sklearn | High (2 d) | ✔ | ✔ | partial | good | Good | Medium | High | Complexity; wasted days if D is dead | **Low until A and D are measured** |
| **F · LLM over summaries** | informative text | LLM API | Med (1 d) | partial | partial | **is the semantics** | medium | Moderate, non-deterministic | Medium | Medium | Label drift across sessions; prompt leakage from A; hides a weak segmenter | **Medium** — E4 isolates it from segmentation for ~3 h |

### 1. Worth experimentally testing (in this order)

1. **Family D — provenance graph.** Highest information-per-hour in the entire project. One hour of field inspection (E0) either hands us native interruption handling and near-parameter-free transfer, or removes an entire branch. Nothing else has this payoff profile.
2. **Family A — dwell blocks.** The natural baseline given that titles and routes are richly informative. Cheap, maximally explainable, and its failure signature (count ratio) is directly diagnostic.
3. **Family B — change-point detection**, *but tested for the shape of its penalty curve rather than its peak score*. It is the only family robust to uninformative window titles, which is the main way Dataset A could differ from B. Treat it as insurance.

Families **E** and **F** are conditionally interesting: E only if D survives E0 and A survives E2; F only via E4, evaluated on ground-truth segments so that it cannot hide behind a segmenter.

### 2. Reject immediately

- **OCR and vision-language screenshot labelling.** The most attractive-looking option in the space and the least justified: it answers a question already answered by `window_title` at 99.4% coverage and 57 distinct values, at far higher cost, with documented hallucination failure modes.
- **ScreenRPA** — CC BY-NC licence is disqualifying for client-facing work.
- **OpenAdapt, SmartRPA** — both solve the inverse problem (replay a known task) and neither can ingest our log format.
- **TimeSeriesInRPM / the Rebmann GitLab code as dependencies** — read them, do not integrate them. The latter's documented inability to handle interleaving targets our central condition.
- **Japanese morphological analysis and OCR pipelines** — a ~30-term glossary beats a tokeniser over a 57-value vocabulary.
- **Any time-gap-threshold segmenter as a serious candidate** — measured dead on Dataset B (one gap > 30 s in 20,477 events). Keep E1 only as a documented baseline floor.
- **PM4Py as a segmentation or discovery tool.** It is excellent and it is a Stage-G tool. Reaching for it earlier is a category error.

### 3. Definitely reuse

`pandas` · `segeval` (boundary scoring — highest value-per-hour reuse available) · `ruptures` · `scikit-learn` (clustering + ARI/NMI) · `rapidfuzz` (sequence distance) · `networkx` (Family D) · **PM4Py at Stage G only**, for process maps over labelled segments.

### 4. Definitely do not build from scratch

Change-point detection, edit distance, clustering algorithms, segmentation metrics (Pk/WindowDiff/boundary similarity), cluster-comparison metrics (ARI/NMI), graph connectivity, process-map rendering.

### 5. The first concrete artifact

**The reconnaissance notebook of Milestone 0, and specifically the `extensions.*` schema dump.**

The justification is the whole of this analysis in one line: `DATA_SCHEMA.md` documents `extensions` as an empty object, and it is not — `uia_v2` is populated on 9,289 events and `dataflow_v2` on 1,759. If `dataflow_v2` encodes copy→paste provenance, Family D delivers native interruption handling, parameter-free transfer to Dataset B and an explanation a client would accept ("the system itself recorded that this paste came from that copy"). If it does not, we have removed a branch and lost an hour.

**And the blocking action that gates everything after M0: get `dataset_a` onto disk.** Without ground truth there is no evaluation harness, no experiment matrix, and no defensible number — only Dataset B descriptive statistics.

---

## Appendix — Open questions this analysis could not close

1. **Does Dataset A look anything like Dataset B?** Everything measured here is from B. If A's window titles are generic (`Microsoft Excel`, `Chrome`) rather than semantic, Family A collapses and Family B becomes primary. This is the largest unknown.
2. **What do the `extensions` namespaces actually contain?** Population rates are known; semantics are not.
3. **Is the interleaving rate high or low in A?** Determines whether M2 is the project or a footnote.
4. **Do shared actions occur across process families in A?** Tests survey L1 directly on our data.
5. **What granularity does A's ground truth treat as one execution** — and how many fragments per canonical execution?
6. **Are there form-input values or `field_identity_v1` records containing per-case identifiers?** The last remaining surrogate-case-ID candidate after clipboard was ruled out.
7. **Is the scorer's boundary tolerance closer to 1 s or 30 s?** Unknowable, which is why Part 8 reports τ-curves rather than single numbers.
