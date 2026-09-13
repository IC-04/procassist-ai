# PHASE 0 — Engineering setup and perception stabilisation

**Objective** Leave the repository runnable, tested and reproducible, with the existing
perception layer measurably improved. **Needs Dataset A: NO** — start immediately.
**Estimated time** 0.5 day · **Gate** G0

**Why it exists** `procmine/{normalise,blocks,tekg,context,cli}.py` already exist and run on
`dataset_b`, but there is no test suite, no dependency pinning, no Makefile, and the block
builder has a measured defect. Every later phase builds on this layer, so it is stabilised first.

**Read first:** `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACT.md` §1–4, `docs/TEKG_SPEC.md`.

---

## Task 0.1 — Repository skeleton
- [ ] `git init` if needed; create branch `phase-0-setup`
- [ ] `.gitignore`: `dataset_a/`, `dataset_b/`, `build/`, `__pycache__/`, `.env`, `*.egg-info/`, `.venv/`
- [ ] `pyproject.toml` — package `procmine`, Python ≥3.10, deps **only**: `pandas`, `numpy`, `networkx`, `pytest`
      (later phases add their own; see `ARCHITECTURE.md` §6)
- [ ] `Makefile` with: `setup`, `test`, `build-b`, `build-a`, `run-b`, `clean`
- [ ] `.env.example` with `ANTHROPIC_API_KEY=` (no real key ever committed)

**Acceptance:** `make setup && make test` runs from a clean clone.

## Task 0.2 — Test suite v0
- [ ] `tests/test_normalise.py` — title normalisation, `route_of`, `origin_of`, `_g` safe access
      on missing/None paths; a malformed JSON line is skipped without raising
- [ ] `tests/test_blocks.py` — synthetic event list → expected blocks; micro-excursion
      `A|x|A → A` absorbed; empty input returns `[]`
- [ ] `tests/test_tekg.py` — edges never cross sessions; `max_lag` respected; relation set is
      exactly the eight in `TEKG_SPEC.md` §2
- [ ] `tests/test_context.py` — **contract test**: no payload contains a key or value matching
      `ts_ms|start_ms|end_ms|block_id|\d{13}` (ADR-006)
- [ ] `tests/test_smoke_b.py` — full build on `dataset_b` completes and `summary.json` validates

**Acceptance:** `make test` green; ≥5 test files; the ADR-006 contract test present and passing.

## Task 0.3 — Fix the block degenerate tail  ← the real work of this phase
Measured defect (see `WORK_LOG.md` 2026-09-12): many 1-event / 0-second blocks survive; 63
blocks have an empty surface key; median is 4 events/block.

- [ ] Absorb zero-duration blocks into their temporal neighbour
- [ ] Route empty-surface blocks (`app:` with no app name) into the previous block
- [ ] Make `min_events` / `min_ms` configurable; sweep `min_events ∈ {2,3,5,8}` × `min_ms ∈ {1000,1500,3000}`
- [ ] Choose a default and **record the sweep table** in the phase report

**Targets (Dataset B):** median events/block **≥ 8**; blocks/session **60–80**;
zero-duration blocks **0**; empty-surface blocks **0**.

**Acceptance:** targets met, before/after table in the report. If a target cannot be met
without collapsing genuine short work, report the trade-off rather than forcing the number.

## Task 0.4 — Artifact conformance
- [ ] `procmine/schemas.py` — light validators for `blocks.jsonl`, tekg JSON, window payloads
- [ ] `cli.py` validates every artifact it writes; invalid output is a hard failure
- [ ] Deterministic ordering everywhere (sort edges by `(src, rel, dst)`) so two runs diff clean

**Acceptance:** `make build-b` twice → byte-identical `blocks.jsonl` and tekg files.

## Task 0.5 — Dataset A readiness probe
- [ ] `make build-a` exits **0** with a clear "dataset_a not present — Phase 1 blocked" message
      when the directory is absent. It must not crash and must not fabricate anything.

---

## Commands
```bash
make setup
make test
make build-b
python3 -m procmine.cli --dataset dataset_b       # same as build-b
```

## Artifacts
`build/dataset_b/{blocks.jsonl,summary.json,tekg/*.json,windows/**}` ·
`docs/phases/PHASE_0_REPORT.md` · updated `docs/WORK_LOG.md`

## Acceptance criteria (all must PASS)
1. `make setup && make test` green from a clean clone
2. ≥5 test files including the ADR-006 contract test
3. Block quality targets met (or trade-off documented with numbers)
4. `make build-b` is byte-reproducible
5. `make build-a` degrades gracefully when A is absent
6. `PHASE_0_REPORT.md` written with the before/after sweep table
7. Committed on `phase-0-setup`

## Failure conditions → STOP
- Block quality targets unreachable without merging genuinely distinct work
- Two runs of `make build-b` differ

## Report
Sweep table, chosen defaults, before/after block statistics, test count, anything that failed.

## Gate G0
Reviewer confirms the repo is runnable and block quality is acceptable. **Do not start Phase 1.**
