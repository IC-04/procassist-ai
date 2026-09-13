# PHASE 1 — Dataset A ingestion, GT canonicaliser, evaluation harness, baselines

**Objective** Turn Dataset A into a measuring instrument. End with a baseline scorecard.
**Needs Dataset A: YES — this phase is BLOCKED until `dataset_a/` is on disk.**
**Estimated time** 1.0 day · **Gate** G1

**Why it exists** Every number the project reports comes from this harness. Building it before
the first real segmenter is what stops us inventing a metric per experiment.

**Read first:** `docs/EVALUATION_PROTOCOL.md` (all), `docs/DATA_CONTRACT.md` §5–6,
`DATA_SCHEMA.md` §3–4.

---

## Task 1.1 — A ingestion on a sample
- [ ] Pick **5 sessions** by a fixed seed; record the ids in the report
- [ ] Run the Phase 0 pipeline over them; compare block statistics against Dataset B
- [ ] **This is risk R1's detector.** If A's `window_title` values are generic rather than
      semantic, block quality collapses — report it immediately and flag for Gate G1.

**Acceptance:** blocks built for 5 A sessions; A-vs-B comparison table in the report.

## Task 1.2 — `procmine/gt.py` — GT canonicaliser
Implement exactly `EVALUATION_PROTOCOL.md` §4 and `DATA_CONTRACT.md` §5.
- [ ] Parse `gt.jsonl` → `gt_events.jsonl` (verbatim, `ts_utc` preserved, no repairs)
- [ ] Parse `gt_manifest.json` → `executions.jsonl` with `repair_flags`, `confidence`,
      and **both** `manifest_value` and `stream_value` retained on disagreement
- [ ] Derive `executions_canonical.jsonl` grouping fragments by `case_id` + `split_id` into `intervals[]`
- [ ] Copy `expected_boundaries` verbatim to `expected_boundaries.json`
- [ ] **Repair rules committed before any segmenter exists** (ADR-011)

**Acceptance:** all four artifacts written and schema-valid for the 5-session sample.

## Task 1.3 — `docs/GT_DEFECT_REPORT.md`  ← a deliverable in its own right
Measure and write up:
- [ ] duplicate `process_started` rate
- [ ] unpaired `process_switched_out` rate
- [ ] manifest-vs-stream disagreement rate and magnitude
- [ ] fragments per canonical execution (the interruption rate — **the number that decides how
      central M2b is**)
- [ ] execution duration distribution; tasks per execution
- [ ] how many executions carry `continues_from_prev/next`

**Acceptance:** report written with real numbers. `DATA_SCHEMA.md` §3 only warns qualitatively;
this quantifies it and belongs in the final submission.

## Task 1.4 — Decide the alignment target
- [ ] Inspect `expected_boundaries`: what are its units and semantics?
- [ ] If it matches our boundary definition → it becomes the **primary** alignment target
- [ ] If not → align on `executions[].start_ts/end_ts` and **record why** in the report

**Acceptance:** an explicit, justified choice written down. Do not guess silently.

## Task 1.5 — `procmine/evaluate.py`
Implement every interface in `EVALUATION_PROTOCOL.md` §3, both coordinate domains (§2).
- [ ] Calibrate τ from A's observed execution durations — **do not hard-code ±2 s**
- [ ] `evaluate_all` returns the nested dict written verbatim to `metrics.json`
- [ ] Tier-1/2/3 reporting (§4)
- [ ] Unit tests with hand-built reference/hypothesis pairs where the answer is known by hand

**Acceptance:** `pytest tests/test_evaluate.py` green; τ and κ grids justified by the data.

## Task 1.6 — `procmine/baselines.py`
- [ ] `B0-single`, `B1-chunk`, `B2-gap`, `B3-random` (20 seeds, mean ± sd), `B4-surface`, `B5-dwell`
- [ ] Each emits `segments.jsonl`-shaped output so the harness scores them identically

**Acceptance:** all six score end to end and produce a scorecard.

## Task 1.7 — Baseline scorecard
- [ ] `experiments/E11-baselines/` per `EXPERIMENT_PROTOCOL.md`
- [ ] Table: baseline × {boundary F1@τ curve, segmental F1@IoU, WindowDiff, count ratio, ARI}

**Acceptance:** `README.md` FAQ says defining "good enough" is part of the task — this
scorecard is that definition, and it is a graded artifact.

---

## Commands
```bash
make build-a                       # after dataset_a/ is present
python3 -m procmine.gt --dataset dataset_a --sample 5
python3 -m procmine.baselines --dataset dataset_a
pytest tests/test_evaluate.py -v
```

## Acceptance criteria
1. 5 A sessions ingested; A-vs-B block comparison reported
2. Four GT artifacts written and schema-valid
3. `docs/GT_DEFECT_REPORT.md` with real defect rates
4. Alignment target chosen and justified
5. Harness implemented, both domains, tiered, unit-tested
6. Six baselines scored; scorecard written
7. `make test` green; `PHASE_1_REPORT.md` written

## Failure conditions → STOP
- `dataset_a/` absent → stop immediately, report the blocker, do nothing else
- GT cannot be canonicalised without a rule not in `EVALUATION_PROTOCOL.md` §4 → propose the
  rule, do not apply it
- A's blocks look nothing like B's (risk R1) → stop and escalate; this changes Phase 2 and 3

## Gate G1
Reviewer confirms the GT representation reflects the schema and baseline numbers are plausible.
