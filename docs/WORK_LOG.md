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
