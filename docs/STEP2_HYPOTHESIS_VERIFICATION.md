# Step 2.5 — Hypothesis Verification

**Status: VERIFIED AND REFRAMED**

> **Decision:** The strong hypothesis is false on Dataset B. This is a deliverable, not an unresolved gap.

This document records the evidence used to test the original hypothesis, distinguishes observations from inference, and defines the conclusions that remain valid for Step 3.

**Evidence policy:** Every substantive claim is tagged as observed or inferred in the underlying analysis and carries its supporting artifact. No VLM was used anywhere in the programme; the reported values come from telemetry already captured by the recorder.

---

## Executive Summary

The original hypothesis proposed that:

> Operators apply recoverable written rules to record variables, and an AI system can learn that decision function.

Testing required four conditions to hold simultaneously:

1. the task and outcome must be observable;
2. a governing rule must be recoverable;
3. the record must contain the variables required by that rule;
4. the outcome must vary sufficiently to distinguish rule application from confirm-and-proceed behaviour.

The evidence shows:

- **G1 — Observability:** PASS
- **G2 — Recoverable governing rule:** PASS
- **G3 — Required record variables:** FAIL
- **G4 — Outcome variance:** FAIL for the system disposition, but **reopened for operator annotations**

The strong hypothesis is therefore **refuted**.

The decisive evidence is that **0 of 225 observed dispositions were negative**, with no backward status transitions and no records reaching two terminal states. At the same time, the parsed rule's required variables are often absent from the records on the modules where the rule hypothesis was tested.

A later telemetry sweep found a different signal: **26 of 481 operator-typed comments contain exception markers**, showing that the operator's annotation is variable even though the system disposition is not. This supports a narrower possible target—predicting operator annotation—but that is a materially different task and is not the original decision function.

What survives most strongly is **H3**: operators open a governing reference document before recording a disposition at substantially higher-than-chance rates in 10 of 11 modules. This licenses an evidence-assembly task, not automated decision-making.

---

# 1. Original Hypothesis

The original hypothesis was:

> **Operators apply recoverable written rules to record variables, and an AI system can learn that decision function.**

In its strong form, this hypothesis requires four conditions to hold at once:

- the task and outcome are observable;
- a rule exists and can be recovered;
- the record contains the inputs required by the rule;
- the outcome varies enough to distinguish rule application from confirm-and-proceed behaviour.

The four conditions are tested independently below.

---

# 2. Four-Gate Decision

| Gate | Criterion | Verdict | Evidence |
|---|---|---|---|
| **G1** | Task, record type, and outcome are observed rather than inferred | **PASS** | `records.jsonl`: 3,011 rows; `outcomes.jsonl`: 549 rows; 216 queue tables; `screen_text.jsonl`: 939 captures. All derive from `context.extracted_text`; zero VLM inference |
| **G2** | A governing rule is recoverable from a content-identified document | **PASS** | `documents.jsonl`: 112 content-hashed bodies; the 接待交際費 threshold parses to `<¥50,000 → 部門長 / ≥¥50,000 → 役員 / ≥¥100,000 → 社長` |
| **G3** | The record carries the variables required by that rule | **FAIL** | H4: 4 REFUTED, 7 INSUFFICIENT. 金額 is present on 9.1% of LO\|契約管理 records, 1.0% of HR\|入社手続き records, and 2.3% of FI\|支払処理 records |
| **G4** | Outcome variance is sufficient to distinguish rule application from confirm-and-proceed | **FAIL for system disposition; REOPENED for operator annotation** | 225/225 observed dispositions positive; 0 backward transitions; 0 double-terminal records over 25,495,968 characters. However, 26 of 481 distinct operator-typed comments contain 差異あり / 要注意 / 要確認 |

`[DATASET]` throughout. The reopening of G4 is addressed in §6.

---

# 3. Hypothesis-Level Results

The programme defined and tested **four hypotheses across eleven modules**, producing 44 module-level verdicts.

> **H5–H18 do not exist in the repository.**

