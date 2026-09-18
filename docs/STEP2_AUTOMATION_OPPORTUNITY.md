# Step 2 — Automation Opportunity Discovery

**AUTHORITATIVE.** This document replaces `docs/STEP2_AUTOMATION_OPPORTUNITY.tex` / `.pdf`
(2026-09-15) and `reports/STEP2_ANALYSIS.md` as the Step 2 analysis of record. Those artifacts are
retained, not deleted; their claims are audited individually in
`docs/STEP2_PREVIOUS_ANALYSIS_AUDIT.md`.

**Date:** 2026-09-16 · **Step 1 is frozen and was not modified.**

**Companion documents**
`docs/STEP2_FORENSIC_RECONCILIATION.md` — evidence contract and process reconstruction
`docs/STEP2_PREVIOUS_ANALYSIS_AUDIT.md` — claim-by-claim audit of the superseded analysis
`docs/STEP2_PEER_REVIEW.md` — external review of task-mining systems and what we borrow
`docs/STEP2_PROCESS_INVENTORY.csv` · `docs/STEP2_EXECUTION_TABLE.csv` ·
`docs/STEP2_LABEL_MODULE_CONFUSION.csv` · `docs/STEP2_CANDIDATE_MATRIX.csv` ·
`docs/STEP2_EVIDENCE_MATRIX.csv` — the underlying data
`analysis/step2_reanalysis.py` — the code that produced them

---

## 1. Objective

The client asked where automation would have the greatest impact, and for something that works.
Step 2 must answer: **what processes exist in Dataset B, how much do they cost, which are suitable
for automation, in what order, and by what mechanism** — with reasoning a sceptical reviewer can
reproduce and attack.

This is a re-performance, not a revision. The previous Step 2 selected a "payroll-items family"
described as *duplicate master-data entry across three siloed systems with the operator as the
integration layer*. **That interpretation is contradicted by the data.** The re-analysis starts from
raw evidence and reaches a different answer.

---

## 2. Inputs and evidence contract

The full contract is in `STEP2_FORENSIC_RECONCILIATION.md` §1. Four consequences govern everything
below.

**2.1 An execution is not a business case.** A Step-1 execution contains **1.83–4.35 recorded
dispositions** depending on module. The business unit is the disposition — one record processed.

**2.2 Only 72.5% of business work is inside an execution.** 456 of 629 recorded `btn-*-ok` clicks
fall inside a Step-1 segment. Roughly a quarter of observable dispositions occur in unsegmented
spans. Every per-module figure below therefore *understates* activity, uniformly but not identically.

**2.3 A route is not a process, and neither is a UI label.**
`/payroll-items` renders **three different businesses** on three origins. `/resident-tax` renders
purchase-order management. On one module the column header reads 入社日 ("start date") above cells
containing 振込 ¥1,182,500. Header, route, badge, button and filename are all **system labels**, not
ground truth.

**2.4 What is unavailable, and stays unavailable.** Business volume, monetary value, labour cost,
FTE saving, error and rework rate, business criticality, compliance exposure, API or import
availability, production selector stability. These are recorded as `UNAVAILABLE` in the inventory
CSV and are never estimated.

---

## 3. Dataset B process reconstruction

Eleven business modules across three systems, each identified from a screenshot showing URL bar,
breadcrumb/H1 and highlighted navigation item together.

| ID | System | Route | Module | Record prefix | Governing document (co-occurring blocks) |
|---|---|---|---|---|---|
| M01 | HR人事給与システム `:5132` | `/payroll-items` | 経費精算・給与変更 | `P1-`,`P4-` | 業務委託経費規程 (57) |
| M02 | HR `:5132` | `/leave-applications` | 勤怠・休暇申請 | `P2-` | (thin) |
| M03 | HR `:5132` | `/onboarding` | 入社手続き | `P3-` | **入社チェックリスト（新卒バッチ処理） (270)** |
| M04 | HR `:5132` | `/social-insurance` | 福利厚生申請 | `P5-` | 育児休業規程 (32), 家族手当規程 |
| M05 | 財務会計システム `:5133` | `/payroll-items` | 請求書承認・経費精算 | `P6-` | **月次定額取引先一覧 (145)** |
| M06 | 財務 `:5133` | `/onboarding` | 支払処理 | `P7-` | 業務委託給与規程 (262) |
| M07 | 財務 `:5133` | `/leave-applications` | 経費承認（管理職） | `P9-` | 接待交際費規程 (216) |
| M08 | 財務 `:5133` | `/resident-tax` | 発注管理 | `P10-` | 新規取引先登録手続き (59) |
| M09 | 受発注在庫管理システム `:5134` | `/payroll-items` | 在庫管理 | `P11-` | 在庫調整メモ (58, operator output) |
| M10 | 受発注 `:5134` | `/leave-applications` | 契約管理 | `P12-` | **契約解除手続き (483), 新規契約手続き (192)** |
| M11 | 受発注 `:5134` | `/social-insurance` | IT申請 | `P13-` | 管理者権限申請手続き (24) |

**Every module has its own semantically matching governing document.** Eleven independent
confirmations, not one example generalised.

**The shape of the work is the same in all eleven.** Select a queue row, open the governing
document, paste a short Japanese justification (median 42 characters) into the module's note field,
click the module's confirm button, and the row's status changes. Evidence: 633 row-selection `td`
clicks against 629 confirm clicks; **all 608 form inputs are pastes with `value: null`**; no free
text is typed anywhere in Dataset B.

**This is not data entry. It is document-governed review-and-disposition.**

---

## 4. Methodology

### 4.1 The corrected pipeline

```
FROZEN Step-1 executions (183)
      |
      v  re-key on evidence Step 1 already preserved, not on its display label
MODULE ATTRIBUTION      dominant (origin, route) of the execution's blocks
      |                 + module identity read from screenshots
      v
IDENTITY QUALITY        per-execution module purity; modules-touched count
      |
      v
QUANTITATIVE INVENTORY  explicit denominators: executions / dispositions / events
      |
      v
HARD GATES              evidence . identity . business-work . target surface
      |
      v
VALUE  .  FEASIBILITY  .  VARIABILITY     three separate readings, never summed
      |
      v
MODALITY SELECTION      per candidate, argued
      |
      v
SHORTLIST -> flagship -> Step 3 scope
```

### 4.2 The specific guards, and what each prevents

