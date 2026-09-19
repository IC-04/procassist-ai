# STEP 2 — Forensic Reconciliation of Dataset B

**Date:** 2026-09-16 · **Status:** authoritative input to the re-performed Step 2
**Scope:** Parts 1–3 of the Step 2 re-analysis. Establishes the evidence contract, reconstructs
Dataset B from raw evidence, and reconstructs the business processes semantically.
**Step 1 is frozen and was not modified.** Nothing under `procmine/` or
`build/dataset_b/*.jsonl` was changed. New analysis code lives in `analysis/step2_reanalysis.py`.

---

## PART 1 — The Step 2 evidence contract

### 1.1 What is an "execution" in Dataset B?

An **execution** is a Step-1 output object: one row of `build/dataset_b/segments_rich.jsonl`, being
a contiguous `[start_seq, end_seq]` span of one session's event stream that Step 1's boundary
decoder and identity clusterer judged to be one coherent unit of work. There are **183** of them.

Three things an execution is **not**, and the re-analysis depends on keeping them apart:

- **An execution is not a business case.** Measured directly: an execution contains between
  **1.83 and 4.35 recorded dispositions** (record-level confirm actions) depending on module.
  A business case is one record processed; an execution is a *sitting* in which the operator
  processes several.
- **An execution is not a complete process.** Only **72.5% (456 / 629)** of all recorded
  dispositions in Dataset B fall inside any Step-1 execution. Just over a quarter of the observable
  business work happens in spans Step 1 did not segment.
- **An execution is not necessarily one business process.** Measured: 102 of 183 executions touch
  exactly one business module, **48 touch two, 15 touch three, and 18 touch none**.

### 1.2–1.10 The evidence table

| Evidence | Source | Directly observable? | Ground truth? | Inference? | Reliability | Potential failure mode |
|---|---|---|---|---|---|---|
| Event stream: type, timestamp, sequence | `events.jsonl` | **Yes** | Yes, for *what the agent recorded* | No | High | Agent gaps; `text_input_complete` documented unreliable in README |
| Active application name / process | `events.jsonl` `context.active_app` | **Yes** | No — an app is not a process | No | High | — |
| Window title | `events.jsonl` | **Yes** | **No** — a document name is not a business meaning | No | High as a string | Title lags the tab at switch time: 18–23% of blocks on an origin carry another system's title |
| Browser origin (`:5132/:5133/:5134`) | `active_browser_tab.url` | **Yes** | No | No | High | — |
| Browser route (`/payroll-items` …) | `active_browser_tab.url` | **Yes** | **NO — this is the central trap** | No | High as a string, **worthless as semantics** | The same route renders three different business functions; see §2.2 |
| Element id (`btn-pi-ok`, `pi-note`) | `browser_click.payload.element.attributes.id` | **Yes** | No | No | High | Only 12 distinct ids exist; ids are route-derived, so they inherit the route's ambiguity |
| Element text / label on click | — | **No** — `text_content` is never populated | — | — | — | Cannot tell which record was clicked, or which button |
| Form field id + placeholder | `browser_form_input.payload.field` | **Yes** | No — it is a UI label | No | High | Five labels only; they describe the *field's* role, not the record's outcome |
| Form field **value** | — | **No** — `value: null` on all 608 inputs | — | — | — | No entered value is recoverable, anywhere |
| Clipboard **content** | — | **No** — `text_content: null` on all 872 events | — | — | — | Only `text_length` survives (24–80 chars, median 42) |
| Typed text | `keystroke.payload.character` | Partially | No | No | Low | 2,014 printable presses, of which 887 are `v` (Ctrl+V) and most of the rest are digits. **No free text is typed anywhere in Dataset B** |
| Screen contents: H1, nav item, table rows, badges, buttons | **Screenshots only** (4,746 files) | Yes, by human/VLM reading | No — still a UI label | No | High for *what the screen said* | Not machine-available; sampling is manual, so coverage is partial and selection is a judgement |
| Reference document contents | **Screenshots only** | Yes | No | No | High | 4 of 13 documents read in full; 9 unread |
| System-assigned badge 種別 定常/調整, ⚠, ステータス | **Screenshots only** | Yes | **NO — a system label, not business correctness** | No | Medium | Demonstrably does not follow the written rule (§3.5) |
| 照合項目数 (item count) | **Screenshots only** | Yes | **No — system label** | No | Medium | Appears on several modules with different meanings |
| Step-1 segment boundaries | `segments_rich.jsonl` | Yes as output | **No** — Dataset B has no GT | It *is* an inference | Measured on Dataset A only: boundary F1 ≈ 0.69, ARI ≈ 0.68 @ match rate 0.76 | Accuracy does not transfer from A to B |
| Step-1 label text (`payroll-items__p01`) | `procmine/label.py::_name` | Yes as output | **NO** | Yes — and **origin-blind by construction** | **Low as semantics** | Built from `sig["routes"][:2]` only. See §2.3 — this is the root cause of the previous error |
| Step-1 cluster assignment | `segments_rich.cluster` | Yes as output | No | Yes | Moderate–good; measured below | 70% of the distance metric is origin-qualified, so clusters are better than their names |
| Operator identity | `source.username_hash` | **Yes** | Yes, as a pseudonymous identity | No | High | One hash per session observed; cannot separate two people sharing a machine |
| Business volume, monetary value, error rate, FTE cost, criticality, API availability | — | **No** | — | — | **UNAVAILABLE** | Any figure would be invented |