Reporting eighteen hypotheses would invent fourteen that were never specified.

Evidence floor:

```text
n ≥ 8 per module
```

Permutation nulls:

```text
10,000 shuffles
seed = 7
```

## 3.1 Summary

| Hypothesis | Verdict Summary |
|---|---|
| **H1** | 8 UNTESTABLE / 3 INSUFFICIENT |
| **H2** | 3 REFUTED / 8 INSUFFICIENT |
| **H3** | **10 SUPPORTED / 1 REFUTED** |
| **H4** | 4 REFUTED / 7 INSUFFICIENT |

---

## 3.2 H1 — Outcome/Disposition Polarity

| Module | n | Statistic | Verdict |
|---|---:|---|---|
| M01 HR\|経費精算・給与変更 | 33 | `{'positive': 33}` | **UNTESTABLE** |
| M02 HR\|勤怠・休暇申請 | 11 | `{'positive': 11}` | **UNTESTABLE** |
| M03 HR\|入社手続き | 36 | `{'positive': 36}` | **UNTESTABLE** |
| M04 HR\|福利厚生申請 | 5 | `{'positive': 5}` | **INSUFFICIENT_EVIDENCE** |
| M05 FI\|請求書承認・経費精算 | 31 | `{'positive': 31}` | **UNTESTABLE** |
| M06 FI\|支払処理 | 11 | `{'positive': 11}` | **UNTESTABLE** |
| M07 FI\|経費承認（管理職） | 5 | `{'positive': 5}` | **INSUFFICIENT_EVIDENCE** |
| M08 FI\|発注管理 | 3 | `{'positive': 3}` | **INSUFFICIENT_EVIDENCE** |
| M09 LO\|在庫管理 | 32 | `{'positive': 32}` | **UNTESTABLE** |
| M10 LO\|契約管理 | 18 | `{'positive': 18}` | **UNTESTABLE** |
| M11 LO\|IT申請 | 16 | `{'positive': 16}` | **UNTESTABLE** |

### Important distinction

`UNTESTABLE` is not equivalent to `REFUTED`.

`[INF]` A REFUTED result means that a test could run and failed to find the proposed relationship.

An UNTESTABLE result means the dependent variable is constant, so the test cannot distinguish a real model from a constant predictor such as:

```text
return "approve"
```

An accuracy of 100% in that setting would be meaningless rather than impressive.

---

## 3.3 H2 — Amount Versus Handling Effort

| Module | n | Statistic | Verdict |
|---|---:|---|---|
| M01 HR\|経費精算・給与変更 | 20 | ρ = -0.2737, p = 0.2317 | **REFUTED** |
| M02 HR\|勤怠・休暇申請 | 1 | — | **INSUFFICIENT_EVIDENCE** |
| M03 HR\|入社手続き | 3 | — | **INSUFFICIENT_EVIDENCE** |
| M04 HR\|福利厚生申請 | 2 | — | **INSUFFICIENT_EVIDENCE** |
| M05 FI\|請求書承認・経費精算 | 19 | ρ = -0.0668, p = 0.7816 | **REFUTED** |
| M06 FI\|支払処理 | 1 | — | **INSUFFICIENT_EVIDENCE** |
| M07 FI\|経費承認（管理職） | 1 | — | **INSUFFICIENT_EVIDENCE** |
| M08 FI\|発注管理 | 1 | — | **INSUFFICIENT_EVIDENCE** |
| M09 LO\|在庫管理 | 8 | ρ = -0.6905, p = 0.0718 | **REFUTED** |
| M10 LO\|契約管理 | 1 | — | **INSUFFICIENT_EVIDENCE** |
| M11 LO\|IT申請 | 2 | — | **INSUFFICIENT_EVIDENCE** |

`[INF]`

For the tested modules, the available evidence does not establish amount as a predictor of handling effort.

---

## 3.4 H3 — Document Consultation

