# Literature, Open-Source and Industry Survey — v2
## Inferring business processes from raw desktop operation logs, and moving from there to an automation proposal

**Prepared:** 2026-09-10 · **Revision:** v2 (second research pass)
**Status:** Fact-finding survey only. No approach, architecture, automation target, or project plan is recommended here.

**Verification key used throughout:**
✅ full text or substantial content retrieved and read during this survey
◐ abstract or landing page retrieved only
○ existence, title and venue confirmed via indexed search results; contents not retrieved

### What changed in v2

The first pass left six areas open. All six were worked; four changed the conclusions materially.

| Gap in v1 | Status in v2 | Did it change a conclusion? |
|---|---|---|
| Leno et al. ICPM 2020 read only as an abstract | **Full text read.** Method, datasets, metrics and — critically — the authors' own stated failure modes now documented | **Yes, substantially.** See §3.2(d) and §8 |
| No coverage of segmentation *evaluation metrics* | **Filled.** The text-segmentation metric family (Pk, WindowDiff, boundary edit distance) and the video action-segmentation convention (segmental F1@IoU) are now surveyed | **Yes.** The "unknown boundary tolerance" ambiguity has a well-developed metric literature behind it |
| Family C (action segmentation, HAR, change-point) barely covered | **Filled.** §4.3 expanded | Partly — supplies method families, not new constraints |
| Japanese-language academic record | **Partly filled.** One Fujitsu IEICE report found; a 2026 Japanese GenAI operation-log product found. English-indexed search remains a real limitation | Yes for the industry picture |
| Vendors I declined to characterise (ABBYY, Automation Anywhere, Nintex/Kryon, SAP Signavio) | **Filled** from official docs and vendor pages; UiPath's privacy documentation read in detail | **Yes.** The vendor picture is more differentiated than v1 suggested |
| Multimodal / screenshot semantics thin | **Filled, and this is the biggest new finding.** A 2026 *BISE* paper evaluates vision-language models labelling activities from UI screenshots | **Yes.** The sparse-screenshot question now has direct evidence |

---

## 1. Executive answer

**Is this exact problem an established benchmark or challenge?**

