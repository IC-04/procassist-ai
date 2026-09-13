# PHASE_0_REPORT

**Date** 2026-09-13 · **Branch** `phase-0-setup` · **Time spent** ~3.5 h

---

## 1. Plan

- [x] 0.1 Repository skeleton — git, `.gitignore`, `pyproject.toml`, `Makefile`, `.env.example`
- [x] 0.2 Test suite v0 — ≥5 files including the ADR-006 contract test
- [x] 0.3 Fix the block degenerate tail — investigate, fix, sweep, record
- [x] 0.4 Artifact conformance — `schemas.py`, CLI validation, deterministic ordering
- [x] 0.5 Dataset A readiness probe

## 2. What was implemented

| File | Change |
|---|---|
| `.gitignore` | committed **before** `git init`'s first `git add`, so `dataset_a/`, `dataset_b/`, `build/`, `.env`, `.DS_Store` can never be staged |
| `pyproject.toml` | package `procmine`, `requires-python >=3.10`, deps `pandas`/`numpy`/`networkx`, `pytest` under `dev` |
| `Makefile` | `setup` `test` `build-b` `build-a` `run-b` `clean`; `setup` refuses to build a venv on < 3.10 rather than silently mismatching the declared floor |
| `.env.example` | key name only |
| `procmine/normalise.py` | `route_of` fixed; `carry_forward_tab_state` added; `USER_LAYERS`; `new_app`/`prev_app`/`url_observed` on the flat record |
| `procmine/blocks.py` | `is_capture_event`, `has_discriminator`, `surface_defining`; `surface_key` made structural and `BROWSERS` deleted; pass 1b `_attach_late_titles`; passes split into `_absorb`/`_summarise`; degeneracy counters in `block_stats` |
| `procmine/schemas.py` | **new** — validators for blocks, TEKG documents, window payloads |
| `procmine/cli.py` | writes `tekg/<session>.json` (previously never emitted); validates every artifact and fails hard; parameters exposed; `logging`; dataset-absent probe |
| `tests/` | **new** — 6 files, 105 tests |
| `experiments/E01-block-sweep/` | **new** — ablation + sweep, `config/metrics/samples/report` + `run.py` |
| `docs/DECISIONS.md` | ADR-012, ADR-013, ADR-014 appended |
| `docs/WORK_LOG.md` | Phase 0 entry |

## 3. Commands run

```bash
git init && git checkout -b phase-0-setup
python3 -m pytest -q                                  # 105 passed
python3 -m pytest -q --ignore=tests/test_smoke_b.py   # 93 passed — dataset-independent
make test                                             # 105 passed
make build-a                                          # "Phase 1 blocked", exit 0, no artifacts
make setup                                            # fails by design: no Python >= 3.10
rm -rf build && python3 -m procmine.cli --dataset dataset_b
python3 -m procmine.cli --dataset dataset_b --out $SCRATCH/run2
diff build/dataset_b/blocks.jsonl $SCRATCH/run2/blocks.jsonl   # identical
diff -r build/dataset_b/tekg    $SCRATCH/run2/tekg             # identical
diff -r build/dataset_b/windows $SCRATCH/run2/windows          # identical
python3 experiments/E01-block-sweep/run.py
```

## 4. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `make setup && make test` green from a clean clone | **PASS** (resolved 2026-09-13, see §12) | CPython **3.12.14** installed; `make setup` builds `.venv` and installs the pinned dependencies; `make test` → **104 passed, 1 skipped**. The skip is `test_the_b_pipeline_does_not_need_dataset_a`, which asserts `dataset_a/` is *absent* and correctly skips now that A is on disk — not a regression. |
| 2 | ≥5 test files including the ADR-006 contract test | **PASS** | 6 files, 105 tests. Contract test: `tests/test_context.py::test_payload_contains_no_absolute_time_or_global_index`, plus `test_the_contract_test_actually_catches_a_violation` (a contract test that cannot fail is decoration) and `tests/test_smoke_b.py::test_every_window_payload_honours_adr_006` over all 1,323 payloads actually written. |
| 3 | Block quality targets met, or trade-off documented with numbers | **PASS** (2 of 4 targets met; 2 documented as trade-offs with numbers, which the criterion explicitly permits) | median events/block **8** ≥ 8 ✅ · empty-surface **0** ✅ · zero-duration 152, target 0 ⚠️ · blocks/session median 91, band 60–80 ⚠️. See §5 and §7. |
| 4 | `make build-b` is byte-reproducible | **PASS** | Two runs diff clean on `blocks.jsonl`, all 15 `tekg/*.json` and all 1,323 `windows/**`. Also asserted by `tests/test_smoke_b.py::test_build_is_reproducible`. |
| 5 | `make build-a` degrades gracefully when A is absent | **PASS** | Prints `dataset_a not present — Phase 1 blocked. No artifacts written.`, exits **0**, and `build/` contains only `dataset_b`. Two regression tests, including a directory that exists but holds no sessions. |
| 6 | `PHASE_0_REPORT.md` written with the before/after sweep table | **PASS** | This file, §5; full tables in `experiments/E01-block-sweep/report.md`. |
| 7 | Committed on `phase-0-setup` | **PASS** | See §9. |