| Guard | Prevents | Mechanism |
|---|---|---|
| Module identity = `(origin, route)` **verified by screenshot** | **route-as-process** | No module enters the inventory without a screenshot showing URL + breadcrumb + nav item |
| Never aggregate on a Step-1 label string | repeating the exact previous failure | Aggregation key is the module, derived from origin-qualified surfaces |
| Cell content over column header | **UI-label-as-truth** | Headers demonstrated wrong on M06 |
| System badges recorded as *system labels* | badge-as-ground-truth | 種別 shown not to follow its own written rule (§8.3) |
| Three denominators named separately | **telemetry-count-as-business-volume** | Executions, dispositions and events reported side by side; dispositions/execution published |
| Automatability proxy, not frequency | **frequency-only ranking** | Adapted from Robidium's RAI; §4.3 |
| No composite score anywhere | **false precision** | Gates are binary; value and feasibility are reported, never summed |
| `UNAVAILABLE` is a value | **unsupported ROI** | Three columns in the inventory CSV carry it literally |
| Task mining != process mining, stated | discipline confusion | We have no case id, so we are doing task mining, and we say so |
| AI must clear the six-part test in §12 | **AI-because-it-is-an-AI-assignment** | Three of five AI candidates are rejected there |

### 4.3 Deviation from the published method, declared

We rank in part on an **automatability proxy** adapted from Robidium's *Routine Automatability
Index* (Leno et al.). RAI as published is the ratio of actions whose **value** is computable from
prior actions' values. **Dataset B has no values** — every form input is `value: null` and every
clipboard event is `text_content: null`. RAI as published is therefore not computable.

Our proxy classifies each recorded interaction inside an execution as **DERIVABLE** (a paste, or a
clipboard capture — the value has an observed source), **STRUCTURAL** (an action on a recovered
element id, or a keystroke inside the instrumented browser), **NAVIGATIONAL** (a browser navigation
or application switch), or **OPAQUE** (anything in an uninstrumented application, a scroll, or a
click with no element identity). The proxy is `(DERIVABLE + STRUCTURAL + NAVIGATIONAL) / all`.

**This is a structural proxy, not RAI.** It measures how much of the observed work happens on a
surface a deterministic agent could address. It does **not** measure whether a value is derivable,
because we cannot see values. The deviation is stated here so that no reader mistakes it for the
published measure.

---

## 5. Process inventory
> ### ⚠ SUPERSESSION NOTICE — 2026-09-18 (Phase 3.5, ADR-022)
>
> **The module inventory in this section is affected by a key defect found after it was
> written, and the per-module execution counts below should be read as ranges, not values.**
>
> `analysis/evidence/module_key_reconcile.py` established that the `(origin, route)` key used
> throughout this document is **wrong about the displayed screen in 21% of captures**. The
> screen header and the record-id prefix agree with each other on 2,904 of 2,904 comparable
> records (100.0%); the URL agrees with them on 78.6% / 79.1%, and every one of the 552
> disagreements is the URL dissenting alone. The cross-module-queue-view explanation was tested
> and **refuted**: 33 captures mix record-id prefixes, and 0 of them cross a module boundary.
>
> Two consequences for the text below, neither of which is edited out:
>
> 1. **All 12 module rows change execution count between keys.** `LO 契約管理` is 26 executions
>    under the URL key and 8 under the record-prefix key; `FI 請求書承認・経費精算` is 25 vs 21.
>    The spread is coverage, not noise — the prefix key can only assign the 107 of 183
>    executions that contain an extracted record, against the URL key's 165.
> 2. **A module is missing entirely.** `FI|予算差異分析` is declared on screen in 11 captures and
>    carries 132 record rows under prefix `P8` at purity 1.00, and has no entry in the
>    `(origin, route)` map — 12 modules on screen against 11 in the map.
>
> The original text is retained unchanged below. See `docs/STEP2_MODULE_KEY_RECONCILIATION.md`
> and ADR-022. The hypothesis this document's §12 rests on is separately refuted — see
> `docs/STEP2_HYPOTHESIS_VERIFICATION.md`.



Full detail: `docs/STEP2_PROCESS_INVENTORY.csv`. Time shares are of 7,642.7 s of measured segmented
activity; **durations are relative comparisons only** — the README states waiting time is compressed
in the capture environment.

| ID | Module | exec | sess | ops | % time | median s | IQR/med | **disp** | disp/exec | s/disp | purity | multi-mod | A-proxy |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **M10** | LO 契約管理 | 26 | 8 | 4 | **15.19** | 31.3 | 1.10 | 65 | 2.50 | 17.9 | 0.85 | 10/26 | 0.501 |
| **M01** | HR 経費精算・給与変更 | 20 | **10** | 4 | 14.33 | 44.1 | **0.48** | **87** | 4.35 | **12.6** | 0.82 | 8/20 | 0.547 |
| **M05** | FI 請求書承認・経費精算 | 25 | 8 | 4 | 12.25 | 35.3 | 0.61 | 52 | 2.08 | 18.0 | 0.88 | 8/25 | 0.436 |
| — | *(no business module)* | 18 | 7 | 4 | 10.18 | 29.6 | 1.70 | 3 | 0.17 | — | 0.00 | 0/18 | 0.341 |
| **M03** | HR 入社手続き | 23 | 8 | 4 | 9.32 | 29.1 | 0.46 | 42 | 1.83 | 17.0 | **0.90** | 6/23 | 0.551 |
| **M08** | FI 発注管理 | 13 | 8 | 4 | 8.18 | 38.7 | 0.55 | 52 | 4.00 | 12.0 | 0.69 | 9/13 | 0.559 |
| **M09** | LO 在庫管理 | 13 | 6 | 4 | 7.55 | 41.3 | 0.86 | 40 | 3.08 | 14.4 | 0.76 | 7/13 | 0.489 |
| **M04** | HR 福利厚生申請 | 10 | 4 | 3 | 6.06 | 45.1 | 0.76 | 33 | 3.30 | 14.0 | 0.74 | 7/10 | 0.604 |
| **M07** | FI 経費承認（管理職） | 10 | 3 | 2 | 5.16 | 38.2 | 0.56 | 22 | 2.20 | 17.9 | 0.89 | 4/10 | 0.493 |
| **M11** | LO IT申請 | 9 | 5 | 4 | 5.08 | 34.3 | 0.61 | 29 | 3.22 | 13.4 | **0.94** | **1/9** | 0.560 |
| **M06** | FI 支払処理 | 9 | 5 | 3 | 4.13 | 31.1 | 0.98 | 17 | 1.89 | 18.6 | **0.94** | **1/9** | 0.429 |
| **M02** | HR 勤怠・休暇申請 | 7 | 4 | 2 | 2.56 | 23.1 | 0.52 | 14 | 2.00 | 14.0 | 0.81 | 2/7 | **0.618** |

Totals: **183 executions · 456 in-segment dispositions · 7,642.7 s · 15 sessions · 4 operators.**

### 5.1 How the previous labels map onto the modules

`docs/STEP2_LABEL_MODULE_CONFUSION.csv`. The Step-1 *clusters* are good; the Step-1 *names* are not.

