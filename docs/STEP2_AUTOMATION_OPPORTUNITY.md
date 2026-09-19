# Step 2 — Automation Opportunity Discovery

**Status: AUTHORITATIVE / SUBMISSION-READY**

**Date:** 2026-09-16  
**Step 1 status:** Frozen; not modified.

> **Scope note:** This document is the authoritative Step 2 analysis. Earlier Step 2 artifacts are retained for auditability but are superseded. Subsequent reconciliation and hypothesis-verification work changes the interpretation of the opportunity space and is incorporated into the decision presented here.

## Companion Evidence

- `docs/STEP2_FORENSIC_RECONCILIATION.md` — evidence contract and process reconstruction
- `docs/STEP2_PREVIOUS_ANALYSIS_AUDIT.md` — audit of the superseded analysis
- `docs/STEP2_PEER_REVIEW.md` — external review and methodological comparison
- `docs/STEP2_MODULE_KEY_RECONCILIATION.md` — ADR-022; module-key reconciliation
- `docs/STEP2_HYPOTHESIS_VERIFICATION.md` — verification of the original decision-learning hypothesis
- `docs/STEP3_TARGET_REFRAME.md` — revised Step 3 scope
- `docs/STEP2_PROCESS_INVENTORY.csv`
- `docs/STEP2_EXECUTION_TABLE.csv`
- `docs/STEP2_LABEL_MODULE_CONFUSION.csv`
- `docs/STEP2_CANDIDATE_MATRIX.csv`
- `docs/STEP2_EVIDENCE_MATRIX.csv`
- `analysis/step2_reanalysis.py`

---

# 1. Objective

The client asked where automation would have the greatest impact and what form a workable solution should take.

Step 2 therefore answers four questions:

1. **What business processes exist in Dataset B?**
2. **How much observable work does each represent?**
3. **Which processes are suitable for automation, and to what extent?**
4. **What automation mechanism is justified by the evidence?**

The analysis is designed so that a skeptical reviewer can reproduce the quantitative results and challenge the assumptions separately from the conclusions.

This is a **re-performance**, not a cosmetic revision. The previous Step 2 interpreted the workload as a “payroll-items family” involving duplicate master-data entry across siloed systems. That interpretation is contradicted by the evidence.

The corrected analysis instead identifies **document-governed review-and-disposition work** across eleven modules.

---

# 2. Evidence Contract and Scope

The full evidence contract is defined in `STEP2_FORENSIC_RECONCILIATION.md`. Four rules govern the analysis.

## 2.1 An Execution Is Not a Business Case

A Step-1 execution contains approximately **1.83–4.35 recorded dispositions**, depending on module.

The business unit is therefore the **disposition / record processed**, not the execution itself.

## 2.2 Only 72.5% of Observable Business Work Falls Inside an Execution

Of 629 recorded `btn-*-ok` clicks, **456** fall inside a Step-1 segment.

Approximately one quarter of observable dispositions therefore occur outside segmented spans.

All per-module activity estimates consequently **understate observed activity**, with the degree of understatement varying by module.

## 2.3 A Route Is Not a Process

A route string and UI label are not sufficient to establish business identity.

For example:

- `/payroll-items` represents different businesses on different origins;
- `/resident-tax` renders purchase-order management;
- column headers can disagree with the actual cell contents.

The authoritative module identity must therefore be derived from **screen evidence**, not from route strings alone.

## 2.4 Unavailable Business Metrics Remain Unavailable

The following are not present in the telemetry and are never estimated:

- business volume;
- monetary value;
- labour cost;
- FTE saving;
- error/rework rate;
- business criticality;
- compliance exposure;
- API/import availability;
- production selector stability.

These are represented as `UNAVAILABLE` where appropriate.

---

# 3. Dataset B Process Reconstruction

Dataset B contains **eleven observed business modules across three systems**.

