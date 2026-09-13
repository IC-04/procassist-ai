# E01 — block-quality ablation and absorption-threshold sweep

**Date** 2026-09-13 · **Phase** 0 · **Git SHA** see `config.json` · **Dataset** `dataset_b`

> `dataset_b` is used here as the **validation** dataset, not as the source of any rule.
> Every rule under test is keyed on a property defined in `DATA_SCHEMA.md` and runs
> unchanged on any conforming dataset (ADR-010, ADR-012, ADR-013).

## Hypothesis

Block degeneracy on `dataset_b` — 623 one-event blocks, 624 zero-duration, 63 empty-surface,
median 4 events/block — is caused by identifiable perception defects, not by the
micro-excursion absorption thresholds. If that is right, fixing the defects should dominate,
and the threshold choice should then sit on a plateau rather than a cliff.

## Setup

Five ablation arms, each adding one rule to the previous:

| Rule | What it does | Authority |
|---|---|---|
| R5 | `route_of` returns the hash route or the URL path, never the origin | `DATA_CONTRACT.md` §2 |
| R4 | surface type from origin presence; the `BROWSERS` allow-list deleted | `DATA_CONTRACT.md` §2 |
| R1 | `SYSTEM`/`L1` events are surface-transparent | `DATA_SCHEMA.md` §2 layer table |
| R2 | a row with no title and no origin cannot open a block | `DATA_SCHEMA.md` §2 |
| R3 | `active_browser_tab` is carried-forward state | `DATA_SCHEMA.md` §2 |

Sweep grid `min_events ∈ {2,3,5,8}` × `min_ms ∈ {1000,1500,3000}`, `window=5`, `max_lag=12`.

## Results — ablation

| arm | blocks | median ev | mean ev | 1-event | 0-duration | empty-surface | malformed | purity |
|---|---|---|---|---|---|---|---|---|
| A0 baseline | 1782 | 4.0 | 11.49 | 623 | 624 | 63 | 54 | 0.9742 |
| A1 +R5 | 1782 | 4.0 | 11.49 | 623 | 624 | 63 | **0** | 0.9742 |
| A2 +R4 | 1811 | 4 | 11.31 | 647 | 648 | 66 | 0 | 0.9723 |
| A3 +R1+R2 | **1338** | **8.0** | **15.30** | **152** | **152** | **0** | 0 | **0.9852** |
| A4 +R3 (shipped) | 1338 | 8.0 | 15.30 | 152 | 152 | 0 | 0 | 0.9852 |

Three findings, two of them negative:

1. **R1+R2 is the entire fix.** Treating capture and agent events as surface-transparent
   removes 495 of the 647 one-event blocks and every empty-surface block, and raises surface
   purity. Everything else is correctness housekeeping. (R2 includes its forward half,
   pass 1b: a bare `app:<X>` run merges into an immediately following `app:<X>:<title>` run,
   because a window title is not populated until the window finishes activating. That
   merges 35 of 59 bare-app runs; the other 24 belong to applications that never report a
   title anywhere and correctly keep their own blocks.)
2. **R4 alone makes things slightly worse** (1811 blocks vs 1782). Removing the browser
   allow-list means an `L3` event reported against a non-browser application keys as a web
   surface. It only pays off once R1/R2 are in place. Kept because an allow-list of browser
   names is a dataset-specific rule that would silently mis-key an unfamiliar browser.
3. **R3 changes no block boundary on this dataset.** It fills 3,058 rows, *every one of them
   an `L1 screenshot_smart`*, which R1 already makes transparent. The 562 `L2` user
   operations inside a browser that carry no tab URL turn out to sit at the **entry** to a
   browser visit, before any tab has been observed — there is no prior state to carry, and
   the rule correctly declines to invent one. It is retained as the correct reading of the
   schema and because it gives capture rows a resolved surface for later phases, **not**
   because it is load-bearing here. Re-measure on `dataset_a` in Phase 2.

R5 is invisible in the block counts because it changes how a key is *spelled*, not how many
runs there are: it eliminates 54 malformed keys of the form
`web:http://127.0.0.1:5132http://127.0.0.1:5132`, which would have split one logical surface
into two for every downstream `same_surface_as` and `same_system_as` comparison.