| Step-1 label | n | Dominant module | share |
|---|---:|---|---:|
| `onboarding__p03` | 21 | HR 入社手続き | **1.00** |
| `payroll-items__p01` | 24 | FI 請求書承認・経費精算 | 0.92 |
| `leave-applications-social-insurance__p00` | 27 | **LO 契約管理** | 0.89 |
| `leave-applications-resident-tax__p10` | 7 | FI 発注管理 | 0.86 |
| `leave-applications-onboarding__p06` | 12 | FI 経費承認（管理職） | 0.83 |
| `leave-applications-payroll-items__p11` | 6 | HR 勤怠・休暇申請 | 0.83 |
| `onboarding__p07` | 11 | **FI 支払処理** | 0.82 |
| `payroll-items__p05` | 13 | **HR 経費精算・給与変更** | 0.77 |
| `social-insurance__p04` | 16 | LO IT申請 | **0.50** |
| `resident-tax__p02` | 23 | *(none)* | **0.26** |
| `hr人事給与システム__p09` | 9 | *(no business module)* | 1.00 |

Eight of eleven clusters are 0.77-pure or better against a business identity Step 1 never saw. Two —
`resident-tax__p02` (0.26) and `social-insurance__p04` (0.50) — are genuine over-merges. **Step 1
performed better than the previous Step 2 gave it credit for.**

---

## 6. Quantitative analysis

**Effort per record is remarkably stable.** Seconds per disposition ranges **12.0–18.6** across all
eleven modules. Seconds per *execution* ranges 23–45. The per-record figure is the more useful
comparison and the less denominator-sensitive one.

**Operator spread.** Seven modules involve all four operators. M07 and M02 involve two. Concentration
(largest single session's share of a module's executions) ranges from **0.15** (M08, most evenly
spread) to **0.54** (M09 — over half its executions come from one session, which is thin evidence).

**Fragmentation.** 102 executions touch exactly one business module; 48 touch two; 15 touch three;
18 touch none. Modules differ sharply: M11 and M06 have 1 of 9 executions touching a second module;
M08 has 9 of 13.

**What is not computed.** Business volume, monetary value, error rate, FTE saving, criticality —
`UNAVAILABLE` in the CSV. Telemetry counts are not converted into business volumes anywhere.

**Interruptions.** 18 executions resolve to no business module at all, consuming 10.18% of measured
time at a dispersion of 1.70 — the highest in the dataset. That is desktop work (Word, Excel,
terminal, portal roots) that the pipeline correctly declines to call a business process.

---

## 7. Automation suitability

No weighted score. Four separate readings.

### 7.1 Hard gates (binary)

| Gate | Rule | Rationale |
|---|---|---|
| **G1 Evidence sufficiency** | `executions >= 10 AND sessions >= 5 AND operators >= 3` | Below 10 executions is under 5.5% of the dataset; under 3 operators cannot distinguish a process from one person's habit. Comparable in spirit to UiPath Unassisted's published "significant tasks" floor |
| **G2 Identity sufficiency** | `mean module purity >= 0.75` | **New, and the direct lesson of the previous failure.** If the executions attributed to a module are not mostly about that module, every downstream number describes a mixture |
| **G3 Business work** | `dispositions per execution >= 1 AND a governing document identified` | Separates work from navigation |
| **G4 Observable target** | `>= 1 recovered element id` | Nothing to target otherwise |
| **G5 Decision-input observability** | Are the inputs the decision depends on present on the record? | **Added after reading an M10 detail pane (§8.4).** A process whose deciding input is invisible can have its *mechanics* automated but not its *decision* |

**Results.**

| Module | G1 | G2 | G3 | G4 | Outcome |
|---|---|---|---|---|---|
| M10 契約管理 | pass 26/8/4 | pass 0.85 | pass 2.50 | pass | **PASS** |
| M01 経費精算・給与変更 | pass 20/10/4 | pass 0.82 | pass 4.35 | pass | **PASS** |
| M05 請求書承認・経費精算 | pass 25/8/4 | pass 0.88 | pass 2.08 | pass | **PASS** |
| M03 入社手続き | pass 23/8/4 | pass 0.90 | pass 1.83 | pass | **PASS** |
| M09 在庫管理 | pass 13/6/4 | pass 0.76 | pass 3.08 | pass | **PASS** (marginal — see §8) |
| M08 発注管理 | pass 13/8/4 | **FAIL 0.69** | pass 4.00 | pass | **FAIL — identity** |
| M04 福利厚生申請 | **FAIL 4 sessions** | fail 0.74 | pass | pass | **FAIL — evidence** |
| M07 経費承認（管理職） | **FAIL 3 sessions, 2 operators** | pass 0.89 | pass | pass | **FAIL — evidence** |
| M11 IT申請 | **FAIL 9 executions** | pass 0.94 | pass | pass | **FAIL — evidence (by one)** |
| M06 支払処理 | **FAIL 9 executions, 3 operators** | pass 0.94 | pass | pass | **FAIL — evidence (by one)** |
| M02 勤怠・休暇申請 | **FAIL 7/4/2** | pass 0.81 | pass | pass | **FAIL — evidence** |
| *(unassigned)* | pass | fail 0.00 | **FAIL 0.17** | — | **FAIL** |

**G5 applied to the gate-passers.** M05 **passes**: vendor, amount and INV number are all on the
record, and the governing rule is written down. M10 **fails**: its detail pane carries 管理ID, 社員ID,
申請種別, 期間, 所属部署, ステータス and a named reference document — **but no contract value**, which is
the input 新規契約手続き §3's approval-authority rule needs (§8.4). M03 **partially passes**: 入社日,
部署 and 照合項目数 are visible, but the attributes that drive the two conditional checklist items
(career-changer status, family-allowance eligibility) are not. M01 and M09: **unknown** — no detail
pane was read.

**Consequence.** G5 does not eliminate a candidate; it determines **how far automation can go**.
Where G5 fails, automation may prepare, assemble and present, but the human must decide.

**Two gate failures deserve stating plainly.** M11 IT申請 and M06 支払処理 have the **highest identity
purity in the dataset (0.94)** and the cleanest footprints (1 of 9 executions touching a second
module), and they fail only on execution count — by one. They are not unsuitable; they are
under-observed. M08 発注管理 has the best operator spread of any module and fails on identity, which
is a statement about our measurement, not about the work.

### 7.2 Value

Not summed. Read together.

| Module | Time share | Dispositions | Operators | Sessions | Concentration | Reading |
|---|---:|---:|---:|---:|---:|---|
| M10 | **15.19%** | 65 | 4 | 8 | **0.23** | Largest, most evenly spread |
| M01 | 14.33% | **87** | 4 | **10** | 0.25 | Most records, widest session presence |
| M05 | 12.25% | 52 | 4 | 8 | 0.20 | Large and evenly spread |
| M03 | 9.32% | 42 | 4 | 8 | 0.30 | Solid |
| M09 | 7.55% | 40 | 4 | 6 | **0.54** | **Half from one session — weak** |

### 7.3 Feasibility