| Module | n | Rate | p-value | Verdict |
|---|---:|---:|---:|---|
| M01 HR\|経費精算・給与変更 | 65 | 0.7846 | 0.0000 | **SUPPORTED** |
| M02 HR\|勤怠・休暇申請 | 14 | 1.0000 | 0.0002 | **SUPPORTED** |
| M03 HR\|入社手続き | 46 | 0.9348 | 0.0000 | **SUPPORTED** |
| M04 HR\|福利厚生申請 | 25 | 0.8400 | 0.0000 | **SUPPORTED** |
| M05 FI\|請求書承認・経費精算 | 46 | 0.8043 | 0.0002 | **SUPPORTED** |
| M06 FI\|支払処理 | 26 | 0.8462 | 0.0163 | **SUPPORTED** |
| M07 FI\|経費承認（管理職） | 24 | 0.8750 | 0.0263 | **SUPPORTED** |
| M08 FI\|発注管理 | 28 | 0.8571 | 0.0000 | **SUPPORTED** |
| M09 LO\|在庫管理 | 34 | 0.6765 | 0.0521 | **REFUTED** |
| M10 LO\|契約管理 | 44 | 0.8636 | 0.0000 | **SUPPORTED** |
| M11 LO\|IT申請 | 29 | 0.6552 | 0.0102 | **SUPPORTED** |

**Result: H3 is supported in 10 of 11 modules.**

---

## 3.5 H4 — Presence of Amount

| Module | n | Amount Present | Verdict |
|---|---:|---:|---|
| M01 HR\|経費精算・給与変更 | 688 | 565/688 = 0.8212 | **INSUFFICIENT_EVIDENCE** |
| M02 HR\|勤怠・休暇申請 | 133 | 12/133 = 0.0902 | **REFUTED** |
| M03 HR\|入社手続き | 410 | 4/410 = 0.0098 | **REFUTED** |
| M04 HR\|福利厚生申請 | 74 | 24/74 = 0.3243 | **INSUFFICIENT_EVIDENCE** |
| M05 FI\|請求書承認・経費精算 | 372 | 324/372 = 0.8710 | **INSUFFICIENT_EVIDENCE** |
| M06 FI\|支払処理 | 132 | 3/132 = 0.0227 | **REFUTED** |
| M07 FI\|経費承認（管理職） | 60 | 23/60 = 0.3833 | **INSUFFICIENT_EVIDENCE** |
| M08 FI\|発注管理 | 29 | 23/29 = 0.7931 | **INSUFFICIENT_EVIDENCE** |
| M09 LO\|在庫管理 | 388 | 203/388 = 0.5232 | **INSUFFICIENT_EVIDENCE** |
| M10 LO\|契約管理 | 241 | 22/241 = 0.0913 | **REFUTED** |
| M11 LO\|IT申請 | 193 | 33/193 = 0.1710 | **INSUFFICIENT_EVIDENCE** |

---

# 4. The Strong Hypothesis Is Refuted

The original hypothesis is **false in its strong form**.

`[DATASET] + [INF]`

The decisive fact is:

> **0 negative outcomes in 225 observed dispositions.**

This is corroborated by:

- 0 backward status transitions;
- 0 records reaching two terminal states;
- 0 negative terms in disposition position;
- 25,495,968 characters of telemetry searched.

There is therefore **no supervision signal for a decision function**.

A model trained on this dataset could learn:

```text
return approve
```

and achieve 100% on every split.

That would not demonstrate a successful decision model. It would demonstrate that the evaluation target is constant.

The problem is therefore structural rather than a question of model quality.

---

# 5. Why the Refutation Is Structural

`[INF]`

G3 and G4 fail for mutually compatible reasons.

If operators were applying the parsed threshold rule, the record would need to contain the variable required by that rule.

Yet on three of the four REFUTED H4 modules, 金額 appears on only **1–9% of records**.

Thus the variable required to apply the proposed rule is generally absent from the record being processed.

The two observations reinforce one another:

> **The deciding variable is usually absent from the record, and the system-level decision never varies.**

