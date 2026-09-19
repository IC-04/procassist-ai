# Step 2.5 — hypothesis verification

**The strong hypothesis is false on this dataset.** This document makes that a deliverable
rather than a gap.

Every claim is tagged OBSERVED / INFERENCE and carries its artifact. No VLM was used anywhere in
this programme (`docs/PHASE4_SCOPE_DECISION.md`): every number below comes from telemetry the
recorder already captured.

---

## 1. The hypothesis, as originally stated

> Operators apply recoverable written rules to record variables, and an AI system can learn that
> decision function.

In its strong form this requires four things to be true at once: that the task and outcome are
observable; that a rule exists and can be recovered; that the record carries the rule's inputs;
and that the outcome varies enough to tell rule-application apart from confirm-and-proceed.

---

## 2. The four-gate decision table

| Gate | Criterion | Verdict | Evidence |
|---|---|---|---|
| **G1** | Task, record type and outcome are OBSERVED, not inferred | **PASS** | `records.jsonl` 3,011 rows · `outcomes.jsonl` 549 rows · 216 queue tables · `screen_text.jsonl` 939 captures — all from `context.extracted_text`, zero VLM inference |
| **G2** | A governing rule is recoverable from a content-identified document | **PASS** | `documents.jsonl` 112 content-hashed bodies; 接待交際費 threshold parsed to `<¥50,000→部門長 / ≥¥50,000→役員 / ≥¥100,000→社長` |
| **G3** | The record carries the variables that rule needs | **FAIL** | H4: 4 REFUTED, 7 INSUFFICIENT. 金額 present on 9.1% (LO 契約管理), 1.0% (HR 入社手続き), 2.3% (FI 支払処理) of records |
| **G4** | The outcome variable has enough variance to distinguish rule-application from confirm-and-proceed | **FAIL for the system disposition · REOPENED for the operator's annotation** | 225/225 toasts positive, 0 backward transitions, 0 double-terminal records over 25,495,968 characters — **but** 26 of 481 distinct operator-typed comments carry 差異あり / 要注意 / 要確認 |

`[DATASET]` OBSERVED throughout. G4's reopening is §6.

---

## 3. Per-hypothesis verdicts

**H5–H18 do not exist.** The programme defined and tested four hypotheses; no H5 through H18 was
ever specified in any document in this repository. Reporting eighteen would be inventing fourteen.
What exists is **four hypotheses × eleven modules = 44 verdicts**, all in
`build/dataset_b/evidence/hypothesis_tests.json`.

Declared before the numbers were inspected: evidence floor **n ≥ 8** per module; permutation
nulls at **10,000 shuffles, seed 7**.

| Summary | count |
|---|---|
| H1 UNTESTABLE / INSUFFICIENT | 8 / 3 |
| H2 REFUTED / INSUFFICIENT | 3 / 8 |
| **H3 SUPPORTED / REFUTED** | **10 / 1** |
| H4 REFUTED / INSUFFICIENT | 4 / 7 |

