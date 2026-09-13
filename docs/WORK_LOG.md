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