No. Two passes of searching found no public benchmark, shared task, competition, or released dataset matching the assignment: unlabeled multi-application desktop operation logs, a ground-truth-bearing calibration set, a separate no-ground-truth production set drawn from *different departments and applications*, a required `segments.jsonl` boundary-plus-label output, and a downstream obligation to produce an automation proposal with a working prototype. The literal title returns nothing. The established competitions — the [BPI Challenges](https://www.tf-pm.org/competitions-awards/bpi-challenge) and the [Process Discovery Contest](https://www.tf-pm.org/competitions-awards/discovery-contest) — run on structured logs that already carry case identifiers and activity labels, the exact opposite premise.

Stated as inference rather than finding: this is a purpose-built assignment over a synthetically generated or scripted-recording dataset. The ground-truth defects the brief describes are characteristic of a generator, and the specification attributes them to "how it is generated."

**Which existing fields collectively cover its components?**

Seven, and they are essentially never combined in one piece of work:

1. **Robotic Process Mining (RPM) / task mining** — the closest single field; defines this pipeline and names segmentation as its hardest open problem.
2. **Process mining: event abstraction and case-ID/correlation discovery** — the formal vocabulary for "low-level events to high-level activities" and for "no case identifier."
3. **Desktop activity recognition and task-switch detection (HCI, ~2006–2010)** — the only lineage evaluated on genuinely real, long-horizon, interruption-rich office desktop traces.
4. **Linear segmentation evaluation (text/topic segmentation; temporal action segmentation)** — supplies the metric machinery for scoring boundaries with near-miss tolerance. *New in v2, and directly relevant to the brief's unstated scoring rule.*
5. **Trace clustering and process-variant discovery** — the "same process, different execution" machinery, assuming segmented traces.
6. **Multimodal UI understanding (VLMs on screenshots)** — *new in v2*; the emerging semantic channel for UI logs.
7. **RPA candidate selection and automation opportunity assessment** — ROI, feasibility and prioritisation frames; largely qualitative and, where quantitative, largely uncalibrated.

**Which is it most like?**

A **task-mining / robotic-process-mining problem wearing an activity-recognition hat, scored like a linear segmentation task, and ending in an RPA-candidate-selection deliverable.** Steps 1 and 2 map almost point-for-point onto stages 2–5 of the Leno et al. RPM pipeline; the output format and its stated scoring criteria map onto the text-segmentation metric tradition; Step 3 maps onto pipeline stage 6 plus the candidate-selection literature.

**Maturity assessment (revised in v2):**

| Component | Maturity |
|---|---|
| Process discovery from *structured* logs with case IDs | Mature |
| Trace clustering / variant discovery on segmented traces | Mature |
| **Evaluation metrics for linear segmentation with boundary tolerance** | **Mature — in NLP and vision, not yet imported into task mining.** Pk, WindowDiff, boundary edit distance, segmental F1@IoU are all well-established |
| Event abstraction as a formalised sub-problem | Established, with a taxonomy; unsolved in general |
| Case-ID / correlation discovery for unlabeled logs | Established niche; structured logs only |
| Segmentation of unsegmented, noisy, **interleaved** UI logs | **Actively researched and explicitly unsolved.** Now confirmed twice over: a 2021 review found no method handling actions shared across concurrent routines, and the flagship 2020 method's own paper reports failure under frequent application switching |
| Consistent labelling without a label vocabulary | Underdeveloped; a handful of unsupervised papers on synthetic streams |
| Interrupted / suspended / resumed work | **A named and confirmed gap** |
| Cross-department transfer under real distribution shift | **Effectively absent from the research record** |
| **Semantic labelling from screenshots via VLMs** | **Newly demonstrated (2026), with modest but real accuracy — and evaluated on 100 screenshots** |
| Automation opportunity ranking with feasibility and risk | Mature as management literature; the quantitative frameworks are self-described as uncalibrated |

**Two structural observations.**

*First,* the academic record and the commercial record disagree, but v2 shows the disagreement is not uniform. The vendors split into three groups: those whose documentation admits human task definition (**Celonis**, **UiPath**); those whose documentation claims automatic pathway discovery in specific technical terms (**Automation Anywhere**, **Nintex/Kryon** — the latter naming computer vision as its data source); and those whose claims are pure marketing (**Mimica**, **Skan**). Only the first group's claims are checkable against their own docs, and that group's claims are the weakest.

*Second,* and new in v2: the single most-cited method for this exact task — Leno et al.'s ICPM 2020 routine discovery from unsegmented UI logs — **states in its own limitations section that it is designed for consecutive routine executions, struggles with overlaps, requires that routines not share UI actions except at starts, and performed poorly on the one real log where the user switched between applications frequently.** Those three conditions are the defining characteristics of the data in this assignment. That is the most useful single fact this survey produced.

---

## 2. Problem-to-literature map

| Project subproblem | Closest research field(s) | Common terminology | Typical input assumptions | Typical outputs | Key mismatch with this project |
|---|---|---|---|---|---|
| **Low-level log interpretation** | Event abstraction; task mining | "event abstraction", "log abstraction", "granularity gap", "UI log" | A log parsed into typed events; often one application; often attribute-rich | Higher-level activity labels; abstracted log | Multi-app OS telemetry with no activity concept; ~96% of events carry no screen text |
| **Boundary detection** | RPM segmentation; task-switch detection; change-point detection; temporal action segmentation | "segmentation", "task boundary", "routine boundary", "sessionization", "change point", "action segmentation" | Pre-segmented traces, or one user / one app / non-interleaved work | Segment indices or boundary points | Boundaries must cross recording chunks, survive interruptions, and be scored against hidden ground truth at unknown tolerance |
| **Boundary *scoring*** | Text/topic segmentation; video action segmentation | "Pk", "WindowDiff", "boundary edit distance", "segmental F1@IoU", "edit score" | A reference segmentation and a hypothesis segmentation over the same linear span | A tolerance-aware error score | **These metrics exist and are standard elsewhere but are not used in task mining**, which uses ad-hoc conventions instead |
| **Task/process labeling** | Unsupervised task recognition; trace clustering; semantic process mining | "task type identification", "task categorization", "activity naming" | A known label set, or clustering scored against known types | Cluster IDs; sometimes tf-idf names | No label vocabulary for Dataset B; labels must be invented, kept consistent across sessions, and be meaningful to management |
| **Repeated-work clustering** | Trace clustering; sequential pattern mining; motif discovery | "trace clustering", "routine identification", "motif discovery", "matrix profile" | Segmented traces with comparable alphabets | Clusters / frequent routines | The alphabet must first be built from raw events; A's alphabet does not transfer to B |
| **Process variants** | Variant discovery; concept drift; variability drivers | "variant", "process family", "deviation", "drift" | Segmented, labeled traces | Variant models / clusters / drift points | Must separate a genuine branch from habit, retry, or error, with no case attributes to condition on |
| **Interrupted / resumed work** | Task-switch detection; RPM segmentation with interleaving | "task switching", "interleaved routines", "suspension/resumption" | Usually excluded by assumption | Switch points | Confirmed open gap; and the required output schema cannot express a split execution |
| **Case-ID absence** | Correlation mining; case-notion discovery | "unlabeled event log", "case ID deduction", "event correlation" | Structured logs with correlation attributes | Inferred case assignment | Desktop telemetry has almost no correlation attributes; nearest equivalents are window titles, URLs, clipboard values, sparse screen text |
| **Sparse screenshot/text interpretation** | Screenshot-based task mining; vision-language UI understanding | "screen text", "OCR", "UI hierarchy", "activity labeling", "VLM" | Dense screenshots (VLM work) or no text at all (event-only work) | Element/region labels; activity descriptions | ~4% screen text plus selective screenshots sits between the two regimes; the 2026 VLM work assumes a screenshot per event |
| **Cross-application transfer** | Domain adaptation; generalization estimation | "generalization", "cross-domain", "distribution shift" | Same-domain splits are the norm | Held-out same-domain accuracy | Calibration on A and delivery on B is a deliberate shift almost never evaluated |
| **Automation-candidate prioritisation** | RPA candidate selection | "automatability", "RPA suitability", "candidate ranking", "ROI", "suitability index" | Interviews, workshops, documentation; occasionally mined frequency/duration | Weighted scorecards, ranked shortlists | Everything must come from log evidence, with compressed waiting times and a 15-session sample |
| **Automation prototype credibility** | RPA script synthesis from UI logs; data-transformation discovery | "executable routine discovery", "software robot synthesis", "deterministic routine" | A recorder capturing element selectors; an actuatable target | RPA scripts | Target systems unreachable; "it works" needs a different, defensible definition |

---

## 3. Exact-match and near-match search

### 3.1 Exact matches — none found

Queries across two passes: the literal assignment title; "operation logs automation proposal"; `dataset_a`/`dataset_b`/`segments.jsonl` with process segmentation; task-mining benchmark queries; both process-mining competition registries; Japanese-language equivalents. No paper, dataset, benchmark, repository, competition, or published intern task matched.

Consequence: no reference solution, no published accuracy figure to target, and no established metric for this output format. The brief's refusal to define "good enough" has no external answer either.

### 3.2 Strong near matches

#### (a) Leno, Polyvyanyy, Dumas, La Rosa & Maggi (2021) — "Robotic Process Mining: Vision and Challenges"
*BISE* 63(3):301–314 · https://doi.org/10.1007/s12599-020-00641-4 · [PDF](https://link.springer.com/content/pdf/10.1007/s12599-020-00641-4.pdf) ✅

The closest published framing of the assignment as a whole. Six-stage pipeline: recording → noise filtering → **segmentation** → simplification → **candidate routine identification** → executable routine discovery and compilation. Verified statements: UI logs "do not come with a notion of case identifier"; time-based segmentation heuristics are unreliable because users are involved in different activities while performing a task; noise filtering is complicated by legitimate behavioural variation between workers; automatability assessment lacks a formal definition and there is "no guarantee" a frequent task is automatable; identifying non-deterministic actions (where a human supplies external input) is unsolved, as are data-transformation discovery and OCR-based element recognition for dynamically generated applications.

*Differs:* a vision paper, not a method or evaluation. No cross-department transfer, no operational-analysis step, and it assumes a purpose-built recorder capturing UI element identifiers.

#### (b) Leno, Augusto, Dumas, La Rosa, Maggi & Polyvyanyy (2020) — "Identifying Candidate Routines for RPA from Unsegmented UI Logs"
ICPM 2020 · [arXiv:2008.05782](https://arxiv.org/abs/2008.05782) · [full PDF](https://arxiv.org/pdf/2008.05782v1) · [IEEE](https://ieeexplore.ieee.org/document/9229975/) ✅ **(upgraded from ◐ in v1 — this is the v2 finding that matters most)**

**Method, now verified in detail.** A user interaction is modelled as (timestamp, type, parameter set, parameter values, mapping function). The log is *normalised* to retain only **context** parameters — attributes describing *where* an action occurs (application, element location) — discarding data values. From the normalised log they build a **Control-Flow Graph** of direct-follows relations, then find **back-edges via strongly-connected-component analysis**: back-edge targets become segment starts and back-edge sources become segment ends. Segments are then extracted by a sequential scan that opens at a start marker and closes at a matching end marker. Candidate routines are then mined from the segments with **CloFast** (closed sequential pattern mining allowing gaps), followed by an optimisation layer that removes overlapping patterns by iteratively selecting high-quality patterns and eliminating their occurrences.

**Noise model.** Noise is defined as "events within or between routine instances that do not belong to any routine." Events falling between segments — unmatched to start/end markers — are **discarded**. Preprocessing removes redundant interactions overwritten by successive ones.

**Data.** Synthetic: nine Coloured Petri Net logs CPN1–CPN9, 100–2,000 segments, 1,400–28,358 actions. Supervised real-life: Student Records (50 segments, 1,539 actions) and Reimbursement (50 segments, 3,114 actions). Unsupervised real-life: Scholarship logs S1 and S2, plus combined variants (SRRT+, RTSR+, SRRTk, RTSRk).

**Metrics and results.** Segmentation scored by **normalised Levenshtein edit distance**: 0.0 average on synthetic logs, 0.059–0.331 on real-life logs. Routine quality scored by **Jaccard coefficient** against ground truth, ≥0.90 for most logs with coverage >0.90. Runtimes 0.461–3.649 seconds.

**Stated limitations — read these against the brief's description of its own data.** The authors report that the approach: depends on data quality and routine frequency; is sensitive to routines having multiple distinct start interactions unless batched; discovers spurious extra variants when the same interactions occur in different orders; **is designed for consecutive routine executions and struggles with overlaps**; **performs poorly when users switch between applications frequently — demonstrated by the failure on the S2 log**; and **requires that routines not share UI actions except at their starts**.

*What overlaps:* the closest published attempt at Step 1 joined to the first half of Step 2, with a real evaluation and a real metric.
*What differs:* the output is a set of candidate routines rather than a labelled segmentation of the entire timeline; and the three conditions under which the method is reported to fail — interleaving, frequent application switching, and shared actions — are exactly the conditions the assignment brief describes as characteristic of its data.

#### (c) Rebmann & van der Aa (2023) — "Unsupervised Task Recognition from User Interaction Streams"
CAiSE 2023 · https://doi.org/10.1007/978-3-031-34560-9_9 · [author PDF](https://hanvanderaa.com/wp-content/uploads/2023/03/CAISE2023-Unsupervised-task-recognition-from-user-interaction-streams.pdf) · [code](https://gitlab.uni-mannheim.de/processanalytics/task-recognition-from-event-stream) ✅

The closest *method* paper to Step 1, and the only one solving both halves — segmentation and consistent typing — unsupervised and without a predefined number of task types. Chunking on completion keywords (e.g. "save", "submit", from IBM design guidelines), plus contextual relatedness via co-occurrence matrices, data-value overlap detection, and overhead-activity filtering; then DenStream density-based online clustering over features encoding event-class frequency and complexity, with tf-idf terms giving human-readable explanations. Evaluation reports boundary quality (task count, normalised edit distance) *and* clustering quality (macro/micro Rand, Jaccard) separately — the same two-part structure as the brief's "boundaries correct AND same label for same process."

Results: SE1 198/200 tasks at 0.04 edit distance, 0.95 Rand; SE2 231/240 at 0.06, 0.95; SE3 138/120 at 0.23, 0.88. Memory under 1% of stored event volume; response times 2–150 ms.

*Differs, and it matters:* three *synthetic* streams built by shuffling existing task logs — 560 tasks, 16,554 events, 8 task types. Authors' own limitations: the data lacks realistic mixed process/overhead sequences; **timestamps are not used for segmentation**; no business-object or case correlation; and the method **assumes sequential task execution and cannot handle interleaved tasks**.

#### (d) Urabe, Yagi, Tsuchikawa & Oishi (2021) — "Task Clustering Method Using User Interaction Logs to Plan RPA Introduction"
BPM 2021 · https://doi.org/10.1007/978-3-030-85469-0_18 ✅

The near match most resembling Steps 1 and 2 together, from a Japanese industrial group. Three stages: segmentation by detecting shifts in operation co-occurrence, explicitly borrowing the analogy from **topic segmentation in natural language** ("the types of operations change as the task changes"); feature creation where an operation ID is built from **application name, window title and GUI component information** — precisely the fields this assignment exposes; and agglomerative hierarchical clustering on cosine similarity over operation types. Purpose is explicitly to plan RPA introduction, and it reports task types *and workload distributions* — Step 2's deliverable.

*Differs:* Dataset 1 is **one employee over two days**: 3,422 operations, five business tasks (travel requests, purchase requests, approvals, meeting scheduling), F = 0.84. Dataset 2 is 7,180 simulated operations over three repeated tasks, F = 0.93. Reported failure mode: segmentation degrades when per-task operation counts vary significantly; parameters need per-setting tuning. No cross-department transfer, no screenshots, no interruption handling.

#### (e) Rodríguez-Ruíz et al. (2026) — "Enriching Process-Related UI Logs Via Screenshot-Based Activity Labeling by Using Vision-Language Models"
*BISE* 68:1097–1120 · https://doi.org/10.1007/s12599-026-00990-6 ✅ **(new in v2)**

The first work I found that directly attacks the semantic-labelling problem this assignment poses, using screenshots. Motivating setting: environments where "structured information about the UI is not accessible" — virtualised desktops, business process outsourcing — so the log's only semantic channel is the pixels.

Data: 100 desktop application screenshots with manual semantic annotations; for activity-level evaluation, 30 randomly selected images representing complete activities yielding 90 events with ground-truth descriptions, split into three groups by activity complexity (2–4 events per activity). Models: VLMs InternVL2.5, Qwen2.5VL, NVILA, UI-TARS; LLMs GPT-4, Mistral-Large, Qwen2.5-72B, Llama-3.1-405B. Metric: cosine similarity between generated and ground-truth descriptions using the all-mpnet-base-v2 sentence transformer, plus inference time.

Results: InternVL2.5 achieved the highest average similarity across component types; a "Component Parent Crop" input with "Highlight" prompting performed best; at the **activity** level the best models reached **0.75+ similarity**, robust across component densities. Stated limitations: hallucination in generalist models, formatting inconsistency, and prompt-engineering effectiveness varying across model architectures.

*Overlap:* demonstrates that activity-level semantics can be recovered from screen images without UI metadata, which is the condition this assignment's sparse-text log approximates.
*Differs:* it assumes a screenshot is available for the event being labelled, and evaluates on 100 screenshots in a single process context. It labels *given* events and activities; it does not find boundaries, does not cluster repeated executions, and does not address a Japanese-language UI.

### 3.3 Partial matches — one major component overlaps

**Segmentation, surveyed.** ✅ Agostinelli, Marrella & Mecella (2021), "Exploring the Challenge of Automated Segmentation in RPA," RCIS 2021 — https://doi.org/10.1007/978-3-030-75018-3_3 · [PDF](https://www.diag.uniroma1.it/marrella/papers/RCIS_2021_Segmentation.pdf). A structured review classifying segmentation difficulty into three cases (single routine repeated; multiple routines without shared actions; multiple routines *with* shared actions) and mapping the literature onto them. Verified quotes: only a few works "have demonstrated the full or partial ability to untangle unsegmented UI logs consisting of many interleaved routine executions," and **"we did not find any literature work able to properly deal with user actions potentially shared by many routine executions."** Recommends shifting from model-based to learning-based approaches.

**Segmentation with a human in the loop.** ✅ Agostinelli, Leotta & Marrella (2021), "Interactive Segmentation of User Interface Logs," ICSOC 2021 — https://doi.org/10.1007/978-3-030-91431-8_5. Frequent-pattern identification derives candidate routines; a domain expert rejects segments real routines do not allow; trace alignment clusters actions into segments. Follow-on: "A Human-in-the-Loop Approach to Support the Segments Compliance Analysis" — https://doi.org/10.1007/978-3-031-16168-1_13.

**Segmentation via signal processing.** ✅ Hohenadl, "Time Series-Based Segmentation of Noisy User Interaction Logs for RPA," BPM 2025 — https://doi.org/10.1007/978-3-032-02936-2_20 · code https://github.com/thohenadl/TimeSeriesInRPM. word2vec encoding plus time-series motif discovery, removing the need for predefined routine boundaries.

**Noise-tolerant routine extraction.** ◐ [arXiv:2510.08118](https://arxiv.org/html/2510.08118), 2025 preprint. *Author list and venue could not be resolved from the arXiv pages I retrieved; treat attribution as unverified.* Verified content: argues prior methods extract only the *set of actions* in routines rather than discovering full routine log models, and that prior segmentation work is not evaluated under noisy or inconsistent execution. Clustering-based; evaluated on nine UI logs from prior literature with systematically injected noise.

**Two-level abstraction.** ✅ Barba, Del Valle, Jiménez-Ramírez, Weber & Reichert (2024), CAiSE 2024 — https://doi.org/10.1007/978-3-031-61057-8_27. Screen-level activities plus fine-grained actions in a dual-layer representation; validated on synthetically generated UI logs.

**Desktop activity, the realistic lineage.** ✅ Shen, Li & Dietterich (2007), IJCAI-07 — [PDF](https://www.ijcai.org/Proceedings/07/Papers/460.pdf). Features from **window titles and file pathnames**, top-200 by information gain; single-window classifier combined over time by probability voting, likelihood-ratio stability testing, or Viterbi with task-transition costs. Evaluated on **four real users over 2–6 months**, 246–1,209 labelled switches, 8–176 distinct tasks, plus 20 synthetic datasets. Best COAP ≈ 0.78; precision improved >15% over baseline using transition costs. Authors note the human labels carry "considerable levels of noise." Companion: Dietterich et al., IUI 2009 — [PDF](https://web.engr.oregonstate.edu/~tgd/publications/IUI2009-TP2.pdf).

**Window-title semantics.** ✅ Oliver, Smith, Thakkar & Surendran (2006), "SWISH," IUI 2006 — [PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/swish.pdf). PLSI over tf-idf-weighted, stemmed, compound-split window titles; separately a window-switching transition matrix with Bron–Kerbosch clique detection; an ensemble falling back to temporal evidence when semantic confidence is low. Four hours, one user, five tasks: ~70% from titles alone, ~80% with temporal information.

**Case-ID absence.** ◐ Pourmirza, Peters & Dijkman (2015), ICSOC 2015 — https://doi.org/10.1007/978-3-662-48616-0_15; Bayomie et al. on deducing case IDs for unlabeled logs; "Attribute-Driven Case Notion Discovery for Unlabeled Event Logs" — [PDF](https://feb.kuleuven.be/drc/LIRIS/misc/bpiworkshop/papers/bpm-2021-paper-151.pdf).

**Automatability as a testable property.** ◐ Bosco, Augusto, Dumas, La Rosa & Fortino (2019), BPM Forum — https://doi.org/10.1007/978-3-030-26643-1_9. ◐ Leno et al., "Automated Discovery of Data Transformations for RPA" — [arXiv:2001.01007](https://arxiv.org/abs/2001.01007). The latter targets routines "where a user transfers data from one spreadsheet or (Web) form to another," applying data-transformation discovery to UI logs with two optimisations exploiting UI log structure and the observation that cross-application data transfers typically copy alphabetic and numeric tokens separately; naive application of existing techniques is reported as computationally inefficient. Evaluated on UI logs replicating a real-life repetitive data-transfer routine. This line is the concrete operationalisation of "is this routine deterministic enough to automate."

**Japanese corporate research.** ✅ Tada, Harada, Funabashi, Maeda, Mizouchi, Hayakawa, Karasudani & Kuraki (Fujitsu Limited; one author at Fujitsu Kansai-Chube Net-Tech), 「PC作業における課題の気付きを支援するためのタスクとPC操作ログの統合分析」 / "Integrated analysis of tasks and PC operation logs to help identify issues for office workers," IEICE technical report, 10 May 2021 — [record](https://ken.ieice.org/ken/paper/20210510qC3W/) · [summary](https://www.ieice.org/publications/ken/summary.php?contribution_id=113511&society_cd=ISS&ken_id=IE&year=2021&presen_date=2021-05-10&schedule_id=7143&lang=jp&expandable=3). Monitors and visualises PC work by **linking task information to the corresponding behavioural data** so workers can notice their own issues. Note the direction: it presupposes task labels and attaches logs to them, rather than inferring tasks from logs. Relevant as evidence of what a major Japanese vendor's research arm was doing in this space, and of the vocabulary used.

### 3.4 No-match findings (unchanged in substance after the second pass)

1. **No method calibrated on one department and deployed on another, with the transfer gap as the object of study.**
2. **No evaluation protocol for a flat `(session, start, end, label)` output against hidden process ground truth** — though v2 establishes that suitable metrics exist in neighbouring fields (§4.4).
3. **No treatment of split executions as an output-representation problem.**
4. **No evaluated method for the ~4% screen-text regime** — the 2026 VLM work assumes a screenshot per labelled event.
5. **No published guidance on label granularity** (family vs. variant) and its interaction with scoring.
6. **Little published work joining discovery to a defended, risk-assessed automation proposal.** Discovery papers stop at candidate routines; selection papers start from interviews or synthetic parameters.
7. **Japanese-language office UI telemetry remains nearly absent** from the peer-reviewed record accessible via English-indexed search: two items found across two passes (Urabe et al., NTT; Tada et al., Fujitsu).

---

## 4. Academic literature survey

### 4.1 Process mining from weakly structured data

| Source | Year / venue | Problem | Data type | Labels / case IDs? | Method | Evaluation | Solves, for this project | Does not solve |
|---|---|---|---|---|---|---|---|---|
| ✅ van Zelst, Mannhardt, de Leoni & Koschmider — [Event Abstraction in Process Mining: Literature Review and Taxonomy](https://sebastiaanvanzelst.com/wp-content/uploads/2020/04/Granular_Computing_in_Process_Mining.pdf) | 2020, *Granular Computing* | Bridging low-level events and business activities | Structured logs | Case IDs assumed; activity labels are what is abstracted | Survey + taxonomy (supervised, unsupervised, model-based) | Literature analysis | The formal vocabulary and taxonomy for "raw events → units of work" | Assumes case IDs; nothing on desktop telemetry or interleaving |
| ◐ Tax, Sidorova, Haakma & van der Aalst — [Event Abstraction using Supervised Learning](https://arxiv.org/abs/1606.07283) | 2016, preprint | Abstracting low-level events | Structured / sensor-style logs | **Requires labeled training data** | Supervised sequence labeling | Labeled datasets | Establishes that abstraction is tractable *with* labels | The labeled-transfer assumption is exactly what the A/B split removes |
| ◐ Pourmirza, Peters & Dijkman — [Correlation Mining](https://doi.org/10.1007/978-3-662-48616-0_15) | 2015, ICSOC | Model discovery with no case ID | Structured logs | **None** | Activity-pair correlation + duration distributions | Synthetic + real | Formalises "no case identifier" as a solvable class | Assumes a known activity alphabet |
| ◐ [Attribute-Driven Case Notion Discovery](https://feb.kuleuven.be/drc/LIRIS/misc/bpiworkshop/papers/bpm-2021-paper-151.pdf) | 2021, BPM workshop | Discovering the case notion itself | Attribute-rich logs | No case ID | Search over candidate case notions | Log experiments | Shows the case notion is a *choice* — the "what is one unit of work" ambiguity has a name | Needs attribute-rich structured data |
| ○ [Empirical evaluation of unsupervised event log abstraction techniques](https://www.sciencedirect.com/science/article/abs/pii/S0306437923001564) | 2024, *Information Systems* | Comparing unsupervised abstraction | Structured logs | Unsupervised | Comparative study | Multi-method | Would be the closest baseline study for abstraction | Publisher blocks retrieval in both passes |
| ◐ [A Survey on Concept Drift in Process Mining](https://arxiv.org/pdf/2112.02000) | 2021/22, *ACM Computing Surveys* | Detecting when process behaviour changes over time | Structured logs | Yes | Survey of drift detection/localisation | Literature | Vocabulary for distinguishing a *change* from a *variant* | Within-log temporal drift, not across-dataset domain shift |
| ○ [Generalization estimation in process mining: the impact of event data quality](https://link.springer.com/article/10.1007/s44311-025-00027-3) | 2025, *Process Science* | How to estimate generalisation | Structured logs | Yes | Estimation methods | — | The nearest thing to a "will this transfer" literature | Structured logs; not cross-domain |

### 4.2 Task mining and user-interaction mining

| Source | Year / venue | Problem | Data type | Labels? | Method | Evaluation | Solves | Does not solve |
|---|---|---|---|---|---|---|---|---|
| ✅ Leno et al. — [RPM: Vision and Challenges](https://doi.org/10.1007/s12599-020-00641-4) | 2021, *BISE* | Defining RPM and its open problems | UI logs | No case IDs (explicit) | Conceptual 6-stage pipeline | None | The canonical problem definition; names segmentation and automatability as unsolved | No method, data, or transfer story |
| ✅ Leno et al. — [Candidate Routines from Unsegmented UI Logs](https://arxiv.org/pdf/2008.05782v1) | 2020, ICPM | Routines from one noisy unsegmented sequence | UI logs; context parameters only after normalisation | Ground truth for evaluation | CFG + back-edge SCC segmentation; CloFast pattern mining; overlap-removal optimisation | CPN1–9 synthetic; Student Records & Reimbursement (supervised real); Scholarship S1/S2 (unsupervised real). NLED 0.0 synthetic, 0.059–0.331 real; JC ≥0.90 | The most complete published attempt at Step 1 + early Step 2, with a real metric | **Consecutive executions only; struggles with overlaps; fails under frequent app switching (S2); requires routines not to share actions except at starts** |
| ✅ Rebmann & van der Aa — [Unsupervised Task Recognition](https://doi.org/10.1007/978-3-031-34560-9_9) | 2023, CAiSE | Segment + categorise with no labels | UI events (id, timestamp, action, application, UI element, data values) | **Unsupervised** | Keyword chunking + contextual relatedness + data-value overlap; DenStream clustering | 3 synthetic streams, 560 tasks / 16,554 events; edit distance + Rand/Jaccard; 0.88–0.95 | Closest method to the full Step 1; two-part evaluation mirroring the brief | **Cannot handle interleaved tasks**; ignores timestamps; synthetic; no case correlation |
| ✅ Urabe, Yagi, Tsuchikawa & Oishi — [Task Clustering for RPA Planning](https://doi.org/10.1007/978-3-030-85469-0_18) | 2021, BPM | Segment + cluster office tasks | Operation logs; op ID from app + window title + GUI component | GT for evaluation | Co-occurrence-shift segmentation; agglomerative clustering | Real: 1 employee, 2 days, 3,422 ops, F=0.84. Simulated: 7,180 ops, F=0.93 | Closest to Steps 1 **and** 2 together, on exactly this assignment's field types | Tiny real evaluation; fails on uneven task lengths; no interruptions |
| ✅ Agostinelli, Marrella & Mecella — [The Challenge of Automated Segmentation](https://www.diag.uniroma1.it/marrella/papers/RCIS_2021_Segmentation.pdf) | 2021, RCIS | What makes segmentation hard | UI logs | n/a | 3-case taxonomy + literature mapping | Analytical | The clearest statement of what is unsolved | No method |
| ✅ Agostinelli, Leotta & Marrella — [Interactive Segmentation](https://doi.org/10.1007/978-3-030-91431-8_5) | 2021, ICSOC | Segmentation with expert filtering | UI logs | Human validates | Frequent patterns + human filter + trace alignment | Segmentation variants | The field's practical fallback; an honest model of residual manual work | Not autonomous |
| ✅ Hohenadl — [Time Series-Based Segmentation](https://doi.org/10.1007/978-3-032-02936-2_20) | 2025, BPM | Boundary-free segmentation of noisy logs | UI logs | Unsupervised | word2vec + motif discovery | [Code + data](https://github.com/thohenadl/TimeSeriesInRPM) | Recent, reproducible attempt at the boundary problem | Small artifact |
| ◐ arXiv [2510.08118](https://arxiv.org/html/2510.08118) | 2025, preprint | Routine *logs* under noise | UI logs | Unsupervised | Clustering-based | 9 literature UI logs + injected noise | Targets execution inconsistency directly | Attribution unverified |
| ✅ Abb & Rehse — [Reference Data Model for UI Logs](https://arxiv.org/abs/2207.12054) | 2022, BPM | What a UI log *is* | UI logs | Flexible case notion | Data model as XES extension | RPA contexts | Documents that every tool conceptualises UI logs differently | Not a mining method |
| ○ Abb & Rehse — [Process-related UI logs: state of the art, reference model, object-centric implementation](https://www.sciencedirect.com/science/article/pii/S0306437924000449) | 2024, *Information Systems* | Extended state of the art | UI logs | — | Reference model + object-centric implementation | — | Likely the fullest inventory of UI-log formats and datasets | **Blocked in both passes**; no arXiv preprint found |
| ○ Rehse, Abb et al. — [User Behavior Mining](https://doi.org/10.1007/s12599-023-00848-1) | 2024, *BISE* | Positioning the field | — | — | Conceptual | — | Field-level framing | Not retrieved |
| ✅ Barba et al. — [Two-Level Process Models from UI Event Logs](https://doi.org/10.1007/978-3-031-61057-8_27) | 2024, CAiSE | Hierarchical abstraction | UI logs | Synthetic GT | Screen-level + action-level dual layer | Synthetic | Addresses granularity (family / execution / task) directly | Synthetic only |
| ✅ Tada et al. (Fujitsu) — [Integrated analysis of tasks and PC operation logs](https://ken.ieice.org/ken/paper/20210510qC3W/) | 2021, IEICE tech. report | Linking task info to PC operation logs for worker self-awareness | PC operation logs | **Task labels presupposed** | Monitoring + visualisation | Evaluation of monitoring/visualisation | Evidence of Japanese corporate research and vocabulary in this exact space | Attaches logs to known tasks; does not infer tasks |
| ◐ Leno et al. — [Action Logger](https://ceur-ws.org/Vol-2420/paperDT2.pdf) | 2019, BPM Demos | Capturing mineable UI logs | Recorder | — | Browser + desktop recorder | Demo | Shows what a purpose-built RPM recorder captures — a useful contrast with this telemetry | Recording only |

### 4.3 Activity segmentation and task recognition (expanded in v2)

| Source | Year / venue | Problem | Data | Labels? | Method | Evaluation | Relevance here |
|---|---|---|---|---|---|---|---|
| ✅ Shen, Li & Dietterich — [Real-Time Detection of Task Switches](https://www.ijcai.org/Proceedings/07/Papers/460.pdf) | 2007, IJCAI | Desktop task-switch detection | Window titles, file paths | Human-labeled, noisy | Info-gain features + voting / likelihood ratio / Viterbi | 4 real users, 2–6 months; COAP ≈ 0.78 | The only long-horizon *real* office desktop evaluation with genuine interruptions. Its accuracy on a **simpler** problem is a sober reference point |
| ✅ Oliver et al. — [SWISH](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/swish.pdf) | 2006, IUI | Grouping windows into tasks | Window titles + switching history | Manual | PLSI + switching-graph cliques + ensemble | 4h, 1 user, 5 tasks; ~70%/~80% | Window titles alone carry substantial task signal; temporal structure adds to it |
| ◐ Farha & Gall — [MS-TCN](https://ar5iv.labs.arxiv.org/html/1903.01945) (CVPR 2019) and [MS-TCN++](https://dl.acm.org/doi/10.1109/tpami.2020.3021756) (TPAMI 2020) | 2019–20 | Temporal action segmentation in untrimmed video | Frame features | Fully supervised | Multi-stage dilated temporal convolutions | Breakfast, 50Salads, GTEA; frame accuracy, edit score, **segmental F1@{10,25,50} IoU** | The strongest analogue for *scoring* a segmentation: segmental F1 at IoU thresholds is precisely a boundary-tolerant interval metric |
| ◐ [OnlineTAS](https://proceedings.neurips.cc/paper_files/paper/2024/file/6c6c5fccf3c8661fcae219be7ca226f7-Paper-Conference.pdf) | 2024, NeurIPS | Online action segmentation | Streaming video | Supervised | Online baseline | Standard TAS benchmarks | The streaming variant of the same problem shape |
| ◐ Aminikhanghahi & Cook — [Using Change Point Detection to Automate Daily Activity Segmentation](https://userpages.umbc.edu/~nroy/courses/shhasp18/papers/p262-aminikhanghahi.pdf) | 2017 | Segmenting continuous sensor streams into activities | Smart-home sensor events | Partially labeled | Change-point detection | Smart-home datasets | The HAR analogue of Step 1: unsupervised boundary detection on a heterogeneous event stream |
| ◐ [Dynamic Segmentation of Sensor Events for Real-Time HAR](https://doi.org/10.3390/s22145458) | 2022, *Sensors* | Adaptive windowing | Sensor events | Labeled | Dynamic sliding windows | Smart-home | Documents the fixed-vs-adaptive window trade-off that any event-stream segmenter faces |
| ◐ Truong, Oudre & Vayatis — [ruptures](https://arxiv.org/abs/1801.00826) | 2018/20, *Signal Processing* | Offline change-point detection | Numeric signals | Unsupervised | Cost functions × search methods (Pelt, binseg, window, dynp) | Library benchmarks | The generic mathematics of "where does the regime change" |
| ◐ [Matrix Profile](https://www.cs.ucr.edu/~eamonn/MatrixProfile.html) (Keogh group, UCR) | 2016– | Motif and discord discovery in time series | Numeric series | Unsupervised | All-pairs subsequence distance profile | Extensive | The motif-discovery machinery Hohenadl's BPM 2025 segmentation builds on |

### 4.4 Segmentation evaluation metrics — the family v1 missed entirely

This is the most consequential addition after §3.2(b). The brief scores "whether boundaries between work units are correct" without stating a tolerance. That problem is well-studied outside task mining, and the field has already learned which naive metrics mislead.

| Source | Year / venue | What it establishes | Why it matters here |
|---|---|---|---|
| ✅ Pevzner & Hearst — [A Critique and Improvement of an Evaluation Metric for Text Segmentation](https://people.ischool.berkeley.edu/~hearst/papers/pevzner-01.pdf) (*Computational Linguistics* 28(1); the manuscript copy retrieved is dated 2000) | 2002 | Documents five specific defects in the **Pk** metric: (1) it penalises missed boundaries roughly twice as heavily as spurious ones (a false negative costs *k*, a false positive on average *k/2*); (2) it misses boundary-count mismatches when several boundaries fall inside one probe window, especially for segments smaller than *k*; (3) its leniency varies with segment-size variance, under-penalising errors in small segments and over-penalising large ones; (4) it over-penalises **near-misses**, treating a boundary placed slightly off worse than an unrelated false positive; (5) scores are hard to interpret. **WindowDiff** fixes these by counting the number of boundaries inside the probe window and penalising whenever that count differs from the reference — penalising a near-miss at roughly *2e* for offset *e*, and staying stable as segment sizes vary from (20,30) to (5,45) | Any scorer for `segments.jsonl` faces exactly these choices. The asymmetry point matters directly: whether over- or under-segmentation is the safer error depends on the metric, and Pk-like metrics systematically favour over-segmentation while WindowDiff does not |
| ◐ Fournier — [Evaluating Text Segmentation using Boundary Edit Distance](https://www.researchgate.net/publication/237073700_Evaluating_Text_Segmentation_using_Boundary_Edit_Distance); library: [segeval](https://segeval.readthedocs.io/) · [GitHub](https://github.com/cfournie/segmentation.evaluation) | 2013 | Boundary-edit-distance based measures (the *B* family) that model near-misses as explicit edit operations, plus inter-annotator agreement measures for segmentation | Provides a scoring model that separates "boundary in roughly the right place" from "boundary missing entirely" — the distinction the brief's phrasing implies but does not define. Also gives a way to reason about the *ground truth's own* annotation reliability |
| ◐ NLTK — [nltk.metrics.segmentation](https://www.nltk.org/_modules/nltk/metrics/segmentation.html) | current | Reference implementations of Pk and WindowDiff | Confirms these metrics are standard and readily available, not exotic |
| ◐ Temporal action segmentation convention (MS-TCN and successors) | 2019– | **Segmental F1@IoU{10,25,50}** plus frame-wise accuracy and edit score | The interval-level analogue: match a predicted segment to a reference segment when their temporal IoU exceeds a threshold. This is the closest existing convention to scoring `(start, end, label)` tuples |

**Note on the gap.** None of the task-mining papers surveyed use these metrics. Leno et al. use normalised Levenshtein edit distance over segment sequences and Jaccard over routine sets; Rebmann & van der Aa use normalised edit distance plus Rand/Jaccard; Urabe et al. use F-score; Shen et al. use COAP. Four papers, four conventions, none of them tolerance-parameterised in the WindowDiff sense. That the mature metric literature exists but has not been imported into task mining is itself a finding about the field's maturity.

### 4.5 Workflow clustering and variant discovery

| Source | Year / venue | Problem | Data | Method | Relevance |
|---|---|---|---|---|---|
| ◐ Song, Günther & van der Aalst — [Trace Clustering in Process Mining](https://link.springer.com/rwe/10.1007/978-3-319-63962-8_91-1) (orig. BPM workshops 2008) | 2008 / encyclopedia 2019 | Splitting heterogeneous logs into homogeneous groups | Structured traces | Profile-based feature vectors + clustering | The canonical "same process, different executions" machinery — but requires traces to exist first |
| ◐ De Weerdt et al. — Active Trace Clustering for Improved Process Discovery | 2013, *TKDE* | Clustering that improves model quality | Structured traces | Model-driven active clustering | Shows the clustering choice changes the discovered model — i.e. segmentation and clustering decisions propagate into Step 2's conclusions |
| ◐ [Discovery of process variants based on trace context tree](https://www.tandfonline.com/doi/full/10.1080/09540091.2023.2194578) | 2023, *Connection Science* | Variant discovery | Structured logs | Context-tree representation | A recent concrete take on variant identification |
| ○ Martínez-Rojas, Jiménez-Ramírez et al. — [A screenshot-based task mining framework for disclosing the drivers behind variable human actions](https://dl.acm.org/doi/10.1016/j.is.2023.102340) (*Information Systems* 118:102340) | 2023 | **Why** the same task is executed differently | UI logs + screenshots | Screenshot-based feature extraction feeding decision discovery | Directly targets the "is this variant a business rule or noise" question. **Full text blocked (403/robots) in both passes**; title, venue and DOI verified from two independent indexes |
| ◐ CloFast / closed sequential pattern mining with gaps | — | Frequent subsequence discovery allowing gaps | Sequences | Pattern mining | The specific algorithm Leno et al. use for routine identification; the gap allowance is what makes noisy interleaved sequences tractable at all |

### 4.6 Multimodal UI, screenshot and text interpretation (substantially expanded in v2)

| Source | Year / venue | Problem | Data | Method | Results | Limits |
|---|---|---|---|---|---|---|
| ✅ Rodríguez-Ruíz et al. — [Screenshot-Based Activity Labeling with Vision-Language Models](https://doi.org/10.1007/s12599-026-00990-6) | 2026, *BISE* 68:1097–1120 | Semantic labelling of UI-log events when UI metadata is inaccessible (virtualised, BPO) | 100 annotated desktop screenshots; 30 images → 90 events with GT descriptions, 3 complexity groups | VLMs (InternVL2.5, Qwen2.5VL, NVILA, UI-TARS) and LLMs (GPT-4, Mistral-Large, Qwen2.5-72B, Llama-3.1-405B); "Component Parent Crop" + "Highlight" prompting | Cosine similarity (all-mpnet-base-v2) vs GT; **activity-level 0.75+** for best models; InternVL2.5 best on events; robust across component density | Hallucination in generalist models; formatting inconsistency; prompt effectiveness varies by architecture; single process context; assumes a screenshot per event |
| ✅ Martínez-Rojas et al. — [Annotated UI Element Dataset for Desktop Environments](https://zenodo.org/records/10822752) | 2024, Zenodo (DOI 10.5281/zenodo.10822752) | Training/evaluating UI element detection | 100 training screenshots + a test set from one business process; six app groups (PDF reader, public-administration course manager, CRM, email client, file explorer, LMS); fullscreen and overlapping-window formats; 148.6 MB | Annotated UI components | — | CC-BY-4.0; small; Windows/desktop focus |
| ◐ [What's Behind the Screen? Unveiling UI Hierarchies in Process-Related UI Logs](https://doi.org/10.1007/978-3-031-70396-6_15) | 2024 | Recovering UI structure from logs | UI logs + hierarchy | Hierarchy reconstruction | — | Assumes richer capture than window titles |
| ◐ Rebmann & van der Aa — [Extracting Semantic Process Information from Natural Language in Event Logs](https://arxiv.org/abs/2103.11761) | 2021, CAiSE | Turning free text in logs into structured semantics (actions, objects, actors) | Event log text | NLP parsing/tagging | Multiple real logs | Assumes text is present on events |
| ◐ Berti, Qafari & van der Aalst — [Leveraging LLMs for Process Mining](https://arxiv.org/pdf/2307.12701) | 2023, tech report | LLMs on process-mining artifacts | Log abstractions | Prompting | Exploratory | No evaluation protocol for segmentation |
| ◐ [On the Potential of LLMs to Solve Semantics-Aware Process Mining Tasks](https://arxiv.org/abs/2504.21074) | 2025 | Benchmarking LLMs on semantics-aware PM | Log semantics | Prompting + benchmark suite | Multi-task | Not UI-log or segmentation specific |
| ◐ [LLMs that Understand Processes: Instruction-tuning for Semantics-Aware Process Mining](https://arxiv.org/html/2508.16270v1) | 2025 | Instruction-tuning for PM semantics | Event logs | Fine-tuning | Benchmarks | Preprint |
| ◐ Burattin et al. — [LLMs and Process Mining: Challenges in RPA](https://andrea.burattin.net/public-files/publications/2023-icpm-ws-pqmi.pdf) | 2023, ICPM workshop | Whether LLMs help RPA-oriented PM | UI/event logs | Position + experiments | Workshop-scale | Small scope |

### 4.7 Automation opportunity discovery and RPA candidate selection (expanded in v2)

| Source | Year / venue | Problem | Data | Method | Validation | Notes |
|---|---|---|---|---|---|---|
| ◐ Wanner et al. — [Process Selection in RPA Projects](https://d-nb.info/1259734102/34) | 2019, ICIS | Making candidate selection quantifiable | Interviews, documentation | Weighted criteria | Expert validation | The framing for prioritisation beyond frequency |
| ○ [Digging for Gold in RPA Projects](https://doi.org/10.1007/978-3-030-79382-1_19) | 2021, CAiSE | Identify and prioritise RPA candidates | — | Quantifiable method | — | **Rate-limited in both passes**; title and venue verified via Springer, ACM DL and the [CAiSE 2021 accepted-papers list](https://caise21.org/accepted-papers/); contents unverified |
| ○ Promitzer, Thalmann et al. — [Objectively Assessing the Suitability of Digital Processes for RPA](https://aisel.aisnet.org/wi2022/bpm/bpm/2/) | 2022, Wirtschaftsinformatik | Objective suitability assessment | Process data | Assessment method | — | Indexed in [dblp](https://dblp.org/rec/conf/wi/PromitzerTW22.html); not retrieved |
| ◐ [Development of Evaluation Criteria for RPA Solution Selection](https://www.mdpi.com/2079-9292/12/4/986) | 2023, *Electronics* | Criteria for choosing RPA solutions | Expert judgement | MCDM criteria development | Expert panel | Solution selection, not process selection from logs |
| ✅ Gomez & Castillo — [A Data-Driven Framework for Identifying and Prioritizing RPA Opportunities in Healthcare Processes](https://arxiv.org/html/2609.09137) | Sept 2026, arXiv preprint | End-to-end opportunity identification and prioritisation | **Synthetic, literature-informed data** | Four modules: (1) process taxonomy — 20 recurring hospital processes in 5 value streams; (2) multi-criteria prioritisation via AHP producing an **Automation Suitability Index** over transaction volume, rule-based standardisation, digital data availability, error/compliance risk, and process stability; (3) tool-tier selection (Python bot / n8n / enterprise RPA) keyed to legacy dependencies, API modernisation and PHI criticality; (4) ROI quantification — labour savings, error-cost avoidance, implementation cost, payback, 3-year NPV. ASI threshold 3.5 gates progression; a separate Automation Risk Index flags high-risk processes | Sensitivity analysis only: mean Spearman 0.83 across 2,000 Monte Carlo trials under ±20% weight perturbation. Authors state it is "developed as a conceptual synthesis…rather than as an instrument calibrated on primary hospital survey data" | The most complete published *structure* for turning discovered processes into a ranked, tool-tiered, ROI-quantified proposal — **and its authors explicitly disclaim empirical calibration**. That combination is instructive for how such a framework should be presented |
| ◐ Bosco et al. — [Discovering Automatable Routines](https://doi.org/10.1007/978-3-030-26643-1_9) | 2019, BPM Forum | Detecting deterministic, automatable fragments | UI logs | Rule and transformation discovery | UI logs | Introduces automatability as a property to be *tested* |
| ◐ Leno et al. — [Automated Discovery of Data Transformations for RPA](https://arxiv.org/abs/2001.01007) | 2020, preprint | Finding routines where data is transferred between spreadsheets/forms | UI logs | Data-transformation discovery with two UI-log-specific optimisations (exploiting log structure; alphabetic and numeric tokens copied separately) | UI logs replicating a real-life repetitive transfer routine | The concrete operationalisation of "is this deterministic enough to automate." Naive application of prior techniques reported as computationally inefficient |
| ◐ Agostinelli et al. — [SmartRPA](https://www.sciencedirect.com/science/article/pii/S2352711024003650) (*SoftwareX* 2025); [Reactive synthesis of software robots](https://dl.acm.org/doi/10.1016/j.compind.2022.103721) (*Computers in Industry* 2022) | 2021–25 | Synthesising executable robots from UI logs | Own recorder format | Reactive synthesis over log variants | Tool papers + case studies | The most complete published path from UI log to running robot |
| ◐ Leno et al. — [Automated Generation of Executable RPA Scripts from UI Logs](https://doi.org/10.1007/978-3-030-58779-6_8) | 2020, BPM industry | Compiling routines into scripts | UI logs | Script synthesis | Industrial | Same actuation assumption |
| ◐ Elkoumy et al. — [Privacy and Confidentiality in Process Mining](https://dl.acm.org/doi/10.1145/3468877) | 2021, *ACM TMIS* | Privacy threats in process mining | Event logs | Threat taxonomy | Conceptual | Directly applicable to telemetry carrying clipboard and screen content |

**Patent activity (new in v2).** The discovery-to-candidate pipeline is being staked out commercially: [Detection of variants of automatable tasks for RPA](https://patents.justia.com/patent/20240134685), [Data transformations for RPA](https://patents.justia.com/patent/11790262), and [Systems and methods for identifying processes for robotic automation and building models therefor](https://patents.justia.com/patent/20240046180). Patents are claims, not evidence of working systems, but their existence indicates where vendors believe the defensible technology sits.

---

## 5. Public datasets and benchmarks

**Headline finding, unchanged after the second pass: no public dataset resembles this assignment's data.** The closest UI-log datasets are small, single-process, screenshot-centric and largely synthetic. The datasets that do contain rich desktop recordings come from the GUI-agent field and carry task labels by construction, which makes them useless as a discovery benchmark.

| Dataset | Link / owner | Modality | Domain | Labels | Task/process boundaries | Interruptions / multi-app | Office-like? | Access | Meaningful comparison? |
|---|---|---|---|---|---|---|---|---|---|
| **UI Logs based on mockups or real-life screenshots** — Martínez-Rojas, Rodríguez Ruiz, Jiménez-Ramírez, González Enríquez, Reijers (Sevilla / Utrecht) | [Zenodo 15195200](https://zenodo.org/records/15195200) | CSV logs + PNG screenshots + JSON metadata + BPMN/Petri nets | Telecom unsubscription handling | Full process model: 10 activities, 1 decision point, 4 variants | Yes, by construction | Screens yes; interruptions no | Partly | CC-BY-4.0 | The most directly comparable public UI-log dataset — but 75–500 events per log over one process, three orders of magnitude smaller and far cleaner, with dense screenshots rather than sparse text |
| **Annotated UI Element Dataset for Desktop Environments** — same group | [Zenodo 10822752](https://zenodo.org/records/10822752) | Annotated desktop screenshots (148.6 MB) | Six app groups: PDF reader, public-administration course manager, CRM, email client, file explorer, LMS | UI component annotations | No | Overlapping-window configurations included | Yes | CC-BY-4.0 | Relevant only to the *screenshot understanding* sub-problem, not to segmentation |
| **Rebmann & van der Aa evaluation streams (SE1–SE3)** | via [GitLab](https://gitlab.uni-mannheim.de/processanalytics/task-recognition-from-event-stream) | Synthetic UI interaction streams | Data entry, reimbursement, student records, travel requests, SAP creation | 8 task types, 560 tasks, 16,554 events | Yes | Multi-app; **no interleaving** | Yes in spirit | Per repo terms | Closest analogue in *evaluation design*; synthetic and explicitly non-interleaved |
| **Leno et al. UI log corpus** — CPN1–9 synthetic; Student Records; Reimbursement; Scholarship S1/S2 | described in [arXiv:2008.05782](https://arxiv.org/pdf/2008.05782v1); redistributed in [TimeSeriesInRPM](https://github.com/thohenadl/TimeSeriesInRPM) | UI event logs | Travel authorisation, student records, reimbursement, scholarship | Routine ground truth | Yes | S2 specifically features frequent application switching — and is the log the method failed on | Simulated back-office | Open via repo | The de facto shared corpus of the RPM sub-field. Reused across many papers, so published comparisons partly measure fit to one generator. **S2 is notable as the field's known hard case, and it is hard for the same reason this assignment's data is hard** |
| **BPI Challenge logs** | [4TU.ResearchData](https://data.4tu.nl/collections/_/5065448/1) via [IEEE TFPM](https://www.tf-pm.org/resources/logs) | Structured XES event logs | Real organisations: loans, purchase-to-pay, permits | **Case IDs and activity labels present** | Case-level | No UI layer | Yes, at IT-system level | Open | The gold standard for process mining and useless here: they begin where this assignment ends |
| **Process Discovery Contest** | [IEEE TFPM](https://www.tf-pm.org/competitions-awards/discovery-contest) | Structured logs | Synthetic | Yes | Yes | No | No | Open | Confirms the community's competitive tradition operates entirely on labelled, case-ID-bearing data |
| **AgentNet** (OpenCUA / XLANG) | [HuggingFace](https://huggingface.co/datasets/xlangai/AgentNet) · [NeurIPS 2025 Spotlight](https://proceedings.neurips.cc//paper_files/paper/2025/hash/cc7ae529e945226b0d52ea4ac478c4f3-Abstract-Conference.html) | Screenshots + actions + reasoning traces | 22.6K computer-use tasks; Windows, macOS, Ubuntu; office, creative, dev, e-commerce, system utilities | Observation/Thought/Action, PyAutoGUI code, quality and difficulty scores | Tasks are given units | Multi-application workflows | Yes for app coverage | MIT | The richest public desktop-interaction corpus, but the **inverse** problem: identity is given and execution is the goal. Useful as evidence about what dense capture makes possible |
| **OSWorld** | [arXiv:2404.07972](https://arxiv.org/abs/2404.07972) · [site](https://osworld-v1.xlang.ai/) | Executable desktop environments + task specs | Real OS applications | Task instructions + execution rewards | Task = item | Multi-app | Partly | Open | Benchmarks agents *doing* work, not analysts *inferring* it |
| **Windows Agent Arena** | [Microsoft](https://microsoft.github.io/WindowsAgentArena/) | Windows VM environments + tasks | Windows applications | Task-level | Given | Multi-app | Yes | Open | Same inversion |
| **Text-segmentation evaluation corpora** (via [segeval](https://segeval.readthedocs.io/)) | Fournier | Segmented text with multi-annotator boundaries | Documents | Multiple reference segmentations | Yes | n/a | No | Open | Not a content comparison, but the only place I found *inter-annotator agreement on segmentation* treated as a first-class question — directly relevant to how much a single imperfect ground truth can be trusted |
| **Screen RPA public samples** | [RPA-US/screenrpa](https://github.com/RPA-US/screenrpa) | UI logs + screenshots + optional gaze | Synthetic RPA scenarios | Experiment-level | Yes | Limited | Simulated | CC BY-NC | Small demonstration data attached to a research framework |

**Consequence.** There is no external corpus on which a Dataset-B-like transfer could be rehearsed, and no leaderboard number to calibrate "good." Any claim about generalisation must be argued from the structure of the data at hand, not from precedent.

---

## 6. GitHub and open-source survey

Verified by visiting each repository during the survey. Figures are as displayed at that time.

| Repository / framework | Link | What it actually implements | Input expected | Output | Relevant component | Maturity | License | Limitations |
|---|---|---|---|---|---|---|---|---|
| **PM4Py** | https://github.com/process-intelligence-solutions/pm4py | Classical process-mining stack: log import/export (XES, CSV), discovery (alpha, inductive, heuristics), conformance checking, performance analysis, filtering, statistics | **Structured log with case ID, activity, timestamp** | Petri nets, process trees, DFGs; conformance and performance metrics | Everything *downstream* of segmentation | Actively maintained, company-backed, published in *SoftwareX* (2023) | Open source (GPL-family core; check current terms) | **Does not interpret raw UI or desktop logs.** No notion of keystrokes, window titles, or segmentation from unlabelled telemetry. Describing it as a task-mining solution would be inaccurate |
| **ScreenRPA** (Univ. Sevilla / RPA-US) | https://github.com/RPA-US/screenrpa | Screen-based task-mining framework: UI recording (Screen Action Logger, StepRecorders), WebGazer.js eye tracking, feature extraction, decision discovery, Graphviz process-flow visualisation, REST API, reporting | Windowed application interactions, screenshots, UI event logs, optional gaze | Structured UI logs (CSV), visualisations, analysis reports | Screenshot-driven enrichment; decision-point discovery | v1.0.2 (Jul 2025), 982 commits, **6 stars / 3 forks** | **CC BY-NC** | Mostly Jupyter (~80%); tiny user base; the non-commercial licence is a real constraint for client-facing work; assumes screenshot-rich capture |
| **OpenAdapt** | https://github.com/OpenAdaptAI/OpenAdapt | Records screenshots, GUI state, user actions and accessibility metadata; embeds and indexes demonstrations; conditions or fine-tunes vision-language models to replay tasks ("Demonstrate → Learn → Execute") | Live desktop recording via its own recorder | Replayable automation; segmentation via UI-element grounding | Closest OSS analogue to the *Step 3* end | **1.6k stars, 247 forks, 1,011 commits, 116 releases; v1.2.4 (Jun 2026)** — most actively maintained project here | MIT | Learns to *replay demonstrated tasks*; not a discovery tool for passive logs. Requires its own recorder; would not consume this log format |
| **TimeSeriesInRPM** | https://github.com/thohenadl/TimeSeriesInRPM | Reproduction code for motif-based UI-log segmentation (word2vec + time-series motifs) plus a log-generation notebook; bundles Leno-format example data | UI logs (CSV) | Segmentation experiment results | Boundary detection | ~20 commits, **0 stars**; artifact for a BPM 2025 paper | MIT | Two notebooks, not a library. Value is as a readable reference implementation |
| **Task recognition from event stream** (Univ. Mannheim) | https://gitlab.uni-mannheim.de/processanalytics/task-recognition-from-event-stream | Companion code to Rebmann & van der Aa (CAiSE 2023) | UI interaction event streams | Identified tasks + type clusters | Boundary detection **and** consistent labelling | University GitLab research artifact | Not stated on the landing page | Hosted outside GitHub; maintenance and licence unverified; implements the method that cannot handle interleaving |
| **SmartRPA** | https://github.com/bpm-diag/smartRPA | Records UI logs, analyses variants, reactively synthesises executable software robots | Its own UI log format | Executable RPA robots | Prototype/automation end | Backed by peer-reviewed papers (*Computers in Industry* 2022, *SoftwareX* 2025) | Check repo | Assumes its own recorder and an actuatable target |
| **ruptures** | https://github.com/deepcharles/ruptures | Offline change-point detection: cost functions (L2, RBF, linear, kernel) × search methods (Pelt, binseg, window, dynp) | Numeric signal / feature matrix | Change-point indices | Generic boundary mathematics | Mature, widely used, published | BSD-2-Clause | Domain-agnostic: knows nothing about processes, identity or labels |
| **segeval** | https://github.com/cfournie/segmentation.evaluation · [docs](https://segeval.readthedocs.io/) | Segmentation evaluation: Pk, WindowDiff, boundary edit distance / *B* measures, inter-annotator agreement for segmentation | Reference and hypothesis segmentations | Tolerance-aware error scores and agreement statistics | **Boundary *scoring*** | Stable published library (v2.0.11 docs) | Check repo | Linear text segmentation model; would need adapting to timestamped intervals, and it scores boundaries, not labels |
| **NLTK** — `nltk.metrics.segmentation` | https://www.nltk.org/_modules/nltk/metrics/segmentation.html | Reference implementations of Pk and WindowDiff | Boundary strings | Scores | Boundary scoring | Mature | Apache-2.0 | Minimal; no interval or label handling |
| **ActivityWatch** | https://github.com/ActivityWatch/activitywatch | Cross-platform desktop time tracker: window/app watchers, AFK detection, browser extension, local REST API and storage, categorisation rules | Live desktop activity | App/window/time buckets; rule-based category reports | Reference for what desktop telemetry looks like in practice | Mature, widely used | MPL-2.0 | Categorisation is **manual rule authoring**, not inference — a real-world sanity check that this problem is normally "solved" by hand |

**Two observations, sharpened in v2.**

First, **no repository implements the assignment end to end**, and the gap is now more precisely located: the mature tools sit on either side of the hard part (PM4Py downstream, ActivityWatch upstream), the research artifacts that address the hard part have single-digit adoption, and the one genuinely mature *evaluation* library (segeval) comes from a different field entirely and has apparently never been applied to UI logs.

Second, the adoption asymmetry is stark. OpenAdapt has 1.6k stars for *replaying known tasks*; every discovery-and-segmentation repository here has fewer than ten. The open-source community has invested heavily in executing known tasks and almost nothing in discovering unknown ones from passive logs.

---

## 7. Industry and commercial landscape

**Method note.** Everything below comes from vendors' own documentation or marketing. None is independently validated. Statements that are *technically specific and checkable in the documentation* are separated from *marketing assertions*. After the second pass the vendor landscape resolves into three distinct groups, which is more informative than v1's binary split.

### Group 1 — documentation admits human task definition

**Celonis — Task Mining / Task Discovery**
[Task Mining](https://docs.celonis.com/en/task-mining.html) · [Task Discovery](https://docs.celonis.com/en/task-discovery.html) · [Desktop application](https://docs.celonis.com/en/task-mining-desktop-application.html) · [Data configuration](https://docs.celonis.com/en/task-mining-data-configuration.html)
Input: desktop activity via a Celonis client plus business-application event data. Output: task frequency, task duration, steps involved. **Task Discovery does not infer tasks.** Verified: users manually create and define tasks by specifying start and end events that demarcate task instances, with up to three start and three end conditions expressed as event rules (the documentation's example runs from "when a user clicks on 'Create Opportunity'" to "when a user clicks on 'Save Opportunity'"). A manual, rule-based configuration system.

**UiPath — Task Mining**
[Unassisted Task Mining analysis guide](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/unassisted-task-mining-analysis-guide) · [Introduction](https://docs.uipath.com/task-mining/automation-suite/2023.4/user-guide/introduction-as) · [Privacy](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/protection-of-personal-data-and-privacy-of-the-users)
Input: recorded desktop activity — mouse clicks, keystrokes, hotkeys — across multiple executions of a task **already identified by a human**. Method: records and compares traces of a *known* task; AI clusters screenshots and merges traces into a single task graph with decision points. Output: task graph with decision points, variant statistics, time per action, a Process Definition Document, and a Studio XAML skeleton. **Explicit non-claims, verified:** it does not automatically discover unknown tasks and does not produce a ranked list of automation recommendations. Analysts must define the task, collect comparable traces, review merged results, quantify findings, and submit candidates to Automation Hub manually.

### Group 2 — documentation claims automatic discovery in specific technical terms

**Automation Anywhere — Process Discovery** ([official docs](https://docs.automationanywhere.com/bundle/enterprise-v2019/page/enterprise-cloud/topics/discovery/configuration/process-discovery-intro.html))
Documentation states it captures, parses and analyses user interactions with various systems; identifies and maps all relevant pathways **including variations** and automatically documents the most common workflow; requires minimal manual intervention compared with interviews and manual mapping. Outputs: ROI comparison across processes for prioritisation, a Process Definition Document, and a path to bot development. This is more specific than marketing copy but remains unvalidated vendor documentation; no method, accuracy or evaluation is published.

**Nintex / Kryon — Process Discovery** ([Nintex explainer](https://www.nintex.com/blog/kryon-process-discovery-what-it-is-and-what-it-isnt/))
Technical detail given: uses **computer vision to gather information in real time** from employee computers rather than from backend systems; an AI analytics engine identifies variants; outputs visual process maps of user actions across all applications, metrics for employee count, frequency, duration, step count and variants, and "automatically generates an automation workflow with all steps already recorded and configured," exported to Kryon Studio. The page explicitly positions this against process mining: computer vision and real-time capture versus event logs, databases and APIs. Marketing claims on the same page: up to 80% reduction in RPA implementation time; a Wyndham Hotels case study citing over $300k saved.

**SAP Signavio — Task Mining** ([wiki](https://www.signavio.com/wiki/process-discovery/task-mining/))
Captures application usage and switching, screen navigation, repetitive data entry and copy-paste behaviour, and task sequences across tools — valuable specifically "when people rely on several applications, spreadsheets, copy-paste steps, or manual workarounds that are not visible in system event logs." On discovery: "AI plays an important role because task-level data is often too detailed to review manually at scale," with AI used to "group similar actions, recognize patterns, and highlight where task behavior is repeated or inefficient." The framing presents grouping into "meaningful task sequences" as analytical processing requiring interpretation, not push-button discovery.

**Microsoft — Power Automate task mining** ([task mining overview](https://learn.microsoft.com/en-us/power-automate/task-mining-overview) · [process advisor](https://learn.microsoft.com/en-us/power-automate/process-advisor-overview))
Captures detailed steps for desktop tasks, individually or collaboratively. Pipeline: prepare processes and recordings → analyse → visualise → identify automation recommendations → share. Outputs: process maps (longest activities, number of variants, time by variant and action), an application analytics report, and automation recommendations expressed as **which connectors to use**. The overview does not document an automatic mechanism for grouping recordings into processes; the "prepare processes and recordings" step implies human organisation. Notable: recommendations are framed by *delivery feasibility* (available connectors) rather than raw repetitiveness.

### Group 3 — claims without checkable technical content

**Mimica** ([article](https://www.mimica.ai/articles/what-is-task-mining)) — claims automated, accurate business process discovery from low-level desktop activity that "identifies when and where processes occur by analyzing repeated behavior patterns across employees without interviews, surveys, or manual observation"; surfaces variations, decision points and exceptions down to screenshot level; runs a scoring engine ranking tasks "by time savings, ease of automation, and ROI" and recommends best-fit technology (RPA, IDP, generative AI); outputs PDDs and BPMN. **No method, evaluation or accuracy published.** These claims describe Steps 1–3 of this assignment almost exactly, which is precisely why the absence of substantiation matters.

**Skan AI** ([article](https://www.skan.ai/blogs/automation-discovery-process-intelligence)) — claims capture of "human-computer interactions across all applications," "process metadata, not personal content," unsupervised continuous discovery, and automatic identification of four "universal automation patterns" (application switching, manual data re-entry, approval variability, exception handling); quantified outcomes such as "10+ automation opportunities" worth "$10.5 million" and "45x average Excel switches per case." All marketing claims. The named patterns are interesting as a *hypothesis* about what is detectable from telemetry without business understanding, but they are asserted, not demonstrated.

**ABBYY Timeline** ([product](https://www.abbyy.com/timeline/)) and others (IBM, iGrafx, KYP.ai, Paxray, EdgeVerve) market process/task-mining capabilities; I found no public technical documentation specifying whether task boundaries are inferred or configured, and therefore do not characterise them.

### Japan (expanded in v2)

Task mining is an established commercial category in Japan, marketed as PC操作ログ (PC operation log) analysis for 業務可視化 (work visualisation) and RPA planning — e.g. [Heartcore](https://www.heartcore.co.jp/task-mining/index.html), [CTC](https://www.ctc-g.co.jp/keys/blog/detail/AI-Task-mining), and PC-log collection products such as [NEC InfoTrace](https://jpn.nec.com/infotrace/index.html).

**Newly found and directly on point: GenTaskMining**, launched 8 April 2026 by Ishidatosys Technologies Solutions ([MONOist report](https://monoist.itmedia.co.jp/mn/articles/2604/22/news042.html)). It applies generative AI to PC operation logs with: a "Report Agent" that gathers data from monitoring tools and creates documentation to help **identify business processes**; automation-candidate identification by **comparing logged processes against actual workflow execution** to surface significant differences between documented and actual procedures; and an "Insight Agent" using retrieval-augmented generation over chat-based instructions to provide objective improvement suggestions. This is the closest commercial analogue to this assignment I found anywhere, in the right country, launched five months before this brief. It is a press-reported product announcement — no method or evaluation is public.

### What the commercial landscape actually tells us

1. **The best-documented products require human task definition.** Celonis is rule-configured; UiPath starts from a human-identified task and explicitly does not discover unknown ones or rank recommendations.
2. **The products claiming automatic discovery split by specificity.** Automation Anywhere and Nintex/Kryon name mechanisms (interaction parsing; computer vision) and outputs; Mimica and Skan name only outcomes. None publishes evaluation.
3. **Where a documented product produces a recommendation, feasibility constrains it** — Microsoft frames recommendations by available connectors.
4. **Privacy is a shipped product requirement, and the obligations land on the customer.** Verified from UiPath's documentation: Task Mining records screenshots, keyboard actions, clicks and movements for configured applications; PII is automatically masked; credit-card data is forbidden and PHI requires a Business Associate Agreement; users may pause recording at any time (up to one-hour intervals, unlimited uses) and may view the full list of applications and interactions being recorded; data is encrypted in transit and at rest. Crucially: **"The customer must take all the appropriate legal measures in order to ensure that data subjects are duly notified about the data capturing and processing initiative"** because "UiPath has no technical possibility of identifying or taking consent from data subjects." The customer is the data controller, responsible for legal compliance, employee notification, access control, and deletion requests. For a project whose data contains clipboard contents, screen text and screenshots of employee work, this is the concrete shape of the governance obligation.

---

## 8. Comparative synthesis

### 8.1 What established approaches assume that this brief withholds

Nearly every mature method assumes at least one of the following; the brief removes all of them simultaneously.

| Assumption | Who assumes it | Status in this assignment |
|---|---|---|
| A case identifier | All classical process mining | Absent; the RPM literature says UI logs never have one |
| A known activity alphabet | Trace clustering, variant discovery, every PM4Py algorithm | Must be constructed from keystrokes and window titles first |
| A label vocabulary | Supervised abstraction (Tax et al.); all classification framings | Dataset A's vocabulary is declared non-transferable |
| Pre-segmented traces | Bosco et al.; the clustering literature | The segmentation *is* the task |
| **Sequential, non-interleaved execution** | Rebmann & van der Aa (explicit); Leno et al. (explicit — "designed for consecutive routine executions") | Interleaving is a stated feature of the data |
| **Routines not sharing actions** | Leno et al. (explicit requirement); the RCIS review found *no* work handling shared actions | Shared actions across processes are near-certain in multi-app back-office work |
| **Infrequent application switching** | Leno et al. (their S2 log failed under frequent switching) | Frequent switching between Excel, Word, browser and internal systems is the premise of the scenario |
| A recorder capturing UI element identifiers | The RPM pipeline; all script synthesis | Telemetry is window titles, keystrokes, clicks, clipboard |
| Dense screen capture | Screenshot-based task mining; the 2026 VLM work; the entire GUI-agent field | ~4% screen text, selective screenshots |
| An actuatable target system | Everything at the automation end | Unreachable |
| Same-domain evaluation | Essentially all of it, usually silently | Calibration and delivery are deliberately different domains |
| A settled boundary metric | Nobody in task mining — four papers, four conventions | Unknown and hidden |

### 8.2 Which normally-separate problems are fused here

In the literature these are separate papers by separate groups: segmentation (Agostinelli; Hohenadl; Leno), task-type identification (Rebmann & van der Aa; Urabe), operational analysis and workload quantification (commercial task-mining products), automation candidate prioritisation (Wanner; Gomez & Castillo), and robot synthesis (Leno; Agostinelli). The assignment asks for all five in seven days — with a cross-domain transfer step inserted between the second and third that no published work performs, and a scoring protocol that no published task-mining work has standardised.

### 8.3 How prior work handles — or fails to handle — this specific setting

**Case-ID-free.** Handled formally for structured logs (correlation mining, case-notion discovery); not for desktop telemetry, where the correlation attributes those methods rely on largely do not exist.

**Low-level events.** Handled as "event abstraction," with a taxonomy and both supervised and unsupervised branches. The supervised branch performs better and is exactly the branch the A/B split forecloses.

**Interrupted work.** This is the weak point, and the second pass strengthened the finding considerably. Three independent lines of evidence now converge:
- The RCIS 2021 review found only a few works able to untangle interleaved routine executions and **none** able to handle actions shared across routine executions.
- The strongest recent unsupervised method (CAiSE 2023) excludes interleaving by assumption.
- The flagship ICPM 2020 method reports in its own limitations that it is designed for consecutive executions, struggles with overlaps, requires routines not to share actions except at starts, and **failed on the one real log characterised by frequent application switching**.

The only literature that engaged seriously with real interruptions is the 2006–2009 HCI work, which detected *switches* without identifying *processes*, on four users, against noisy human labels, at roughly 0.78 agreement.

**Cross-application.** The HCI lineage handled it naturally (window titles span applications); the RPM lineage handles it via multi-application recorders; neither handles a *change of application set between datasets*.

**Scoring.** Task mining has no shared metric. Neighbouring fields do, and they have already discovered the traps: Pk penalises misses about twice as heavily as false alarms and over-penalises near-misses; WindowDiff corrects both; boundary-edit-distance measures model near-misses explicitly and also support inter-annotator agreement; video action segmentation uses segmental F1 at IoU thresholds for interval outputs. None of this has been imported into UI-log research.

### 8.4 Evidence on sparse UI text versus event-only traces (substantially revised in v2)

There is now a coherent, if incomplete, picture across three regimes.

**Metadata-only (window titles, app names, GUI component identity).** SWISH: ~70% task assignment from window titles alone, ~80% adding window-switching structure (2006, one user, four hours). Shen et al.: ~0.78 COAP from window titles and file paths (four real users, 2–6 months). Urabe et al.: F = 0.84 real / 0.93 simulated with operation identity built from application name + window title + GUI component and **no screen text at all**. Leno et al.: normalised edit distance 0.059–0.331 on real logs using only *context* parameters after discarding data values. The consistent message is that metadata alone supports meaningful but imperfect recovery, in the rough vicinity of 70–85% on simple task sets, degrading with interleaving and app switching.

**Dense screenshots.** The 2026 *BISE* study shows vision-language models can produce activity-level semantic descriptions at 0.75+ cosine similarity to human annotations, in an environment where UI metadata is deliberately unavailable — with hallucination, formatting instability and prompt sensitivity as named failure modes, on 100 screenshots in one process context.

**The intermediate regime — this assignment's regime — remains unevaluated.** Whether text present on ~4% of events materially improves over window titles alone, and whether selective screenshots can be leveraged the way dense ones can, is an open empirical question. It is not answered by either body of evidence, and the honest position in a downstream report is that it is a question to be settled on the data rather than assumed either way.

### 8.5 Is an end-to-end method under these exact constraints common, rare, or absent?

**Absent, on the published record**, and the second pass sharpened rather than softened this. Urabe et al. (2021) is the nearest single-paper approximation of Steps 1–2, evaluated on one employee over two days. Rebmann & van der Aa (2023) is the nearest method for segmentation-plus-consistent-labelling, and excludes interleaving. Leno et al. (2020) is the nearest attempt at unsegmented discovery, and reports failure under precisely this data's conditions. No published work adds cross-department transfer. No published work carries through to a justified automation proposal with evidenced risk analysis — the closest, Gomez & Castillo (2026), has a complete *structure* for doing so and explicitly disclaims empirical calibration.

The nearest thing to an end-to-end system may be commercial and Japanese: **GenTaskMining**, launched five months before this brief, applying generative AI to PC operation logs to identify business processes and automation candidates. Nothing about its method is public.

### 8.6 Claims requiring especially careful evidence in a later phase

Ranked by how easily an evaluator holding Dataset B's ground truth could challenge them.

1. **Any accuracy or quality claim about Dataset B.** All measurement is on A, which the specification declares to be a different distribution. The literature offers no precedent for how much accuracy survives such a shift, because the experiment has essentially never been run. The closest indirect evidence is discouraging: the one method evaluated across several real logs (Leno et al.) succeeded on some and failed on the one with frequent app switching.
2. **Any absolute time-savings or ROI figure.** Waiting times are compressed by design. The RPM literature states frequency does not imply automatability. The candidate-selection literature derives ROI from interviews or, in the one fully quantitative framework found, from synthetic literature-informed parameters that its own authors decline to call calibrated. Every step from "this segment took 40 seconds" to "this saves N hours per year" imports an outside assumption.
3. **Any claim that a discovered pattern is automatable.** Leno et al. (2021) state there is no guarantee, and that identifying non-deterministic actions — where a human supplies external input or judgement — is unsolved. The data-transformation line ([arXiv:2001.01007](https://arxiv.org/abs/2001.01007)) shows what a *testable* determinism claim looks like, and it is narrow: routines transferring data between spreadsheets and forms.
4. **Any claim that a variant is a business rule rather than an artifact.** The one paper directly targeting variability drivers is screenshot-based and its full text was inaccessible. Nothing in the accessible literature offers a way to distinguish a genuine branch from operator habit, retry, or correction from logs alone.
5. **Any accuracy figure quoted without naming its metric.** Given four incompatible conventions in the literature and a hidden scorer, a number stated without its metric and tolerance is close to meaningless — and an evaluator who works in this field will know that.

---

## 9. Research gaps and uncertainties

### 9.1 Gaps in the literature specific to this setting

1. **No shared evaluation protocol in task mining** for a flat `(session, start, end, label)` output against process ground truth. Four papers use four conventions; none is tolerance-parameterised. Mature alternatives exist one field over and have not been imported.
2. **No treatment of split executions as an output-representation problem.** Interleaving is studied as a detection obstacle; nobody asks how to *write down* a suspended-and-resumed execution in a flat schema.
3. **No cross-department transfer study in task mining.** The distribution-shift experiment the assignment mandates appears unpublished.
4. **No evaluated method for the ~4% screen-text regime.** The field is bimodal: dense screenshots or metadata only.
5. **No published guidance on label granularity** (process family vs. variant) and its interaction with scoring.
6. **No published, reproducible join from discovery to a risk-assessed proposal.** Discovery papers stop at candidate routines; selection frameworks start from interviews or synthetic parameters.
7. **No published method handling actions shared across concurrent routine executions** — stated as a finding by the RCIS 2021 review and reinforced as an explicit prerequisite by Leno et al.
8. **Japanese-language office UI telemetry remains nearly absent** from the peer-reviewed record reachable by English-indexed search: two items across two passes (Urabe et al., NTT, BPM 2021; Tada et al., Fujitsu, IEICE 2021), against a visibly active commercial market.
9. **Inter-annotator reliability of process ground truth is not studied in task mining.** The text-segmentation field treats it as a first-class question; given that this assignment's ground truth is acknowledged to be defective, that omission is notable.

### 9.2 Results that may not transfer

- **Anything tuned on the Leno et al. corpus.** Small and reused across many papers, so reported improvements partly measure fit to one generator.
- **Leno et al.'s own real-log results (NLED 0.059–0.331).** Achieved on logs of consecutive routine executions; the method failed on the log with frequent application switching, and requires routines not to share actions.
- **Rebmann & van der Aa's 0.88–0.95 Rand.** Synthetic streams, no interleaving, no overhead-task mixing, timestamps unused — by the authors' own account.
- **Urabe et al.'s F = 0.84.** One employee, two days, five tasks, with a documented failure mode on uneven task lengths.
- **SWISH's 70–80%.** One user, four hours, five tasks, 2006-era desktops.
- **Shen et al.'s 0.78 COAP.** Real and long-horizon, but the target is switch detection, not process identity, and the labels are described as noisy.
- **The 2026 VLM 0.75+ similarity.** 100 screenshots, one process context, a screenshot per labelled event, and cosine similarity to a description — not a classification accuracy and not a boundary result.
- **Any supervised abstraction result.** Predicated on labelled training data from the same domain.
- **Gomez & Castillo's prioritisation framework.** Self-described as conceptual synthesis on synthetic data; its sensitivity analysis tests robustness to weight perturbation, not correctness against outcomes.
- **All vendor accuracy and savings claims.** None independently validated.

### 9.3 Terms for a third search pass

Not tried, or tried only shallowly, across the two passes:

`segmented UI log` · `routine trace` · `action log abstraction` · `desktop process discovery` · `work pattern mining` · `interaction log clustering` · `object-centric UI log` · `bag-of-actions representation` · `automatability score` · `deterministic routine detection` · `human-in-the-loop process discovery` · `TextTiling` · `session boundary detection web logs` · `dialogue topic segmentation granularity` · `boundary similarity metric` · `segmentation inter-annotator agreement` · `weakly supervised action segmentation` · `activity discovery without labels` · `keystroke dynamics task inference` · `clipboard provenance tracking`
Japanese: `操作ログ 業務プロセス 推定` · `タスク粒度 分割` · `業務分類 クラスタリング 操作ログ` · `RPA 適用候補 抽出 ログ` · `業務可視化 セグメンテーション`
Venues worth browsing directly rather than searching: ICPM and its workshops (2019–2026), BPM Forum and BPM industry track, CAiSE, RCIS, ICSOC, IEICE ISS technical reports, IPSJ SIG reports.
Authors worth citation-chasing: Marlon Dumas, Marcello La Rosa, Volodymyr Leno, Andrea Marrella, Simone Agostinelli, Han van der Aa, Adrian Rebmann, Jana-Rebecca Rehse, Luka Abb, Andrés Jiménez-Ramírez, Antonio Martínez-Rojas, Antonio Rodríguez-Ruíz, Hajo Reijers, Thomas Dietterich, Yuki Urabe.

### 9.4 Questions only the data can settle

1. What fraction of events carry *any* discriminative signal beyond timing and application context.
2. Whether window titles in this client's systems are informative (case numbers, screen names, record IDs) or generic ("Microsoft Excel", "Chrome"). This single fact separates the SWISH/Shen/Urabe regime from a much harder one.
3. Whether the ~4% of events with screen text cluster usefully (at process starts, at form submissions) or scatter at random.
4. How much interleaving actually occurs — what fraction of Dataset A's ground-truth executions are split by suspension/resumption, and how long the interruptions are. This determines whether the field's known failure mode is actually triggered.
5. How often distinct processes **share UI actions** — the condition the RCIS review found unaddressed and Leno et al. require to be absent.
6. How frequently the application switches — the specific condition under which the flagship method failed.
7. What Dataset A's ground truth implies empirically about granularity: the ratio of families to executions to tasks, and within-family variance.
8. The boundary-time distribution: long idle gaps between executions (easy) or immediate transitions (hard).
9. The severity of the ground-truth defects: what proportion of `process_started` records duplicate, and how many switch-outs are unpaired.
10. Whether Dataset B's applications share any structural family with Dataset A's, or are genuinely disjoint.
11. Whether Dataset B's 15 sessions come from distinguishable individuals, and by which field.
12. Whether waiting-time compression is uniform across process types, which determines whether even *relative* duration comparisons are safe.
13. Whether clipboard contents or browser DOM attributes carry correlation keys (case numbers, employee IDs) that could serve as a surrogate case identifier — the one route by which the correlation-mining literature would become applicable.
14. What fraction of each session is non-business or unclassifiable activity.

---

## 10. Annotated bibliography

**Primary framing**

- **Leno, V., Polyvyanyy, A., Dumas, M., La Rosa, M. & Maggi, F.M. (2021). Robotic Process Mining: Vision and Challenges. *BISE* 63(3), 301–314.** https://doi.org/10.1007/s12599-020-00641-4 — *The most important single source.* Defines the six-stage pipeline the assignment reproduces; states UI logs have no case identifier; states frequency does not imply automatability; names non-deterministic action detection as unsolved. Informs: whole problem framing; Step 2 risk argument.
- **Leno, V. et al. (2020). Identifying Candidate Routines for RPA from Unsegmented UI Logs. ICPM 2020.** [arXiv:2008.05782](https://arxiv.org/pdf/2008.05782v1) — *The most important source for calibrating expectations.* CFG back-edge segmentation plus CloFast pattern mining, with real metrics (NLED 0.059–0.331 on real logs) — and a limitations section stating the method needs consecutive executions, non-shared actions, and infrequent application switching. Informs: boundary detection; realistic accuracy expectations; risk evidence.
- **Agostinelli, S., Marrella, A. & Mecella, M. (2021). Exploring the Challenge of Automated Segmentation in RPA. RCIS 2021.** [PDF](https://www.diag.uniroma1.it/marrella/papers/RCIS_2021_Segmentation.pdf) — *The key negative result.* Three-case taxonomy; no published work handles actions shared across routine executions. Informs: expectation-setting; risk.

**Closest methods**

- **Rebmann, A. & van der Aa, H. (2023). Unsupervised Task Recognition from User Interaction Streams. CAiSE 2023.** https://doi.org/10.1007/978-3-031-34560-9_9 — Closest method to Step 1; solves segmentation and typing unsupervised; evaluates both halves separately. Its inability to handle interleaving is as informative as its results.
- **Urabe, Y., Yagi, S., Tsuchikawa, K. & Oishi, H. (2021). Task Clustering Method Using User Interaction Logs to Plan RPA Introduction. BPM 2021.** https://doi.org/10.1007/978-3-030-85469-0_18 — Closest to Steps 1 and 2 together, from a Japanese industrial group, built on exactly this assignment's field types, and reporting workload distribution as the output.
- **Rodríguez-Ruíz, A. et al. (2026). Enriching Process-Related UI Logs Via Screenshot-Based Activity Labeling by Using Vision-Language Models. *BISE* 68, 1097–1120.** https://doi.org/10.1007/s12599-026-00990-6 — *The key new source in v2.* Demonstrates activity-level semantics recoverable from screen images without UI metadata (0.75+ similarity), with hallucination and prompt sensitivity as named failure modes. Informs: what selective screenshots might and might not buy.

**Evaluation metrics — the family to reason with, from outside task mining**

- **Pevzner, L. & Hearst, M. A Critique and Improvement of an Evaluation Metric for Text Segmentation. *Computational Linguistics* 28(1).** [PDF](https://people.ischool.berkeley.edu/~hearst/papers/pevzner-01.pdf) — Documents five defects in Pk and introduces WindowDiff. The asymmetry finding (misses penalised ~2× false alarms) and the near-miss finding are directly relevant to whether over- or under-segmentation is the safer error under an unknown scorer.
- **Fournier, C. Evaluating Text Segmentation using Boundary Edit Distance; `segeval`.** https://segeval.readthedocs.io/ · https://github.com/cfournie/segmentation.evaluation — Boundary-edit-distance measures plus inter-annotator agreement for segmentation. The only place in this survey where the reliability of a *reference* segmentation is treated as a first-class question.
- **Farha, Y.A. & Gall, J. MS-TCN (CVPR 2019); MS-TCN++ (TPAMI 2020).** [ar5iv](https://ar5iv.labs.arxiv.org/html/1903.01945) · https://doi.org/10.1109/TPAMI.2020.3021756 — Establishes segmental F1@IoU{10,25,50} plus frame accuracy and edit score as the convention for interval-level segmentation scoring: the closest existing analogue to scoring `(start, end, label)` tuples.

**Desktop activity, the realistic lineage**

- **Shen, J., Li, L. & Dietterich, T.G. (2007). Real-Time Detection of Task Switches of Desktop Users. IJCAI-07.** [PDF](https://www.ijcai.org/Proceedings/07/Papers/460.pdf) — The only work on genuinely real, months-long, interruption-rich office desktop data. ~0.78 agreement on a *simpler* problem is the soberest reference point available.
- **Oliver, N. et al. (2006). SWISH. IUI 2006.** [PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/swish.pdf) — Earliest clear demonstration that window titles carry task signal and that switching structure adds to it.
- **Tada, A. et al. (Fujitsu, 2021). Integrated analysis of tasks and PC operation logs. IEICE technical report.** https://ken.ieice.org/ken/paper/20210510qC3W/ — Japanese corporate research linking known tasks to operation logs for worker self-awareness. Note the direction of inference, which is the reverse of this assignment's.

**Structural background**

- **van Zelst, S. et al. Event Abstraction in Process Mining: Literature Review and Taxonomy.** [PDF](https://sebastiaanvanzelst.com/wp-content/uploads/2020/04/Granular_Computing_in_Process_Mining.pdf) — The formal vocabulary for what Step 1 is doing.
- **Pourmirza, S., Peters, S. & Dijkman, R. (2015). Correlation Mining. ICSOC 2015.** https://doi.org/10.1007/978-3-662-48616-0_15 — Formalises the no-case-identifier problem.
- **Abb, L. & Rehse, J.-R. (2022). A Reference Data Model for Process-Related User Interaction Logs. BPM 2022.** [arXiv:2207.12054](https://arxiv.org/abs/2207.12054) — Documents that every tool conceptualises UI logs differently, which is why this assignment's bespoke schema is normal rather than unusual.
- **A Survey on Concept Drift in Process Mining. *ACM Computing Surveys*.** [arXiv:2112.02000](https://arxiv.org/pdf/2112.02000) — Vocabulary for distinguishing a change over time from a variant.
- **Elkoumy, G. et al. (2021). Privacy and Confidentiality in Process Mining. *ACM TMIS*.** https://dl.acm.org/doi/10.1145/3468877 — Threat taxonomy for exactly this kind of data.

**Automation candidate selection**

- **Gomez, M.A. & Castillo, J.M. (2026). A Data-Driven Framework for Identifying and Prioritizing RPA Opportunities in Healthcare Processes.** [arXiv:2609.09137](https://arxiv.org/html/2609.09137) — The most complete published *structure* for taxonomy → multi-criteria suitability index → tool-tier selection → ROI quantification, with an explicit authorial disclaimer that it is not empirically calibrated. Informs both how to structure a prioritisation argument and how honestly to caveat it.
- **Wanner, J. et al. (2019). Process Selection in RPA Projects. ICIS 2019.** [PDF](https://d-nb.info/1259734102/34) — Criteria beyond frequency.
- **Leno, V. et al. (2020). Automated Discovery of Data Transformations for RPA.** [arXiv:2001.01007](https://arxiv.org/abs/2001.01007) — What a *testable* determinism claim looks like, and how narrow it is.

**Datasets and code**

- Martínez-Rojas, A. et al. — [UI Logs based on mockups or real-life screenshots](https://zenodo.org/records/15195200), CC-BY-4.0 — closest public UI-log dataset.
- Martínez-Rojas, A. et al. — [Annotated UI Element Dataset for Desktop Environments](https://zenodo.org/records/10822752), CC-BY-4.0.
- [PM4Py](https://github.com/process-intelligence-solutions/pm4py) — mature process mining; *does not* interpret raw UI logs.
- [OpenAdapt](https://github.com/OpenAdaptAI/OpenAdapt) — MIT, 1.6k stars, actively maintained; replays demonstrated tasks, does not discover unknown ones.
- [ScreenRPA](https://github.com/RPA-US/screenrpa) — CC BY-NC; screenshot-driven task-mining research framework.
- [TimeSeriesInRPM](https://github.com/thohenadl/TimeSeriesInRPM) — MIT; motif-based segmentation reference implementation with bundled Leno-format data.
- [segeval](https://github.com/cfournie/segmentation.evaluation) — segmentation evaluation metrics (Pk, WindowDiff, boundary edit distance, agreement).
- [ruptures](https://github.com/deepcharles/ruptures) — BSD-2; generic change-point detection.
- [ActivityWatch](https://github.com/ActivityWatch/activitywatch) — MPL-2.0; real desktop telemetry with *hand-written* categorisation rules.
- [AgentNet](https://huggingface.co/datasets/xlangai/AgentNet) — MIT; 22.6K annotated computer-use tasks. The inverse problem; useful as a modality contrast.

**Vendor documentation (claims, not evidence)**

- [Celonis Task Discovery](https://docs.celonis.com/en/task-discovery.html) — *verified: manual rule-based task boundary definition.*
- [UiPath Task Mining analysis guide](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/unassisted-task-mining-analysis-guide) — *verified: requires a human-identified task; does not auto-discover unknown tasks; does not rank recommendations.*
- [UiPath Task Mining privacy documentation](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/protection-of-personal-data-and-privacy-of-the-users) — *verified: PII masking, user pause control, visibility of what is recorded, and the customer as data controller responsible for notifying data subjects.* The most concrete governance material found.
- [Automation Anywhere Process Discovery docs](https://docs.automationanywhere.com/bundle/enterprise-v2019/page/enterprise-cloud/topics/discovery/configuration/process-discovery-intro.html) — *vendor documentation claiming automatic pathway and variant discovery with minimal manual intervention; no method or evaluation published.*
- [Nintex/Kryon Process Discovery](https://www.nintex.com/blog/kryon-process-discovery-what-it-is-and-what-it-isnt/) — *names computer vision as the data source; claims automatic workflow generation; savings figures are marketing.*
- [SAP Signavio Task Mining](https://www.signavio.com/wiki/process-discovery/task-mining/) — *AI used to group actions and recognise patterns; grouping framed as analytical processing rather than push-button discovery.*
- [Microsoft Power Automate task mining](https://learn.microsoft.com/en-us/power-automate/task-mining-overview) — *verified outputs; grouping mechanism not documented; recommendations framed by available connectors.*
- [Mimica](https://www.mimica.ai/articles/what-is-task-mining) and [Skan AI](https://www.skan.ai/blogs/automation-discovery-process-intelligence) — *unverified marketing claims of end-to-end automatic discovery and ROI ranking.*
- [GenTaskMining launch report, MONOist](https://monoist.itmedia.co.jp/mn/articles/2604/22/news042.html) — *Japanese generative-AI PC-operation-log analysis service, launched April 2026; the closest commercial analogue found. Press report only; no method public.*

---

## Limits of this survey (v2)

Two passes, conducted through web search and page retrieval. Four weaknesses should be assumed by anyone relying on it.

1. **Publisher access remains the binding constraint.** Three relevant items resisted retrieval in both passes: Abb & Rehse's *Information Systems* (2024) state-of-the-art paper on UI logs (no preprint found), the CAiSE 2021 "Digging for Gold" candidate-prioritisation paper (rate-limited), and Martínez-Rojas et al.'s *Information Systems* (2023) screenshot-based framework for variability drivers (403/robots). Titles, venues and DOIs are verified; contents are not. The third of these is the most consequential omission, since it targets the variant-driver question directly.
2. **The arXiv 2510.08118 attribution is unresolved.** Content was readable; author list and venue were not returned by the pages retrieved.
3. **Japanese-language academic coverage is improved but still thin.** CiNii's search interface is robots-disallowed to this tool, and IPSJ SIG reports are largely paywalled and poorly indexed in English search. Two academic items were found across two passes against a visibly active commercial market — a ratio that almost certainly reflects search reach rather than reality. A native-language pass through CiNii, J-STAGE and IPSJ SIG proceedings would likely change §4.2 and §9.1.
4. **Negative findings are claims about this search, not proofs of absence.** "No exact match," "no cross-department transfer study," and "no shared evaluation protocol" should be stated that way in any downstream report — as the result of a bounded search, with the search terms named.