| ID | System | Route | Module | Record Prefix | Governing Document / Evidence |
|---|---|---|---|---|---|
| M01 | HR人事給与システム `:5132` | `/payroll-items` | 経費精算・給与変更 | `P1-`, `P4-` | 業務委託経費規程 |
| M02 | HR `:5132` | `/leave-applications` | 勤怠・休暇申請 | `P2-` | Thin evidence |
| M03 | HR `:5132` | `/onboarding` | 入社手続き | `P3-` | 入社チェックリスト（新卒バッチ処理） |
| M04 | HR `:5132` | `/social-insurance` | 福利厚生申請 | `P5-` | 育児休業規程; 家族手当規程 |
| M05 | 財務会計システム `:5133` | `/payroll-items` | 請求書承認・経費精算 | `P6-` | 月次定額取引先一覧 |
| M06 | 財務 `:5133` | `/onboarding` | 支払処理 | `P7-` | 業務委託給与規程 |
| M07 | 財務 `:5133` | `/leave-applications` | 経費承認（管理職） | `P9-` | 接待交際費規程 |
| M08 | 財務 `:5133` | `/resident-tax` | 発注管理 | `P10-` | 新規取引先登録手続き |
| M09 | 受発注在庫管理システム `:5134` | `/payroll-items` | 在庫管理 | `P11-` | 在庫調整メモ |
| M10 | 受発注 `:5134` | `/leave-applications` | 契約管理 | `P12-` | 契約解除手続き; 新規契約手続き |
| M11 | 受発注 `:5134` | `/social-insurance` | IT申請 | `P13-` | 管理者権限申請手続き |

Every module has evidence of a semantically matching governing reference.

The observed work has a common structure:

1. select a queue row;
2. open or consult the governing reference;
3. enter or paste a short justification;
4. click the module's confirmation control;
5. observe the row status change.

There are **633 row-selection clicks for 629 confirmation clicks**.

All **608 observed form inputs are pastes with `value: null`**; no free text is typed in the captured form-input telemetry.

The resulting interpretation is:

> **This is document-governed review-and-disposition, not ordinary data entry.**

---

# 4. Methodology

## 4.1 Corrected Analysis Pipeline

```text
Frozen Step-1 executions (183)
        |
        v
Evidence-based module attribution
        |
        v
Identity quality
(purity + modules touched)
        |
        v
Quantitative inventory
(executions / dispositions / events)
        |
        v
Hard gates
(evidence / identity / business work / target surface)
        |
        v
Value + feasibility + variability
(reported separately)
        |
        v
Modality selection
        |
        v
Candidate shortlist
        |
        v
Flagship opportunity + Step 3 scope
```

## 4.2 Analysis Guards

| Guard | Prevents | Mechanism |
|---|---|---|
| Module identity verified by screenshot | Route-as-process | Require screen evidence for business identity |
| Never aggregate on Step-1 label strings | Repeating the original error | Aggregate by module identity |
| Cell content over column header | UI-label-as-truth | Inspect actual record content |
| System badges treated as system labels | Badge-as-ground-truth | Validate against written rules |
| Three denominators reported separately | Telemetry-count-as-business-volume | Keep executions, dispositions, and events distinct |
| Automatability proxy rather than frequency alone | Frequency-only ranking | Use a declared structural proxy |
| No composite score | False precision | Gates are binary; value and feasibility remain separate |
| `UNAVAILABLE` remains explicit | Unsupported ROI | Never infer business economics |
| Task mining distinguished from process mining | Methodological confusion | No case ID is available |
| AI must pass an explicit role test | AI-by-default | Reject roles where deterministic mechanisms suffice |

---

## 4.3 Automatability Proxy

The published Routine Automatability Index (RAI) cannot be calculated directly because Dataset B does not expose action values: form inputs have `value: null` and clipboard contents are redacted.

The analysis therefore uses a **structural automatability proxy**, not RAI.

Interactions are classified as:

- **DERIVABLE** — a paste or clipboard-derived action;
- **STRUCTURAL** — action on a recovered element or instrumented keystroke;
- **NAVIGATIONAL** — browser navigation or application switching;
- **OPAQUE** — uninstrumented application activity, scrolling, or unidentified clicks.

The proxy is:

```text
(DERIVABLE + STRUCTURAL + NAVIGATIONAL) / all observed interactions
```

This measures the proportion of observed work occurring on surfaces a deterministic agent could address.

It does **not** establish that a value is computationally derivable.

---

# 5. Module-Key Reconciliation and Inventory Status

## 5.1 ADR-022 Supersession

A later forensic reconciliation established that the original `(origin, route)` key is not a reliable representation of the displayed module.

Three keys were tested:

- **K1:** URL/route;
- **K2:** screen header;
- **K3:** record-ID prefix.

K2 and K3 agree on **2,904 / 2,904 comparable records**.

K1 agrees with K2 on **78.6%** and with K3 on **79.1%**.

All **552** disagreements have the same structure:

> K2 = K3, while K1 alone disagrees.

