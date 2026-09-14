# S-E2 — miss attribution

**Date** 2026-09-14 · **Dataset** `dataset_a`, all 63 sessions · **Git SHA** see `config.json`
**Population and τ grid** taken from `experiments/SE1-gt-metric-correction/`, not recomputed.

> **Verdict, one line: the representation does not need to change.**
> **Category (a) INFORMATION DESTROYED = 0 of 1,381 missed boundaries (0.0%).** Not a single
> missed boundary is explained by preprocessing loss, and the claim is backed by a whole-corpus
> trace rather than an argument. (b) + (c) account for **73.7%**. This is the
> candidate-space limitation ADR-015 predicted, not representation loss.

This experiment MEASURES. It repairs nothing, and builds no candidate generator, scorer,
decoder or LLM.

---

## 1. The population

| | |
|---|---|
| scoreable canonical executions (S-E1) | 1,589 |
| fragments → boundary points | 1,752 → **3,504** |
| reachable within τ = 2 s of a block edge | 60.6% *(reproduces S-E1 exactly)* |
| **missed, and classified below** | **1,381** |

---

## 2. The five decision rules, stated mechanically

Precedence is fixed and total. Each boundary is tested in this order and falls through to (d),
so exactly one category is assigned and the counts sum to 1,381. Implemented in
`classify.py::classify_boundary`; each rule has a unit test in `tests/test_se2_classify.py`.

| Order | Category | Mechanical rule |
|---|---|---|
| 1 | **(e)** GT/telemetry mismatch | the boundary lies outside `[first_event_ts, last_event_ts]`; **or** removing the measured annotation lead makes it reachable — `min |(g − lead) − edge| ≤ τ`; **or** no retained event exists within τ at all |
| 2 | **(a)** information destroyed | a raw event exists in the source `chunk_*/events.jsonl` within ±τ whose `event_id` is **absent** from the normalised stream |
| 3 | **(c)** absorbed micro-excursion | unreachable against the default blocks **and** reachable against blocks rebuilt with absorption disabled: `min |g − edge_no_absorb| ≤ τ` |
| 4 | **(b)** preserved inside a block | `block.start < g < block.end` **and** ≥ 1 discriminating signal among the retained events within ±τ |
| 5 | **(d)** ambiguous | everything else — the residue, by construction |

**Why this order.** (e) is tested first so the annotation lead cannot leak into (d) and inflate
the "genuinely ambiguous" residue, which is the exact failure this experiment exists to
prevent. (a) outranks every rule that presumes the events are present. (c) precedes (b) so a
provably absorbed excursion is never merely reported as "a signal was nearby".

**Discriminating signals** — ten event types that mark a transition rather than the continuation
of typing or pointing (`browser_navigation`, `app_switch`, `browser_form_input`,
`clipboard_change`, `shortcut`, `mouse_drag_drop`, `dialog_opened`, `dialog_closed`,
`browser_tab_event`, `window_title_change`), plus five state signals derived by comparing
consecutive retained rows (`route_change`, `origin_change`, `app_change`, `field_key_change`,
`large_relative_gap`). `keystroke`, `mouse_click`, `mouse_scroll` and `screenshot_smart` are
deliberately excluded: they are the background hum of any activity and including them would
make every window "signalled" and category (d) vacuous. A gap counts as large at or above the
**session's own p95** of `ms_since_last` — per-session, because ADR-003 keeps *relative* gap as
a feature and an absolute threshold would be a dataset-specific rule.

---

## 3. Result — the five-category table

| Category | n | % of missed |
|---|---|---|
| **(a)** information destroyed by preprocessing | **0** | **0.0%** |
| **(b)** information preserved inside a block | **892** | **64.6%** |
| **(c)** absorbed micro-excursion | **126** | **9.1%** |
| **(d)** ambiguous — no discriminating evidence | **14** | **1.0%** |
| **(e)** GT / telemetry mismatch | **349** | **25.3%** |
| **TOTAL** | **1,381** | 100.0% |

Sub-categories:

| | n |
|---|---|
| (b) signal present inside a block | 892 |
| (c) absorbed under the `A\|x\|A → A` rule | 126 |
| (d) inside a block, no signal | 14 |
| (e) no telemetry within τ — a recording gap | **308** |
| (e) outside the telemetry span (the truncated session) | 37 |
| (e) explained by the annotation lead | 4 |