**All seven criteria PASS.** Criterion 1 was BLOCKED at the time of writing and was resolved
on 2026-09-13; see §12.

## 5. Key numbers produced

Read from `build/dataset_b/summary.json` and `build/dataset_b/blocks.jsonl`.

### Before / after — perception

| | before | after | |
|---|---|---|---|
| events | 20,477 | 20,477 | unchanged input |
| blocks | 1,782 | **1,338** | −24.9% |
| median events/block | 4 | **8** | target ≥8 ✅ |
| mean events/block | 11.5 | **15.3** | |
| one-event blocks | 623 | **152** | −75.6% |
| zero-duration blocks | 624 | **152** | target 0 ⚠️ |
| empty-surface blocks | 63 | **0** | target 0 ✅ |
| malformed surface keys | 54 | **0** | `web:<origin><origin>` |
| surface purity | 0.9742 | **0.9852** | |
| blocks/session (median) | 119 | **91** | band 60–80 ⚠️ |
| absorbed excursions | 2,771 | 90 | the old figure counted screenshot artifacts |
| noise blocks | 120 | 53 | |

### Before / after — TEKG

| relation | before | after |
|---|---|---|
| `same_surface_as` | 2,150 | 1,936 |
| `returns_to` | 2,150 | 1,936 |
| `temporal_next` | 1,767 | 1,323 |
| `same_field_as` | 940 | **1,185** |
| `same_system_as` | 235 | **443** |
| `same_route_as` | 182 | **387** |
| `shared_value_with` | 74 | 80 |
| `dataflow_to` | 35 | 36 |
| **files written** | **0** | **15** (1,338 nodes, 7,326 edges) |

`same_system_as` (+89%) and `same_route_as` (+113%) rise because the `route_of` fix and the
structural surface key let blocks on the same backend actually compare equal — evidence that
was silently absent before. Reasoner windows: 1,767 → 1,323 (−25% prompt volume).

### Ablation (`experiments/E01-block-sweep`)

| arm | blocks | median | 1-event | 0-dur | empty | malformed | purity |
|---|---|---|---|---|---|---|---|
| A0 baseline | 1782 | 4.0 | 623 | 624 | 63 | 54 | 0.9742 |
| A1 +R5 route fix | 1782 | 4.0 | 623 | 624 | 63 | **0** | 0.9742 |
| A2 +R4 structural key | 1811 | 4 | 647 | 648 | 66 | 0 | 0.9723 |
| A3 +R1+R2 transparency | **1338** | **8.0** | **152** | **152** | **0** | 0 | **0.9852** |
| A4 +R3 carry-forward | 1338 | 8.0 | 152 | 152 | 0 | 0 | 0.9852 |

### Sweep — chosen default `min_events=3`, `min_ms=1500`

| min_ev | min_ms | blocks | median | purity | frag(lag2) | short-work kept | stability |
|---|---|---|---|---|---|---|---|
| 2 | 1500 | 1428 | 7.0 | **0.9884** | 0.2079 | 89 | 0.063 |
| **3** | **1500** | **1338** | **8.0** | 0.9852 | **0.1983** | 67 | 0.067 |
| 5 | 1500 | 1286 | 8.0 | 0.9807 | 0.2024 | 45 | 0.040 |
| 8 | 1500 | 1278 | 8.5 | 0.9800 | 0.2011 | 43 | 0.016 |

Full 4×3 grid in the experiment report. `min_events=3` has the lowest fragmentation and
purity within 0.003 of the best cell; `min_ms` is inert on B (identical block counts across
1000/1500/3000). Where two settings are close, the conservative one wins, because an absorbed
excursion is exactly the `INTERRUPTION` signature the reasoner is later asked to judge.

## 6. What did not work

Required section.