This is inconsistent with the strong interpretation that operators are applying a recoverable rule to record variables.

It is more consistent with the observed workflow being **confirmation rather than adjudication**.

## 5.1 The Single Contradictory Record

One in-scope test of the parsed threshold rule produces a contradiction:

```text
Record: P1-07048822-009
Category: 接待交際費
Amount: ¥123,224
```

The parsed rule states that amounts ≥ ¥100,000 require:

```text
社長承認
```

but the system displays:

```text
承認権限 = 役員
```

`[DATASET]` OBSERVED.

However:

> **n = 1.**

This single record cannot establish a general conclusion. It is retained because it is the only in-scope test of the only parsed threshold rule and therefore defines an important limitation of the evidence.

---

# 6. Phase 3.9 — Free Sweep and G4 Reopening

A subsequent free sweep searched for negative, exception, and reversal signals across the complete telemetry.

The sweep covered:

- **31 negative/exception/reversal terms**
- **1,563,587 string values**
- **25,495,968 characters**
- **20,477 events**
- **4,746 screenshot filenames**
- **898 record-status series**

A keyword-free structural reversal test was also applied.

`[DATASET]`

## 6.1 System-Disposition Null Result

For the system disposition, the null result remains:

- 0 candidate negative outcomes
- 0 backward transitions
- 0 lateral transitions
- 0 records with two terminal states
- 0 filename hits

Therefore, the original conclusion about the **system-level disposition target** remains unchanged.

---

## 6.2 The UI Contains an Unused Rejection Path

The disposition comment box is labelled:

> 「承認コメントまたは**差戻し**理由を入力してください…」

Meaning: enter an approval comment or a send-back reason.

`[DATASET]` This text occurs **1,748 times**.

`[INF]` The evidence establishes that `差戻し` is a **supported UI action that was never exercised during this capture window**.

This does not prove that rejection never occurs in real operation. It establishes only that this approximately two-hour dataset contains no observed instance of that branch.

---

## 6.3 G4 Reopens for Operator Annotations

`payload.target_field.value` on keystroke events records what the operator typed.

This produces:

- **481 distinct comments**
- **1,347 comment-related events**

This evidence source is roughly half the size of the `extracted_text` corpus and was missed by the initial Pass 0 analysis, which examined only `context.extracted_text`.

### Exception-marked comments

**26 of 481 comments (5.4%) contain an exception marker.**

| Clean Annotation | n | Flagged Annotation | n | Module |
|---|---:|---|---:|---|
| 差異なし | 36 | **差異あり** | **19** | 請求書照合 |
| 通常 | 46 | **要注意** | **7** | 発注管理 |
| 確認完了 | 16 | 要確認 | 19 | — |

Examples:

> 「請求書照合完了。INV-2026-7351　金額：1,218,687円。**差異あり要確認**。」

> 「発注管理処理。発注変更：サーバー保守部品　数量 380　合計 14,078,240円　**要注意**。発注書確認・**登録完了**。」

Importantly:

> **Every flagged record was still disposed positively.**

The second example is explicitly flagged and nevertheless completed in the same sentence.

### Interpretation

`[INF]`

There is therefore a supervision signal—but it is **not the target proposed by the original hypothesis**.

The potentially learnable target is:

> **predict the operator's annotation**

rather than:

> **predict the system disposition**

This is a materially smaller and different task, with observed flagged counts of only **n = 19** and **n = 7** in the identified categories.

It should not be conflated with decision prediction.

---

## 6.4 Correction to the Analysis History

The initial analysis committed to a clean null result and closed G4.

Commit `d5b2f67` read only locations where a system outcome would appear and did not inspect operator-entered text.

This was corrected in commit `a83111b`.

Both commits remain in the project history.

This correction is retained explicitly rather than silently overwriting the earlier result.

---

# 7. What Survives

## H3: Document Consultation

**H3 is supported in 10 of 11 modules.**

The observed rates range from approximately **0.66 to 1.00**, against a permutation null that places document-open events uniformly within the same execution span; most p-values are < 0.001.