---

## 4. Category (a) = 0 — the trace, not an assertion

The brief requires a raw-event trace for any (a) claim. There are no (a) claims, so the
evidence is the negative: **no missed boundary has a raw event in its window that fails to
survive normalisation.** Whole-corpus audit:

| | |
|---|---|
| raw events in source `chunk_*/events.jsonl` | **162,768** |
| events in the normalised stream | **162,768** |
| malformed raw lines skipped | **0** |

The two counts are identical and nothing was skipped. This is consistent with the code:
`normalise.load_session` drops only malformed JSON lines, and `blocks.build_blocks` assigns
**every** retained row to exactly one block — capture events attach to the open block
(ADR-012), undiscriminated rows attach to a same-application block (ADR-012), absorption merges
runs without discarding rows. No stage deletes an event.

**Three quoted examples for (a) cannot be produced because there are zero instances.** That is
the finding, and the aggregate trace above is what backs it.

---

## 5. The annotation lead — re-verified, and a definition corrected

Phase 1's "+820 ms lead" is quoted in `EVALUATION_PROTOCOL.md` §8. Re-measured on the corrected
population (n = 3,504):

| quantity | p25 | **p50** | p75 |
|---|---|---|---|
| GT → nearest retained **event** | 169 ms | **176 ms** | 803 ms |

**The +820 ms figure is not the GT-to-event lead.** It is the GT-to-**block-edge** distance,
also measured in Phase 1 (+822 ms p50) — a different quantity, and one this experiment is
measuring rather than correcting for. The classifier therefore applies the **176 ms** event lead,
because that is the genuine annotation offset; using 820 ms would be circular, correcting for
the very block-edge distance under test.

Consequence: only **4** boundaries are explained by the lead. The lead is real but small, and
it does **not** silently inflate any category. This is the second definitional confusion of the
same shape S-E1 found; both arise from quoting a number without its denominator or its
reference object.

---

## 6. Contingency table — signal rate at missed boundaries vs controls

Controls are sampled at ±5 s from each missed boundary and **rejected if their ±2 s window
contains any GT boundary**, so a control is never secretly a boundary. Window ±2 s, matching
the tolerance.

| signal | boundary n | boundary % | control n | control % | direction |
|---|---|---|---|---|---|
| `app_switch` | 980 | **71.0%** | 1,718 | 63.9% | weakly positive |
| `large_relative_gap` | 841 | **60.9%** | 1,145 | 42.6% | positive |
| `shortcut` | 22 | 1.6% | 1,184 | **44.0%** | strongly **inverse** |
| `origin_change` | 123 | 8.9% | 1,078 | **40.1%** | inverse |
| `route_change` | 123 | 8.9% | 912 | **33.9%** | inverse |
| `clipboard_change` | 8 | 0.6% | 713 | **26.5%** | inverse |
| `app_change` | 8 | 0.6% | 554 | **20.6%** | inverse |
| `browser_form_input` | 60 | 4.3% | 448 | **16.7%** | inverse |

n = 1,381 boundaries, 2,690 controls. A second table at the literally-specified ±2 s offset is
in `metrics.json`; it necessarily uses a ±1 s window, because at offset = window the control
window contains the boundary it was offset from and every control is rejected.

The boundary-side column reproduces the prior evidence almost exactly — `app_switch` 71.0% vs
the hypothesised 71.0%, `shortcut` 1.6% vs 1.6%, `clipboard_change` 0.6% vs 0.6%,
`browser_form_input` 4.3% vs the hypothesised `browser_click` 4.3%. The control-side column
differs because control sampling was never specified before.

**Two readings matter.**

1. **`app_switch` at 71.0% while `app_change` is 0.6%.** The application does *not* change at
   these boundaries — so these are the **self-referential `app_switch` events ADR-014
   deliberately declined to suppress**, on the evidence that 176 of 738 on Dataset B carried a
   meaningfully different window title. They are present at seven in ten missed boundaries and
   produce **no block edge**. That is the single most usable signal this experiment found, and
   ADR-014 is the reason it still exists in the stream.