1. **Two rules I proposed were wrong, and measuring them first is what caught it.**
   - Suppressing `app_switch` self-transitions (`new_app == previous_app`) looked clean and
     schema-licensed. Measured: 738 such events on B, but **176 carry a different, meaningful
     window title** — `getsujitsu_teigaku_torihikisaki_ichiran` → `kazoku_teate_kitei`,
     `Opening - Excel` → `expense_calc - Excel`. Those are real document switches. The rule
     would have erased 176 genuine boundaries while buying nothing for the other 559, which
     are already no-ops under surface-key equality. **Rejected → ADR-014.**
   - The browser-tab carry-forward was expected to repair 562 L2 browser operations that
     carry no tab URL. Measured: it repairs **none** of them and changes **no block
     boundary**. Those 562 events sit at the *entry* to a browser visit, before any tab has
     been observed, so there is nothing to carry. It only fills 3,058 L1 screenshot rows,
     which the layer-transparency rule already makes transparent. Kept as correct schema
     modelling and for later phases, reported as a **negative result** rather than a fix.
     My first commit message claimed otherwise and was amended.
2. **Deleting the `BROWSERS` allow-list made things worse in isolation** — 1782 → 1811 blocks
   — because an L3 event reported against a non-browser application then keys as a web
   surface. It only pays off combined with layer transparency. Kept anyway: an allow-list of
   browser names is precisely the dataset-specific rule that must not exist.
3. **I wrote the artifact validators wrong twice**, and the CLI's hard-fail caught both
   before anything shipped. The surface grammar `^(web:https?://[^\s]*|app:[^\s]*)$` rejected
   753 legitimate blocks because window titles contain spaces (`app:WindowsTerminal:Windows
   PowerShell`). The ADR-006 rule `\d{13}`, taken verbatim from the docs, flagged the
   field-key hash `b6853646633736950071805f01503e95`, which carries a 22-digit run. Both are
   now anchored to token boundaries and both have regression tests.
4. **The carry-forward leaked across applications on the first attempt** — 87 non-browser
   events inherited a browser URL, because an L3 `browser_navigation` reported against
   Notepad seeded the state. Fixed by seeding only from L2 (the OS-level view that populates
   `active_app` and `active_browser_tab` from one vantage point). Leak now 0, verified.

## 7. Deviations from the spec

1. ~~**`requires-python >=3.10` cannot be satisfied on this machine.**~~ **Resolved
   2026-09-13** — CPython 3.12.14 installed, `make setup && make test` green. `pyproject.toml`
   was never weakened to accommodate 3.9, and no Phase 0 code was changed. See §12.