| Module | Input structure | Target stability | Systems | A-proxy | Documentation | Reading |
|---|---|---|---|---:|---|---|
| M10 | Queue + 5 contract types | 1 origin, `la-note`/`btn-la-ok` | 1 + Word | 0.501 | **2 手続き read in full; explicit ¥1M/¥30M authority rule** | Good |
| M01 | Queue mixing `P1-`/`P4-` | 1 origin, `pi-note` | 1 + Word | 0.547 | 規程 not read | Good, but the P1/P4 question is open |
| M05 | Queue + 5-row reference table | 1 origin, `pi-note` | 1 + Word | **0.436** | **一覧 read in full, contains a written rule** | Best rule, most Word time |
| M03 | Queue + 7-item checklist | 1 origin, `ob-note` | 1 + Word (**2 apps only**) | 0.551 | **Checklist read in full** | Best |
| M09 | Queue + operator memo | 1 origin, `pi-note` | 1 + Notepad | 0.489 | No external document | Weak — the "reference" is the operator's own output |

### 7.4 Variability — and what kind it is

Variance is not automatically bad.

| Module | IQR/median | Diagnosis |
|---|---:|---|
| M03 | **0.46** | **Legitimate, low.** One document, one queue, conditional item count 4 or 5 |
| M01 | 0.48 | **Legitimate business variants** — `P1-` expense claims vs `P4-` payroll changes |
| M05 | 0.61 | **Legitimate + exception** — 定常 vs 調整 records take different effort |
| M09 | 0.86 | **Evidence insufficiency** — concentration 0.54 |
| M10 | **1.10** | **Legitimate business variants** — 5 contract types x 4 actions (解除/新規締結/変更/更新), each governed by a different 手続き. The dispersion *is* the process |
| M08 | 0.55 | **Exception handling** — ⚠ rows are deferred; `rt-note` comments are the dataset's longest (median 54 chars vs 30–46) |
| *(unassigned)* | 1.70 | **Process instability / not a process** |

**The previous analysis treated variance as a disqualifier.** On the corrected evidence, the highest
variance among gate-passing candidates (M10) is the clearest case of *legitimate business variants* —
a reason to build a definition-driven engine, not a reason to reject the candidate.

### 7.5 Modality

| Module | Appropriate intervention | Why |
|---|---|---|
| **M10 契約管理** | **HITL decision support + deterministic execution** | The decision is which 手続き governs and whether the value clears the authority threshold. The rule is in prose and the client edits it; the execution is a note and a button |
| **M01 経費精算・給与変更** | Same, after the P1/P4 question is answered | Two record families may need two definitions |
| **M05 請求書承認・経費精算** | Same, **conditional on validating the badge** | The written rule and the system's own label disagree (§8.3) |
| **M03 入社手続き** | **Deterministic rules engine + verification** | Only two of seven checklist items are conditional. This mostly does not need AI |
| **M11 IT申請** | **Deterministic rules engine — no AI** | Approver routing is a pure lookup, fully visible: システム権限→情報セキュリティ委員会, ICカード再発行→総務部, PC新規発行/VPN→情報システム部, ソフトウェアライセンス→部門長+情報システム部 |
| **M08 発注管理** | **No automation yet — investigate** | We do not know what ⚠ means |
| **M09 在庫管理** | **No automation** | Insufficient evidence; the only "reference" is the operator's own memo |
| **M02, M04, M06, M07** | **Defer** | Failed the evidence gate. Not unsuitable — under-observed |
| *(unassigned)* | **Process redesign, or nothing** | 10% of measured time that is not a business process |

**API/integration is not ruled out for any of these.** Nothing in the telemetry indicates the
presence or absence of an import or API path, and observing staff use a browser is not evidence that
no other interface exists. UI automation is the defensible default **under present uncertainty**,
which makes a swappable target adapter an architectural requirement rather than a caveat.

---

## 8. Variants and exceptions

### 8.1 Variants are real, and they are the design requirement

M10 契約管理 shows **5 contract types x 4 actions**: 業務委託契約（解除）, 秘密保持契約（新規締結）,
売買契約（変更）, 取引基本契約（新規締結）, 保守委託契約（更新）. Each action has a governing 手続き
document, and the operator is observed opening the matching one — 契約解除手続き co-occurs 483 times,
新規契約手続き 192 times.

M01 shows two record families in one queue: `P1-` expense claims (接待交際費 / 研修費 / 消耗品費) and
`P4-` payroll changes (扶養控除変更 / 残業手当調整 / 役職手当廃止・新設). **Whether these are one process
or two is unresolved** and it changes the scope of any M01 automation.

M03 shows a conditional checklist: seven 照合項目 of which two are conditional —
雇用保険被保険者証（**転職者のみ**） and 扶養控除等申告書（**家族手当対象者確認**）. The system publishes
照合項目数 as 4 項目 or 5 項目 per record.

### 8.2 Exceptions are observable in behaviour, not just in state

On M08 発注管理, two of twelve purchase orders carry a red ⚠ marker beside the vendor name. Across one
session the module badge fell **12 → 11 → 5** while **both flagged rows stayed 未確認**. The operator
cleared the clean work and deferred the flagged work. `rt-note` comments on this module are the
longest in the dataset (median pasted length 54 characters against 30–46 elsewhere), consistent with
writing an explanation rather than a confirmation.

**We do not know what ⚠ means.** No detail pane for a flagged row was read. Any automation here must
be able to abstain.

### 8.3 The exception that matters most: a system label that contradicts its own rule

`月次定額取引先一覧` states the rule verbatim:
「受領した請求書の INV 番号・金額・取引先名をこの一覧と照合すること。**差異がある場合は要確認として保留する**」
— match INV number, amount and partner name against this list; on a discrepancy, hold as requiring
confirmation.

The list gives 株式会社山田製作所 at 月額 385,000 円. The queue contains two invoices from that vendor:
**393,384 badged 定常** and **374,313 badged 調整**. Both differ from the listed amount; only one is
flagged. Either an unstated tolerance exists, or 種別 is not a function of this rule.

Further: three queue vendors (福岡システム設計, 沖縄物流センター, 北陸部品工業株式会社) are **absent from
the list entirely**, and the list contains 北陸電子部品 while the queue contains 北陸部品工業株式会社 —
different strings that may or may not be the same legal entity.

**Consequence for Step 2:** the 種別 badge is a system label and **must not be used as ground truth
for business correctness.** It may be used as a weak reference signal with the disagreements
inspected individually, never averaged away.

### 8.4 What an M10 detail pane actually shows — and how it changed this analysis

Late in the re-analysis one 契約管理 detail pane was read (`scr_smart_1782924528912`). It changed two
conclusions, and both changes are against the direction the analysis was heading.

The pane shows: 管理ID `P12-07010448-002` · 社員ID `V3007` · 申請種別 取引基本契約（新規締結） ·
期間 2026-07-05 · 所属部署 新規締結 · ステータス 処理待ち · a highlighted reference line
**「参照：参照書類：`shinkui_keiyaku_tetsuzuki.docx`」** · a 承認コメント textarea containing
「契約管理処理。種別：取引基本契約（新規締結）。期日：2026-07-05。関連書類確認済み。」 · and **two buttons,
✓承認 and ✕差戻し.**