### 1.3 Rules that follow from the table

- **R-A.** A route is a string. Its business meaning requires the `(origin, route)` pair *and* a
  screenshot. Neither alone is sufficient.
- **R-B.** A UI label — badge, button, column header, nav item, document filename — is evidence of
  *what the system displays*, never of business correctness. §2.4 shows the SPA displays column
  headers that contradict their own cell contents.
- **R-C.** A telemetry count is a count of recorded interactions. Converting it to business volume
  requires a stated, checked ratio. We have one: dispositions per execution, measured per module.
- **R-D.** Step 1's *clusters* and Step 1's *label text* are different artefacts with different
  reliability. The README says the label text is not evaluated; we must not use it as an identity.

---

## PART 2 — Forensic reconstruction

### 2.1 Method

Nothing was taken from `build/dataset_b/step2/process_inventory.json`. The reconstruction ran:

1. Enumerate every `(origin, route)` pair actually visited, from `active_browser_tab.url`.
2. For each pair, select a screenshot taken while that URL was in the address bar, preferring
   captures triggered by `on_browser_click` (detail pane likely open).
3. Read the screenshot: URL bar, breadcrumb, H1, highlighted navigation item, table headers,
   table cell contents, badges, buttons, toast messages.
4. Record the module identity only where URL + breadcrumb/H1 + highlighted nav item are visible
   **together in one image**.
5. Re-key the frozen Step-1 executions by the dominant module of their constituent blocks.

**20 screenshots were read.** 11 business modules were identified this way; every one of the 11 had
all three identifiers visible in a single frame.

### 2.2 The authoritative map — and the finding that overturns the previous analysis

| Origin | System (department) | Route | **Module actually rendered** | Record prefix | Evidence | Conf. |
|---|---|---|---|---|---|---|
| `:5132` | HR人事給与システム（人事部門） | `/payroll-items` | **経費精算・給与変更** expense settlement + payroll change | `P1-`, `P4-` | screenshot | High |
| `:5132` | | `/leave-applications` | **勤怠・休暇申請** attendance & leave | `P2-` | screenshot | High |
| `:5132` | | `/onboarding` | **入社手続き** onboarding verification | `P3-` | screenshot | High |
| `:5132` | | `/social-insurance` | **福利厚生申請** benefits applications | `P5-` | screenshot | High |
| `:5132` | | (nav item 住民税・その他) | **empty, badge 0** | — | screenshot | High |
| `:5133` | 財務会計システム（経理部門） | `/payroll-items` | **請求書承認・経費精算** invoice approval | `P6-` | screenshot | High |
| `:5133` | | `/onboarding` | **支払処理** payment processing | `P7-` | screenshot | High |
| `:5133` | | `/leave-applications` | **経費承認（管理職）** managerial expense approval | `P9-` | screenshot | High |
| `:5133` | | `/resident-tax` | **発注管理** purchase-order management | `P10-` | screenshot | High |
| `:5133` | | (nav item 予算差異分析, badge 12) | not visited with URL captured | `P8-`? | nav only | Low |
| `:5134` | 受発注在庫管理システム（物流管理部） | `/payroll-items` | **在庫管理** inventory management | `P11-` | screenshot | High |
| `:5134` | | `/leave-applications` | **契約管理** contract management | `P12-` | screenshot | High |
| `:5134` | | `/social-insurance` | **IT申請** IT requests | `P13-` | screenshot | High |
| `:5134` | | (返品処理, 受注・その他) | badge 0 | — | screenshot | High |