2. **The strong signals are inverse.** `shortcut`, `clipboard_change`, `origin_change`,
   `route_change` and `browser_form_input` are all 3–27× *more* common away from a missed
   boundary. Absence of transactional activity is itself evidence. A scorer should use negative
   evidence, not only positive.

**Caveat that governs the whole table:** it is computed over **missed** boundaries only. Any
boundary accompanied by a surface change was reachable and is excluded by construction — which
is precisely why `browser_navigation` and `route_change` are near-absent here. This table
describes the residual population a finer candidate layer must target, **not** all GT
boundaries.

---

## 7. Quoted examples

Full records with surrounding events are in `samples.jsonl`.

### (c) absorbed micro-excursion — three examples

All three show the same signature: an `app_switch` a few hundred ms *before* the boundary and
another a few hundred ms *after*, the pair forming an `A|x|A` excursion that `blocks._absorb`
merged away.

| session | proc | boundary ts | surrounding |
|---|---|---|---|
| `ses_20260630-124826-CHAITANYA0BCF` | M | 1782823760542 | `app_switch` −387 ms, `app_switch` +172 ms (WindowsTerminal) |
| `ses_20260630-124826-CHAITANYA0BCF` | L | 1782823994540 | `app_switch` −1267 ms, −173 ms, +169 ms (Notepad) |
| `ses_20260630-135451-CHAITANYA0BCF` | H | 1782827744970 | `app_switch` −381 ms, `app_switch` +169 ms (WindowsTerminal) |

Absorption is doing exactly what it was designed to do; it simply also removes the edge a
boundary needed. Blocks built with absorption disabled: **5,565 vs 4,957 default** — 608 extra
edges, of which 126 land on a missed boundary.

### (d) ambiguous — three examples

| session | proc | boundary ts | nearest events |
|---|---|---|---|
| `ses_20260630-121953-LAPTOP-R36BQBTE` | B | 1782822311308 | `mouse_click` −1509 ms; next `app_switch` **+50,907 ms** |
| `ses_20260630-125757-LAPTOP-R36BQBTE` | L | 1782824732449 | `mouse_click` −1508 ms; next `app_switch` **+36,380 ms** |
| `ses_20260630-125757-LAPTOP-R36BQBTE` | K | 1782824913352 | `mouse_click` −1859 ms; next `app_switch` **+7,404 ms** |

The pattern is identical in all three: the worker stops, and GT says the next execution begins
in the silence that follows. There is a retained event just before (so it is not a recording
gap) but nothing discriminating within tolerance. **This is the honest residue** — 14
boundaries, 1.0% — and it is the population a semantic adjudicator would target. It is far too
small to justify an LLM on its own.

### (a) information destroyed — **no examples exist**

Zero instances. See §4.

---

## 8. GATE-1

**Category (a) = 0.0%, far below the ~25% threshold. (b) + (c) = 1,018 = 73.7%.**

Per the gate's second branch — *"if (a) is small and (b) + (c) dominate: report that finding and
stop for review anyway"* — this experiment **stops here**. S-E3 is a separate prompt.

What the result licenses, and what it does not:

- **Licensed:** the candidate-layer plan (`STEP1_SPEC.md` §3.2). 73.7% of missed boundaries have
  their evidence still present in the retained events; they were simply never nominated as
  candidates. The two signals with real mass are self-referential `app_switch` (71.0%) and a
  large relative gap (60.9%).
- **Not licensed:** rebuilding the perception layer. There is no measured information loss to
  repair, and `STEP1_SPEC.md` §1 is explicit that it must not be rebuilt on suspicion.
- **A ceiling S-E3 must respect:** category (e) is **25.3%**, and 308 of those (22.3% of all
  missed) have **no retained event within 2 s**. No candidate generator can nominate a boundary
  where there is no event. Combined with the 60.6% already reachable, the arithmetic upper
  bound for any event-level candidate space on this population is about **74.7%** at τ = 2 s
  — meaningfully below the "high 80s" that S-E3's decision table treats as a clean pass. That
  should be known *before* S-E3 runs, so its result is read against the right expectation
  rather than treated as a disappointment.

## 9. Threats to validity

