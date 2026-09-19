# Phase 3.5 — Module Key Reconciliation

**Status: RESOLVED**

The disagreement reported in Phase 3 is not a tie between two valid keys. One key is wrong, and this document identifies which one.

**Evidence artifact:** `build/dataset_b/evidence/module_key_reconciliation.json`  
**Analysis script:** `analysis/evidence/module_key_reconcile.py`

---

## Executive Summary

Three candidate module keys were evaluated:

- **K1 — URL/route:** `(origin, route)` from `context.active_browser_tab.url`
- **K2 — screen header:** the system name plus the `ダッシュボード / <module>` breadcrumb rendered inside the capture text
- **K3 — record prefix:** the `P<n>` prefix of the record ID

All three keys were computed over the same **3,011 records** in `build/dataset_b/evidence/records.jsonl`. The values were read directly from `context.extracted_text` or the stored URL; no VLM or additional inference was used.

The decisive result is that **K2 and K3 agree perfectly on the records for which both are available, while K1 independently disagrees with them in a substantial subset**.

The reconciliation therefore resolves the dispute as follows:

> **K2 is authoritative for a record's home module, with K3 as an exact proxy where available. K1 is not reliable as a screen/module identity key.**

The two keys have different coverage characteristics: K3 is more accurate but less complete, while K1 is more complete but less accurate. Consequently, **no single key should be used as the sole basis for the execution inventory**.

This reconciliation is recorded as **ADR-022**.

---

# 1. The Three Candidate Keys

| Key | Definition | Source |
|---|---|---|
| **K1 — URL/route** | `(origin, route)` from `context.active_browser_tab.url` | Used by `analysis/step2_reanalysis.py` and the current inventory |
| **K2 — screen header** | System name plus the `ダッシュボード / <module>` breadcrumb rendered inside capture text | Represents what the operator was actually looking at |
| **K3 — record prefix** | `P<n>` portion of the record ID | Derived from the captured screen; see §2 |

`[DATASET]`

All three keys are computed over the same **3,011 records** in `build/dataset_b/evidence/records.jsonl`.

Every value is read from either:

- `context.extracted_text`; or
- the URL stored by the recorder.

No VLM and no additional inference is used.

---

# 2. K3 Was Derived, Not Assumed

The briefing supplied the mapping:

```text
P1–P5  → HR
P6–P10 → FI
P11–P13 → LO
```

This mapping is treated as a hypothesis rather than as a given.

It is re-derived from the screen: every capture containing at least two record-ID lines and a rendered breadcrumb is used to associate the prefixes appearing in its table with the module declared by that capture.

`[DATASET]`

## 2.1 Derived Prefix-to-Module Mapping

| Prefix | Module (verbatim) | System | Supporting Rows | Purity |
|---|---|---|---:|---:|
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

**All 13 prefixes resolve at purity 1.00**, based on 211 queue captures.

The supplied HR/FI/LO grouping is therefore confirmed, while the derivation provides the finer-grained **module-level** mapping.

## 2.2 Findings from the Derivation

### P1 and P4 are the same module

`P1` and `P4` both belong to **HR|経費精算・給与変更**.

This is not a mapping error. Both prefixes appear side by side in the same rendered table consistently, indicating two record streams within one module.

### P10 was initially omitted

`P10 → FI|発注管理` was nearly lost by the first derivation.

The initial heuristic required one of four hard-coded list headings:

```text
申請一覧
処理一覧
処理待ち一覧
入社照合一覧
```

`発注管理` renders a different heading, so P10 produced no association and silently disappeared.

The heuristic was replaced with a structural test requiring **two or more record-ID lines**. Under this test, P10 resolves at purity 1.00 across 204 rows.

`[INF]`

This illustrates a broader implementation risk: a heuristic that fails closed for one module can make a data-coverage defect appear to be missing data rather than an analysis bug.

---

# 3. Decisive Test: The Leading Hypothesis Is Refuted