The cross-module queue-view explanation was directly tested and refuted: 33 captures contained multiple record prefixes, but **0 crossed a module boundary**.

### Consequence

For record identity:

> **K2 screen header is authoritative, with K3 as an exact proxy where available.**

For execution-level analysis:

> **K3 is used where available; K1 may be used where K3 is unavailable, but disagreements must be preserved rather than silently resolved.**

Therefore, the execution counts in the original inventory should be treated as **ranges rather than exact values** until the key/coverage issue is resolved.

## 5.2 Missing Module

`FI|予算差異分析` is explicitly visible in **11 captures**, contains **132 P8 record rows** at purity 1.00, but is absent from the original `(origin, route)` map.

It therefore has **6 executions under the K3 reconstruction and 0 under K1**.

This is an omission in the original map, not evidence that the module was absent.

---

# 6. Quantitative Inventory

The original URL-key inventory contains 183 executions, 456 in-segment dispositions, and 7,642.7 seconds of measured segmented activity.

**Durations are comparative only** because waiting time is compressed in the capture environment.

| ID | Module | Exec | Sessions | Operators | % Time | Median s | IQR/Median | Dispositions | Disp/Exec | s/Disp | Purity | Multi-module | A-proxy |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M10 | LO 契約管理 | 26 | 8 | 4 | **15.19** | 31.3 | 1.10 | 65 | 2.50 | 17.9 | 0.85 | 10/26 | 0.501 |
| M01 | HR 経費精算・給与変更 | 20 | **10** | 4 | 14.33 | 44.1 | **0.48** | **87** | 4.35 | **12.6** | 0.82 | 8/20 | 0.547 |
| M05 | FI 請求書承認・経費精算 | 25 | 8 | 4 | 12.25 | 35.3 | 0.61 | 52 | 2.08 | 18.0 | 0.88 | 8/25 | 0.436 |
| — | Unassigned | 18 | 7 | 4 | 10.18 | 29.6 | 1.70 | 3 | 0.17 | — | 0.00 | 0/18 | 0.341 |
| M03 | HR 入社手続き | 23 | 8 | 4 | 9.32 | 29.1 | 0.46 | 42 | 1.83 | 17.0 | **0.90** | 6/23 | 0.551 |
| M08 | FI 発注管理 | 13 | 8 | 4 | 8.18 | 38.7 | 0.55 | 52 | 4.00 | 12.0 | 0.69 | 9/13 | 0.559 |
| M09 | LO 在庫管理 | 13 | 6 | 4 | 7.55 | 41.3 | 0.86 | 40 | 3.08 | 14.4 | 0.76 | 7/13 | 0.489 |
| M04 | HR 福利厚生申請 | 10 | 4 | 3 | 6.06 | 45.1 | 0.76 | 33 | 3.30 | 14.0 | 0.74 | 7/10 | 0.604 |
| M07 | FI 経費承認（管理職） | 10 | 3 | 2 | 5.16 | 38.2 | 0.56 | 22 | 2.20 | 17.9 | 0.89 | 4/10 | 0.493 |
| M11 | LO IT申請 | 9 | 5 | 4 | 5.08 | 34.3 | 0.61 | 29 | 3.22 | 13.4 | **0.94** | **1/9** | 0.560 |
| M06 | FI 支払処理 | 9 | 5 | 3 | 4.13 | 31.1 | 0.98 | 17 | 1.89 | 18.6 | **0.94** | **1/9** | 0.429 |
| M02 | HR 勤怠・休暇申請 | 7 | 4 | 2 | 2.56 | 23.1 | 0.52 | 14 | 2.00 | 14.0 | 0.81 | 2/7 | **0.618** |

### Important interpretation

The per-record effort is relatively stable:

> **12.0–18.6 seconds per disposition**

across the eleven modules.

Seconds per execution range more widely because executions contain different numbers of dispositions. For business comparison, seconds per disposition is therefore the more useful denominator.

Business volume, monetary value, FTE savings, criticality, and error rates are not inferred.

---

# 7. Variability and Fragmentation

## 7.1 Operator and Session Spread

Seven modules involve all four operators.

Concentration—the largest single session's share of a module's executions—ranges from:

- **0.15** for M08;
- to **0.54** for M09.

The latter indicates relatively thin evidence for M09.

## 7.2 Cross-Module Fragmentation

Across 183 executions:

- 102 touch exactly one business module;
- 48 touch two;
- 15 touch three;
- 18 touch no business module.

M11 and M06 are relatively clean, with only 1 of 9 executions touching a second module.

