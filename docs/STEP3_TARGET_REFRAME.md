# Step 3 — target reframe: prepare-and-present, not decide

**This document ends at a decision gate. No Step 3 implementation is started.**

The strong hypothesis is refuted (`docs/STEP2_HYPOTHESIS_VERIFICATION.md`). This is what
survives it, tested for feasibility and made to earn its place against a deterministic baseline.

---

## 1. The reframed claim

> Operators perform **document-referenced confirmation work**: they retrieve a record, locate
> and open a governing reference document, and record a disposition.

`[DATASET]` OBSERVED. Supported by H3 in 10 of 11 modules, rates 0.66–1.00 against a
permutation null, most p < 0.001.

The candidate system is **prepare-and-present**: assemble the record and its linked fields,
identify and surface the governing document, pre-fill the templated comment, flag records whose
fields are incomplete relative to what the governing document requires — **and the human
decides.**

---

## 2. The one genuinely non-trivial sub-task: governing-document retrieval

**Input:** (module, record type, record fields, screen context). **Output:** the reference
document the operator will open. **Ground truth:** the observed (disposition, document-open)
pairs that produced H3.

### 2.1 How much labelled data actually exists

`[DATASET]` OBSERVED — `build/dataset_b/evidence/retrieval_feasibility.json`:

| | |
|---|---|
| dispositions total | 629 |
| **with a document opened before them, inside the same execution** | **148 (23.5%)** |
| without | 481 |
| distinct document labels | **17** (by heading) |
| majority label share | 18.9% (`新規取引先登録手続き`) |

| Module | n | | Module | n |
|---|---|---|---|---|
| HR\|入社手続き | 33 | | HR\|福利厚生申請 | 11 |
| HR\|経費精算・給与変更 | 24 | | FI\|経費承認（管理職） | 9 |
| LO\|契約管理 | 19 | | FI\|支払処理 | 8 |
| FI\|請求書承認・経費精算 | 17 | | LO\|在庫管理 | 8 |
| FI\|発注管理 | 16 | | HR\|勤怠・休暇申請 | 3 |

Nine of eleven modules clear the declared n ≥ 8 floor.

**The label space had to be settled before any of this meant anything.** `[INF]` Keying
documents on content `sha256` — correct for "are these the same bytes" — gives **50 labels**,
because a long regulation captured at two scroll positions yields two ids. Keying on the
document's own first heading gives **17**, close to the 13 reference documents Dataset B is
stated to contain. Both are reported; the hash space is the pessimistic bound and depresses
every score by roughly 20 points.

### 2.2 Does n support evaluation?

**Barely, and not for the question that matters.** Leave-one-out is used rather than a held-out
split, because a split would spend evidence the task cannot spare. At n = 148 the 95% Wilson
interval on a single accuracy estimate is roughly ±7.5 points — wide enough that the interesting
comparisons are unresolvable. Per-module n of 3–33 supports no per-module model at all.

---

## 3. The decisive test — AI does not earn its place

`[DATASET]` Leave-one-out, seed 7, heading label space, n = 148:

| Baseline | Accuracy |
|---|---|
| **B0** random | 5.4% |
| **B1** most-frequent document overall | 18.9% |
| **B2** most-frequent document **per module** | **52.7%** |
| **B3** deterministic `(module, record type) → document` lookup | **64.2%** — 95% CI **56.2–71.5%** |

### The finding

**A lookup table gets 64.2%, and a learned retriever would have to exceed 71.5% before this
evidence could distinguish it from that table at all.** `[INF]`

That is the honest answer and it is not the AI answer. **The recommendation is a lookup table
plus a good UI**, instrumented so the residual is measured in production. Nothing in Dataset B
justifies a learned retriever today.

### What would have to be true for a learned component to earn its place

`[INF]`, stated so the door is open on evidence rather than on hope:

1. **More documents, or a growing set.** 17 labels with one covering 18.9% is a small, static
   space — exactly where a table wins. A client with hundreds of policies, or policies that
   change monthly, inverts that.
2. **Per-record conditioning that the table cannot express.** B3 keys on (module, record type).
   If the governing document depends on amount band, vendor, or employee class, a table needs a
   row per combination and a model does not.