**Change 1 — the system names the governing document itself.** We had treated "which 手続き governs
this record" as an inference problem, corroborated by 483 co-occurrences of 契約解除手続き with M10.
It is not an inference problem: the record carries the filename. That corroborates the module-document
pairing beautifully **and removes the AI task we had proposed for it** (§12). Document selection here
is a lookup, not a judgement.

**Change 2 — the comment is a template, and the deciding input is absent.** The pasted comment is
`契約管理処理。種別：{申請種別}。期日：{期間}。関連書類確認済み。` — every field is already on the record. And
critically, **there is no 金額 anywhere in the pane.** 新規契約手続き §3 sets approval authority by
contract value (100 万円未満 → 部門長; 100 万円以上 → 役員; 3000 万円以上 → 取締役会). **That value is not
visible in the system.** We can therefore reproduce M10's *mechanics* exactly, and we cannot
reproduce its *decision* at all.

This is what motivated gate **G5** (§7.1). It is also a direct application of Rule 2 — do not trust
your own first interpretation — and it is recorded here rather than quietly absorbed.

---

## 9. External peer review

Full review: `docs/STEP2_PEER_REVIEW.md`. Four conclusions that changed this analysis.

**9.1 We are doing task mining, not process mining, and we should say so.** UiPath, Power Automate
and Apromore all require `Case_ID` as a mandatory input field for process mining. We have no case id
and cannot derive one — values are redacted. Every commercial task-mining product either requires an
SME to nominate the task first (UiPath, Celonis, OpenAdapt) or requires a per-project configuration
rule to synthesise a case id (Apromore). **Our Step 1 attempts what the academic Robotic Process
Mining literature names as an open problem.** That is defensible; pretending it is novel is not.

**9.2 Frequency is the wrong ranking criterion, and we were using it.** The RPM literature offers
the *Routine Automatability Index* — the ratio of a routine's automatable actions — and ranks on
that. Our previous Step 2 ranked on frequency plus a route-similarity determinism proxy. We now
report an automatability proxy per module (§4.3), with the deviation from the published measure
declared.

**9.3 Everyone who does semantics well uses screenshots; we used a URL.** UiPath clusters
screenshots, Celonis and Apromore capture them optionally, OpenAdapt captures DOM and accessibility
trees and OCR. Our previous Step 2 derived business semantics from route strings and never opened
one of the 4,746 available screenshots. **That is the reinvention that went badly.**

**9.4 One documented anti-pattern to avoid.** Apromore fills null case ids with "the Case ID value
of the prior events or subsequent events" — forward/backward imputation that manufactures structure.
Nothing in our pipeline should do anything analogous.

**A Step-1 validation gap, recorded not acted on.** PM4Py ships `correlation_mining`, implementing
Pourmirza, Dijkman & Grefen (2017) — a published algorithm for mining process models **without case
identifiers**. We have not benchmarked Step 1 against it. Step 1 is frozen, so this is recorded as a
known gap in our evidence, not a change request. It is the single strongest thing a reviewer could
ask us for.

---

## 10. Candidate comparison

`docs/STEP2_CANDIDATE_MATRIX.csv`. Gate-passing candidates only.

| | **M10 契約管理** | **M01 経費精算・給与変更** | **M05 請求書承認** | **M03 入社手続き** | M09 在庫管理 |
|---|---|---|---|---|---|
| Evidence | 26 exec / 8 ses / 4 ops | 20 / 10 / 4 | 25 / 8 / 4 | 23 / 8 / 4 | 13 / 6 / 4 |
| Observed frequency | 65 dispositions | **87** | 52 | 42 | 40 |
| Observed effort | **15.19%** of time | 14.33% | 12.25% | 9.32% | 7.55% |
| Repeatability (purity) | 0.85 | 0.82 | 0.88 | **0.90** | 0.76 |
| Variance | 1.10 — **legitimate variants** | 0.48 — legitimate | 0.61 — legitimate + exception | **0.46** | 0.86 — thin evidence |
| Human judgement | Which 手続き + authority threshold | Amount vs 規程 | 承認 vs 保留 on discrepancy | Conditional item selection | Adjustment classification |
| Structuredness | Queue + typed contract actions | Queue, two record families | Queue + 5-row table | Queue + 7-item checklist | Queue |
| Target stability | `la-note`/`btn-la-ok` | `pi-note`/`btn-pi-ok` | `pi-note`/`btn-pi-ok` | `ob-note`/`btn-ob-ok` | `pi-note` |
| Systems | 1 + Word | 1 + Word | 1 + Word | 1 + Word (**2 apps**) | 1 + Notepad |
| Exception profile | Not directly observed | Not observed | 定常/調整 badge; badge contradicts rule | 4 vs 5 item records | 定常/調整 badge |
| Modality | HITL decision support | HITL decision support | HITL, **after validation** | Deterministic rules + verification | None |
| AI relevance | **High** — document routing + threshold extraction | Medium | **High** — entity resolution | **Low** — mostly deterministic | None |
| Validation mechanism | Contract action is visible in the queue | P1/P4 split is visible | 種別 badge (weak) | **照合項目数 — free label** | None |
| Risk | Contract values not visible in list view | P1/P4 may be two processes | Badge contradicts the written rule | May be too simple to matter | One session dominates |
| Unknowns | Is the 手続き set complete? | One process or two? | Tolerance; entity identity | Are conditions only the two? | What the memo contains |

---

## 11. Selected opportunity

### 11.1 The selection

**Flagship opportunity: M10 · 契約管理 — contract management, 受発注在庫管理システム.**
**Flagship *decision* candidate: M05 · 請求書承認・経費精算 — invoice approval, 財務会計システム.**

The split is not indecision; it is what §8.4 forces. **M10 is the largest opportunity and the most
mechanically automatable module in the dataset** — the system names the reference document, the
comment is a fillable template, and the action is one of two buttons. But **its deciding input is not
observable**, so a system can prepare every record and cannot decide any of them. **M05 is the only
module where the decision itself is reproducible** from inputs on the record plus a rule we have read.

**Step 3 scope: one definition-driven engine, two definitions — M10 (prepare-and-present, no AI) and
M05 (propose-and-validate, bounded AI).** M03 入社手続き is the reserve third definition; it carries
the only free evaluation label in the dataset (照合項目数).

### 11.2 Why M10, argued rather than scored

- **Largest measured opportunity.** 15.19% of measured segmented time, the highest of any business
  module. 26 executions, 65 dispositions.
- **Best evidence spread of the large candidates.** Four operators, eight sessions, and the
  lowest-but-one concentration (0.23) — no single session or person dominates it. This is the
  strongest available evidence that it is an organisational process rather than one person's habit.
