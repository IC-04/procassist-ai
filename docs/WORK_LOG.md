# WORK_LOG

Append-only. One entry per working session. This is a **graded deliverable**
(`README.md` Deliverables §4): it must record what was tried, what failed, decisions taken,
and how generative AI was used.

Newest entries at the bottom.

---

## Template

```markdown
### YYYY-MM-DD · Phase N · <session title>

**Goal**
**Did**
**Result**            numbers, not adjectives
**Problems**          including things that did not work
**Decisions**         link to ADR if architectural
**Generative AI use** what was used, for what, how verified
**Next**
**Time spent**
```

---

### 2026-09-12 · Phase 0 (pre) · Perception layer bootstrap

**Goal** Build the deterministic perception + TEKG layer and see whether the representation
is rich enough to support contextual reasoning.

**Did** Implemented `procmine/{normalise,blocks,tekg,context,cli}.py`. Ran against
`dataset_b` (15 sessions, 20,477 events).

**Result**
- 7,408 raw context-state changes → **1,782 activity blocks** (11.5 events/block,
  2,771 micro-excursions absorbed, 119 blocks/session).
- TEKG edges: `same_surface_as` 2150, `returns_to` 2150, `same_field_as` 940,
  `same_system_as` 235, `same_route_as` 182, `shared_value_with` 74, `dataflow_to` 35.
- Reasoner payload ≈ 1.7k tokens at `window=5`.

**Problems**
- Degenerate tail: many 1-event / 0-second blocks survive absorption; 63 blocks have an empty
  surface key. Median is 4 events/block, which is lower than intended.
- 1,767 ungated windows × 1.7k tokens ≈ 3M tokens for B alone → the ambiguity gate is
  mandatory, not optional.
- `dataset_a/` is not on disk. Phase 1 is blocked.

**Decisions** ADR-002 (provenance demoted), ADR-004 (block is the reasoning unit),
ADR-005 (TEKG is evidence/explanation, not inference).

**Generative AI use** GenAI-assisted development. Claude (chat) was used as a research and
development assistance tool for architecture exploration, spec drafting and drafting the
initial perception layer; all output was reviewed, edited and accepted by me before it entered
the repository. All numbers above were produced by running the code, not asserted by the tool.

**Next** Phase 0: stabilise repo, fix the block tail, then Gate G0.

**Time spent** ~3 h

---

### 2026-09-13 · Phase 0 · Engineering setup and perception stabilisation

**Goal** Leave the repository runnable, tested and reproducible, and fix the measured block
degenerate tail. Dataset A not required.

**Did**
- Repository skeleton: `git init` + branch `phase-0-setup`, `.gitignore` committed *first* so
  `dataset_a/`, `dataset_b/`, `build/`, `.env` can never be staged; `pyproject.toml`
  (`requires-python >=3.10`, deps `pandas`/`numpy`/`networkx`, `pytest` under `dev`);
  `Makefile` (`setup`/`test`/`build-b`/`build-a`/`run-b`/`clean`); `.env.example`.
- **Investigated the degenerate tail against the raw telemetry before changing anything.**
  It was not a threshold problem: four distinct perception defects accounted for it.
  Wrote each fix as a rule keyed on a `DATA_SCHEMA.md` property — never on an application
  name, URL, title or frequency observed in B — so the same code path runs unchanged on A.
  ADR-012 (capture/agent layers are surface-transparent), ADR-013 (browser tab is
  carried-forward state; surface type is structural, `BROWSERS` allow-list deleted),
  ADR-014 (`app_switch` self-transitions are *not* suppressed — tested and rejected).
- `procmine/schemas.py`: validators for `blocks.jsonl`, TEKG documents and window payloads.
  `cli.py` now fails hard rather than writing a non-conforming artifact, and **writes
  `build/<dataset>/tekg/<session>.json`, which `DATA_CONTRACT.md` §3 requires but which was
  never emitted at all**. Parameters exposed (`--min-events/--min-ms/--max-lag/--no-windows`);
  `logging` replaces `print`.
- Test suite: 105 tests across 6 files, all on synthetic fixtures except one guarded smoke
  test, so the suite is green with either dataset absent.
- Experiment `E01-block-sweep`: a 5-arm ablation and a 4×3 threshold sweep.

**Result** (measured from artifacts, `build/dataset_b/summary.json`)

| | before | after |
|---|---|---|
| blocks | 1782 | **1338** |
| median events/block | 4 | **8** |
| mean events/block | 11.5 | **15.3** |
| one-event blocks | 623 | **152** |
| zero-duration blocks | 624 | **152** |
| empty-surface blocks | 63 | **0** |
| malformed surface keys | 54 | **0** |
| surface purity | 0.9742 | **0.9852** |
| blocks/session (median) | 119 | 91 |
| TEKG files written | 0 | 15 |

105 tests pass; `make build-b` is byte-identical across runs (`blocks.jsonl`, `tekg/`,
`windows/`); `make build-a` prints "Phase 1 blocked", exits 0 and writes nothing.

**Problems**
- **No Python ≥3.10 on this machine** (only `/usr/bin/python3` 3.9.6; no Homebrew, no pyenv).
  `pyproject.toml` declares `>=3.10` as the phase spec requires, so `make setup` fails by
  design with the required version and a remediation hint. Everything was validated on 3.9.6
  instead — the package imports and runs correctly there — so acceptance criterion 1 is
  **BLOCKED**, not passed. Re-run once an interpreter is installed.
- **Two rules I proposed did not survive contact with the data**, which is the useful part:
  (a) suppressing `app_switch` self-transitions would have destroyed 176 genuine document
  boundaries (`Opening - Excel` → `expense_calc - Excel`), so it was rejected → ADR-014;
  (b) the browser-tab carry-forward changes **no block boundary** on B — it only fills L1
  screenshot rows that are already transparent. Kept as correct schema modelling, reported
  as a negative result rather than claimed as a fix.
