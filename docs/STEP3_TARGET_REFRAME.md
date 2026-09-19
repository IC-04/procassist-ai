# Step 3 — Target Reframe: Prepare-and-Present, Not Decide

> **Decision Gate:** This document concludes at a decision gate. No Step 3 implementation is started.

## Executive Summary

The strong hypothesis tested in Step 2 is refuted. The evidence that survives testing supports a narrower and more defensible system objective: **prepare-and-present rather than decide**.

The observed workflow is document-referenced confirmation work. Operators retrieve a record, locate and open a governing reference document, and record a disposition. The candidate system should therefore assemble the record and linked fields, identify and surface the governing document, pre-fill the templated comment, and flag records whose available fields are incomplete relative to the governing document.

**The human remains responsible for the decision and disposition.**

The most substantive candidate automation task is governing-document retrieval. However, the available labelled data is limited, and the deterministic `(module, record type) → document` lookup already achieves 64.2% leave-one-out accuracy. The evidence therefore does not currently justify a learned retriever.

---

## 1. The Reframed Claim

> Operators perform **document-referenced confirmation work**: they retrieve a record, locate and open a governing reference document, and record a disposition.

`[DATASET]` **Observed.** H3 is supported in 10 of 11 modules, with rates of 0.66–1.00 against a permutation null; most p-values are < 0.001.

The candidate system is **prepare-and-present**:

- assemble the record and its linked fields;
- identify and surface the governing document;
- pre-fill the templated comment;
- flag records whose fields are incomplete relative to the requirements of the governing document;
- **leave the decision to the human operator.**

---

## 2. Primary Sub-Task: Governing-Document Retrieval

**Input:** module, record type, record fields, and screen context.

**Output:** the reference document the operator will open.

**Ground truth:** the observed `(disposition, document-open)` pairs that produced H3.

### 2.1 Available Labelled Data

`[DATASET]` Observed from `build/dataset_b/evidence/retrieval_feasibility.json`:

| Measure | Value |
|---|---:|
| Total dispositions | 629 |
| Dispositions with a document opened before them, within the same execution | **148 (23.5%)** |
| Dispositions without a document opened | 481 |
| Distinct document labels | **17** by heading |
| Majority-label share | **18.9%** (`新規取引先登録手続き`) |

### 2.2 Retrieval Pairs by Module

| Module | n | Module | n |
|---|---:|---|---:|
| HR\|入社手続き | 33 | HR\|福利厚生申請 | 11 |
| HR\|経費精算・給与変更 | 24 | FI\|経費承認（管理職） | 9 |
| LO\|契約管理 | 19 | FI\|支払処理 | 8 |
| FI\|請求書承認・経費精算 | 17 | LO\|在庫管理 | 8 |
| FI\|発注管理 | 16 | HR\|勤怠・休暇申請 | 3 |

Nine of eleven modules clear the declared `n ≥ 8` floor.

### 2.3 Document Label Space

The label space must be settled before retrieval performance can be interpreted.

Keying documents by content `sha256` gives **50 labels**, because a long regulation captured at different scroll positions can produce different identifiers. Keying documents by their own first heading gives **17 labels**, which is closer to the stated 13 reference documents in Dataset B.

Both representations are relevant:

- the **50-label hash space** is the pessimistic bound;
- the **17-label heading space** is the operationally meaningful representation used for the main comparison.

The hash representation depresses scores by approximately 20 points.

`[INF]`

---

## 3. Evaluation Feasibility

The available sample supports evaluation only **barely**, and not for the strongest modelling question.

Leave-one-out evaluation is used instead of a held-out split because a split would consume evidence that the task cannot spare.

At `n = 148`, the 95% Wilson interval around a single accuracy estimate is approximately **±7.5 percentage points**. This makes close model-versus-baseline comparisons difficult to resolve.

Per-module sample sizes range from 3 to 33 and therefore do not support reliable per-module model training.

---

## 4. Decisive Test: The Learned System Does Not Yet Earn Its Place

`[DATASET]` Leave-one-out evaluation, seed 7, heading label space, `n = 148`:

| Baseline | Accuracy |
|---|---:|
| **B0 — Random** | 5.4% |
| **B1 — Most-frequent document overall** | 18.9% |
| **B2 — Most-frequent document per module** | **52.7%** |
| **B3 — Deterministic `(module, record type) → document` lookup** | **64.2%** — 95% CI **56.2–71.5%** |

### Finding

A deterministic lookup reaches **64.2%** accuracy. A learned retriever would need to exceed the upper bound of **71.5%** before the current evidence could distinguish it from the existing lookup at this level of uncertainty.

`[INF]`

### Decision

The evidence supports a **lookup table plus a good UI**, instrumented so that the residual cases can be measured in production.

Nothing in Dataset B currently justifies a learned retriever.

---

## 5. Conditions Under Which a Learned Component Could Earn Its Place

The following are evidence-based conditions rather than assumptions about future model performance.

### 5.1 A Larger or Growing Document Set

Seventeen labels, with the largest label accounting for 18.9%, represent a small and relatively static label space where a lookup table has a structural advantage.

A substantially larger policy set, or policies that change frequently, could change this trade-off.

### 5.2 Per-Record Conditioning Beyond the Lookup Key

B3 uses `(module, record type)`.

If the governing document also depends on variables such as:

- amount band;
- vendor;
- employee class;

then a lookup table would require a row for each combination, while a learned system could potentially express the dependency more compactly.

### 5.3 A Genuinely Ambiguous Residual

B3's remaining 35.8% of errors may be concentrated in one or two confusable document pairs.

If so, the appropriate intervention may be a better lookup key rather than a model.

This ambiguity has **not yet been measured** and should be investigated before implementing a retriever.

