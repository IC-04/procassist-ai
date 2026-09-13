# CLAUDE.md — Operational entry point

You are implementing this repository. Read this file first, every session.

---

## 1. Objective

Reconstruct **business-process executions** from low-level desktop operation logs, analyse
the production dataset, rank automation opportunities, and demonstrate a working prototype.

This is a 7-day recruitment assignment for an **AI Engineer** role. The system must be
AI-native where intelligence is genuinely required, and deterministic everywhere else.

## 2. Source-of-truth hierarchy

Higher wins. Never contradict a higher level.

| Rank | Source | Status |
|---|---|---|
| 1 | `README.md` (repo root) | **The assignment. Never edit.** |
| 2 | `DATA_SCHEMA.md` (repo root) | **Authoritative schema. Never edit.** |
| 3 | `docs/ARCHITECTURE.md`, `docs/*_SPEC.md`, `docs/DATA_CONTRACT.md` | Design. Change only via an ADR in `docs/DECISIONS.md`. |
| 4 | `docs/phases/PHASE_N.md` | Your task list for the current phase. |
| 5 | `Claude outputs/*.md` | Background research. **Not authoritative. Do not implement from these.** |

If levels 1–2 conflict with 3–4, **STOP and report**. Do not silently resolve.

## 3. Architecture (fixed)

```
raw telemetry
   → deterministic perception      (normalise, dissolve chunks, surface keys)
   → activity blocks               (micro-excursion absorption)
   → TEKG                          (typed, locality-bounded evidence graph)
   → ambiguity gate                (deterministic; routes the uncertain tail only)
   → AI execution reasoner         (LLM, structured output, cites evidence)
   → constrained decoder           (global, deterministic, hard constraints)
   → executions                    → segments.jsonl
   → family / variant              (embeddings + clustering; LLM names only)
   → automation reasoning          (deterministic metrics; LLM rationale)
   → SOP / workflow generation     (LLM, grounded in step sequences)
   → Streamlit demo
```

Details: `docs/ARCHITECTURE.md`.

## 4. Repository layout

```
README.md  DATA_SCHEMA.md          assignment + schema (read-only)
CLAUDE.md                          this file
procmine/                          the package
  normalise.py blocks.py tekg.py context.py cli.py
  gt.py evaluate.py baselines.py gate.py reasoner.py decoder.py
  families.py automation.py sop.py memory.py
app/                               streamlit prototype
tests/                             pytest
docs/                              specs, plan, decisions, work log
  phases/PHASE_0..7.md             your task lists
  phases/PHASE_N_REPORT.md         your output per phase
build/<dataset>/                   generated artifacts (gitignored)
experiments/<exp_id>/              experiment records (committed)
dataset_a/ dataset_b/              data (gitignored, never committed)
```

## 5. Hard rules — never violate

- **DO NOT INVENT DATA.** If a field is missing, handle it; never fabricate a value.
- **DO NOT CHANGE THE ASSIGNMENT CONTRACT.** `README.md` and `DATA_SCHEMA.md` are read-only.
- **DO NOT USE CHUNKS AS BUSINESS BOUNDARIES.** Chunks are recording artifacts (SCHEMA §1).
  They are dissolved in `normalise.load_session` and must never appear as a predicted boundary.
- **DO NOT LET LLM OUTPUT CONTROL HARD TEMPORAL ARITHMETIC.** The model never sees or emits a
  timestamp, an absolute index, a duration or an interval. Enforced in `context.py`.
- **DO NOT BUILD UNNECESSARY INFRASTRUCTURE.** No graph DB, no vector DB, no agent framework,
  no fine-tuning, no global OCR. See `docs/DECISIONS.md` ADR-007.
- **DO NOT RESEARCH FOR HOURS** when an implementation decision can be tested in 20 minutes.
  Write the experiment, run it, record the result.
- **DO NOT PROCEED TO THE NEXT PHASE** until every acceptance criterion in the current
  `PHASE_N.md` passes. Partial passes are failures.
- **DO NOT COMMIT DATA OR SECRETS.** `dataset_a/`, `dataset_b/`, `build/`, `.env` are ignored.
- **DO NOT LEAK DATASET A INTO DATASET B.** No A process name, code, vocabulary, keyword list,
  cluster count or prompt example may reach the B pipeline. See `docs/DECISIONS.md` ADR-010.
  Mechanical test: `make run-b` must succeed with `dataset_a/` absent from disk.