- **Its rule is written down and we have read it.** 新規契約手続き §3 states approval authority by
  contract value: 100 万円未満 → 部門長承認; 100 万円以上 → 役員承認; 3000 万円以上 → 取締役会決議. That is
  a machine-checkable rule that currently lives in a Word file.
- **Its variants are legitimate and typed.** Five contract types crossed with four actions, each
  routed to a specific 手続き document. The IQR/median of 1.10 is that structure, not noise — and
  it is precisely the case for a definition-driven engine rather than a single script.
- **The operator's document use is observable, matches, and is confirmed by the system itself.**
  契約解除手続き co-occurs 483 times and 新規契約手続き 192 times with M10 executions, and the record's
  own 参照書類 field names the file (§8.4).
- **Its mechanics are fully determined.** Reference document named by the system; comment a template
  over fields already on the record; action one of two buttons. Nothing here needs to be guessed.

**And the limit, stated in the same breath:** the contract value that 新規契約手続き's authority rule
keys on is **not present in the system** (§8.4). M10 therefore supports *preparation* automation
with a human decision, not decision automation. That is a smaller claim than the previous Step 2
made for its flagship, and it is one we can actually support.

### 11.3 Why not the others

- **M01** has the most dispositions (87) and the widest session presence (10) and is a genuine
  second choice. It is not first because its queue mixes two record families (`P1-` expense claims,
  `P4-` payroll changes) and we cannot tell whether that is one process or two. Answering that
  question could promote it.
- **M05** is **promoted to the decision candidate** on the strength of G5. It is the only module
  where every input the written rule needs — vendor, amount, INV number — is visible on the record,
  and where the rule itself has been read verbatim. Its weakness is real and stated: **its own 種別
  badge contradicts that rule** (§8.3), so the first thing any M05 automation must do is surface the
  disagreements rather than average over them.
- **M03** is the best-evidenced module in the dataset (purity 0.90, lowest dispersion, 21/21 cluster
  agreement) and carries the only free evaluation label (照合項目数). It is *not* the flagship because
  only two of seven checklist items are conditional, so the decision content is thin. It is the
  **ideal second definition**: it proves the engine generalises and it can be scored without
  hand-labelling.
- **M09** passes the gates marginally and is rejected on evidence: 54% of its executions come from a
  single session, and its only "reference document" is a Notepad memo the operator writes.
- **M08** would be a strong candidate — best operator spread in the dataset, a visible exception
  mechanism — but it **fails the identity gate at 0.69 purity**, and we do not know what its ⚠
  marker means. It is the top candidate for the next round of evidence gathering.

### 11.4 Priority order for the client

1. **M10 契約管理** — largest, best-spread, richest documented rule.
2. **M01 経費精算・給与変更** — most records and fastest per record (12.6 s), pending the P1/P4 question.
3. **M05 請求書承認・経費精算** — clearest rule, blocked on one validation question.
4. **M03 入社手続き** — smallest of the four but the most verifiable; recommended as the second build.
5. **M11 IT申請 / M06 支払処理** — highest identity purity in the dataset, failing the evidence gate by
   one execution each. **Collect more data before deciding.**
6. **M08 発注管理** — investigate the ⚠ semantics first.
7. Everything else — defer.

**No monetary ROI, FTE saving or business volume is claimed for any of these.**

---

## 12. AI opportunity
> ### ⚠ SUPERSESSION NOTICE — 2026-09-18 (Phase 5)
>
> **The hypothesis underlying this section is REFUTED.** `docs/STEP2_HYPOTHESIS_VERIFICATION.md`
> establishes that operators were not observed applying recoverable rules to record variables:
> 0 of 225 observed dispositions were negative, 0 backward status transitions occurred over
> 25,495,968 characters of telemetry, and the deciding variable (金額) is absent from 91–99% of
> records on four modules. There is no supervision signal for a decision function.
>
> What survives is **document-referenced confirmation work** (H3, SUPPORTED in 10/11 modules).
> The revised target is in `docs/STEP3_TARGET_REFRAME.md`, where a deterministic lookup table
> reaches 64.2% on the retrieval sub-task and **AI is not justified on current evidence**.
>
> The original text is retained unchanged below.



Six-part test, applied to each candidate role. AI is justified only if deterministic rules are
insufficient or brittle; there is real ambiguity; the output can be evaluated; it can be bounded by
deterministic validation and human control; it materially changes the system; and it can be
demonstrated.

| # | Candidate AI role | Verdict |
|---|---|---|
| 1 | **Document selection** — given a contract action, choose the governing 手続き | **REJECTED after §8.4.** We proposed this as an AI task. The record's 参照書類 field **names the file**. It is a lookup. This is the clearest example in the analysis of AI failing to earn its place |
| 1b | **Clause retrieval + citation** — having the document, locate and quote the clause that applies | **ACCEPT, narrowly.** Selecting the document is free; finding the governing paragraph inside a multi-section 手続き and quoting it verbatim is not, and it is checkable by substring |
| 2 | **Threshold extraction** — parse 「100 万円未満：部門長承認…」 into an evaluable expression | **ACCEPT for M05-style rules; NOT APPLICABLE to M10** — the value the M10 threshold keys on is not in the system (§8.4). The model extracts; **code evaluates** |
| 3 | **Entity resolution** (M05) — resolve 北陸部品工業株式会社 against a list containing 北陸電子部品, or abstain | **ACCEPT.** Genuinely ambiguous; abstention is the correct answer for out-of-list vendors and is directly measurable |
| 4 | **Semantic interpretation of screen content** — recovering business identity from screenshots | **ACCEPT for analysis, not for execution.** This is what the previous Step 2 lacked. It belongs in the discovery pipeline, not the runtime |
| 5a | Japanese comment drafting | **REJECTED for M10, downgraded generally.** The observed M10 comment is `契約管理処理。種別：{申請種別}。期日：{期間}。関連書類確認済み。` — a string template over fields already on the record. A template does this; a model is not needed |
| 5b | Decision proposal (M05 only) | **ACCEPT, bounded.** Propose 承認 or 保留 with the cited clause and the computed delta; a human approves each one |
| 6 | Exception classification (M08 ⚠) | **REJECT — unevaluable.** We do not know what the flag means, so no classification can be scored |
| 7 | Approver routing (M11) | **REJECT — a lookup.** The mapping is fully visible in twelve rows |
| 8 | Checklist applicability (M03) | **REJECT as AI; ACCEPT as deterministic rules** — two conditional items out of seven |
| 9 | Natural-language process configuration | **REJECT.** No evidence anyone configures anything |
| 10 | **UI execution by an agent** | **REJECT.** WorkArena: GPT-4 42.7%, open-source SOTA 17.9% on enterprise form filling. A deterministic selector path either works or fails visibly |