M08 is substantially more fragmented, with 9 of 13 executions touching more than one module.

## 7.3 Non-Business Activity

The 18 executions that resolve to no business module consume **10.18%** of measured time.

This includes desktop work such as Word, Excel, terminal activity, and portal roots.

The pipeline deliberately does **not** treat these as business processes.

---

# 8. Automation Suitability

No weighted score is used.

Suitability is assessed using separate binary gates, followed by independent readings of value, feasibility, variability, and modality.

## 8.1 Hard Gates

| Gate | Rule | Purpose |
|---|---|---|
| **G1 Evidence sufficiency** | `executions >= 10 AND sessions >= 5 AND operators >= 3` | Prevent decisions based on very small or single-person samples |
| **G2 Identity sufficiency** | `mean module purity >= 0.75` | Prevent downstream analysis of mixed processes |
| **G3 Business work** | `dispositions/execution >= 1 AND governing document identified` | Distinguish business work from navigation |
| **G4 Observable target** | `>= 1 recovered element id` | Ensure a deterministic interaction target exists |
| **G5 Decision-input observability** | Required decision inputs are present on the record | Distinguish preparation automation from decision automation |

### Gate Results

| Module | G1 | G2 | G3 | G4 | Overall |
|---|---|---|---|---|---|
| M10 契約管理 | Pass | Pass | Pass | Pass | **Pass** |
| M01 経費精算・給与変更 | Pass | Pass | Pass | Pass | **Pass** |
| M05 請求書承認・経費精算 | Pass | Pass | Pass | Pass | **Pass** |
| M03 入社手続き | Pass | Pass | Pass | Pass | **Pass** |
| M09 在庫管理 | Pass | Pass | Pass | Pass | **Pass, marginal** |
| M08 発注管理 | Pass | **Fail** | Pass | Pass | **Fail — identity** |
| M04 福利厚生申請 | **Fail** | Fail | Pass | Pass | **Fail — evidence** |
| M07 経費承認（管理職） | **Fail** | Pass | Pass | Pass | **Fail — evidence** |
| M11 IT申請 | **Fail by one execution** | Pass | Pass | Pass | **Fail — evidence** |
| M06 支払処理 | **Fail by one execution** | Pass | Pass | Pass | **Fail — evidence** |
| M02 勤怠・休暇申請 | **Fail** | Pass | Pass | Pass | **Fail — evidence** |

### G5 Finding

G5 does not eliminate a candidate automatically. It determines **how far automation can safely go**.

- **M05 passes:** vendor, amount, and invoice number are visible and the governing rule is documented.
- **M10 fails:** the detail pane contains identifiers, contract type, period, department, status, and a named reference document, but **no contract value**, even though the governing procedure's authority rule depends on contract value.
- **M03 partially passes:** some checklist conditions are visible, while the attributes driving two conditional items are not.
- M01 and M09 remain unknown because the required detail panes were not fully inspected.

Therefore:

> Where G5 fails, the system may prepare, assemble, and present evidence, but the human must retain the decision.

---

# 9. Value, Feasibility, and Variability

## 9.1 Value

| Module | Time Share | Dispositions | Operators | Sessions | Concentration | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| M10 | **15.19%** | 65 | 4 | 8 | 0.23 | Largest and broadly distributed |
| M01 | 14.33% | **87** | 4 | **10** | 0.25 | Most records and widest session presence |
| M05 | 12.25% | 52 | 4 | 8 | 0.20 | Large and evenly distributed |
| M03 | 9.32% | 42 | 4 | 8 | 0.30 | Solid evidence |
| M09 | 7.55% | 40 | 4 | 6 | **0.54** | High concentration; weaker evidence |

These are **observed telemetry measures**, not business-volume or ROI estimates.

## 9.2 Feasibility

| Module | Input Structure | Target Stability | Systems | A-proxy | Documentation | Interpretation |
|---|---|---|---|---:|---|---|
| M10 | Queue + 5 contract types | 1 origin | 1 + Word | 0.501 | Two procedures read in full; explicit authority rule | Good |
| M01 | Queue mixing P1/P4 | 1 origin | 1 + Word | 0.547 | Governing regulation not fully read | Good, but scope unresolved |
| M05 | Queue + 5-row reference table | 1 origin | 1 + Word | 0.436 | Reference list read in full; written rule | Strong, but requires validation |
| M03 | Queue + 7-item checklist | 1 origin | 1 + Word | 0.551 | Checklist read in full | Strong |
| M09 | Queue + operator memo | 1 origin | 1 + Notepad | 0.489 | No external governing document | Weak |