`[DATASET]`

The surviving empirical statement is:

> Operators retrieve a record, **open a governing reference document**, and record a disposition more often than expected under chance placement.

### What this licenses

The evidence supports the claim that:

- document consultation is a real and near-universal step in the observed workflow;
- identifying which document is being consulted is a well-posed task;
- observed document-open events provide labels for that task.

### What this does not license

`[INF]`

H3 measures **sequence, not causation**.

It does not establish that document content determined the outcome.

The operator may consult the document:

- to confirm a decision already made;
- to satisfy a procedural requirement;
- out of habit;
- or for another reason not represented in the telemetry.

The G3 and G4 results make the causal interpretation unsupported: the proposed deciding variable is often absent from the record, while the system-level outcome does not vary.

---

# 8. Threats to Validity

Unless otherwise marked, the following limitations are `[DATASET]`.

### 8.1 Limited `extracted_text` Coverage

`extracted_text` covers **4.59% of events**:

```text
939 / 20,477
```

Therefore, every content-based claim is measured on the subset of screens that happened to be captured with text.

There is no direct evidence about the remaining events.

### 8.2 Redaction

`clipboard_change.text_content` is null on all **872 events**; only `text_length` survives.

Element and field labels are hashed in:

```text
uia_v2
dom_v2
```

### 8.3 Compressed Waiting Times

`README.md` states that waits are compressed in the capture environment.

Therefore:

> **All durations are comparative only. No duration in this document should be interpreted as wall-clock effort.**

### 8.4 Limited Observation Window

The dataset covers approximately:

- **2 hours**
- **15 sessions**
- **4 operators**

It therefore provides no basis for conclusions about:

- seasonality;
- workload volume;
- broader operational variation;
- the rejection branch that the UI supports but which did not occur in the observed window.

### 8.5 Module-Key Reconciliation

The module keys disagree.

Under ADR-022, the URL is incorrect about the displayed screen in approximately **21% of captures**, and `FI|予算差異分析` is missing from the existing inventory.

Per-module counts that were originally keyed by URL inherit this limitation.

### 8.6 Parser Defect

A parser defect discovered during Phase 3.9 remains documented rather than silently patched.

`records.py` misassigns `status_ja` on the 発注管理 table for **19 rows**, placing a record ID in the status field because that table has a different column count.

This does **not** affect the outcome counts, which come from toasts.

### 8.7 Single-Record Rule Test

The only in-scope test of the only parsed threshold rule has:

```text
n = 1
```

No general conclusion can be drawn from it.

---

# 9. Constraint Imposed on Step 3

This section states the implication for the next phase without replacing the Step 3 design document.

The appropriate Step 3 target is documented separately in:

```text
docs/STEP3_TARGET_REFRAME.md
```

The constraint imposed by this verification is:

> **A system built on Dataset B cannot be evaluated on whether it decides correctly, because no incorrect decision was observed.**

The defensible evaluation target is whether the system can:

> **assemble and surface the right evidence**

This is what H3 supports, and it is the strongest conclusion the present dataset licenses.

---

# 10. Final Decision Gate

| Question | Result |
|---|---|
| Is the original strong decision-learning hypothesis supported? | **No — refuted** |
| Is the task/outcome observable? | **Yes** |
| Is a governing rule recoverable? | **Yes** |
| Does the record consistently contain the rule's required inputs? | **No** |
| Does the system disposition provide sufficient target variance? | **No** |
| Does operator-entered annotation contain a smaller variable signal? | **Yes, but sparsely** |
| Is document consultation empirically supported? | **Yes, in 10 of 11 modules** |
| Can Dataset B justify automated disposition? | **No** |
| Can Dataset B support evidence-assembly / document-identification work? | **Yes** |

### Bottom line

The evidence does **not** support building an AI system that decides the disposition.

It **does** support a narrower, testable problem around **identifying and assembling the evidence operators consult before recording the disposition**.

That is the boundary that should be carried into Step 3.