| H | Module | n | Statistic | Verdict |
|---|---|---|---|---|
| H1 | M01 HR|経費精算・給与変更 | 33 | polarity {'positive': 33} | **UNTESTABLE** |
| H1 | M02 HR|勤怠・休暇申請 | 11 | polarity {'positive': 11} | **UNTESTABLE** |
| H1 | M03 HR|入社手続き | 36 | polarity {'positive': 36} | **UNTESTABLE** |
| H1 | M04 HR|福利厚生申請 | 5 | polarity {'positive': 5} | **INSUFFICIENT_EVIDENCE** |
| H1 | M05 FI|請求書承認・経費精算 | 31 | polarity {'positive': 31} | **UNTESTABLE** |
| H1 | M06 FI|支払処理 | 11 | polarity {'positive': 11} | **UNTESTABLE** |
| H1 | M07 FI|経費承認（管理職） | 5 | polarity {'positive': 5} | **INSUFFICIENT_EVIDENCE** |
| H1 | M08 FI|発注管理 | 3 | polarity {'positive': 3} | **INSUFFICIENT_EVIDENCE** |
| H1 | M09 LO|在庫管理 | 32 | polarity {'positive': 32} | **UNTESTABLE** |
| H1 | M10 LO|契約管理 | 18 | polarity {'positive': 18} | **UNTESTABLE** |
| H1 | M11 LO|IT申請 | 16 | polarity {'positive': 16} | **UNTESTABLE** |
| H2 | M01 HR|経費精算・給与変更 | 20 | rho=-0.2737, p=0.2317 | **REFUTED** |
| H2 | M02 HR|勤怠・休暇申請 | 1 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M03 HR|入社手続き | 3 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M04 HR|福利厚生申請 | 2 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M05 FI|請求書承認・経費精算 | 19 | rho=-0.0668, p=0.7816 | **REFUTED** |
| H2 | M06 FI|支払処理 | 1 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M07 FI|経費承認（管理職） | 1 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M08 FI|発注管理 | 1 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M09 LO|在庫管理 | 8 | rho=-0.6905, p=0.0718 | **REFUTED** |
| H2 | M10 LO|契約管理 | 1 |  | **INSUFFICIENT_EVIDENCE** |
| H2 | M11 LO|IT申請 | 2 |  | **INSUFFICIENT_EVIDENCE** |
| H3 | M01 HR|経費精算・給与変更 | 65 | rate=0.7846, p=0.0 | **SUPPORTED** |
| H3 | M02 HR|勤怠・休暇申請 | 14 | rate=1.0, p=0.0002 | **SUPPORTED** |
| H3 | M03 HR|入社手続き | 46 | rate=0.9348, p=0.0 | **SUPPORTED** |
| H3 | M04 HR|福利厚生申請 | 25 | rate=0.84, p=0.0 | **SUPPORTED** |
| H3 | M05 FI|請求書承認・経費精算 | 46 | rate=0.8043, p=0.0002 | **SUPPORTED** |
| H3 | M06 FI|支払処理 | 26 | rate=0.8462, p=0.0163 | **SUPPORTED** |
| H3 | M07 FI|経費承認（管理職） | 24 | rate=0.875, p=0.0263 | **SUPPORTED** |
| H3 | M08 FI|発注管理 | 28 | rate=0.8571, p=0.0 | **SUPPORTED** |
| H3 | M09 LO|在庫管理 | 34 | rate=0.6765, p=0.0521 | **REFUTED** |
| H3 | M10 LO|契約管理 | 44 | rate=0.8636, p=0.0 | **SUPPORTED** |
| H3 | M11 LO|IT申請 | 29 | rate=0.6552, p=0.0102 | **SUPPORTED** |
| H4 | M01 HR|経費精算・給与変更 | 688 | 金額 on 565/688 = 0.8212 | **INSUFFICIENT_EVIDENCE** |
| H4 | M02 HR|勤怠・休暇申請 | 133 | 金額 on 12/133 = 0.0902 | **REFUTED** |
| H4 | M03 HR|入社手続き | 410 | 金額 on 4/410 = 0.0098 | **REFUTED** |
| H4 | M04 HR|福利厚生申請 | 74 | 金額 on 24/74 = 0.3243 | **INSUFFICIENT_EVIDENCE** |
| H4 | M05 FI|請求書承認・経費精算 | 372 | 金額 on 324/372 = 0.871 | **INSUFFICIENT_EVIDENCE** |
| H4 | M06 FI|支払処理 | 132 | 金額 on 3/132 = 0.0227 | **REFUTED** |
| H4 | M07 FI|経費承認（管理職） | 60 | 金額 on 23/60 = 0.3833 | **INSUFFICIENT_EVIDENCE** |
| H4 | M08 FI|発注管理 | 29 | 金額 on 23/29 = 0.7931 | **INSUFFICIENT_EVIDENCE** |
| H4 | M09 LO|在庫管理 | 388 | 金額 on 203/388 = 0.5232 | **INSUFFICIENT_EVIDENCE** |
| H4 | M10 LO|契約管理 | 241 | 金額 on 22/241 = 0.0913 | **REFUTED** |
| H4 | M11 LO|IT申請 | 193 | 金額 on 33/193 = 0.171 | **INSUFFICIENT_EVIDENCE** |
### 3.1 UNTESTABLE is not REFUTED, and the difference matters