## 9.3 Variability

Variance is not automatically a reason to reject automation.

| Module | IQR/Median | Interpretation |
|---|---:|---|
| M03 | **0.46** | Legitimate, low variation |
| M01 | 0.48 | Legitimate business variants |
| M05 | 0.61 | Legitimate variation plus exceptions |
| M09 | 0.86 | Evidence insufficiency; concentrated session |
| M10 | **1.10** | Legitimate business variants |
| M08 | 0.55 | Exception handling |
| Unassigned | 1.70 | Process instability / not a business process |

M10's high variance is not treated as noise. It reflects multiple contract types and actions governed by different procedures.

---

# 10. Variants and Exceptions

## 10.1 M10 — Contract Variants

M10 contains **five contract types across four actions**, including:

- 業務委託契約（解除）
- 秘密保持契約（新規締結）
- 売買契約（変更）
- 取引基本契約（新規締結）
- 保守委託契約（更新）

Each action is associated with a governing procedure.

The observed co-occurrence counts include:

- 契約解除手続き: **483**
- 新規契約手続き: **192**

This is a strong example of why a definition-driven engine is preferable to one fixed script.

## 10.2 M01 — Two Record Families

M01 contains both:

- `P1-` expense claims;
- `P4-` payroll changes.

Whether these represent one process or two remains unresolved.

This must be resolved before M01 is treated as a single automation scope.

## 10.3 M03 — Conditional Checklist

M03 contains seven checklist items, with two conditional items:

- 雇用保険被保険者証 — **転職者のみ**
- 扶養控除等申告書 — **家族手当対象者確認**

The system exposes 4-item or 5-item checklist counts.

This provides a potentially useful evaluation label without requiring manual annotation.

## 10.4 M08 — Observable Exception Behaviour

Two of twelve purchase orders carry a red `⚠` marker.

In one observed session:

```text
module badge: 12 → 11 → 5
```

while both flagged rows remained `未確認`.

The operator cleared unflagged work and deferred flagged work.

`rt-note` comments are also the longest in the dataset, with a median of 54 characters compared with approximately 30–46 elsewhere.

However:

> **The meaning of `⚠` is unknown.**

No flagged-row detail pane was read.

Any automation must therefore support abstention rather than assume the semantics of the marker.

---

# 11. M05 — Important Rule/Label Conflict

The governing document `月次定額取引先一覧` states:

> 「受領した請求書の INV 番号・金額・取引先名をこの一覧と照合すること。**差異がある場合は要確認として保留する**」

The queue contains invoices whose amounts differ from the listed vendor amount, yet the system's `種別` badge does not consistently correspond to that rule.

Additional vendor mismatches are present between the queue and reference list.

Therefore:

> **The `種別` badge is a system label, not ground truth for business correctness.**

It may be used as a weak reference signal, but disagreements must be inspected individually rather than averaged away.

This issue is central to M05's validation plan.

---

# 12. M10 Detail-Pane Finding and Its Consequence

A detailed M10 screenshot changed the automation interpretation.

The detail pane contains:

- 管理ID
- 社員ID
- 申請種別
- 期間
- 所属部署
- ステータス
- an explicit reference document filename
- a templated approval comment
- `✓承認`
- `✕差戻し`

The system itself therefore names the governing document.

### Consequence 1 — Document selection is not an AI problem

The record already carries the reference filename.

Document selection for M10 is therefore a **lookup**, not a learned inference task.

### Consequence 2 — The decision input is missing

The observed comment is a template over fields already present on the record.

However, the governing `新規契約手続き` rule uses contract value:

```text
< ¥1,000,000  → 部門長承認
≥ ¥1,000,000  → 役員承認
≥ ¥30,000,000  → 取締役会決議
```

The detail pane contains **no contract value**.

Therefore:

> **M10 mechanics are automatable; its decision is not supported by the observed record data.**

This finding is the direct basis for separating the **flagship opportunity** from the **flagship decision candidate**.

---

# 13. Automation Modality by Module