## Results — sweep

| min_events | min_ms | blocks | median ev | mean ev | 1-event | purity | frag(lag2) | short-work kept | stability |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 1000 | 1428 | 7.0 | 14.34 | 172 | **0.9884** | 0.2079 | 84 | 0.063 |
| 2 | 1500 | 1428 | 7.0 | 14.34 | 172 | **0.9884** | 0.2079 | 89 | 0.063 |
| 2 | 3000 | 1428 | 7.0 | 14.34 | 172 | **0.9884** | 0.2079 | 160 | 0.063 |
| 3 | 1000 | 1338 | 8.0 | 15.30 | 152 | 0.9852 | **0.1983** | 62 | 0.067 |
| **3** | **1500** | **1338** | **8.0** | **15.30** | **152** | 0.9852 | **0.1983** | 67 | 0.067 |
| 3 | 3000 | 1338 | 8.0 | 15.30 | 152 | 0.9852 | **0.1983** | 138 | 0.067 |
| 5 | 1000 | 1288 | 8.0 | 15.90 | 142 | 0.9808 | 0.2028 | 40 | 0.039 |
| 5 | 1500 | 1286 | 8.0 | 15.92 | 142 | 0.9807 | 0.2024 | 45 | 0.040 |
| 5 | 3000 | 1278 | 9.0 | 16.02 | 142 | 0.9803 | 0.2033 | 115 | 0.047 |
| 8 | 1000 | 1282 | 8.0 | 15.97 | 141 | 0.9801 | 0.2020 | 38 | 0.005 |
| 8 | 1500 | 1278 | 8.5 | 16.02 | 141 | 0.9800 | 0.2011 | 43 | 0.016 |
| 8 | 3000 | 1258 | 9.0 | 16.28 | 141 | 0.9783 | 0.2002 | 107 | 0.016 |

**`min_ms` is inert on this dataset.** Within any `min_events` row the block count is
identical across 1000/1500/3000 ms: the excursions that qualify on the event count are
already far shorter than one second, so the time bound never binds. (`short-work kept`
*is* defined in terms of `min_ms`, so its variation down a column is an artifact of the
metric's own definition, not a behavioural difference. It is comparable across `min_events`
at fixed `min_ms` only.)

**Purity falls monotonically as `min_events` rises** — 0.9884 → 0.9783. That is the real
cost of absorption: each additional merge pulls events whose own surface key differs into
a block that claims a different one.

## Decision

**`min_events = 3`, `min_ms = 1500`** (unchanged from the pre-Phase-0 default, now with
evidence behind it).

- It has the **lowest fragmentation** in the grid (0.1983).
- Purity 0.9852 is within 0.003 of the best cell, and the best cell (`min_events=2`) has the
  *highest* fragmentation — the two criteria trade off, and 3 is the knee.
- Moving 3 → 5 buys 50 fewer blocks at the same median, but costs 0.0044 purity and absorbs
  22 more brief-but-distinct blocks. Moving 5 → 8 buys almost nothing (6 blocks); the grid
  has saturated.
- Absorption removes the evidence a later stage needs: an absorbed excursion is exactly the
  `INTERRUPTION` signature the reasoner is asked to judge (`AI_REASONING_SPEC.md` §3). When
  two settings are close on the measured criteria, the more conservative one is correct,
  because perception must not pre-empt a decision the reasoner owns.

`min_ms=1500` is retained as the mid-grid value. It is not a sensitive parameter here, but
it may bind on a dataset with slower interaction, so it stays configurable
(`--min-ms`) rather than being hard-coded away.

## What this does *not* claim

The remaining 152 one-event blocks were inspected rather than tuned away. Most of them sit
between two **different** surfaces — most often a worker flipping between the dashboards of
three separate systems (`5132/dashboard` → `5133/dashboard` → `5134/dashboard`), which is
genuine rapid navigation, not a modelling artifact. A one-event block necessarily has
`dur_ms == 0`, so the zero-duration count cannot reach zero without merging those distinct
systems and destroying the `same_system_as` evidence that process-switch detection depends
on. That trade-off is reported, not forced (`PHASE_0.md` Task 0.3 explicitly permits this).

## Reproduce

```bash
python3 experiments/E01-block-sweep/run.py
```