`[INF]` H2 REFUTED means a test ran and found nothing: amount does not predict handling effort
(ρ = −0.27, −0.07, −0.69; p = 0.23, 0.78, 0.07). That is a result about the world.

H1 UNTESTABLE means **no test can run**. The dependent variable is a constant, so every
predictor — including `return "approve"` — scores 100%. An accuracy figure here would not be a
weak result; it would be a meaningless one, and reporting it would be the error. This is the
more serious of the two facts.

---

## 4. The refutation, stated plainly

**The original hypothesis is false in its strong form.** `[DATASET]` + `[INF]`

The decisive fact is **0 negative outcomes in 225 observed dispositions**, corroborated by 0
backward status transitions, 0 records reaching two terminal states, and 0 negative terms in
disposition position across 25,495,968 characters of telemetry.

There is therefore **no supervision signal for a decision function**. A model trained on this
data learns `return approve`, scores 100% on every split, and is worth nothing. The failure is
not that the model would be weak — it is that the evaluation cannot distinguish a good model
from a constant.

---

## 5. Why the refutation is structural, not a measurement artifact

`[INF]` G3 and G4 fail for **compatible reasons**, and that is what makes this more than a
sampling accident.

If the operator were applying the parsed threshold rule, the record would have to carry 金額.
On three of the four REFUTED modules it carries it on **1–9%** of records. The deciding variable
is absent from the thing being decided on.

So the two failures corroborate: **the operator is not deciding from the record, and there is no
decision recorded**. A dataset where the rule's input is missing *and* the rule's output never
varies is not a dataset where a decision is being made and we failed to measure it. It is a
dataset where the observed work is confirmation, not adjudication.

**The single contradiction, reported at its true weight.** `P1-07048822-009`: 接待交際費,
¥123,224, which is ≥¥100,000, so the parsed rule says 社長承認 — and the system shows 承認権限
= 役員. `[DATASET]` OBSERVED. **n = 1.** One record supports no conclusion. It is recorded
because it is the only in-scope test of the only parsed threshold rule in the dataset, and
because a single contradiction is worth more as a stated limit than as an omission.

---

## 6. Phase 3.9 — the free sweep, and what it changed

31 negative/exception/reversal terms were swept across **every string value in every event** —
1,563,587 values, 25,495,968 characters, 20,477 events — plus 4,746 screenshot filenames and 898
record-status series, with a keyword-free structural test for reversal. `[DATASET]`

**For the system disposition, the null result holds:** 0 candidate negative outcomes, 0 backward
transitions, 0 lateral transitions, 0 records with two terminal states, 0 filename hits.

**Two findings changed the picture anyway.**

### 6.1 The UI exposes a rejection path that was never used

The disposition comment box is labelled:

> 「承認コメントまたは**差戻し**理由を入力してください…」 — *enter an approval comment or a send-back reason*

`[DATASET]` OBSERVED, 1,748 occurrences. `[INF]` So 差戻し (send-back) is a **supported action
that was never exercised in this window**. This reframes G4: the dataset does not show that
rejection never happens — it shows that this ~2-hour capture contains none. Any system built or
evaluated here has never seen the branch the interface is built around.

### 6.2 G4 REOPENS — for the operator's annotation, not the system's outcome