| Module | Appropriate Intervention | Rationale |
|---|---|---|
| **M10 契約管理** | **Prepare-and-present + deterministic execution + human decision** | Reference document is named; comment is templated; action is deterministic; decision input is unavailable |
| **M01 経費精算・給与変更** | Prepare-and-present, pending P1/P4 reconciliation | Two record families may require separate definitions |
| **M05 請求書承認・経費精算** | **Human-in-the-loop decision support, after validation** | Required inputs are visible, but the system badge conflicts with the written rule |
| **M03 入社手続き** | **Deterministic rules engine + verification** | Only two of seven checklist items are conditional |
| **M11 IT申請** | **Deterministic lookup; no AI required** | Approver mapping is explicitly documented |
| **M08 発注管理** | Investigate before automating | Exception semantics are unknown and identity purity is insufficient |
| **M09 在庫管理** | Defer | Evidence is insufficient and reference is operator-generated |
| **M02, M04, M06, M07** | Defer | Failed evidence gate; under-observed rather than necessarily unsuitable |
| Unassigned activity | Process redesign or exclusion | Not established as a business process |

UI automation is the defensible current execution mechanism under present uncertainty. An import/API path is **not ruled out** and should remain a replaceable target-adapter layer.

---

# 14. AI Opportunity

## 14.1 Updated Decision

The original hypothesis that AI should learn the business disposition decision is **not supported**.

Hypothesis verification found:

- **0 of 225 observed system dispositions were negative**;
- 0 backward status transitions;
- the proposed decision variable is frequently absent from records;
- document consultation is nevertheless supported in 10 of 11 modules.

The appropriate target is therefore **evidence preparation and bounded decision support**, not autonomous disposition.

## 14.2 AI Role Assessment

| AI Role | Decision | Rationale |
|---|---|---|
| Document selection for M10 | **Reject** | Record already names the document |
| Clause retrieval + citation | **Accept, narrowly** | Finding the applicable clause inside a multi-section document is non-trivial and directly checkable |
| Threshold extraction | **Accept where applicable** | Model extracts the expression; deterministic code evaluates it |
| M05 entity resolution | **Accept** | Genuine ambiguity; abstention is measurable |
| Screenshot semantic interpretation | **Accept for discovery** | Needed to recover business identity; not required in runtime |
| Japanese comment drafting | **Reject for M10** | Observed comment is a deterministic template |
| M05 bounded decision proposal | **Accept, human-approved** | Inputs and rule are observable, subject to badge/rule validation |
| M08 exception classification | **Reject for now** | `⚠` meaning is unknown and cannot be evaluated |
| M11 approver routing | **Reject** | Lookup table is sufficient |
| M03 checklist applicability | **Reject as AI; accept as deterministic rules** | Only two conditional items |
| Natural-language process configuration | **Reject** | No evidence of this requirement |
| Autonomous UI execution | **Reject as AI** | Deterministic selectors are more auditable; agentic execution is unnecessary |

The surviving AI roles are therefore deliberately narrow:

> **clause retrieval, threshold extraction, entity resolution, bounded decision proposal, and screenshot interpretation during discovery.**

AI does not own the execution path.

---

# 15. Bounded Architecture

```text
Typed record
     |
     v
Retrieve governing clause/document
     |
     v
+---------------------------+
| MODEL                     |
| - read                    |
| - match                   |
| - cite                    |
| - phrase                  |
+-------------+-------------+
              |
              v
+---------------------------+
| DETERMINISTIC VALIDATOR   |
| - clause is verbatim?     |
| - thresholds evaluated    |
|   in code                 |
| - rule overrides model    |
| - abstention enforced     |
+-------------+-------------+
              |
              v
        HUMAN APPROVAL
   accept / edit / reject
              |
              v
     TARGET ADAPTER
   UI today / API later
              |
              v
            AUDIT
```

### Non-negotiable boundary

> **Where the model and the written rule disagree, the rule wins.**

The model may propose.

Code validates.

The human approves.

The deterministic driver executes.

---

# 16. Candidate Selection

## 16.1 Flagship Opportunity

### **M10 — 契約管理**

M10 is the largest measured opportunity and the most mechanically determined module in the observed dataset.

Evidence:

- **15.19%** of measured segmented time;
- **26 executions**;
- **65 dispositions**;
- four operators;
- eight sessions;
- concentration approximately 0.23;
- explicit governing procedures;
- record-level reference document field;
- templated comment;
- deterministic approval/rejection controls.

However:

> **M10 is a preparation-automation opportunity, not a decision-automation opportunity.**

The contract value required by its approval-authority rule is not visible in the observed record.

## 16.2 Decision Candidate

### **M05 — 請求書承認・経費精算**

M05 is the strongest candidate for bounded decision support because:

