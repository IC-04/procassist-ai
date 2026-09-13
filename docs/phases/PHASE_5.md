# PHASE 5 — Dataset B analysis: families, variants, effort, automation opportunities

**Objective** Answer `README.md` Step 2 and produce the ranked automation-candidate table.
**Needs Dataset A: NO** · **Estimated time** 1.0 day · **Gate** G5

**Why it exists** Step 1 is instrumental. `README.md` says the goal is ROI: *what processes
run, how often, how much time, how many people, what variants, and what should be automated
in what order, with reasoning.*

**Read first:** `docs/DATA_CONTRACT.md` §7–8, `docs/RETRIEVAL_SPEC.md` §6, `README.md` Step 2.

---

## Task 5.1 — Step structure (M6)
- [ ] Derive steps within each execution from surface transitions, `field_keys`, form submissions
      and navigation events
- [ ] Validate against Dataset A's `task_started` (`task_id`, `action`, `entity`) using
      `evaluate.task_agreement`
- [ ] **Gate for `pm4py`** (ADR-008): introduce it only if step recovery works. `case = execution`,
      `activity = step`. If step recovery fails, skip `pm4py` entirely and say so.

## Task 5.2 — Families and variants
- [ ] `procmine/families.py` — cluster executions; choose `k` by stability (`RETRIEVAL_SPEC.md` §6)
- [ ] Variants = sub-clusters within a family; report **counts and examples**, not accuracy
      (we cannot distinguish a business branch from operator habit — say so)
- [ ] Build `ExecutionMemory` for B **from B only**
- [ ] Emit `families.json` per `DATA_CONTRACT.md` §7

## Task 5.3 — LLM naming layer
- [ ] One call **per cluster**, not per segment — label drift is then structurally impossible
- [ ] Input: cluster signature, surfaces, representative step sequence, UI labels (Japanese)
- [ ] Output: short English name + one-paragraph description
- [ ] `name_source` and `name_model` recorded (`DATA_CONTRACT.md` §7)

**Note:** `README.md` states label *text* is not evaluated. This layer is zero-risk to the
score and high-value to the report. It is also where Japanese content is handled — no
tokeniser, no OCR.

## Task 5.4 — Operational analysis
Answer each Step 2 question with its evidence class (`DATA_CONTRACT.md` §8):
- [ ] which processes, how often — **derived**
- [ ] time consumed — **derived, ordinal only** (`README.md`: waiting time is compressed)
- [ ] how many people — **derived** from `source.username_hash`; state the one-account-one-person assumption
- [ ] variants — **derived**, low confidence
- [ ] application count and cross-application transitions — **measured**; report tab switches
      and true application switches **separately** (on B, ~80% of `app_switch` events are Edge→Edge)

## Task 5.5 — Automation opportunity scoring
- [ ] `procmine/automation.py` — deterministic metrics; every field carries `class`
- [ ] Include: frequency, effort share, repetition (mean pairwise sequence similarity),
      variability, application count, cross-app transitions, free-text field count
      (**human decision points** — e.g. a textarea whose label asks for a comment),
      determinism proxy, exception proxy (`browser_error`)
- [ ] Explicit gate: a threshold below which a candidate does not progress, with the threshold stated
- [ ] LLM writes the **rationale** only; it never produces a number
- [ ] **No monetary ROI field.** Any `assumed` field carries its assumption text.
- [ ] Sensitivity: ±20% on weights → is the top-3 ranking stable? Report it.

---

## Commands
```bash
python3 -m procmine.families --dataset dataset_b
python3 -m procmine.automation --dataset dataset_b
python3 -m procmine.sop --dataset dataset_b --list
```

## Acceptance criteria
1. Step structure derived; A-validated or explicitly reported as failed
2. `families.json` written; `k` chosen by stability with the selection curve reported
3. Families named; naming is per-cluster
4. All five Step 2 questions answered with evidence classes
5. `automation.json` written; every field classed; no monetary ROI anywhere
6. Ranking stability under ±20% perturbation reported
7. `PHASE_5_REPORT.md` written

## Failure conditions → STOP
- Step recovery fails **and** clustering is unstable → the analysis has no foundation; escalate
- Any automation claim cannot be traced to a measurement, a stated derivation or a declared assumption

## Gate G5
Reviewer confirms automation claims are supported and assumptions are declared.