**Net: five of eleven candidate AI roles survive, and two were killed by a single screenshot.**
The honest summary is that **most of this workload is deterministically automatable and AI's role in
it is small** — confined to entity resolution, clause retrieval, threshold parsing, a bounded
decision proposal on one module, and screenshot interpretation in the discovery pipeline. That is a
smaller AI claim than an AI-engineering assignment might invite, and it is the one the evidence
supports.

### 12.1 The bounded architecture

```
record (typed)  ->  retrieve governing clause  ->  [ MODEL ]  ->  typed proposal
                                                      |
                    may: read, match, cite, phrase ---+
                    may NOT: compute, decide the rule, click, write
                                                      |
                                                      v
                                          +------------------------+
                                          |  DETERMINISTIC         |
                                          |  VALIDATOR             |
                                          |  - clause is a verbatim|
                                          |    substring?          |
                                          |  - thresholds evaluated|
                                          |    in code             |
                                          |  - rule OVERRIDES the  |
                                          |    model on conflict   |
                                          |  - abstention forced   |
                                          |    below threshold     |
                                          +-----------+------------+
                                                      v
                                            HUMAN APPROVAL
                                       accept / edit(+reason) / reject
                                                      v
                                    TARGET ADAPTER (interface)
                                    UI driver today, import/API tomorrow
                                                      v
                          AUDIT: definition version, model + prompt version,
                          clause, proposal, verdict, approver, change reason
```

**Per AI role: input, output, validation, approval, executor, audit, abstention.**

| Role | AI input | AI output | Deterministic validation | Human approval | Executor | Abstention condition |
|---|---|---|---|---|---|---|
| Rule retrieval | Record + document corpus | `{document_id, cited_clause, basis}` | Clause must be a verbatim substring of the named document | Yes, per record | n/a | No document matches the contract action |
| Threshold extraction | Document text | `{condition_expr, source_line}` | Expression must parse **and be evaluated by code, never by the model** | One-time review, then versioned | n/a | Expression does not parse |
| Entity resolution | Vendor string + reference list | `{matched_row \| null, basis, evidence}` | Match must exist in the list; arithmetic recomputed in code | Yes | n/a | Similarity below a declared threshold |
| Comment drafting | Validated proposal | `{comment_ja}` | Length and template conformance | Yes, editable, edits captured with a reason | n/a | n/a |
| Execution | — | — | — | Required | **Deterministic driver over recovered selectors** | n/a |

**The inversion that makes this safe: where the model and the written rule disagree, the rule wins.**
Code overrides the model, never the reverse.

---

## 13. Risks and unknowns

| # | Risk | Severity | Evidence it is real |
|---|---|---|---|
| R1 | **The module map is derived from a sample of screenshots.** 20 of 4,746 were read | High | Four `(origin, route)` pairs are marked *inferred* in the forensic document and nothing depends on them |
| R2 | **Only 72.5% of dispositions fall inside a Step-1 execution** | High | Measured. Every per-module figure understates activity |
| R3 | The 種別 badge contradicts its own written rule | **Observed** | §8.3 |
| R4 | Two Step-1 clusters are genuine over-merges (purity 0.26, 0.50) | **Observed** | §5.1. Their executions are redistributed, which is why M08 fails the identity gate |
| R5 | Evidence base is 15 sessions, 4 operators, one capture window | Certain | Every count is small; no confidence interval is computed on n<30 |
| R6 | Dataset B has no ground truth; Step 1's Dataset A accuracy does not transfer | Certain | Stated in Step 1 |
| R7 | Step 1 has not been benchmarked against a published no-case-id baseline | High | `correlation_mining` exists in PM4Py and we did not run it |
| R8 | Durations are compressed in the capture environment | Certain | README |
| R9 | Contract values — the input to M10's authority rule — are **not visible** in the queue list view | High | We infer the rule applies; we have not seen the value it applies to |
| R10 | ⚠ semantics unknown | High | Blocks M08 entirely |
| R11 | Japanese-language model competence assumed rather than evidenced | Medium | Every document is Japanese; Microsoft's Copilot is English-only, UiPath warns against mixed-language recording |

---

## 14. Validation plan

Borrowed from the Macro Mining validation triad (§9), adapted to a no-ground-truth setting.

**14.1 Things only the client can answer.** What ⚠ means on a purchase order. Whether 北陸電子部品 and
北陸部品工業株式会社 are the same entity. The tolerance implied by 「差異がある場合」. Whether `P1-` and
`P4-` are one process or two. Whether the 手続き set is complete and who owns it. True volumes,
seasonality, error rates, criticality. Whether an import or API path exists in each system.

**14.2 Things we can validate ourselves, before building.**
- **Module map coverage** — read one screenshot for each of the four inferred `(origin, route)` pairs
  and for 予算差異分析. Cost: under an hour.
- **Module attribution** — hand-adjudicate a random 50 of the 183 executions against their
  screenshots and report agreement with the automatic dominant-module assignment. This is the single
  most valuable validation available and it does not need the client.
- **Document-rule extraction** — transcribe the remaining 9 reference documents and check that each
  module's rule is machine-checkable.

**14.3 Things to measure once Step 3 exists.**
- Document-selection accuracy for M10 (contract action is visible, so the label exists).
- Item-count exact match for M03 against 照合項目数 — a **free label**.
- Grounding rate: proportion of proposals whose cited clause is a verbatim substring.
- Abstention rate on out-of-list entities, which should approach 1.0.
- Validator-catch rate against injected faults — this measures the *boundary*, which is the
  engineering contribution.
- A structured rating study on drafted comments (design after Macro Mining: ~11 raters, ~60 items,
  5-point scale).

**Report `n` beside every metric.** Queues are twelve rows; no percentage should be quoted without
its denominator, and no confidence interval should be computed at these sample sizes.

---

## 15. Implications for Step 3

1. **Build the engine, not the script.** Eleven modules share one shape. The README explicitly
   permits "a general mechanism that can be extended across several processes (a shared foundation
   with per-process definitions)" — and the evidence, not a preference for generality, points there.
2. **First definition: M10 契約管理. Second: M03 入社手続き.** The first is the opportunity; the second
   proves generality and supplies the only free metric.
3. **The target adapter is an interface.** UI automation is its first implementation. The import/API
   question is open for every module.
4. **The model proposes; code validates; a human approves; a deterministic driver acts.** Where the
   model and the rule disagree, the rule wins.
5. **Abstention is a first-class outcome**, not an error.
6. **Ship one deliberate failure** — selector drift must stop and report, never adapt.
7. **Label every artefact** as TELEMETRY-RECOVERED / SYNTHETIC / REPLICA / PRODUCTION-UNVERIFIED.
8. **Screenshots move into the pipeline.** The discovery stage should read screen content rather than
   route strings. That is the durable lesson of this re-analysis.

---

## 16. What we deliberately do NOT claim

1. **No monetary ROI, no FTE saving, no labour cost.** Not in the telemetry. Any figure would be
   invented.