## 6. Dataset rules

| | Dataset A | Dataset B |
|---|---|---|
| Role | build + validate the method | **the deliverable** |
| Ground truth | yes, and **imperfect** (SCHEMA §3) | none |
| Use | every number we report | `segments.jsonl` + Step 2 analysis |
| Scale-up | **sample ~5–6 sessions first**, expand only after the loader is stable | full |

Ground truth is evidence, not truth. Disagreements between `gt.jsonl` and `gt_manifest.json`
are **preserved and reported**, never silently resolved (`docs/EVALUATION_PROTOCOL.md` §4).

Fields documented in `DATA_SCHEMA.md` may be relied on. Everything under `extensions.*` and
`correlation.correlated_events` is **undocumented and optional** — code must run when absent.

## 7. Coding conventions

- Python 3.10+. Standard library + the approved dependency list (`docs/ARCHITECTURE.md` §6).
- Pure functions where practical; no hidden global state.
- Every module that reads telemetry uses the safe accessor `normalise._g` — never `d["k"]["j"]`.
- Type hints on public functions. Docstrings state the contract, not the implementation.
- No new third-party dependency without an ADR.
- Determinism: any function on the critical path must be reproducible given the same inputs.

## 8. Testing expectations

- `pytest` under `tests/`. Every module gets at least: one unit test of its core transform,
  and one "runs on real data without raising" smoke test against `dataset_b`.
- Tests must pass with `dataset_a/` absent.
- `make test` is green before any phase is declared complete.

## 9. Experiments

Every experiment produces `experiments/<exp_id>/` per `docs/EXPERIMENT_PROTOCOL.md`.
No experiment result is reported from memory or from console scrollback.

## 10. Git and work log

- Branch per phase: `phase-0-setup`, `phase-1-eval-harness`, …
- Commits: meaningful units of work, imperative subject, phase tag.
  `[P1] Add GT canonicaliser with repair flags`
- Do **not** create hundreds of trivial commits. Aim for 3–10 per phase.
- Append to `docs/WORK_LOG.md` after every work session. It is a graded deliverable
  (`README.md`, *Deliverables* §4) and must record failures and generative-AI use.

## 11. Phase workflow — follow exactly

1. Read `CLAUDE.md` (this file).
2. Read `docs/phases/PHASE_N.md` and every spec it references.
3. Inspect repository state and `git status`.
4. Read `docs/phases/PHASE_<N-1>_REPORT.md` if it exists.
5. Write a short implementation plan (in the report file, as a checklist).
6. Implement incrementally; run `make test` after each meaningful change.
7. Run the phase validation command.
8. **Inspect the artifacts, not just the exit code.** Open the JSON. Look at the numbers.
9. Fix failures. Re-run.
10. Update `docs/WORK_LOG.md`.
11. Write `docs/phases/PHASE_N_REPORT.md` (template: `docs/phases/REPORT_TEMPLATE.md`).
12. Mark the phase complete **only** when all acceptance criteria pass.
13. **STOP** at the human review gate. Do not start phase N+1.

## 12. Definition of done (per phase)

- [ ] All tasks in `PHASE_N.md` checked off
- [ ] All acceptance criteria pass, verified by inspecting artifacts
- [ ] `make test` green
- [ ] Artifacts exist at the documented paths and match `docs/DATA_CONTRACT.md`
- [ ] `docs/WORK_LOG.md` updated
- [ ] `PHASE_N_REPORT.md` written, including anything that failed
- [ ] Committed on the phase branch

## 13. When to STOP and report

Stop immediately, write what you know into the phase report, and wait:

- A required dataset is absent (e.g. `dataset_a/` for Phase 1).
- An acceptance criterion fails and two fix attempts have not resolved it.
- The data contradicts a spec (e.g. a documented field behaves differently than `DATA_SCHEMA.md` says).
- An implementation decision would change the architecture.
- A phase would exceed its estimated time by more than 50%.
- You are about to add a dependency, invent a schema field, or work around a hard rule.

Report format: what you attempted, what the evidence shows, the two or three options, and your
recommendation. Do not choose unilaterally.

## 14. Reporting completion

End every phase with a single message containing: phase number, acceptance criteria with
pass/fail, the key numbers produced, artifacts written, anything that failed, and the
review gate you have stopped at.