2. **Two of the four Task 0.3 targets are reported as trade-offs, with numbers**, which
   Task 0.3 explicitly permits ("If a target cannot be met without collapsing genuine short
   work, report the trade-off rather than forcing the number").
   - *Zero-duration blocks: 152, target 0.* A one-event block necessarily has
     `dur_ms == 0`, so this count **is** the one-event count and cannot reach zero without
     eliminating single-event blocks. They were inspected, not tuned: most sit between two
     **different** surfaces, typically a worker flipping between three separate systems'
     dashboards (`5132/dashboard` → `5133/dashboard` → `5134/dashboard`). Merging them would
     fuse distinct business systems and destroy the `same_system_as` evidence that
     process-switch detection depends on.
   - *Blocks/session median 91, band 60–80.* Reaching the band needs `min_events ≥ 5`, which
     costs surface purity and absorbs 22 more brief-but-distinct blocks for no gain in median
     events/block. Per the user directive of 2026-09-13 the band is treated as exploratory,
     and thresholds were selected on coherence, fragmentation, short-work preservation and
     stability instead.
3. **The ADR-006 regex is enforced as the union of the two the docs give**, tightened to
   token boundaries. `DATA_CONTRACT.md` §4 lists `idx`; `TEKG_SPEC.md` §6 lists `\d{13}`.
   The union is stricter than either. **Documentation discrepancy for the reviewer:** the two
   files specify different regexes for the same contract; they should be reconciled.
4. **One file outside the `CLAUDE.md` §4 layout:** `experiments/E01-block-sweep/run.py`.
   `EXPERIMENT_PROTOCOL.md` §1 lists four artifacts per experiment and `CLAUDE.md` §4
   enumerates `procmine/`, so the sweep driver lives with its experiment rather than becoming
   a package module. It is committed, so the experiment is reproducible.
5. **`blocks.BROWSERS` was deleted** (ADR-013) and `app_switch` self-transition suppression
   was **not** implemented (ADR-014). Both recorded as ADRs.

## 8. Open questions / risks for the next phase

- **R1 (`ARCHITECTURE.md` §7) is still live.** Every number here is from B. A's window titles
  are reportedly more generic, so surface keys may carry less signal and the block-quality
  comparison in Phase 2 must be run before trusting any of this on A.
- **Re-measure ADR-013 on A.** The carry-forward is a no-op on B. If A's L2/L3 coverage
  differs it may become load-bearing — or it may be removable.
- **The 24 remaining bare `app:<X>` blocks** belong to applications that never report a window
  title anywhere (`OpenWith`, `Windows Explorer`, `prl_cc`). They are correctly distinct, but
  Phase 2 should decide whether they are business work or chrome.
- **1,323 reasoner windows × ~1.7k tokens ≈ 2.2M tokens for B alone.** Down 25%, still far
  too much. The ambiguity gate remains mandatory (Phase 2).
- `dataset_a/` is still not on disk. **Phase 1 cannot start.**

## 9. Repository state

Branch `phase-0-setup`, working tree clean. Commits:

```
[P0] Initialise repository: gitignore, pyproject, Makefile, env template
[P0] Fix block degeneracy at its source; add artifact validators and TEKG output
[P0] Add the Phase 0 test suite: 105 tests over 6 files
[P0] Record E01 ablation and sweep; ADR-012/013/014; phase report and work log
```

`git status` verified clean of datasets, build artifacts and secrets: `dataset_a/`,
`dataset_b/`, `build/`, `.env` and `.DS_Store` are all ignored, confirmed with
`git check-ignore -v`. No file over 1 MB is tracked except the pre-existing
`Claude outputs/` research PDF.

## 10. Recommendation

At the time of writing, Phase 1 was blocked on two things. **Both are now resolved:**

1. ~~`dataset_a/` is absent~~ — ingested and verified 2026-09-13; see
   `docs/DATASET_A_READINESS.md` (63 sessions, 162,768 events, 0 malformed lines).
2. ~~Acceptance criterion 1 is BLOCKED pending a Python ≥3.10 interpreter~~ — resolved; §12.

The perception layer itself is in good shape and I would not spend more time on it before
Phase 2 can compare it against A — further tuning on B alone would be fitting to one dataset.

## 11. Gate

Stopped at gate **G0**. Awaiting review. **Phase 1 not started.**

---

## 12. Addendum — Python environment blocker resolved (2026-09-13)

Acceptance criterion 1 was BLOCKED because macOS ships only Python 3.9.6 at
`/usr/bin/python3`, while `pyproject.toml` pins `requires-python >= 3.10`.

**Neither the pin nor any Phase 0 code was changed to accommodate 3.9.** The interpreter was
installed instead.

**Constraint:** no passwordless `sudo` on this machine, so the python.org `.pkg` installer and
Homebrew were both unavailable — each needs administrator rights. The sudo-free route is a
relocatable CPython build (`astral-sh/python-build-standalone`, the distribution `uv` itself
uses).

```
build      cpython-3.12.14+20260901-aarch64-apple-darwin-install_only.tar.gz
sha256     3ee3ee547cedfeb7c2b16b2b7156039f7b470bb8f857e226fd3d2eb11db83c76
           verified against the release's official SHA256SUMS before extraction
installed  ~/.local/share/cpython-3.12      (outside the repository)
on PATH    ~/.local/bin/python3.12 -> …     via ~/.zshrc and ~/.zprofile
```

`ssl` (OpenSSL 3.5.8), `sqlite3`, `lzma`, `zlib` and `ctypes` all import; pip 26.2.1 present.

### Verification

| Check | Result |
|---|---|
| `make setup` | **PASS** — `.venv` on 3.12.14; installed pandas 3.0.5, numpy 2.5.3, networkx 3.6.1, pytest 9.1.1, procmine 0.1.0 (editable) |
| `make test` | **PASS** — 104 passed, 1 skipped, 2.33 s |
| The one skip | `test_the_b_pipeline_does_not_need_dataset_a`, guarded `skipif(dataset_a present)`. It asserts the ADR-010 property that B needs no A; with A now on disk it cannot run. Expected, not a regression. |
| `make build-b` | **PASS** — 15 sessions, 20,477 events, 1,338 blocks, 152 one-event, 152 zero-duration, 0 empty-surface, 1,323 windows — **identical to the figures in §5**, so the interpreter change moved nothing |
| B byte-reproducibility | **PASS** — two runs diff clean on `blocks.jsonl`, all 15 `tekg/*.json`, all 1,323 `windows/**` |
| Dataset A intact | **PASS** — 34,923 files, 63 sessions, 34,563 images, 117 `events.jsonl`, 63 `gt.jsonl`; **0 files modified** since extraction; all five source archives preserved |
| Dataset A ingests on 3.12 | **PASS** — 63 sessions, 162,768 events, 4,968 blocks, 0 empty-surface: identical to the 3.9.6 readiness run |

### Reproducing on another machine

`make setup` now works unaided wherever a Python ≥3.10 is on `PATH`. Otherwise the Makefile
already accepts an explicit interpreter:

```bash
make setup BOOTSTRAP_PY=/path/to/python3.12
```
