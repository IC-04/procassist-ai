# PHASE 4 — Constrained decoder, full reconstruction, `segments.jsonl`

**Objective** Produce the contractual deliverable: `segments.jsonl` for Dataset B, with
Dataset A metrics to justify it. **Needs Dataset A: YES (for metrics)**
**Estimated time** 1.0 day · **Gate** G4

**Why it exists** Everything before this is preparation. `README.md` Deliverables §1 is
`segments.jsonl`. **Ship it early and imperfect rather than late and polished** (risk R5).

**Read first:** `docs/DATA_CONTRACT.md` §6, `docs/ARCHITECTURE.md` §5, `PHASE_3_REPORT.md`.

---

## Task 4.1 — `procmine/decoder.py`
Turn local decisions into a globally consistent segmentation.

- [ ] Input: blocks + per-transition decisions (gate rule and/or reasoner) with confidence
- [ ] Dynamic-programming / Viterbi-style pass over transitions maximising total confidence
      subject to the hard constraints below
- [ ] **Hard constraints (rejections, not penalties):**
  - monotone time; segments ordered and non-overlapping within a session
  - no zero-length segment
  - no segment below the duration floor observed in A's canonical executions
  - `RESUMPTION` must reference a genuinely open earlier execution; else demote to `NEW_EXECUTION`
  - a boundary may move at most `max_shift` blocks from its deterministic candidate
- [ ] `UNCERTAIN` and `confidence < threshold` fall back to the gate's `rule_decision`
- [ ] Emit both `segments.jsonl` (exactly 4 keys) and `segments_rich.jsonl`

**Acceptance:** decoder never emits output violating `DATA_CONTRACT.md` §6; asserted in tests.

## Task 4.2 — Interruption representation — decide and document
`segments.jsonl` cannot express one execution in two intervals (`DATA_CONTRACT.md` §5.3).
- [ ] Choose: **(a)** two lines sharing a label, or **(b)** one line spanning the interruption
- [ ] Score both on A under all three conventions (`EVALUATION_PROTOCOL.md` §5)
- [ ] Pick one, document the choice and the scores in the report and the final submission

## Task 4.3 — Label assignment (M4)
- [ ] Cluster executions on structural signature (`rapidfuzz` over surface-key sequence)
- [ ] Labels must be stable **across sessions** — this is half of what `README.md` scores
- [ ] Oracle-k on A (k = true family count) **and** unknown-k reported separately (`RETRIEVAL_SPEC.md` §6)

## Task 4.4 — Full A evaluation
- [ ] Expand from the 5-session sample to all available A sessions
- [ ] `experiments/E41-full-a/` with the complete metric suite, tiered
- [ ] Leave-one-session-out spread; ±20% parameter perturbation (`EVALUATION_PROTOCOL.md` §7)

## Task 4.5 — Dataset B run — the deliverable
- [ ] Re-estimate every threshold **from B's own distributions**; carry over only the rule (ADR-010)
- [ ] Select `k` on B by stability, not by A's value
- [ ] Emit `segments.jsonl` for B
- [ ] **Leakage check:** `make run-b` succeeds with `dataset_a/` renamed away. CI-enforced.
- [ ] Validator: exact session directory names, ISO-8601 `Z`, 4 keys, ordered, non-overlapping

**Acceptance:** a schema-valid `segments.jsonl` for Dataset B exists at the repository root
and passes the validator. **This is the submission.**

---

## Commands
```bash
python3 -m procmine.decoder --dataset dataset_a --full
python3 -m procmine.decoder --dataset dataset_b --emit segments.jsonl
python3 -m procmine.validate_segments segments.jsonl --dataset dataset_b
mv dataset_a /tmp/ && make run-b && mv /tmp/dataset_a .   # leakage check
```

## Acceptance criteria
1. Decoder implemented; all hard constraints enforced and tested
2. Interruption representation chosen, scored both ways, documented
3. Labels stable across sessions; oracle-k and unknown-k reported separately
4. `E41-full-a` complete with tiered metrics, LOSO spread and perturbation
5. `segments.jsonl` for B is schema-valid
6. Leakage check passes with `dataset_a/` absent
7. `make test` green; `PHASE_4_REPORT.md` written

## Failure conditions → STOP
- Decoder cannot satisfy constraints without dropping >10% of transitions
- Leakage check fails → find and remove the dependency before anything else

## Gate G4
Reviewer confirms `segments.jsonl` is valid and the A metrics are defensible.