- vendor, amount, and invoice number are present;
- the governing rule has been read;
- the target decision is observable;
- entity resolution is genuinely ambiguous in at least some cases.

The principal blocker is the disagreement between the written reference rule and the system's `種別` badge.

Therefore M05 requires validation before decision support is deployed.

## 16.3 Reserve Candidate

### **M03 — 入社手続き**

M03 has:

- high module purity;
- low dispersion;
- strong evidence spread;
- a deterministic checklist structure;
- a free evaluation label (`照合項目数`).

It is an appropriate second definition for demonstrating that the automation engine generalizes beyond one process.

---

# 17. Priority Order

The priority order is evidence-based but **not a composite score**:

1. **M10 契約管理** — largest measured opportunity and strongest mechanical structure.
2. **M01 経費精算・給与変更** — most dispositions and fastest per-record effort, pending P1/P4 reconciliation.
3. **M05 請求書承認・経費精算** — strongest decision-support candidate, pending rule/badge validation.
4. **M03 入社手続き** — highly verifiable deterministic candidate.
5. **M11 IT申請 / M06 支払処理** — collect more data; both miss the evidence gate by one execution.
6. **M08 発注管理** — investigate the `⚠` semantics and improve identity evidence.
7. Remaining modules — defer.

No monetary ROI, FTE saving, or annualized business volume is claimed.

---

# 18. Validation Plan

## 18.1 Questions Only the Client Can Answer

- What does `⚠` mean on purchase orders?
- Are 北陸電子部品 and 北陸部品工業株式会社 the same entity?
- What tolerance is implied by 「差異がある場合」?
- Are `P1-` and `P4-` one process or two?
- Is the governing-procedure set complete?
- Who owns and maintains the procedures?
- What are true production volumes, seasonality, error rates, and business criticality?
- Does an import/API path exist in each system?

## 18.2 Validation Before Implementation

1. Read one screenshot for each of the four inferred `(origin, route)` pairs and for 予算差異分析.
2. Hand-adjudicate a random sample of **50 of the 183 executions** against screenshots and compare with automatic dominant-module assignment.
3. Transcribe the remaining reference documents and verify that their rules are machine-checkable.
4. Resolve the M05 badge/rule discrepancy.
5. Determine whether M10 contract value exists anywhere in the record or supporting systems.

## 18.3 Validation After Step 3 Exists

Measure:

- M10 document/reference accuracy;
- M03 exact match against `照合項目数`;
- grounding rate: cited clause is a verbatim substring;
- entity-resolution abstention rate;
- validator-catch rate using injected faults;
- structured quality ratings for generated comments where comments remain useful.

Every reported metric must include its **n**.

---

# 19. Risks and Unknowns

| ID | Risk | Severity | Evidence |
|---|---|---|---|
| R1 | Module map is based on a limited screenshot sample | High | Only a small subset of 4,746 screenshots was manually read |
| R2 | Only 72.5% of dispositions fall inside Step-1 executions | High | Measured |
| R3 | M05 `種別` badge contradicts its written rule | High | §11 |
| R4 | Two Step-1 clusters are genuine over-merges | Observed | Purity 0.26 and 0.50 |
| R5 | Evidence base is 15 sessions / 4 operators | High | Small sample |
| R6 | Dataset B has no independent ground truth | Certain | Step-1 validation does not transfer |
| R7 | Step 1 has not been benchmarked against a published no-case-ID baseline | High | PM4Py `correlation_mining` not run |
| R8 | Durations are compressed | Certain | README |
| R9 | M10 contract value is not visible in the observed record | High | §12 |
| R10 | M08 `⚠` semantics are unknown | High | §10.4 |
| R11 | Japanese-language model competence has not been independently validated | Medium | Dataset/document language |

---

# 20. What This Analysis Does Not Claim

The following claims are deliberately excluded:

1. **No monetary ROI or FTE saving.**
2. **No annualized business volume.**
3. **No claim that an observed system lacks an API or bulk-import path.**
4. **No claim that observed durations equal wall-clock effort.**
5. **No transfer of Step-1 Dataset A accuracy to Dataset B.**
6. **No assumption that UI badges, markers, checklist counts, or navigation labels are business ground truth.**
7. **No claim that the current module map is complete.**
8. **No claim that the eleven observed modules represent all client work.**
9. **No claim that Step 1 is fully correct on Dataset B.**
10. **No claim of novelty for case-less task segmentation.**
11. **No claim that AI should make the final business disposition.**

---

