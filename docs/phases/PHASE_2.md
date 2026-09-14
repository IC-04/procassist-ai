> **⛔ SUPERSEDED — do not implement from this document.**
> Replaced by `docs/STEP1_SPEC.md` (ADR-016). Retained for history only.

---

# PHASE 2 — Blocks and TEKG validated on A; the ambiguity gate

**Objective** Prove the representation holds on Dataset A, and build the gate that decides what
the reasoner is asked. **Needs Dataset A: YES** · **Estimated time** 0.75 day · **Gate** G2

**Why it exists** Everything measured so far is from Dataset B. The architecture assumes blocks
are semantically meaningful; A is a different domain and may not cooperate (risk R1). The gate
is what makes the LLM affordable (payloads are ~1.7k tokens).

**Read first:** `docs/TEKG_SPEC.md`, `docs/AI_REASONING_SPEC.md` §13, `PHASE_1_REPORT.md`.

---

## Task 2.1 — Experiment `E21-block-quality-a-vs-b`
- [ ] Full Phase 0 pipeline over the A sample
- [ ] Compare: events/block, blocks/session, distinct surfaces, % noise blocks, edge counts by type
- [ ] **Explicit R1 check:** what fraction of A blocks have a non-empty, non-generic `title`?

**Decision it drives**
- Blocks on A behave like B → proceed as planned
- Blocks on A are poor → add a `ruptures` change-point arm in Phase 3 and raise gate routing.
  **The AI layer becomes more important, not less.** Record as an ADR.

## Task 2.2 — Boundary evidence attribution
- [ ] For each *true* GT boundary in the sample, record which TEKG relations are present across it
- [ ] For a matched sample of non-boundaries, the same
- [ ] Produce a contingency table: relation × (boundary / not)

**This is the single most informative table in the project.** It tells us which relations carry
boundary signal *before* any model is trained or prompted, and it directly parameterises the gate.

## Task 2.3 — `procmine/gate.py`
Implement `AI_REASONING_SPEC.md` §13 using Task 2.2's evidence.
- [ ] Ambiguity score per transition from the six listed signals
- [ ] Deterministic `rule_decision` for confident transitions
- [ ] Routing output: `{"route","rule_decision","ambiguity"}` per transition
- [ ] Routing histogram written to `build/<ds>/gate_report.json`

**Target:** 10–20% routed to `llm`. **If >40%, the gate is too weak — fix it before spending
on calls.** Report the histogram every run.

## Task 2.4 — Deterministic-only reconstruction (baseline `B6-gate`)
- [ ] Apply gate `rule_decision` to every transition, including routed ones
- [ ] Score against GT with the Phase 1 harness

**This is the number the LLM must beat.** Without it, Phase 3 has no control.

## Task 2.5 — Stratified transition sample for Phase 3
- [ ] Build the 150-item stratified sample now (strata in `EXPERIMENT_PROTOCOL.md` §2)
- [ ] Freeze it as `experiments/E31-reasoner-3arm/sample.jsonl` with GT answers attached

---

## Commands
```bash
python3 -m procmine.cli --dataset dataset_a --sample 5
python3 -m procmine.gate --dataset dataset_a --report
python3 -m procmine.baselines --dataset dataset_a --only B6-gate
```

## Acceptance criteria
1. `E21` complete; A-vs-B comparison table; R1 answered yes/no with numbers
2. Boundary-evidence contingency table produced
3. Gate implemented; routing fraction within 10–20% (or the deviation explained)
4. `B6-gate` scored — the control for Phase 3 exists
5. Stratified 150-item sample frozen with GT answers
6. `make test` green; `PHASE_2_REPORT.md` written

## Failure conditions → STOP
- Routing fraction >40% after two attempts at strengthening the gate
- No relation shows boundary signal in Task 2.2 → the representation is wrong; escalate before
  spending anything on the LLM

## Gate G2
Reviewer confirms blocks/TEKG behave on A, and the routing fraction is sane.
