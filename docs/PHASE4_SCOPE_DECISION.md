# Phase 4 — Scope Decision: Blanket VLM Pass Cancelled

## Submission-Ready Decision Record

| Field | Value |
|---|---|
| **Artifact type** | Phase decision / evidence record |
| **Decision** | Blanket VLM pass cancelled; zero VLM calls |
| **Dataset** | Dataset B |
| **Scope** | Phase 4-Micro / evidence review |
| **Status** | **Final decision record** |
| **Spend** | **$0.00** |
| **Implementation consequence** | Bounded visual-extraction capability retained; no blanket execution |

> **Submission note:** This document records a completed scope decision supported by observed telemetry and bounded verification. It does **not** claim that visual extraction is universally unnecessary; it records why the blanket Phase 4 pass was not justified for the questions examined, what residual uncertainty remains, and what capability was retained for controlled future use.

## Reviewer Navigation

1. Original Phase 4 premise and why it no longer applies
2. Three sanctioned Phase 4-Micro questions and answers
3. Bounded visual-extraction capability retained
4. Actual spend
5. Known cost of the cancellation

## Submission Integrity

- Evidence-derived observations are explicitly marked `[DATASET]`; inferences are explicitly marked `[INF]`.
- The decision is based on the available text telemetry and bounded verification described below.
- Zero VLM calls means no visual-model result is presented as evidence.
- Residual uncertainty is stated explicitly rather than treated as resolved.
- The retained extractor is fail-safe and auditable; it does not silently substitute a different provenance path.
- This record does not expand the Phase 4 scope beyond the questions and residual defined here.

---

## 1. Original Scope and Why It No Longer Applies

Phase 4 was designed before Pass 0 ran. Its premise was that the screens were only available as
pixels, so a vision model would be needed to read record values, queue contents and badges
across 4,746 screenshots.

Two discoveries removed that premise:

| Discovery | Where | Scale |
|---|---|---|
| `context.extracted_text` — the recorder already captures screen text | Pass 0 | **939 captures**, incl. 216 queue tables, 5 detail panes |
| `payload.target_field.value` — the recorder already captures what the operator **typed** | Phase 3.9 | **481 distinct comments** over 1,347 keystroke events |

`[INF]` A blanket pass would have been spending to re-derive what the telemetry already
contains, in lower fidelity: the text is exact, and OCR of a JPEG is not.

**Corroborating evidence that OCR is the wrong tool here.** The recorder itself ran OCR on 15
events (`extensions.ocr_v1.full_text`) and the output is unusable — it renders 第1条(目的) as
`第1条(白的)`, and interleaves Word ribbon chrome ("Mailings Review View Help", "NO Spacing")
with the document body. `[DATASET]` OBSERVED. Separately, `tesseract` is not installed on this
machine at all, and ADR-007's rejection of global OCR pipelines stands.

---

## 2. Sanctioned Phase 4-Micro Questions and Answers

### Q1 — what does the ⚠ marker on FI|発注管理 denote? **ANSWERED FROM TEXT**

Candidate meanings, declared before looking: a validation failure; an amount over an approval
threshold; a data-completeness warning; an operator-set flag.

`[DATASET]` OBSERVED — 7 of 481 distinct operator-typed comments, all on 発注管理:

> 「発注管理処理。発注変更：サーバー保守部品　数量 380　合計 14,078,240円　**要注意**。発注書確認・登録完了。」

`要注意` ("requires attention") is **the operator's own annotation**, typed into the comment
box — the fourth candidate. And the same sentence ends in `登録完了`: the record is **flagged and
still completed**. The marker accompanies processing; it does not block it.

`[INF]` This is a better answer than a VLM would have given. A vision model could have reported
that a warning glyph is present; the text shows who put it there and what happened next.

### Q2 — what authority fields exist, and are they per-record or per-user? **ANSWERED FROM TEXT**

`[DATASET]` OBSERVED — 2 of the 5 detail-pane captures carry a parsed `参照` line:

| Record | 区分 | 金額 | 申請者区分 | 承認権限 |
|---|---|---|---|---|
| `P1-07048822-009` | 接待交際費 | ¥123,224 | manager | **役員** |
| `P1-07080388-001` | 出張旅費 | ¥56,120 | regular | **部門長** |

Both fields vary between the two records, and so do the amounts. **The field is per-record.**
`[INF]` n=2, which is enough to show the field is not a per-user constant and not enough for
anything else.

### Q3 — visually confirm a negative-state candidate. **SKIPPED**

Phase 3.9 found no negative *system* state to confirm: 0 candidate negative outcomes in screen
text, 0 backward transitions, 0 records reaching two terminal states, over 25,495,968 characters.
The variance it did find is operator-typed text, which needs no visual confirmation.
`[DATASET]`

---

## 3. Bounded Capability Retained, and Why

The capability exists, bounded and auditable, so that **not spending is a measured decision
rather than an absence**:

- `VisualExtractor` protocol with backends `null` (default) / `openai` / `anthropic` / `gemini` /
  `local`, selected by environment variable.
- **Fail-safe verified**: with no key set, `make_extractor("anthropic")` exits non-zero with
  `backend 'anthropic' requires the environment variable ANTHROPIC_API_KEY, which is not set.`
  No key is hard-coded, prompted for, or read from a file, and there is **no silent fallback** —
  falling back would change the provenance of every downstream claim.
- Hard cap of **60 images** across all questions combined. A question needing more is not a
  Phase 4-Micro question.
- `--dry-run` is the default; `--execute` is required to send anything.
- The residual is defined and measurable: **60 decision-adjacent states lacking a text capture
  within 10 events** — that is what *would* have been sent.

---

## 4. Actual Spend

| | |
|---|---|
| images sent | **0** |
| API calls | **0** |
| cost | **$0.00** |
| ledger rows | **0** (`build/dataset_b/evidence/vlm_ledger.jsonl`) |

---

## 5. Cost and Residual Uncertainty

Stated plainly, because a cancellation should carry its own downside: `[INF]`

- The **60 decision-adjacent states with no nearby text capture** remain unread. If a
  disposition was driven by something visible only in those frames, we cannot see it.
- Badge **colour** is unrecoverable. `要注意` is recovered as a word, but whether the UI also
  colour-codes severity is unknown, and colour is exactly what text cannot carry.
- The 5 detail panes are all we have of per-record authority fields. A VLM pass over the
  residual might have found more, at n greater than 2.

`[INF]` None of these changes the Phase 5 verdict, because that verdict turns on the *absence*
of negative outcomes across the whole corpus, and reading 60 more frames cannot manufacture a
class that 25.5M characters of text do not contain. It would refine Q2's n, which is the
strongest argument for spending later, and the reason the capability is left in place.