3. **The ambiguous residual is genuinely ambiguous.** B3's 35.8% of errors may be dominated by
   one or two confusable document pairs — in which case the fix is a better key, not a model.
   **This is measurable now and was not measured**, and it is the first thing to do before
   anyone writes a retriever.

---

## 4. Which module to target

`[INF]`, from the Phase 3.5 inventory (ADR-022) and §2.1.

**`FI|請求書承認・経費精算` (invoice approval).** Not the largest, and chosen for reasons the
other candidates fail:

- **It is the only module where the operator's recorded judgement varies.** 19 comments read
  `差異あり要確認` against 36 `差異なし承認` `[DATASET]`. Everywhere else the annotation is constant,
  so there is nothing to surface and nothing to be right or wrong about.
- **The record carries an amount.** H4: 87.1% of its records have 金額, against 1–9% on the
  REFUTED modules. A prepare-and-present system needs the variable to present.
- **n = 17 labelled retrieval pairs**, above the floor.
- **The comment is templated** — `請求書照合完了。INV-XXXX　金額：¥N。差異{なし承認|あり要確認}。` — so
  pre-filling is well-defined and the only free slot is the one judgement the operator makes.

**Rejected:** `HR|入社手続き` has the most retrieval pairs (33) but 金額 on 1.0% of records and no
annotation variance. `LO|契約管理` is the largest by time in the current inventory but carries 金額
on 9.1%, so its ¥1M/¥30M authority rule is inapplicable as recorded, and ADR-022 puts its true
execution count somewhere between 8 and 26.

---

## 5. What the system cannot do — stated first-class

`[DATASET]` + `[INF]`

1. **It cannot decide.** 0 of 225 observed dispositions were negative. There is no supervision
   signal for a decision function.
2. **It cannot detect errors.** No incorrect disposition was ever observed, so there are no
   negative examples and no way to measure a false-accept rate.
3. **It cannot be evaluated against rejection behaviour** — even though the UI supports it. The
   comment box reads 「承認コメントまたは**差戻し**理由を入力してください…」, so 差戻し is a supported
   action that **never occurred in this window**. A system built here has never seen the branch
   the interface is built around.
4. **It cannot claim its retrieval is useful**, only that it matches what was opened. Nothing
   measures whether the document helped.
5. **It applies to under a quarter of the work as posed.** 481 of 629 dispositions have no
   document open before them.

---

## 6. The human-in-the-loop contract

| | |
|---|---|
| **Surfaced** | the record and its fields; the governing document, opened to the relevant clause; the fields the document requires that the record does not carry |
| **Pre-filled** | the templated comment, with the judgement slot **left blank** |
| **The operator must still do** | make and record the judgement (`差異なし` / `差異あり`), click the disposition, and override the suggested document when it is wrong |
| **Never automated** | the disposition click. There is no evidence licensing it. |

---

## 7. Measurable success criteria that need no negative class

`[INF]` Each is measurable against the current telemetry as a baseline.

| Criterion | Baseline today | Measured how |
|---|---|---|
| Document-retrieval top-1 accuracy | **64.2%** (B3) | against observed document-opens |
| Document-retrieval top-3 accuracy | not measured | same labels, ranked output |
| Seconds from record-open to disposition | measurable per module | existing telemetry |
| Operator override rate on the suggested document | n/a — new | instrument the suggestion |
| Share of dispositions with a pre-filled comment accepted unedited | n/a — new | instrument the comment box |
| Share of records flagged incomplete that the operator agreed with | n/a — new | instrument the flag |

The last three do not exist yet and are the reason to instrument before modelling: **they are
the measurements that would tell us whether a learned component is needed**, and none of them
requires a negative class.

---

## 8. The single strongest reason this may still be wrong

`[INF]` **H3 measures sequence, not causation.** The operator opens the document before
disposing far above chance — but G3 and G4 together suggest they are not deciding from it. If
the document-open is procedural, or habitual, or a UI artifact of where the file happened to be,
then surfacing it faster saves keystrokes and changes nothing about the work. This programme
cannot distinguish those, and no amount of Dataset B can: it would take an operator interview or
an A/B test with the document suppressed.