- Removing the `BROWSERS` allow-list *on its own* made things slightly worse (1782 → 1811
  blocks). It only pays off combined with the layer-transparency rule. Kept because an
  allow-list of browser names is exactly the dataset-specific rule the constraint forbids.
- My first artifact validators were wrong twice and the CLI's hard-fail caught both: the
  surface grammar rejected 753 legitimate blocks whose window titles contain spaces, and the
  ADR-006 `\d{13}` rule flagged a field-key hash carrying a 22-digit run. Both tightened to
  token boundaries, both now regression-tested.
- Zero-duration blocks cannot reach the Task 0.3 target of 0. A one-event block necessarily
  has `dur_ms == 0`, and the 152 that remain are mostly genuine — a worker flipping between
  three separate systems' dashboards. Forcing the number would merge distinct business
  systems and destroy the `same_system_as` evidence process-switch detection needs. Reported
  as the trade-off Task 0.3 explicitly permits.

**Decisions** ADR-012, ADR-013, ADR-014 (above). Absorption defaults kept at
`min_events=3`, `min_ms=1500` — now argued from E01 rather than inherited: lowest
fragmentation in the grid, purity within 0.003 of the best cell, and the conservative choice
when two settings are close, because an absorbed excursion is exactly the `INTERRUPTION`
signature the reasoner is later asked to judge. `min_ms` turns out to be inert on B.

**Generative AI use** GenAI-assisted implementation and review. Claude Code (Opus 5) was used
as a development assistance tool to draft the Phase 0 implementation, tests and experiment
harness in this session; I reviewed, directed and accepted the result, and set the constraint
that every perception rule be dataset-agnostic and justified against `DATA_SCHEMA.md`. Every
number in this entry was produced by running the code and read back out of the artifacts; none
was asserted by the tool. Two rules the tool proposed were discarded after measurement
contradicted them (ADR-014, and the carry-forward negative result) — the measurements, not the
tool's suggestions, decided.

**Next** Gate G0 review. Phase 1 needs `dataset_a/`, which is still not on disk.

**Time spent** ~3.5 h

---

### 2026-09-13 · Phase 0 (post) · Dataset A ingestion, then the Python environment blocker

**Goal** Clear the two things standing between Gate G0 and Phase 1: get Dataset A on disk and
verified, and resolve the Python ≥3.10 blocker. Not Phase 1.

**Did**
- **Dataset A.** Delivered as Google Drive's multi-part export — five *independent*
  self-contained ZIPs, not `.001/.002` split parts. Verified the format from file signatures
  before touching anything: each begins `PK\x03\x04` and ends with its own EOCD, and the five
  hold disjoint subsets (34,923 entries, 0 duplicate paths). Concatenating them, which the
  naming invites, would have produced a corrupt archive. CRC-verified all five before
  extraction, then extracted each with `unzip -n`. Sources untouched and retained.
  Full audit written to `docs/DATASET_A_READINESS.md`.
- **Python.** No passwordless sudo, so the python.org installer and Homebrew were both
  unavailable. Installed a relocatable CPython 3.12.14 (`python-build-standalone`) into
  `~/.local`, SHA256-verified against the release's official `SHA256SUMS`, and put it on PATH
  via `~/.zshrc` + `~/.zprofile`. **`pyproject.toml` was not weakened to `>=3.9` and no Phase
  0 code was changed.**

**Result**
- Dataset A: **63 sessions, 162,768 events, 0 malformed lines**, 34,923/34,923 files, 10.22 GB;
  GT complete for every session (63 + 63 files, 10,609 records, 0 malformed). All 13 documented
  top-level schema fields and all five `correlation.*` fields at 100%.
- Generic pipeline ingested A unmodified: 63 sessions → 4,968 blocks, 0 contract violations,
  6.1 s. **No A-specific code anywhere.**
- On 3.12.14: `make setup` green; `make test` **104 passed, 1 skipped** (the skip is the
  ADR-010 guard that only runs when `dataset_a/` is absent — expected); `make build-b`
  byte-reproducible and **numerically identical** to the 3.9.6 figures, so the interpreter
  change moved nothing.

**Problems**
- **I nearly reported a wrong number.** My first audit said 20 screenshot references were
  missing. That was an artifact of my own `len(...) < 20` example cap — the real figure is
  3,568. Re-measured properly: **0 images are truly absent**; in 11 of 63 sessions the
  screenshots simply live in a sibling short-named chunk (`chunk_1200`) rather than the event's
  own chunk, so the literal `DATA_SCHEMA.md` §2 join resolves 89.68% while a session-scoped
  lookup reaches 100%. Harmless for Phase 0/1, which never opens an image; recorded as
  observation O1 for whichever phase first does. Not fixed now.
- **A real git leak, found and closed.** The five delivered archives sat in the repository root
  as 9.5 GB of untracked-but-*committable* files: `.gitignore` covered `dataset_a/` but not
  `dataset_a-*.zip`, so a single `git add -A` would have staged them.
- The scripted Google Drive download I started first was the wrong approach: ~5,700 files
  fetched individually, still enumerating after 15 minutes and 0 bytes transferred. Abandoned
  and its 166 MB partial discarded once the manual download was available. A server-side zip
  was always going to beat per-file scraping here.

**Decisions** No ADR. Nothing architectural changed. Dataset A observations O1–O4 are recorded
in `docs/DATASET_A_READINESS.md` as observations, explicitly *not* as generic pipeline rules;
O3 (`app_switch` is 31.1% of A's events against 8.1% of B's) flags ADR-014 for re-measurement
in Phase 2.

**Generative AI use** GenAI-assisted verification and documentation. Claude Code (Opus 5) was
used as a development assistance tool to run the integrity/schema audit, diagnose the archive
format and install the interpreter, under my direction. Every figure was measured by running
the code and read back from artifacts; the one number the tool initially got wrong (the
screenshot count above) was caught by re-measuring, not by accepting its first answer.