# 21. Implications for Step 3

The evidence establishes the following implementation constraints:

1. **Build an extensible engine, not a one-off script.**
2. **Start with M10 as the prepare-and-present definition.**
3. **Use M03 as a second deterministic definition to demonstrate generality.**
4. **Treat M05 as the bounded decision-support candidate, subject to validation.**
5. **Keep the target adapter replaceable:** UI automation today, API/import later if available.
6. **Model proposes; deterministic code validates; human approves; deterministic driver executes.**
7. **Abstention is a first-class outcome.**
8. **Selector drift must stop execution and report failure; it must never silently adapt.**
9. **Label artifacts as TELEMETRY-RECOVERED / SYNTHETIC / REPLICA / PRODUCTION-UNVERIFIED.**
10. **Use screenshots for business-semantic discovery rather than relying on routes.**

---

# 22. Final Decision

## What Step 2 establishes

Dataset B contains a family of **document-governed review-and-disposition workflows** rather than the previously assumed duplicate-entry process.

The strongest measured opportunity is:

> **M10 — 契約管理**

but its automation boundary is **prepare-and-present**, because the observed record does not expose the contract value required for its authority rule.

The strongest bounded decision-support candidate is:

> **M05 — 請求書承認・経費精算**

subject to resolving the disagreement between the governing written rule and the system's `種別` badge.

The strongest deterministic validation candidate is:

> **M03 — 入社手続き**

because its conditional checklist structure is explicit and its output count provides a free evaluation label.

## What Step 2 does not establish

It does not establish that an AI model should make the business decision.

The subsequent hypothesis verification found that the original decision-learning formulation is unsupported: the system disposition did not vary in the observed data, while document consultation did.

## Step 3 scope

The defensible Step 3 scope is therefore:

> **A definition-driven prepare-and-present engine with bounded AI assistance where deterministic methods are insufficient, with human approval retained for all business decisions.**

The runtime contract is:

```text
EVIDENCE → MODEL (where needed) → DETERMINISTIC VALIDATOR → HUMAN → DETERMINISTIC EXECUTOR → AUDIT
```

This is the smallest system architecture supported by the evidence and preserves a clear boundary between model assistance and business authority.

---

# Appendix A — Reviewer Questions

### 1. Did the analysis initially confuse routes with processes?

Yes. The previous Step 2 did. The corrected analysis requires screen-based business identity and treats route strings as system metadata rather than semantics.

### 2. Did it confuse UI labels with business truth?

The earlier analysis did. The corrected analysis explicitly treats badges and labels as system observations. The M05 badge/rule disagreement demonstrates why.

### 3. Did it mistake activity counts for business volume?

The corrected analysis keeps executions, dispositions, and events separate and does not extrapolate to annual business volume.

### 4. Could M10's decision actually be automated?

Not from the observed record. Its authority rule depends on contract value, and the observed detail pane does not contain that value.

### 5. Could M05 become the primary decision-support target?

Yes, subject to validation of the discrepancy between its written rule and system badge.

### 6. Was process variation treated as a problem?

Not automatically. Legitimate variants are treated as a design requirement. M10's high variance is explained by contract types and actions.

### 7. Were exceptions ignored?

No. M08's `⚠` behaviour is documented, but its semantics are explicitly unknown, so the system must abstain rather than guess.

### 8. Was AI forced into the solution?

No. Several candidate AI roles are rejected because lookup tables or deterministic rules are sufficient.

### 9. Is there a composite automation score?

No. Gates are binary, while value, feasibility, and variability are reported separately.

### 10. Is the proposed Step 3 evaluable?

Yes, subject to the stated limitations. M03 provides a free exact-match label; M05 provides measurable rule/entity-resolution tests; grounding and validator-catch rates can be evaluated directly.

---

# Appendix B — Evidence Discipline

The project deliberately distinguishes:

- **OBSERVED / TELEMETRY-RECOVERED** — directly present in the captured data;
- **INFERENCE** — interpretation derived from observed evidence;
- **SYNTHETIC** — generated test or injected condition;
- **REPLICA** — recreated environment or artefact;
- **PRODUCTION-UNVERIFIED** — not yet validated in the live system.

No unavailable business metric is converted into an estimate merely to complete the analysis.

The purpose of this discipline is to ensure that the Step 2 conclusion remains useful even where the dataset is incomplete: **the system automates what the evidence supports, exposes what remains uncertain, and leaves business authority with the appropriate human or deterministic rule.**
