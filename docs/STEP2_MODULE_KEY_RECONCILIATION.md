# Phase 3.5 — module key reconciliation

**Status: RESOLVED.** The disagreement reported in Phase 3 is not a tie between two valid keys.
One key is wrong, and this document identifies which.

Artifact: `build/dataset_b/evidence/module_key_reconciliation.json`
Script: `analysis/evidence/module_key_reconcile.py`

---

## 1. The three keys

| Key | Definition | Source |
|---|---|---|
| **K1 — URL/route** | `(origin, route)` from `context.active_browser_tab.url` | what `analysis/step2_reanalysis.py` and the current inventory use |
| **K2 — screen header** | the system name plus the `ダッシュボード / <module>` breadcrumb **rendered inside the capture text** | what the operator was actually looking at |
| **K3 — record prefix** | the `P<n>` of the record id | **derived**, not assumed — see §2 |

`[DATASET]` All three are computed over the same 3,011 records in
`build/dataset_b/evidence/records.jsonl`. OBSERVED throughout: every value is read from
`context.extracted_text` or from the URL the recorder stored. No VLM, no inference.

---

## 2. K3 was derived, not assumed

The briefing supplied `P1–5 → HR, P6–10 → FI, P11–13 → LO` as a given. It is treated here as a
hypothesis and re-derived from the screen: for every capture containing two or more record-id
lines *and* a rendered breadcrumb, the prefixes in its table are associated with the module that
capture declares. `[DATASET]`

| Prefix | Module (verbatim) | System | Supporting rows | Purity |
|---|---|---|---|---|
| `P1` | 経費精算・給与変更 | HR | 372 | 1.00 |
| `P2` | 勤怠・休暇申請 | HR | 180 | 1.00 |
| `P3` | 入社手続き | HR | 480 | 1.00 |
| `P4` | 経費精算・給与変更 | HR | 372 | 1.00 |
| `P5` | 福利厚生申請 | HR | 48 | 1.00 |
| `P6` | 請求書承認・経費精算 | FI | 468 | 1.00 |
| `P7` | 支払処理 | FI | 120 | 1.00 |
| `P8` | 予算差異分析 | FI | 132 | 1.00 |
| `P9` | 経費承認（管理職） | FI | 36 | 1.00 |
| `P10` | 発注管理 | FI | 204 | 1.00 |
| `P11` | 在庫管理 | LO | 336 | 1.00 |
| `P12` | 契約管理 | LO | 241 | 1.00 |
| `P13` | IT申請 | LO | 120 | 1.00 |
**All 13 prefixes resolve at purity 1.00**, derived from 211 queue captures. The supplied
HR/FI/LO grouping is confirmed, and the derivation is finer than it: it names the *module*, not
just the system.

Two things the derivation shows that the supplied mapping does not:

- **`P1` and `P4` both belong to HR|経費精算・給与変更.** One module, two record streams. This is
  not a mapping error; both prefixes appear side by side in the same rendered table, always.
- **`P10` → FI|発注管理 was nearly lost.** The first derivation gated on four hard-coded list
  headings (`申請一覧` `処理一覧` `処理待ち一覧` `入社照合一覧`); 発注管理 renders a different heading, so
  P10 produced no association at all and dropped out of the map silently. Replaced with a
  structural test — two or more record-id lines — after which P10 resolves at purity 1.00 over
  204 rows. `[INF]` A heuristic that fails *closed* on one module is the kind of defect that
  looks like missing data rather than a bug.

---

## 3. The decisive test — and the leading hypothesis is REFUTED

The leading explanation for the disagreement was **cross-module queue views**: a shared inbox
whose URL names one module while the rows belong to several, in which case both keys would be
right about different questions. The test is direct — *does a single capture contain rows whose
prefixes map to different modules?*

| | |
|---|---|
| captures containing more than one record-id prefix | **33** |
| of those, captures whose prefixes cross module boundaries | **0** |

`[DATASET]` **Zero.** Every mixed-prefix capture is `P1` + `P4`, both of which are
HR|経費精算・給与変更 — mixing *within* one module, not across modules. There are no cross-module
queue views in Dataset B.

**The cross-module-view hypothesis is refuted.** The keys are not answering different questions.

---

## 4. Three-way contingency

`[DATASET]` Over 3,011 records, 2,630 comparable on all three keys:

| Comparison | Comparable | Agree | Rate |
|---|---|---|---|
| **K2 screen ↔ K3 prefix** | 2,904 | 2,904 | **1.000** |
| K1 url ↔ K3 prefix | 2,704 | 2,139 | 0.791 |
| K1 url ↔ K2 screen | 2,630 | 2,067 | 0.786 |