The leading explanation for the disagreement was the presence of **cross-module queue views**: a shared inbox whose URL names one module while its rows belong to several modules.

If that hypothesis were correct, K1 and K2/K3 could each be valid for different questions.

The direct test is:

> Does a single capture contain record rows whose prefixes map to different modules?

## 3.1 Result

| Measure | Count |
|---|---:|
| Captures containing more than one record-ID prefix | **33** |
| Captures whose prefixes cross module boundaries | **0** |

`[DATASET]`

Zero captures contain prefixes from different modules.

Every mixed-prefix capture contains **P1 + P4**, and both resolve to **HR|経費精算・給与変更**.

Therefore:

> **The cross-module-view hypothesis is refuted. The keys are not answering different questions.**

---

# 4. Three-Way Key Comparison

`[DATASET]`

Across 3,011 records, **2,630** are comparable on all three keys.

| Comparison | Comparable | Agree | Agreement Rate |
|---|---:|---:|---:|
| **K2 screen ↔ K3 prefix** | 2,904 | 2,904 | **1.000** |
| K1 URL ↔ K3 prefix | 2,704 | 2,139 | **0.791** |
| K1 URL ↔ K2 screen | 2,630 | 2,067 | **0.786** |

Three-way agreement is:

**2,067 / 2,630 = 78.6%**

## 4.1 The Agreement Pattern

Only two patterns occur:

| Pattern | n |
|---|---:|
| K1 = K2 = K3 — all agree | 2,064 |
| **K1 ≠ K2, K1 ≠ K3, K2 = K3 — K1 alone disagrees** | **552** |

`[INF]`

K2 and K3 never disagree with each other across the 2,904 comparable records.

K1 either:

- agrees with both; or
- disagrees with both.

This is the signature of **one incorrect key rather than three partially overlapping views**.

The evidence indicates that the URL stored with a capture does not reliably describe the screen represented by that capture.

## 4.2 Concentration of the Disagreement

The 552 disagreeing records occur in:

- **40 of 234 captures (17.1%)**
- median of **12 records per affected capture**

The disagreement therefore occurs in whole tables rather than being scattered across individual rows.

`[DATASET]`

## 4.3 What Remains Unexplained

The mechanism causing the URL discrepancy is **not established**.

Every record-bearing capture is an `app_switch` event:

- 563 disagreeing captures
- 2,067 agreeing captures

Therefore, event type does not distinguish the two cases.

A possible explanation is that the SPA's hash route and the recorder's stored `active_browser_tab.url` are updated through different code paths, allowing a capture taken during navigation to retain the previous route.

This is an **inference, not a finding**.

---

# 5. Reconciliation Decision

| Unit of Analysis | Authoritative Key | Rationale |
|---|---|---|
| **A record's home module** | **K2 screen header**, with **K3 prefix** as an exact proxy | Purity 1.00; 2,904/2,904 agreement; independent of the URL |
| **An operator action / execution** | **K3 where available; K1 elsewhere, with disagreement flagged** | K3 is more accurate but has lower coverage; see §6 |

### Key conclusion

K1 is **not** promoted to a "view key." It is simply unreliable as a screen/module identity key in the affected captures.

However, K1 remains the only candidate with full coverage. This difference in coverage is the central reason that neither key dominates the other for execution-level inventory.

**Decision recorded as ADR-022.**

---

# 6. Inventory Impact

`[DATASET]`

Each execution is assigned the module carried by the majority of its evidence, using the same rule already implemented in `analysis/step2_reanalysis.py`.

The script itself is **not modified**; its logic is replicated under each candidate key so that the inventories differ only because of the key.

## 6.1 Execution Counts by Key