**Three conflicts between technical identifiers and business semantics, all resolved in favour of
the evidence:**

1. **`/payroll-items` is three different businesses.** Invoice approval (finance), expense/payroll
   change (HR), inventory management (logistics). Not one module in three systems — three modules
   sharing one SPA path.
2. **`/resident-tax` is not resident tax.** On `:5133` it renders 発注管理, purchase-order
   management, with vendor names and `PO-2026-52xx` references. The HR system's genuine
   住民税・その他 module exists and is **empty**.
3. **`/leave-applications` is three different businesses.** Attendance/leave (HR), managerial
   expense approval (finance), contract management (logistics).

**Nowhere in Dataset B is the same record observed being entered into more than one system.**

### 2.3 Root cause of the previous error — located precisely in code

This is not a vague "we should have looked harder". The defect is one function.

`procmine/label.py::_name()` builds the display label from `sig["routes"][:2]` — **routes only,
origins discarded**. That is legitimate: the README states "The label text itself is not evaluated."

`procmine/label.py::distance()` — the function that actually forms the clusters — weights
`surface_shape` 0.45, `surface_set` 0.25, `routes` 0.20, `profile` 0.10. The surface strings are
origin-qualified (`web:http://127.0.0.1:5133/payroll-items`). **So 70% of Step 1's clustering signal
is origin-aware.**

`analysis/step2_inventory.py::_family()` then aggregated by `label.rsplit("__p", 1)[0]` — a string
prefix of the *display name*.

**Step 2 aggregated on a cosmetic name and thereby discarded an origin distinction that Step 1 had
correctly preserved.** Step 1 is not at fault and does not need to change.

### 2.4 A second, subtler trap: the column headers lie too

On `:5133/#/onboarding` (支払処理, payment processing) the table header reads **入社日** ("start
date") over cells containing **振込 ¥1,182,500** (a transfer amount), and **部署** ("department")
over cells containing **INV-1345 承認済** (an approved invoice reference). The SPA reuses one table
component and its column labels across every module.

**Consequence:** even inside a screenshot, only *cell content* is trustworthy. A pipeline that
scraped headers would be wrong in a new way.

### 2.5 What is recoverable per module, and what the operator is doing

For every module, the same five-step shape was observed: **select a row → open the governing
document → paste a short Japanese justification into the module's note field → click the confirm
button → the row's status changes.** Evidence: 633 `td` clicks against 629 `btn-*-ok` clicks (one
row-selection per disposition), 608 form inputs all of `input_method: "paste"`, and per-module
document co-occurrence (§3).