`payload.target_field.value` on keystroke events carries **what the operator typed**: 481
distinct comments over 1,347 events, an evidence source roughly half the size of the
`extracted_text` corpus and **entirely missed by Pass 0**, which read only `context.extracted_text`.

`[DATASET]` OBSERVED — **26 of 481 (5.4%) carry an exception marker:**

| Clean | n | Flagged | n | Module |
|---|---|---|---|---|
| 差異なし | 36 | **差異あり** | **19** | 請求書照合 (invoice matching) |
| 通常 | 46 | **要注意** | **7** | 発注管理 (PO management) |
| 確認完了 | 16 | 要確認 | 19 | — |

> 「請求書照合完了。INV-2026-7351　金額：1,218,687円。**差異あり要確認**。」
> 「発注管理処理。発注変更：サーバー保守部品　数量 380　合計 14,078,240円　**要注意**。発注書確認・**登録完了**。」

**Every flagged record was still disposed positively.** The second example is flagged *and*
completed in the same sentence.

`[INF]` So there **is** a supervision signal, and it is not the one the hypothesis assumed. The
learnable target is **"predict the annotation"**, not "predict the decision" — a different and
much smaller claim, at n = 19 and n = 7.

**This also corrects a claim I made and committed.** Commit `d5b2f67` reported a clean null
result and closed G4. It read only the places a *system* outcome would appear and never looked
at what the operator wrote. Corrected in `a83111b`; both commits stand in history.

---

## 7. What survives

**H3 is SUPPORTED in 10 of 11 modules** `[DATASET]`, at rates 0.66–1.00 against a permutation
null that places document-open events uniformly inside the same execution span, most p < 0.001.

> Operators retrieve a record, **open a governing reference document**, and record a
> disposition — far more often than chance placement.

**What that licenses:** that document consultation is a real and near-universal step in this
work, and that identifying *which* document is being consulted is a well-posed task with
observed labels.

**What it does not license** `[INF]`: any claim that the document's content *determined* the
outcome. H3 measures sequence, not causation. The operator may consult the document to confirm a
decision already made, to satisfy a procedural requirement, or out of habit. G3 and G4 make the
causal reading actively unlikely — the deciding variable is usually absent from the record, and
the outcome never varies.

---

## 8. Threats to validity

`[DATASET]` unless marked.

1. **`extracted_text` covers 4.59% of events** (939 of 20,477). Every content claim is measured
   on the subset of screens that happened to be captured with text. There is no evidence about
   the rest.
2. **Redaction.** `clipboard_change.text_content` is null on all 872 events; only `text_length`
   survives. Element and field labels are hashed in `uia_v2` and `dom_v2`.
3. **Compressed waiting times.** `README.md` states waits are compressed in the capture
   environment, so **all durations are comparative only**. No figure here is wall-clock effort.
4. **One ~2-hour window, 15 sessions, 4 operators.** No seasonality, no volume, and — per §6.1 —
   no observed instance of the rejection branch the UI supports.
5. **Module keys disagree** (ADR-022): the URL is wrong about the displayed screen in 21% of
   captures, and `FI|予算差異分析` is missing from the inventory entirely. Per-module counts in
   §3 are keyed by URL and inherit that error.
6. **A parser defect found during Phase 3.9 and left in place:** `records.py` mis-assigns
   `status_ja` on the 発注管理 table, putting a record id in the status field on 19 rows, because
   that table has a different column count. It does not affect the outcome counts, which come
   from toasts, and it is recorded rather than quietly patched.
7. **`n = 1`** for the only in-scope test of the only parsed threshold rule (§5).

---

## 9. What this means for Step 3

Not a recommendation — that is `docs/STEP3_TARGET_REFRAME.md`. Only the constraint this document
imposes:

**A system built on Dataset B cannot be evaluated on whether it decides correctly**, because no
incorrect decision was ever observed. It can be evaluated on whether it **assembles the right
evidence** — which is what H3 licenses, and the only thing it licenses.