---

## 6. Target Module

`[INF]` Based on the Phase 3.5 inventory (ADR-022) and the retrieval data:

### `FI|請求書承認・経費精算` — Invoice Approval

This module is selected because it provides the strongest basis for a measurable prepare-and-present workflow.

#### 6.1 Decision Variation

It is the only module in which the operator's recorded judgement varies:

- 19 comments: `差異あり要確認`
- 36 comments: `差異なし承認`

`[DATASET]`

Other modules have constant annotations, leaving little observable variation for a system to surface or evaluate.

#### 6.2 Amount Information

The record contains an amount field in **87.1%** of cases, compared with **1–9%** in the refuted modules.

This makes the amount a meaningful variable for a prepare-and-present interface.

#### 6.3 Sufficient Retrieval Sample

The module has **17 labelled retrieval pairs**, above the declared floor.

#### 6.4 Structured Comment

The comment is templated:

```text
請求書照合完了。INV-XXXX　金額：¥N。差異{なし承認|あり要確認}。
```

This makes pre-filling well-defined while leaving the judgement slot to the operator.

### 6.5 Rejected Alternatives

**HR\|入社手続き** has the largest number of retrieval pairs (33), but:

- 金額 appears in only 1.0% of records;
- there is no annotation variance.

**LO\|契約管理** has the largest time footprint in the current inventory, but:

- 金額 appears in only 9.1% of records;
- the recorded ¥1M/¥30M authority rule is therefore inapplicable as recorded;
- ADR-022 places its true execution count somewhere between 8 and 26.

---

## 7. System Boundaries: What the System Cannot Do

`[DATASET]` + `[INF]`

The following limitations are first-class requirements.

### 7.1 It Cannot Decide

Zero of 225 observed dispositions were negative.

There is therefore no supervision signal for learning a decision function.

### 7.2 It Cannot Detect Errors

No incorrect disposition was observed.

Consequently, there are no negative examples from which to estimate a false-accept rate.

### 7.3 It Cannot Be Evaluated Against Rejection Behaviour

The interface supports rejection:

> 「承認コメントまたは**差戻し**理由を入力してください…」

However, `差戻し` never occurred in the observed window.

A system built from this data has therefore never observed the branch around which that interface capability is designed.

### 7.4 Retrieval Usefulness Is Not Established

The system can be evaluated on whether it matches the document the operator opened.

It cannot yet establish whether opening that document actually helped the operator complete the task.

### 7.5 Coverage Is Limited

Of 629 dispositions:

- 148 (23.5%) had a document open before them;
- 481 did not.

Thus the document-retrieval formulation directly covers **less than one quarter of the observed dispositions**.

---

## 8. Human-in-the-Loop Contract

| Responsibility | System Behaviour |
|---|---|
| **Surfaced** | The record and its fields; the governing document opened to the relevant clause; fields required by the document that are missing from the record |
| **Pre-filled** | The templated comment, with the judgement slot **left blank** |
| **Operator must still do** | Make and record the judgement (`差異なし` / `差異あり`), click the disposition, and override the suggested document when it is wrong |
| **Never automated** | The disposition click; there is no evidence licensing this automation |

The system therefore supports the operator's work without replacing the decision.

---

## 9. Measurable Success Criteria

`[INF]` Each criterion can be measured against the current telemetry or instrumented workflow.

| Criterion | Current Baseline | Measurement |
|---|---:|---|
| Document-retrieval top-1 accuracy | **64.2% (B3)** | Compare against observed document opens |
| Document-retrieval top-3 accuracy | Not measured | Evaluate ranked output against the same labels |
| Seconds from record-open to disposition | Measurable per module | Existing telemetry |
| Operator override rate for suggested document | Not yet available | Instrument the suggestion |
| Share of pre-filled comments accepted without edits | Not yet available | Instrument the comment box |
| Share of incomplete-record flags accepted by operator | Not yet available | Instrument the flag |

The final three metrics are particularly important because they would establish whether the proposed preparation features are useful in practice.

They also provide evidence for deciding whether a learned component is warranted, without requiring a negative class.

---

## 10. Remaining Threat to Validity

`[INF]`

### H3 Measures Sequence, Not Causation

The operator opens the document before disposing at a rate substantially above chance. However, G3 and G4 suggest that the document open may not be the basis of the decision.

The observed document opening could instead be:

- procedural;
- habitual;
- a consequence of the interface;
- or an artefact of where the relevant file happened to be located.

If so, surfacing the document faster may reduce keystrokes without changing the substantive work.

The current Dataset B cannot distinguish these explanations.

Resolving this question requires evidence outside the existing telemetry, such as:

1. an operator interview; or
2. an A/B test in which document access is deliberately suppressed or altered.

---

# 11. Decision Gate

Based on the evidence available at this stage:

### Proceed with

**Prepare-and-present + deterministic governing-document lookup + instrumentation.**

The initial implementation should focus on:

1. retrieving the relevant invoice record;
2. surfacing the governing document and relevant clause;
3. identifying missing required fields;
4. pre-filling the templated comment while leaving the judgement blank;
5. measuring operator edits, overrides, timing, and acceptance.

### Do not proceed yet with

**A learned document-retrieval model or automated disposition decision.**

The present dataset does not provide sufficient evidence that a learned retriever would outperform the deterministic baseline, and it provides no negative decision examples that could support automated disposition.

### Evidence required for the next gate

Before introducing a learned component, measure:

- the concentration and nature of B3's residual errors;
- top-3 retrieval performance;
- operator override rate;
- comment acceptance/edit rate;
- incomplete-field flag acceptance rate;
- time saved per disposition;
- whether document surfacing changes the actual workflow.

This keeps the next development step evidence-driven rather than model-driven.