**Next** Gate G0 review. Both Phase 1 blockers are now clear.

**Time spent** ~1.5 h

---

### 2026-09-13 · Phase 1 · GT canonicaliser, evaluation harness, baselines

**Goal** Turn Dataset A into a measuring instrument and end with a baseline scorecard.
Not a segmenter phase; no method was built or tuned.

**Did** `procmine/gt.py` (GT canonicaliser under ADR-011's frozen repair rules),
`procmine/evaluate.py` (the harness, both coordinate domains, tiered), `procmine/baselines.py`
(the six baselines plus a CLI), `experiments/E11-baselines/`, `docs/GT_DEFECT_REPORT.md`,
58 new tests with hand-computed expected values.

**Result**
- GT: 10,609 stream records → 2,009 executions → **1,819 canonical**; tiers clean 1,946 /
  repaired 63 / **disputed 0**; **98 interrupted (5.4%)**, spanning **5.6×** their own
  working time.
- Baselines (63 sessions, τ=2 s, headline tier/convention): B0 0.000 · B1 **0.008** ·
  B2-gap **0.089** · B3-random 0.109 · B4-surface 0.247 · **B5-dwell 0.258**.
- **B2-gap scores below random while holding the oracle count** — ADR-003 confirmed on A.
- **Representational ceiling: only 60.4% of execution boundaries have any block boundary
  within 2 s**, and **98.4% of the misses involve no screen change at all.**
- Risk R1 retired: A's blocks are richer than B's (median 30 vs 8 events/block).

**Problems**
- My first canonicaliser reported **0 interrupted executions** because it grouped fragments by
  `case_id`, as the task wording suggests. Dataset A's case_ids are unique *per fragment*;
  `split_id` is the only link, and the manifest records it on one side only. Trusting that
  output would have reported the interruption phenomenon as non-existent.
- My first GT scan reported **159 unpaired `process_switched_out`**; the true count is 0. The
  scan did not treat `process_resumed` as re-opening an execution. Both numbers are in the
  defect report, because the wrong one is the trap.
- My first artifact layout committed dataset-A-derived GT into `experiments/` and produced a
  **44 MB** `metrics.json`. Both fixed before the first Phase 1 commit.
- I introduced an inconsistency in the spread statistic while trimming that file (per-session
  values for seed 0 mixed with pooled values for seeds 1–19). Caught because `B3-random`'s
  spread moved between two runs whose arm means were identical.
- Two generic Phase 0 defects surfaced by A and deliberately **not** fixed mid-phase:
  `_TITLE_STRIP` does not strip Chrome's ` - Google Chrome`, and `NOISE_TITLE_HINTS`
  misflags Notepad's `Untitled`. Fixing either changes block statistics and would invalidate
  this scorecard; recommended for the start of Phase 2.

**Decisions** No ADR. The alignment target is `executions[].start_ts/end_ts`, chosen because
`expected_boundaries` was measured to be exactly the same information (100% exact match) but
strictly less complete. τ is calibrated from A's median execution duration (34.8 s), the only
parameter selected from A in this phase.

**Generative AI use** GenAI-assisted implementation and analysis. Claude Code (Opus 5) was
used as a development assistance tool to write the modules, tests and experiment harness under
my direction. Every figure was produced by running the code and read back from artifacts. The
two wrong numbers above were caught by re-measuring against the raw data rather than by
accepting the tool's first output.

**Next** Gate G1. Phase 2 not started.

**Time spent** ~2.5 h

---

## 2026-09-13 — Step 1 reorientation (specification only, no code)

**What changed and why.** Phase 1 measured 59.9% of Dataset A GT boundaries within τ=2 s of a
block edge, and the repository had begun treating that as a ceiling on the representation. It is
not: it is the reachability of the block-edge **candidate space**. 74.5% of GT boundaries fall
strictly inside a block, and the events that discriminate them survive into the retained stream.
The correction is to keep the perception layer and add an event-level candidate layer beneath it.

Separately, the project had specified retrieval/memory, agentic tools, vision, family/variant
analysis, SOP generation and a Streamlit prototype before Step 1 worked, and `segments.jsonl` —
Deliverables §1 — still does not exist. Scope is now Step 1 only.

**Written**

- `docs/STEP1_SPEC.md` — the authoritative Step 1 specification (two-level architecture, stage
  contracts, six experiments with decision gates, implementation order, definition of done).
- `CLAUDE.md` — rewritten around the Step 1 objective, with the source-of-truth hierarchy and
  hard rules restated.
- `docs/DECISIONS.md` — ADR-015 (block = container, refines ADR-004), ADR-016 (Step-1-only
  scope; phase plan replaced), ADR-017 (accuracy reported on the scoreable canonical population;
  τ grid to be unified), ADR-018 (LLM adjudicates the ambiguous tail, ablatable).
- `docs/IMPLEMENTATION_PLAN.md` — replaced with the Step 1 order and its three gates.
- `docs/EVALUATION_PROTOCOL.md` — §8 GT populations, §9 candidate reachability as a separate
  measurement.
- `docs/DATA_CONTRACT.md` — §10: blocks expose `first_seq`/`last_seq`; `candidates.jsonl`.
- Supersession/deferral banners on `ARCHITECTURE.md`, `AI_REASONING_SPEC.md`, `RETRIEVAL_SPEC.md`,
  `PROTOTYPE_SPEC.md`, `phases/PHASE_2..7.md`.

**Measured during this review (no new analysis code committed)**

`build/dataset_a/executions_canonical.jsonl`: 1,819 canonical executions · 230 with no usable
interval · **1,589 scoreable** · 98 interrupted · confidence clean 1,756 / repaired 63. These
confirm the populations recorded in ADR-017.

**Defects found in our own prior reporting**

1. The Phase 1 §8 ceiling analysis was computed ad hoc and never committed as an experiment
   directory, contrary to `EXPERIMENT_PROTOCOL.md`. S-E1 repairs this.
2. The τ grid disagrees between `PHASE_1_REPORT.md` and `experiments/E11-baselines/config.json`.
3. The "98.4% of missed boundaries have no surface change" figure is over execution-to-execution
   transitions, not over all boundary points; an independent recomputation over all boundary
   points gave ≈69.8%. The denominator was not stated.
4. The baseline scorecard was computed on a 5-session sample while the ceiling analysis used all
   63 sessions; the two were read side by side.

**Generative-AI use.** This reorientation — audit of existing specs, the new Step 1
specification, the ADRs and these edits — was drafted with Claude (Opus 5) in an interactive
session, then reviewed and accepted by the author. No code was written or changed.

**Next action.** Hand `docs/STEP1_SPEC.md` to Claude Code and implement in the order of §7,
stopping at the S-E3 gate.

---

### 2026-09-14 · Step 1 (safety net) · Provisional `segments.jsonl` for Dataset B

**Goal** Put a contract-valid `segments.jsonl` on disk so the submission is never empty while
the real Step 1 pipeline (`docs/STEP1_SPEC.md`) is built. Explicitly provisional: no candidate
generation, no scoring, no decoder, no LLM, no Dataset A, **no accuracy claim**.

**Did** `procmine/emit_segments.py` (reuses `baselines.b5_dwell` and `to_segments`; slugs each
surface key into a stable label, merges adjacent same-label segments, absorbs sub-second
slivers) and `procmine/validate_segments.py` (the five DATA_CONTRACT §6 constraints).
`make segments`, `make validate-segments`; `run-b` now emits the file. 21 new tests.

**Result** 958 segments · 15 sessions · 52 distinct labels · median 6.0 s (p90 21 s, max 125 s)
· 39 labels reused across sessions. From 1,338 blocks: 380 merged by label, 277 sub-second
slivers absorbed, **0 dropped**. Validator passes. `make test` 182 passed / 1 skipped; with
`dataset_a/` physically removed, `make run-b` exits 0 and the suite is 183 passed.

**Problems / things measured rather than assumed**
- **"Merge adjacent blocks sharing a surface key" is a strict no-op.** `build_blocks` pass 1
  already guarantees consecutive blocks never share a surface key — 0 of 1,323 adjacent pairs
  on B. Merging on the emitted *label* is the operative step and is what was implemented.
- **25.9% of blocks (346) begin and end inside the same second**, so they cannot satisfy
  §6.2's `start < end` at second precision. They are absorbed into a neighbour rather than
  dropped or given invented duration; the absorbed events take the neighbour's label.
- **Route-only labels conflate backend systems.** 93.3% of B's web blocks sit on a route
  served by more than one origin (`/payroll-items` appears on all three ports, which carry
  three different system titles). The specified route slug is kept as the default and a
  `--label-scheme surface` option preserves the origin. Reported, not silently changed.
- **A strict "no boundary may touch a chunk edge" rule would be wrong**: 4 of 1,781 block
  boundaries coincide with one legitimately. The check requires a boundary to be chunk-aligned
  *and* otherwise unexplained.

**Decisions** No ADR; nothing architectural changed. §6.5 (duration floor from A) is not
enforced — it needs Dataset A and the B deliverable must not depend on A (ADR-010). §6.6 is
guaranteed by construction and measured rather than asserted.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote the two modules
and their tests under my direction; every figure above was produced by running the code.

**Next** The real Step 1 pipeline per `STEP1_SPEC.md`. This file is a floor to be replaced.

**Time spent** ~0.5 h

---

### 2026-09-14 · Step 1 · D-1 / D-2 fixes and experiment S-E1

**Goal** Establish the empirical baseline. No algorithm: no candidate generator, no scorer,
no decoder, no LLM.

**Did** D-1 (`normalise._TITLE_STRIP` generalised structurally — trailing separator, optional
`Profile N`, one to three Capitalised tokens; no browser allow-list, ADR-013 stands) and D-2
(bare `"Untitled"` removed from `blocks.NOISE_TITLE_HINTS`), each with regression tests.
Created `experiments/SE1-gt-metric-correction/`.

**Result**
- Block-count deltas, both well inside the ~10% STOP threshold: A 4,968 → 4,957 (−0.2%),
  B 1,338 → 1,338 (0.0%); distinct surfaces A 134 → 130 (−4, exactly the D-1 defect).
- **Reported because it is a finding, not a detail:** `noise_blocks` A 652 → **1** (−99.8%),
  B 53 → 36 (−32.1%). 651 of A's 652 noise flags came from that one `"Untitled"` hint — almost
  all of A's "noise" was Notepad work. Nothing gates on `is_noise`, so no behaviour changed.
- GT populations verified **exactly, zero disagreements**: canonical 1,819 · unscoreable 230 ·
  scoreable canonical 1,589 · interrupted 98 · clean 1,756 / repaired 63 · raw 2,009 with 257
  lacking `end_ts`.
- τ unified to **{1000, 2000, 5000, 10000} ms**, justified from the scoreable canonical
  fragment durations (median 31.7 s; the grid spans 3.2–31.5% of it). Both prior grids
  superseded.
- **Block-edge reachability survives correction: 60.6% at τ=2 s** on 3,504 boundary points,
  against the prior ad-hoc 59.9%. 74.1% inside a block (was 74.5%); median distance 1,026 ms
  (was 1,040). Candidate density 0.059/event, 1.95/block.
- Baselines re-scored on all 63 sessions: **every arm reproduces its prior value to three
  decimals** (B5-dwell 0.258). E11 had already been scoring the scoreable population without
  naming it.

**Problems / things measured rather than assumed**
- The `PHASE_1_REPORT.md` §8 numbers came from three **uncommitted** scratchpad scripts
  (`ceiling.py`, `why_missed.py`, `offset.py`). No committed artifact produced them. They
  happened to be close to correct; that was not knowable before S-E1.
- The "98.4% vs ≈69.8%" question has **three** readings, not two, and the distinction is
  *conditioning*, not granularity: of missed transitions 98.5%, of missed boundary points
  97.5%, of all boundary points 73.2%. The first two agree; the third is a different statistic.
- τ=5 s reachability moves 82.8% → 76.9%, purely because the prior was measured at 5,250 ms.
  82.8% must not be quoted again.
- `segments.jsonl` is now **stale** after D-1/D-2 — 958 segments still, but 65 lines differ and
  distinct labels drop 52 → 50. It was outside this change's modification budget; `make
  segments` regenerates it.

**Decisions** No ADR; nothing architectural changed. D-2 chose removal over scoping because it
is the smaller change and the only one inside the stated budget (`NOISE_TITLE_HINTS` only).

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) applied the fixes and
wrote the experiment under my direction; every figure was produced by running the code.

**Next** S-E2 (miss attribution) and S-E3 (intra-block candidate reachability — the decisive
experiment). Suite: 194 passed, 1 skipped.

**Time spent** ~1 h

---

### 2026-09-14 · Step 1 · Experiment S-E2 — miss attribution

**Goal** For every GT boundary unreachable within τ=2 s of a block edge, decide mechanically
which of five causes explains it. Measure only; repair nothing.

**Did** `experiments/SE2-miss-attribution/` with the classifier factored into `classify.py`
so each rule is unit-tested. Population and τ grid taken from S-E1, not recomputed. Category
(c) is proven by rebuilding blocks with `min_events=0`, which makes the `len(rows) < min_events`
guard in `blocks._absorb` unsatisfiable — **`blocks.py` was not modified**.

**Result** — 1,381 missed boundaries of 3,504, partitioned exactly:

| category | n | % |
|---|---|---|
| (a) information destroyed | **0** | **0.0%** |
| (b) preserved inside a block | 892 | 64.6% |
| (c) absorbed micro-excursion | 126 | 9.1% |
| (d) ambiguous | 14 | 1.0% |
| (e) GT/telemetry mismatch | 349 | 25.3% |

- **GATE-1: (a) = 0%**, far below the ~25% threshold; (b)+(c) = 73.7%. Stopped for review as
  the gate's second branch requires.
- (a)=0 is backed by a whole-corpus trace, not an argument: raw events **162,768** =
  normalised **162,768**, 0 malformed lines skipped.
- Contingency: `app_switch` **71.0%** at missed boundaries vs 63.9% at controls, while
  `app_change` is only **0.6%** — these are the self-referential `app_switch` events ADR-014
  declined to suppress. They sit at seven in ten missed boundaries and create no block edge.
- The strong signals are **inverse**: `shortcut` 1.6% vs 44.0%, `clipboard_change` 0.6% vs
  26.5%, `origin_change` 8.9% vs 40.1%. Absence of transactional activity is itself evidence.

**Problems / things measured rather than assumed**
- **The "+820 ms annotation lead" is not the GT-to-event lead.** Re-measured on the corrected
  population it is **176 ms** (p50). 820 ms is the GT-to-**block-edge** distance — the quantity
  under test, so correcting for it would have been circular. Using the true 176 ms lead, only
  4 boundaries are explained by it. Second definitional confusion of the same shape S-E1 found.
- My first contingency table returned **zero** control points. At control offset = window half,
  every control's window contains the boundary it was offset from and is rejected. Fixed by
  making the window narrower than the offset, and both tables are reported with their windows
  stated.
- **Category (a) has no quoted examples because there are zero instances.** Stated as the
  finding rather than padded.
- A ceiling S-E3 must respect: 308 missed boundaries (22.3%) have **no retained event within
  2 s**, so no event-level candidate generator can reach them. Arithmetic upper bound for any
  event-level candidate space is ≈**74.7%** at τ=2 s — below the "high 80s" S-E3's decision
  table treats as a clean pass. Worth knowing before S-E3 runs, not after.

**Decisions** No ADR; nothing architectural changed. Verdict: **the representation does not
need to change** — this is candidate-space limitation, exactly as ADR-015 predicted.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote the classifier,
experiment and tests under my direction; every figure was produced by running the code.

**Next** S-E3 (intra-block candidate reachability) — a separate prompt, after review.
Suite: 208 passed, 1 skipped.

**Time spent** ~1 h

---

### 2026-09-14 · Step 1 · S-E3 — intra-block candidate generation and reachability

**Goal** Build the event-level candidate layer and measure whether it recovers the boundaries
S-E2 showed are present inside blocks. Ends at GATE-2. No scorer, gate, decoder or LLM.

**Did** Task 0 corrections (see the previous entry's commit), `first_seq`/`last_seq` on blocks
(DATA_CONTRACT §10.1), `procmine/candidates.py`, candidates wired into `cli.py`,
`experiments/SE3-candidate-reachability/`, 15 generator tests.

**Result — GATE-2: PROCEED.**

| τ | block-edge | candidates | ceiling | ceiling-adjusted |
|---|---|---|---|---|
| 1 s | 48.2% | **77.2%** | 77.8% | **99.3%** |
| **2 s** | 60.6% | **88.0%** | 90.0% | **97.8%** |
| 5 s | 76.9% | 92.2% | 98.7% | 93.4% |
| 10 s | 92.4% | 98.7% | 98.9% | 99.8% |

- Density **0.165/event** on A, 0.127 on B — both well inside the 0.30 gate. Per-session mean
  87.5%, sd 12.7, range [27.8, 98.4]; the floor is the truncated session, retained.
- **Recovery of S-E2's missed boundaries confirms its prediction exactly:** (b) 858/892 =
  96.2%, (c) 125/126 = 99.2%, (d) 7/14, **(e) 0/349 = 0.0%**. The 349 unreachable-in-principle
  records are the entire gap between 90.0% and 100%.
- (c) is recovered **without touching absorption** — the events the excursion was made of are
  still in the block. That removes most of the reason to change it.

**Problems / things measured rather than assumed**
- **Two design tensions resolved by measurement, not judgement.** (i) Contract 3 says nominate
  at *every* self-referential `app_switch`; those arrive in bursts with p50 inter-arrival
  **55 ms**, so the literal reading costs 0.3769/event for **0.0 points** of reachability.
  Dedup at 250 ms — a quarter of the tightest τ — saves 56% density for nothing. (ii)
  `mode_transition` fires on 77.7% of intra-block positions and pushed **dataset_b density to
  0.330/event, over the gate**; demoted to a feature (which §3.2.1 requires anyway) at a cost
  of 1.9 points.
- **The dominant evidence is negative**: `shortcut_w` lift **0.01**, `keystroke_w` 0.02,
  `browser_click_w` 0.03. A boundary is a *lull*, not an event. Deliberately not used to prune
  — a suppressed candidate cannot be recovered downstream.
- **The two contingency tables disagree as predicted**: `app_switch_self_at` lift 1.48 over all
  boundaries vs 1.81 over missed-only. Fitting a scorer on missed-only would mis-rank the 60.6%
  the block-edge space already handles.
- My first `_features` rebuilt the session timeline per candidate — quadratic, unusable on A's
  162k events. Fixed by precomputing once.
- My first GT-isolation test grepped the source and failed on the module's own docstring
  *explaining* that it reads no GT. Rewritten to parse with `ast` so only real imports and
  non-docstring string literals count.

**Decisions** No ADR. Verdict: 88.0% absolute / 97.8% of ceiling / 0.165 density — all three
GATE-2 criteria pass with margin. Carried forward honestly: the ceiling is **90.0%** at τ=2 s,
so any end-to-end recall must be read against 90.0%, not 100%.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote the generator,
experiment and tests under my direction; every figure was produced by running the code.

**Next** Scoring (stage 4) — a separate prompt, after GATE-2 review. Suite: 223 passed,
1 skipped.

**Time spent** ~1.5 h

---

### 2026-09-14 · Step 1 · Scoring, ambiguity gate, constrained decoder

**Goal** Turn the Phase C candidate space into segments. Entirely a precision problem: ~28 true
boundaries among ~426 candidates per session. No LLM, no labelling beyond a placeholder.

**Did** `score.py` (logistic regression, 28 domain-neutral features, clean tier, LOSO),
`gate.py`, `decoder.py` (O(n²) DP under hard constraints), CLI `--segment` / `--fit-scorer`,
`build/<ds>/thresholds.json`, ADR-019, 25 new tests.

**Result — dataset_a, LOSO, scoreable canonical, λ=0.8**

| τ | P | R | F1 |
|---|---|---|---|
| 1 s | 0.551 | 0.564 | 0.557 |
| **2 s** | **0.694** | **0.710** | **0.702** |
| 5 s | 0.746 | 0.762 | 0.754 |
| 10 s | 0.791 | 0.808 | 0.799 |

count ratio **0.9703** · segmental F1@IoU0.5 0.7746 · WindowDiff 0.4736 · **0 constraint
violations** · per-session F1 0.695 ± 0.115 · LOSO AUC 0.979 · **2.72× B5-dwell (0.258)**.
Recall 0.710 against the 90.0% ceiling is **78.9% of achievable**, not 71% of 100%.

**Problems / things measured rather than assumed**
- **GT does not tile the session** — median coverage 0.81, 12% of span in inter-fragment gaps.
  A partitioning decoder emits N+1 boundary points where the reference has 2N, capping recall
  near **52%** however good the ranking. The decoder therefore selects **disjoint** segments.
  Caught before building, by measuring coverage.
- **NMS measured and deliberately NOT used.** The duration floor already suppresses clusters;
  adding NMS makes things worse — nms=2 s drops F1 0.702 → 0.589 (ratio 0.73). Reported the
  measurement instead of adding the machinery.
- **The duration floor is p01 of FRAGMENT durations (19.0 s).** Phase 1's "34.8 s / 23.9 s" were
  *execution-active* durations — a different quantity, correctly not reused.
- **The gate's routed population is discouraging, and that is the point of measuring it.**
  Routing is 3.4% (918/26,860), well inside the 15% target, but it contains only **161 true
  boundaries — 2.7% of all 6,034** — at base rate 0.175, rule-only precision 0.196. An
  adjudicator could address at most 2.7% of boundaries. That decides Phase G on evidence.
- **`is_web_surface` ablation: F1 0.702 → 0.698, Δ −0.004.** The headline does not rest on the
  feature most likely to be A-specific. Good news for the B transfer, and the evidence ADR-019
  cites.
- **Operating point chosen for count ratio ≈ 1.0, not maximum F1.** λ=1.4 scores F1 0.718 at
  ratio 0.83 — a bet on under-segmenting. λ=0.8 gives 0.97 and makes no such bet.
- **B transfer flagged, not validated.** The A-fitted chain emits 4.9 segments/session on B
  against 28.2 on A — 1 per 143 s vs 1 per 46 s, roughly 3× sparser per unit time, covering
  35–85% of each session. B has no ground truth, so this cannot be checked. Recorded as the
  live ADR-010/ADR-019 risk.

**Decisions** ADR-019 — fitted scorer weights are a sanctioned A→B transfer under four
conditions, all met; `thresholds.json` tags all 11 thresholds so the leakage check is mechanical.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote the three stages
and their tests under my direction; every figure was produced by running the code.

**Next** Labelling (stage 8). Suite 248 passed / 1 skipped; 249 passed with `dataset_a` absent.

**Time spent** ~2 h

---

### 2026-09-14 · Step 1 · Calibration, labelling, and S-E4 full Dataset A validation

**Goal** Fix the cross-dataset operating point, add process labelling, validate the whole
deterministic chain on all of A, and size Phase G. No LLM.

**Did** percentile calibration in `score.py`, `label.py`, ADR-020, `experiments/SE4-end-to-end-a/`,
`segments.jsonl` regenerated from the chain, 38 new tests.

**Result — dataset_a, LOSO, `--no-llm`, all 63 sessions**

| τ | P | R | F1 | ceiling | R/ceiling |
|---|---|---|---|---|---|
| 1 s | 0.534 | 0.551 | 0.543 | 77.8% | 70.9% |
| **2 s** | **0.680** | **0.702** | **0.690** | **90.0%** | **77.9%** |
| 5 s | 0.729 | 0.752 | 0.740 | 98.7% | 76.2% |
| 10 s | 0.781 | 0.806 | 0.794 | 98.9% | 81.5% |

count ratio **0.98** · segmental F1@.5 0.768 · WD 0.470 · Pk 0.257 · ARI 0.431 **at match_rate
0.760** · interruption_recall 0.122 **at ratio 0.98** · labels 51, 90% cross-session ·
per-session F1 0.683 ± 0.115 · **2.67× B5-dwell (0.258)** · 265 s.

**Problems / things measured rather than assumed**
- **Calibration.** The A/B divergence was in the scores, not the data: B's p90 0.309 vs A's
  0.975. Percentile calibration costs A 0.012 F1 and moves B from 3.8 to 12.2 segments/session
  with durations 24/87/204 s → 21/35/71 s. **3 thresholds moved `a_fitted` → `structural`.**
  Cannot be proven correct on B — only self-consistent and rule-transferable.
- **Gate bands had to be recentred.** Under percentile calibration band *width is* the routing
  fraction, so the old 0.35/0.65 routed exactly 30%. Now 0.80/0.94 straddling the operating cut
  → **exactly 14.0% on both datasets**, a structural guarantee.
- **Labelling took two attempts.** Selecting `k` by stability is degenerate — fine clusters are
  trivially stable, giving k=849 at 27% cross-session reuse. Switching to co-clustering Jaccard
  did not fix it. **stability × cross-session reuse** has a clean interior optimum: k=63 on A,
  33 on B, each from its own data.
- **The Phase G oracle sizing was wrong and I corrected it.** The first version counted
  *candidates* in the routed band and added them to a *boundary*-level confusion matrix. With
  **1.72 candidates per true boundary** that overstated the gain several-fold — it reported
  +0.08 F1 at 3.4% routing. Recomputed in boundaries: **+0.004 at 3.4%, +0.025 at the full 15%
  budget.** This is the fourth denominator error in the project and the only one that would have
  changed a build decision. **Recommendation: Phase G is a compressed demonstration, not a full
  experiment.**
- **`segments.jsonl` trips a validator false positive.** One intra-block boundary lands on a
  chunk edge; `validate_segments.dataset_context` builds `justified` from *block* boundaries, a
  Phase B assumption predating ADR-015. The candidate was triggered by `large_relative_gap`; no
  trigger references `chunk_id`. Outside this phase's budget — reported with the one-line fix.
- **Interruption stitching is the largest real gap**: 0.122. The decoder has no resumption model.
  Measured and stated rather than hidden.

**Decisions** ADR-020 — A's GT does not tile the session (coverage 0.81, 12% gaps), so the
decoder selects disjoint segments; a partitioning decoder would cap recall near 52%. Downstream:
**~19% of observed session time belongs to no execution**, which Step 2 effort estimates must not
assume away.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote the calibration,
labeller and experiment under my direction; every figure was produced by running the code, and
the two wrong numbers above were caught by re-deriving them, not by accepting the first output.

**Next** Phase F/G per the spec. Suite 267 passed, 1 skipped.

**Time spent** ~2.5 h

---

## 2026-09-14 — S-E6: process identity as representation, similarity and grouping

**Goal** Locate the identity ceiling and decide which grouping method is justified — by
measurement, not by assuming the answer is an LLM. Segmentation frozen throughout; hard cap
2 h 15 m; no LLM.

**Contract** Every arm ran on the exact frozen S-E4 segmentation (1,717 segments, boundary F1
0.6904 @ τ=2 s, count ratio 0.98), reproduced by `build_frozen.py` and asserted identical on
every row of the results table and in `tests/test_identity.py`. Match rate is 0.760 on every
row for the same reason. Every metric came from `evaluate.evaluate_all`; none was
reimplemented.

**Result** The graph arm beats the structural control at unchanged boundary F1:
ARI **0.431 → 0.583**, NMI 0.563 → 0.688, homogeneity 0.622 → 0.679 **and** completeness
0.514 → 0.698 (so neither over-merging nor over-splitting), 51 → 15 labels, cross-session reuse
0.902 → 1.000, interruption_recall 0.122 → 0.337 — the last read beside the label count,
because coarser labels raise it mechanically.

**What failed, and what it taught**
- **The reframe's own hypothesis was wrong.** It predicted the signature overweights WHERE and
  needs WHAT and HOW. The per-view supervised probe says WHERE is the *strongest* view
  (accuracy 0.851), HOW is nearly worthless (0.256 on 15 classes, chance ≈ 0.07), WHAT is real
  and additive (0.741 alone, +0.040 on top of WHERE), all three 0.891. I reported that against
  the brief rather than around it.
- **My first unsupervised selection rule failed, and not by accident.** Modularity ×
  cross-session reuse chose `how_heavy, k_nn=5` → ARI 0.204. Modularity is not comparable
  across graphs of different density, so the rule was really picking the sparsest graph, and it
  scored `how_heavy` and `where_heavy` *identically* at 0.8669 — blind to the difference
  between the informative view and the uninformative one. Replaced by the Phase E rule
  (stability × reuse, co-clustering Jaccard), declared before its ARI was inspected: it picks
  `where_heavy, k_nn=20`, which the GT-informed sweep confirms is the grid optimum. Both rules
  are reported; the failed one is not hidden.
- **The merge-only oracle is small: +0.047 ARI.** 37 of 41 matched labels are impure and 30.2%
  of matched members sit under a wrong-majority label. Impurity is not merge-fixable, so an
  "LLM renames the clusters" design was bounded at 0.478 before it was written.
- **Segmentation is not the limiter.** The same method on GT segments scores 0.427 — within
  0.004 of the control on hypothesis segments. Perfect boundaries would not have fixed identity.
- **Dataset A has no rare process.** All 15 codes appear ≥ 14 times, so case study 5 could not
  be answered on A. Reported as a dataset limit rather than faked with the smallest cluster.
- **`context.extracted_text` is not exposed** by the frozen `normalise.flatten_event` record,
  and `normalise.py` was not modifiable. WHAT was built from titles, element labels, element ids
  and field keys; recorded rather than worked around.

**Decisions** ADR-021 — identity ships as three-view representation → weighted similarity →
kNN graph → Louvain (`procmine/identity.py`, consumed by `label.py` as `method="graph"`), with
the configuration selected unsupervised so Louvain picks its own community count on B.
**Decision: CASE B by the letter of the criterion, with the qualification that matters** — the
residual is *not* a missing-semantics gap (a logistic regression on the same features reaches
0.891), so **no LLM is justified yet**; the next thing to try is IDF-weighting the surface
Jaccard, aimed at the measured defect that 99% of the highest-similarity cross-code pairs share
the portal dashboard root. "LLM identity normalisation" is explicitly not hard-coded and
`STEP1_SPEC.md` §3.7 is unchanged.

**Transfer** On `dataset_b` the same code re-runs its own sweep and Louvain selects **6**
communities over 183 segments (vs 33 structural labels), 100% cross-session reuse. B has no GT;
this is an observation, not a validation, and B was not tuned to resemble A. Flagged, not acted
on: the committed `segments.jsonl` was emitted under the previous default and now diverges from
it.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote
`procmine/identity.py`, the `label.py` wiring, the tests and the experiment under my direction.
Every figure was produced by running the code; the failed selection rule was found by
inspecting what it chose, not by trusting it.

**Next** ADR-021's follow-up (IDF-weighted surface Jaccard) and Phase F/G per the spec. Suite
275 passed, 1 skipped.

**Time spent** ~2 h

---

## 2026-09-15 — S-E6b: the fixes S-E6 proposed, measured

**Goal** Build and measure the two fixes ADR-021 named: IDF-weighted set similarity, and
adaptive view combination. Assess Dataset B's 6-cluster result. Cap 75 minutes; segmentation
frozen; no LLM.

**Headline: the main fix does not work, because my own diagnosis in ADR-021 was wrong.**
S-E6 reported that 99% of the highest-similarity cross-process pairs were wrongly grouped and
that *"what they share is the portal dashboard root"*. That observation was true (71% share it)
but the causal claim built on it was not, and I did not check it before writing it into an ADR.
Measured now: those pairs have a surface **Jaccard of exactly 1.00** — identical surface sets,
mean 1.35 shared surfaces and that is all either has. The Jaccard of two identical sets is 1.0
under any term weighting, so IDF could never have moved them. It moved case study 3 by one pair
in 97, and cost separability (gap 0.2263 → 0.2180, Cohen's d 1.535 → 1.508) and 0.031 ARI. IDF
is implemented, unit-tested, ablatable and **off by default**.

This is the same failure mode as the four denominator errors before it: a real observation
promoted to a mechanism without the one check that would have falsified it.

**A number I had been carrying across arms.** S-E6's case studies 1 and 2 (13.3%) were computed
under the *rule-1* arm, not the shipped one. Under the shipped arm the figure is **1.7%**, and
no combination mode moves it. Case-study rates are only comparable within one arm; they should
not have been quoted across them.

**What did work.** Adaptive per-pair renormalisation over applicable views: ARI 0.580 → 0.585,
NMI 0.685 → 0.696, homogeneity *and* completeness both up, at identical boundary F1. Small and
real. Noisy-OR reaches 0.588 but at 17 labels with completeness falling — it buys ARI by
over-merging, so it is not the default.

**Scaffolding, reported and not removed.** 98/1,717 executions (5.7%) carry a structural
scaffolding signature; 44 are in the matched population and they account for 39 of 411
misgrouped executions — 9.5% of the residual, a 2.9× enrichment. Real contamination, a minority
of the problem, and not what drives case studies 1/2. Left in the pipeline: excluding
inconvenient executions is fitting the evaluation set.

**Dataset B: 6 clusters was not defensible, and I should have caught it last session.**
The selection rule picks `where_heavy` on A's 1,717 executions and `how_heavy` on B's 183 —
the view the probe scored at 0.256. Its 6 clusters have a modal-surface share of 0.32–0.52:
fewer than half the members of a "process" visit that process's own most common surface.
Constraining the weighting to `where_heavy` and letting the rule choose only `k`, B yields
**8 clusters** at modal-surface 0.77 / modal-route 0.92, 100% cross-session reuse. The
weighting is declared as an A→B transfer under the ADR-019 conditions; no A content crosses.
`segments.jsonl` regenerated: 183 segments, 8 labels, 15 sessions. It still trips the one known
`validate_segments` false positive (block-derived `justified` set, predating ADR-015).

**Not done** Task 5 (pretrained multilingual embedding probe) was conditional on 60 minutes
remaining and was not reached. No dependency was added. The prior stated in the brief —
that a corpus of code identifiers and filenames suits char n-grams — is untested and remains
open.

**Decisions** ADR-021 addendum: IDF default off with the measured reason; adaptive combination
ships; B's weighting fixed to `where_heavy` with provenance; no LLM still justified.

**Generative AI use** GenAI-assisted implementation. Claude Code (Opus 5) wrote the IDF and
combination code, the diagnostic and the experiments under my direction. The diagnostic that
falsified the premise was written specifically to test it, and reported against my own prior
conclusion.

**Next** Open questions: the identical-footprint residual; whether a semantic judge can earn its
place there, by ablation; task 5's embedding question. Suite 278 passed, 1 skipped.

**Time spent** ~1.2 h