| Module | Executions (K1) | Executions (K3) | Δ |
|---|---:|---:|---:|
| LO\|契約管理 | 26 | 8 | -18 |
| FI\|請求書承認・経費精算 | 25 | 21 | -4 |
| HR\|入社手続き | 23 | 19 | -4 |
| HR\|経費精算・給与変更 | 20 | 18 | -2 |
| FI\|発注管理 | 13 | 4 | -9 |
| LO\|在庫管理 | 13 | 10 | -3 |
| FI\|経費承認（管理職） | 10 | 2 | -8 |
| HR\|福利厚生申請 | 10 | 3 | -7 |
| FI\|支払処理 | 9 | 5 | -4 |
| LO\|IT申請 | 9 | 5 | -4 |
| HR\|勤怠・休暇申請 | 7 | 6 | -1 |
| FI\|予算差異分析 | 0 | 6 | +6 |

**All 12 rows change.**

## 6.2 Coverage Explains the Difference

The differences must **not** be interpreted simply as corrections to the K1 inventory.

K1 assigns **165 of 183 executions**.

K3 assigns only **107 executions**, because `extracted_text` is available for only **4.59% of events**, and an execution containing no extracted record cannot be keyed by prefix.

Therefore:

> **K3 is more accurate and less complete. K1 is more complete and less accurate. Neither dominates, and no single-key inventory is defensible.**

Where both keys apply, they agree on:

**64 of 97 executions = 66.0%**

---

# 7. The Inventory Is Missing a Module

`FI|予算差异分析` (**budget variance analysis**) is explicitly declared on screen in **11 captures** and contains **132 record rows** under prefix `P8`, with purity 1.00.

However, the module is absent from the `(origin, route)` map used by `analysis/step2_reanalysis.py` and is therefore absent from `docs/STEP2_PROCESS_INVENTORY.csv`.

Under K3, the module accounts for **6 executions**.

Under K1, it accounts for zero because there is no corresponding map entry.

`[DATASET]`

The existing map contains 11 entries while the screen evidence identifies 12 modules. The difference is exactly this one module.

Therefore:

> **The error is omission, not misattribution.**

---

# 8. What the Evidence Licenses

## 8.1 Licensed Conclusions

The evidence supports statements about which module a **record** belongs to, at purity 1.00, for the **2,904 records where a screen header is available**.

`[DATASET]`

## 8.2 Conclusions Not Licensed

A single-key execution inventory should **not** be presented as an exact count to two significant figures.

For example, `LO|契約管理` has an observed range of:

```text
8–26 executions
```

depending on the key used.

The reason for the spread is **coverage**, not ordinary measurement noise.

## 8.3 Threat to Validity

The **4.59% `extracted_text` coverage** is the principal limitation carried forward.

K3's purity of 1.00 is measured only on the subset of screens captured with usable text. The available evidence does not establish K3's behaviour on the remaining events.

---

# 9. Final Decision and Carry-Forward Requirements

### Decision

**Use K2 screen headers as the authoritative record-module key, with K3 as an exact proxy where available.**

For execution-level analysis:

- use K3 when a record prefix is available;
- use K1 when K3 is unavailable;
- flag K1/K3 disagreements rather than silently resolving them;
- do not treat either single-key inventory as ground truth.

### Required carry-forward actions

1. Add `FI|予算差异分析` to the module inventory.
2. Preserve the K1/K3 coverage distinction in all subsequent execution-count reporting.
3. Avoid presenting single-key execution counts as exact.
4. Carry the **4.59% extracted-text coverage limitation** into downstream analyses.
5. Investigate the mechanism behind the URL/screen mismatch before treating K1 as a semantic screen identifier.
6. Retain ADR-022 as the formal record of the reconciliation decision.

---

## 10. Bottom Line

The reconciliation resolves the Phase 3 disagreement:

> **K2 and K3 form the consistent module identity signal; K1 is the outlier.**

At the same time, **K3 cannot replace K1 wholesale** because its coverage is substantially lower.

The correct downstream approach is therefore not to select one key and discard the other, but to use the **screen-derived identity as authoritative where observable, use the record prefix as its exact proxy, and explicitly preserve uncertainty where only the URL is available**.

This is the basis on which subsequent module-level and execution-level analysis should proceed.