Three-way agreement: **2,067 / 2,630 = 78.6%**.

**The agreement pattern is the finding.** Only two patterns occur:

| Pattern | n |
|---|---|
| K1=K2, K1=K3, K2=K3 — all agree | 2,064 |
| **K1≠K2, K1≠K3, K2=K3 — K1 alone dissents** | **552** |

`[INF]` K2 and K3 never disagree with each other, in 2,904 comparable records. K1 disagrees with
both, together, or with neither. That is the signature of **one wrong key**, not three partial
views: the URL stored with a capture does not describe the screen the capture shows.

**Concentration.** The 552 disagreeing records sit in **40 of 234 captures (17.1%)**, median 12
records per involved capture — i.e. whole tables, not scattered rows. `[DATASET]`

**What is not established:** *why* the URL lags. Every record-bearing capture is an `app_switch`
event — 563 disagreeing and 2,067 agreeing — so event type does not discriminate them, and the
mechanism remains unexplained. INFERENCE, offered as the most likely account and not as a
finding: the SPA's hash route and the recorder's stored `active_browser_tab.url` are updated by
different code paths, so a capture taken mid-navigation carries the previous route.

---

## 5. Decision

| Unit of analysis | Authoritative key | Why |
|---|---|---|
| **A record's home module** | **K2 screen header**, with **K3 prefix** as an exact proxy | purity 1.00; 2,904/2,904 agreement; independent of the URL |
| **An operator action (execution)** | **K3 where available, K1 elsewhere, disagreement flagged** | K3 is more accurate but less complete — see §6 |

K1 is **not** demoted to "the view key". It is simply wrong about the screen in 21% of captures.
It remains the only key with full coverage, which is the whole difficulty.

Recorded as **ADR-022**.

---

## 6. Inventory impact

`[DATASET]` Each execution is assigned the module a majority of its evidence carries — the rule
`analysis/step2_reanalysis.py` already uses, applied under each key so the two inventories differ
only in the key. `step2_reanalysis.py` is **not modified**; its logic is replicated.

| Module | n executions (K1) | n executions (K3) | Δ |
|---|---|---|---|
| LO|契約管理 | 26 | 8 | -18 |
| FI|請求書承認・経費精算 | 25 | 21 | -4 |
| HR|入社手続き | 23 | 19 | -4 |
| HR|経費精算・給与変更 | 20 | 18 | -2 |
| FI|発注管理 | 13 | 4 | -9 |
| LO|在庫管理 | 13 | 10 | -3 |
| FI|経費承認（管理職） | 10 | 2 | -8 |
| HR|福利厚生申請 | 10 | 3 | -7 |
| FI|支払処理 | 9 | 5 | -4 |
| LO|IT申請 | 9 | 5 | -4 |
| HR|勤怠・休暇申請 | 7 | 6 | -1 |
| FI|予算差異分析 | 0 | 6 | +6 |
**All 12 rows change. `[DATASET]`**

**Coverage is the reason most deltas are negative, and it must not be read as a correction.**
K1 assigns 165 of 183 executions; K3 assigns only **107**, because `extracted_text` reaches just
4.59% of events and an execution with no extracted record cannot be keyed by prefix at all. So:

> **K3 is more accurate and less complete. K1 is more complete and less accurate.** Neither
> dominates, and no single-key inventory is defensible.

Where both keys apply, they agree on **64 of 97 executions (66.0%)**.

### 6.1 The inventory is missing a module

`FI|予算差異分析` (budget variance analysis) is **declared on screen in 11 captures**, carries
**132 record rows** under prefix `P8` at purity 1.00, and is **absent from the `(origin, route)`
map** in `analysis/step2_reanalysis.py` and therefore from
`docs/STEP2_PROCESS_INVENTORY.csv`. Under K3 it holds **6 executions**; under K1, zero, because
it has no map entry to be assigned to. `[DATASET]`

The map's 11 entries and the screen's 12 modules differ by exactly this one. Nothing in the map
is declared-but-unseen — the error is omission, not misattribution.

---

## 7. What this does and does not license

**Licensed:** statements about which module a *record* belongs to, at purity 1.00, for the 2,904
records where a screen header is available. `[DATASET]` OBSERVED.

**Not licensed:** any per-module execution count quoted to two significant figures from a
single key. The honest form is a range: `契約管理` is between 8 and 26 executions depending on
the key, and the reason for the spread is coverage, not measurement noise.

**Threat to validity carried forward:** the 4.59% `extracted_text` coverage bounds everything in
this document. K3's purity of 1.00 is measured on the subset of screens that happened to be
captured with text, and there is no evidence about the rest.