2. **No business volume.** 456 in-segment dispositions is a count of recorded interactions in one
   ~2-hour capture window across 15 sessions. It is **not** an annual case volume and is not
   extrapolated.
3. **No claim that any observed system lacks an API or bulk import.** We cannot see one; that is a
   fact about our telemetry, not about the client's architecture.
4. **No claim that durations are wall-clock effort.** The README states waiting time is compressed.
5. **No claim that Step 1's Dataset A accuracy (boundary F1 ≈ 0.69, ARI ≈ 0.68 @ match rate 0.76)
   transfers to Dataset B.** Dataset B has no ground truth.
6. **No claim that the 種別 badge, the ⚠ marker, the 照合項目数 count, or any nav badge is ground truth
   for business correctness.** They are system labels; one of them demonstrably contradicts its own
   written rule.
7. **No claim that our module map is complete.** Twenty screenshots of 4,746 were read. Four
   `(origin, route)` pairs remain inferred; one module (予算差異分析) was never observed.
8. **No claim that the eleven modules are all of the client's work.** They are what appeared in one
   capture window from three departments.
9. **No claim that Step 1 is correct on Dataset B.** Two of its eleven clusters are demonstrable
   over-merges, and 27.5% of dispositions fall outside any execution.
10. **No claim of novelty for the segmentation approach.** It re-derives the Robotic Process Mining
    pipeline, and has not been benchmarked against the published no-case-id baseline that exists in
    PM4Py.
11. **No claim that the previous Step 2 was careless.** It was rigorous and wrong: it aggregated on a
    display name instead of a business identity, and never opened a screenshot.

---

## Appendix — hostile reviewer questions

Asked adversarially, answered honestly.

**1. Did we confuse routes with business processes?** *Previously yes — catastrophically.* The
previous Step 2 treated `/payroll-items` as one module across three systems. It is three businesses.
Now every module identity requires a screenshot showing URL + breadcrumb + nav item together, and
route strings are never used as semantics.

**2. Did we confuse UI labels with ground truth?** *Previously yes; now guarded, and one instance
remains uncomfortable.* Badges, buttons, filenames and column headers are recorded as system labels.
Column headers are demonstrably wrong on M06. The 種別 badge is used only as a weak reference, and
§8.3 shows it contradicting its own rule.

**3. Did we mistake activity volume for business volume?** *Previously implicitly; now explicitly
guarded.* Three denominators are reported separately, dispositions-per-execution is published per
module (1.83–4.35), and §16.2 states the counts are not annual volumes.

**4. Did we overestimate automation suitability?** *Possibly — one specific risk.* M10's authority
rule keys on contract value, and **contract values are not visible in the queue list view we read**.
If they are not available on the record at all, the rule cannot be applied automatically. This is
R9 and it is the biggest single threat to the selection.

**5. Did we infer semantics from filenames/routes without screenshots?** *Previously yes, entirely.
Now, partially.* Eleven modules are screenshot-verified; four `(origin, route)` pairs remain inferred
from navigation ordering and are marked as such; nine of thirteen reference documents are unread and
their classification rests on filename conventions (規程 / 手続き / 一覧), which is exactly the kind
of inference this re-analysis exists to distrust.

**6. Did we ignore process variants?** *No, and we changed our position on them.* The previous
analysis treated variance as a disqualifier. §7.4 classifies variance by kind, and the flagship
candidate has the highest dispersion of any gate-passer precisely because its variants are real.

**7. Did we ignore exception handling?** *No.* §8.2 documents the ⚠ deferral behaviour. But we
cannot classify the exceptions because we do not know what the flag means, and we say so rather than
guessing.

**8. Did we force AI into the solution?** *We tried not to, and rejected five of ten candidate
roles* — including two on the flagship's nearest neighbours (M11 approver routing is a lookup; M03
checklist applicability is deterministic). The AI that survives does rule retrieval, threshold
extraction and entity resolution, and never touches the execution path.

**9. Did we use a ranking formula that creates false precision?** *No.* There is no composite score
anywhere. Gates are binary; value, feasibility and variability are three separate readings; the
final ordering is an argued human judgement, stated as such.

**10. Could an experienced RPA/process-mining engineer reproduce our conclusion?** *The quantitative
part, yes* — `analysis/step2_reanalysis.py` is deterministic and the CSVs are emitted from it. *The
semantic part, only partly* — it depends on 20 screenshots chosen by hand. A different sample might
identify the same eleven modules (the identifications were unambiguous) but could weight them
differently. **§14.2's 50-execution hand-adjudication is the fix, and it has not been done.**

**11. Does our approach differ meaningfully from existing task-mining systems?** *Yes, in one
respect that matters:* we segment with no case id and no SME-nominated task, which no commercial
product attempts. *But* we have not benchmarked against the published research baseline, and until
we do the claim is weaker than it sounds.

**12. Are we building something existing open-source tooling already solves?** *For Step 3, we would
be if we built a GUI-task compiler* — OpenAdapt (MIT) does that. We are not. *For Step 1, no* —
PM4Py assumes case ids almost everywhere and has no task-mining support. *For Step 2's process
discovery, partly* — and we should have used PM4Py's correlation miner as a baseline.

**13. Are we using screenshots in the right places?** *Now yes, previously no.* They are the only
source of business semantics and the only source of reference-document content. They are used for
discovery and evaluation, not in the runtime execution path. The remaining weakness is that we read
them by hand rather than in the pipeline.

**14. Is the proposed Step 3 actually evaluable?** *Yes, and unusually well for a no-ground-truth
setting.* M03 publishes 照合項目数, giving a free exact-match label. M10's contract action is visible,
giving a document-selection label. Grounding is a verbatim-substring check. Abstention on out-of-list
entities is provable from the list. Validator-catch rate is measurable against injected faults.

**15. What single assumption, if wrong, would invalidate the selected candidate?** This question was
asked, and then **answered by opening one more screenshot — and the assumption was wrong.**

The assumption was that the contract value needed by 新規契約手続き's approval-authority rule is
available on the record. §8.4 shows the M10 detail pane in full: 管理ID, 社員ID, 申請種別, 期間,
所属部署, ステータス, a named reference document, a comment box and two buttons. **There is no amount.**

We did not quietly drop the candidate or quietly keep it. We split it: M10 remains the flagship
*opportunity* — largest, best-spread, and mechanically the most determined module in the dataset —
but its automation stops at *prepare and present*, and **M05 becomes the decision candidate** because
it is the only module whose deciding inputs are visible alongside a rule we have read.

**The next assumption of the same kind, still untested:** that M05's 種別 badge disagreement with its
own written rule (§8.3) is an unstated tolerance rather than a different rule entirely. If it is a
different rule, M05's decision is not reproducible either, and the correct conclusion for this
dataset becomes *"prepare, present, and let the human decide — everywhere"*, with AI confined to
entity resolution and clause retrieval. **That would still be a useful system, and we should be
willing to ship it.**