- The classifier's precedence is a modelling choice. A boundary that is both absorbed and
  signalled counts as (c); one both lead-explained and signalled counts as (e). The order is
  stated, tested and auditable, but different precedence would move counts between (b), (c)
  and (e). It would not move (a), which is zero under any ordering.
- The discriminating-signal list is a hypothesis set, not a fitted model. (b) means "at least
  one listed signal is present", not "the boundary is recoverable".
- `large_relative_gap` uses the session's p95, so it fires on ~5% of events by construction;
  its 60.9%-vs-42.6% contrast should be read with that base rate in mind.
- (e)`telemetry_gap` at 308 is sensitive to τ: a boundary with its nearest event 2.1 s away is
  (e) at τ = 2 s and something else at τ = 5 s.

## Reproduce

```bash
python3 experiments/SE1-gt-metric-correction/run.py   # population + grid
python3 experiments/SE2-miss-attribution/run.py
pytest tests/test_se2_classify.py -q
```

---

## Correction — 2026-09-14

Appended after the experiment; the sections above are the record as written and are not
rewritten.

### C1. The ceiling in §8 was wrong: ~74.7% → **90.0%** at τ = 2 s

§8 stated "the arithmetic upper bound for any event-level candidate space is about **74.7%** at
τ = 2 s". That was computed as `100 − 25.3`, where 25.3% is category (e) as a share of the
**1,381 missed** boundaries (349/1,381). It should have been taken as a share of **all 3,504
boundary points** (349/3,504 = 9.96%). Mixing a share-of-missed with a share-of-all is the
third instance in this project of a figure quoted against the wrong denominator, and the one
that mattered most, because it understated the achievable ceiling by 15 points.

Recomputed directly rather than by subtraction — a boundary is reachable **in principle** by an
event-level generator iff at least one retained event lies within τ of it, since a candidate can
only be placed at an event:

| τ | ceiling n | **ceiling** | block-edge n | block-edge | headroom |
|---|---|---|---|---|---|
| 1,000 ms | 2,726 | **77.8%** | 1,690 | 48.2% | 29.6 pts |
| 2,000 ms | 3,155 | **90.0%** | 2,123 | 60.6% | 29.5 pts |
| 5,000 ms | 3,459 | **98.7%** | 2,696 | 76.9% | 21.8 pts |
| 10,000 ms | 3,466 | **98.9%** | 3,236 | 92.4% | 6.6 pts |

n = 3,504 boundary points, scoreable canonical, tiers `clean + repaired`.

At τ = 2 s the ceiling is **90.04%** (3,155/3,504), so 349 boundaries are unreachable in
principle — matching category (e) exactly, which confirms the classifier partitioned correctly
and only the arithmetic was at fault. **The ceiling is τ-dependent and must be quoted per τ**:
at τ = 1 s it is 77.8%, and at τ = 10 s the block-edge space is already within 6.6 points of it,
so there is very little for a finer candidate layer to win at the loose end of the grid. The
headroom a finer generator can compete for is ~29.5 points, and it is at τ = 1–2 s.

§8's conclusion that the ceiling sits "below the high 80s" is therefore **withdrawn**. At
τ = 2 s the ceiling is 90.0%, which is within the range S-E3's decision table treats as a clean
pass.

### C2. Category (a) = 0 re-tested at FIELD level — and it holds

§4 established (a) = 0 by showing 162,768 raw events = 162,768 normalised events. That proves no
**event** is deleted; it does not prove no **field value** is normalised away — and defect D-1
was exactly that kind of loss, a stripped title suffix collapsing two surfaces into one.

Re-tested on all **906** boundaries classified (b) or (d), comparing the event immediately
before each boundary with the event immediately after:

- does the **raw** `window_title` differ across the boundary while the **normalised** title is
  identical?
- does the **raw** `url` differ while the derived `(origin, route)` pair is identical?

Live suspects in `normalise._TITLE_STRIP`: the `^\*` unsaved-document marker,
`- Compatibility Mode`, the trailing application suffix, the whitespace collapse; and
`route_of` discarding the origin.

**Result: zero cases, on both tests, across all 906 boundaries.** No boundary is hidden by
normalisation collapsing two distinct raw values into one.

This is a materially stronger claim than the event-count trace, and it is what properly
establishes (a) = 0. GATE-1 is **not** reopened.