| Module | Note field | Dominant reference document (block co-occurrences) | Repetitive? | Contains judgement? |
|---|---|---|---|---|
| M01 経費精算・給与変更 | `pi-note` (77) | 業務委託経費規程 (57) | Yes | Yes — amount vs regulation |
| M02 勤怠・休暇申請 | `la-note` (16) | thin | Yes | Yes — 承認 or 差戻し **with reason** |
| M03 入社手続き | `ob-note` (39) | **入社チェックリスト（新卒バッチ処理） (270)** | Yes | Conditional item selection |
| M04 福利厚生申請 | `si-note` (28) | **育児休業規程 (32)** | Yes | Entitlement determination |
| M05 請求書承認・経費精算 | `pi-note` (44) | **月次定額取引先一覧 (145)** | Yes | 承認 or 保留 on discrepancy |
| M06 支払処理 | `ob-note` (17) | **業務委託給与規程 (262)** | Yes | Payment verification |
| M07 経費承認（管理職） | `la-note` (22) | **接待交際費規程 (216)** | Yes | Managerial approval |
| M08 発注管理 | `rt-note` (43) | **新規取引先登録手続き (59)** | Yes | Exception deferral (⚠ rows) |
| M09 在庫管理 | `pi-note` (35) | 在庫調整メモ (58, operator's own output) | Yes | Adjustment classification |
| M10 契約管理 | `la-note` (45) | **契約解除手続き (483) / 新規契約手続き (192)** | Yes | Contract-type routing + authority |
| M11 IT申請 | `si-note` (25) | 管理者権限申請手続き (24) | Yes | **Approver routing — deterministic** |

**Every module pairs with a semantically matching governing document.** This is eleven independent
confirmations of the same structure, not a generalisation from one example.

---

## PART 3 — Semantic process reconstruction

Presented for the five best-evidenced processes. `OBSERVE` = read from telemetry or a screenshot.
`INFER` = our reasoning. Full quantitative detail is in `docs/STEP2_PROCESS_INVENTORY.csv`.

### M10 · 契約管理 — contract management (logistics system)

| Field | Content |
|---|---|
| Process ID / name | **M10** · 契約管理 Contract management |
| Application / origin | 受発注在庫管理システム · `http://127.0.0.1:5134/#/leave-applications` |
| Trigger / input | OBSERVE: a queue of 12 contract applications, `P12-07088456-001…012`, badged 承認 or 処理待ち |
| Main business object | OBSERVE: a contract application — vendor (`V300x` + name), 申請種別, action (解除/新規締結/変更/更新), date |
| Reference documents | OBSERVE: 契約解除手続き (483 co-occurring blocks), 新規契約手続き (192), 新規取引先登録手続き (136) |
| Observed steps | OBSERVE: select row → open the 手続き matching the contract action → paste justification into `la-note` → click `btn-la-ok`; toast confirms 「申請を承認しました」 |
| Decision points | OBSERVE: 承認 vs 処理待ち. INFER: which 手続き governs is determined by 申請種別; 新規契約手続き §3 states approval authority by value — <¥1M department head, ≥¥1M executive, ≥¥30M board |
| Action / outcome | OBSERVE: status → 承認 |
| Systems touched | OBSERVE: 1 browser system + Word. Mean 2.2 distinct applications |
| People | OBSERVE: 4 operators, 8 sessions, most-even spread of any module (max single-session share 0.23) |
| Observed variants | OBSERVE: 5 contract types × 4 actions |
| Evidence quality | **Strong.** 26 executions, 89% of them from one Step-1 cluster, mean module purity 0.85 |
| Unknowns | Contract values (not displayed in the list view); whether the 手続き set is complete; true volume |

### M01 · 経費精算・給与変更 — expense settlement and payroll change (HR system)

| Field | Content |
|---|---|
| Trigger / input | OBSERVE: two record families in one queue — `P1-` expense claims (接待交際費 / 研修費 / 消耗品費) and `P4-` payroll changes (扶養控除変更 / 残業手当調整 / 役職手当廃止・新設) |
| Reference documents | OBSERVE: 業務委託経費規程 (57). Also 精算確認メモ (72) — but that is the operator's **output**, not input |
| Decision points | OBSERVE: 種別 定常 vs 調整 badge. INFER: amount checked against an expense regulation; the operator's own memo reads 「規程内であることを確認した」 |
| Evidence quality | **Strong on volume** — 87 dispositions, the most of any module, 10 sessions, 4 operators. **Weaker on identity** — mean purity 0.82, 8 of 20 executions touch another module |
| Unknowns | Whether `P1-` and `P4-` are one process or two; the regulation was not read in full |

### M05 · 請求書承認・経費精算 — invoice approval (finance system)

| Field | Content |
|---|---|
| Trigger / input | OBSERVE: 12 invoices `P6-07010448-001…012`, vendor, `INV-2026-73xx`, amount ¥316,664–1,993,825, badge 定常/調整 |
| Reference document | OBSERVE: **月次定額取引先一覧** (145 blocks) — 5 fixed-amount vendors with monthly amounts **and a written rule**: 「受領した請求書の INV 番号・金額・取引先名をこの一覧と照合すること。差異がある場合は要確認として保留する」 |
| Decision points | OBSERVE: two buttons ✓承認 and ⏸保留. INFER: discrepancy → 保留 |
| Evidence quality | **Strong** — 25 executions, 92% from one cluster, purity 0.88, rule document read in full |
| **Contradiction found** | The badge does not follow the written rule: 株式会社山田製作所 at 393,384 vs listed 385,000 is badged **定常**, while the same vendor at 374,313 is badged **調整**. Either an unstated tolerance exists, or 種別 is not a function of this rule |
| Unknowns | The tolerance; whether 北陸電子部品 (list) and 北陸部品工業株式会社 (queue) are the same entity |

### M03 · 入社手続き — onboarding verification (HR system)

| Field | Content |
|---|---|
| Trigger / input | OBSERVE: 入社照合一覧, 12 records `P3-07054374-…`, 入社日, 部署, **照合項目数 4 項目 or 5 項目**, status 照合中 |
| Reference document | OBSERVE: **入社チェックリスト（新卒バッチ処理）**, 270 co-occurring blocks — 7 items, **two conditional**: 雇用保険被保険者証（転職者のみ）, 扶養控除等申告書（家族手当対象者確認） |
| Evidence quality | **Best identity in the dataset** — 23 executions, **`onboarding__p03` maps 21/21 (100%) to this module**, mean purity 0.90, lowest duration dispersion (IQR/median 0.46) |
| Notable | The system publishes 照合項目数, which an applicability-derivation model could be scored against without hand-labelling |

### M08 · 発注管理 — purchase-order management (finance system)

| Field | Content |
|---|---|
| Trigger / input | OBSERVE: 12 POs `P10-07010448-…`, vendor, `PO-2026-52xx`, status 完了/未確認 |
| Decision points | OBSERVE: **two rows carry a red ⚠ marker** next to the vendor name |
| Exception behaviour | OBSERVE: across one session the badge fell 12 → 11 → 5 while **both ⚠ rows stayed 未確認**. The operator cleared the clean work and deferred the flagged work |
| Evidence quality | Moderate — 13 executions but the **most even operator spread** (max single-session share 0.15), 4 operators. `rt-note` comments are the longest in the dataset (median pasted length 54 chars vs 30–46) |
| Unknowns | **What ⚠ means is unknown.** No detail pane for a flagged row was read |

### Where the previous "resident-tax" candidate went

`resident-tax__p02` — 23 executions, called "the largest process and the least repeatable thing in
the dataset" — resolves to **no dominant module at all**: 福利厚生申請 ×6, 在庫管理 ×6, 発注管理 ×5,
経費精算・給与変更 ×5, 請求書承認 ×1. Dominant share **0.26**.

Its variance was not business variance. It is a Step-1 cluster that merged five different business
processes. That is a much more useful finding than "this process is unrepeatable", and it means the
previous recommendation to "redesign rather than automate resident-tax" was answering a question
about an artefact.

---

## Appendix — screenshots read for this reconstruction

`dataset_b/…/screenshots/` — 20 files. The 11 module identifications above come from:
`scr_smart_1782924293023` (M05 detail), `1782924287812` (M05 queue), `1782924349955` (M01),
`1782926303587` (M09), `1782930493501` (M09 alt), `1782924480910` + `1782924826403` (M08, two time
points), `1782927856806` + `1782929745913` (M02), `1782926349932` (M03), `1782926638282` (M04),
`1782929890985` (M07), `1782929420783` (M06), `1782930249966` (M10), `1782929070625` (M11);
documents: `1782924288510` (月次定額取引先一覧), `1782926352063` (入社チェックリスト),
`1782924516206` (新規契約手続き), `1782926731166` (家族手当規程), `1782927208531` (精算確認メモ).
