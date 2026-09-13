# PHASE 3 — AI execution reasoner experiment

**Objective** Determine, with evidence, whether contextual AI reasoning improves execution
reconstruction — and specifically whether **graph evidence** earns its place.
**Needs Dataset A: YES** · **Estimated time** 0.75 day · **Gate** G3 (the most important gate)

**Why it exists** This decides Phase 4's shape and the project's AI story. It must be a real
experiment with a real control, not a demo.

**Read first:** `docs/AI_REASONING_SPEC.md` (all), `docs/EXPERIMENT_PROTOCOL.md`,
`PHASE_2_REPORT.md`.

---

## Task 3.1 — `procmine/reasoner.py`
- [ ] `pydantic` models per `AI_REASONING_SPEC.md` §3; `instructor` for enum-constrained output
- [ ] Post-validation: invalid `resumes` → `None`; `RESUMPTION` without `resumes` → `UNCERTAIN`;
      unknown `evidence_used` entries dropped
- [ ] Content-hash cache (§7), **committed to git**
- [ ] `llm_calls.jsonl` logging (§9)
- [ ] Retry/backoff; persistent failure → `UNCERTAIN`, never an exception (§8)
- [ ] `--no-llm` mode tested

## Task 3.2 — Move the prompt to a versioned file
- [ ] `procmine/prompts/reasoner_system_v1.txt` from `context.SYSTEM_PROMPT`
- [ ] Verify it is domain-neutral: **no Dataset A process name may appear** (ADR-010)

## Task 3.3 — Experiment `E31-reasoner-3arm`  ← the core experiment
Three arms over the frozen 150-item stratified sample:

| Arm | Input | Isolates |
|---|---|---|
| `deterministic_rule` | gate rule only | the control |
| `llm_blocks_only` | blocks + gaps, **relations stripped** | value of the LLM alone |
| `llm_with_tekg` | blocks + gaps + relations | **value of the graph** |

The middle arm is what makes this an experiment rather than a demo: it separates "the LLM
helps" from "the TEKG helps".

- [ ] Run all three; write `samples.jsonl` per `EXPERIMENT_PROTOCOL.md` §3
- [ ] **Report per stratum**, not just overall (§5)
- [ ] Cost, cache hits, token counts, p50/p95 latency
- [ ] Stability: 3 runs at temperature 0, cache disabled → % identical decisions

## Task 3.4 — Decision criteria (fixed in advance — do not move the goalposts)
Keep the reasoner on the critical path only if **all** hold:
1. `llm_with_tekg` beats `deterministic_rule` on the **ambiguous + interruption + resumption**
   strata (overall average is not sufficient — it dilutes the effect)
2. No degradation on the `easy` stratum
3. ≥95% run-to-run stability at temperature 0
4. Full-dataset cost and wall-clock are acceptable and measured, not estimated
5. `llm_with_tekg` beats `llm_blocks_only` — otherwise keep the LLM and **drop the graph from
   the prompt** (it stays for explanation and Step 2 queries)

## Task 3.5 — Conditional: tools and vision
Only if Task 3.3 shows failures are **confidence-limited** rather than knowledge-limited:
- [ ] `expand_window`, `similar_executions`, `look_at_screen` per `AI_REASONING_SPEC.md` §11–12
- [ ] Fire only when `confidence < 0.6`; **max 2 calls per transition**
- [ ] Measure: does tool use change the decision in >20% of the cases where it fires?
      If not, remove the tool and record the finding.

---

## Commands
```bash
export ANTHROPIC_API_KEY=...
python3 -m procmine.reasoner --experiment E31-reasoner-3arm --arms all
python3 -m procmine.reasoner --experiment E31-reasoner-3arm --stability 3
```

## Acceptance criteria
1. `reasoner.py` implemented with cache, logging, retries, `--no-llm`
2. Prompt versioned and verified domain-neutral
3. All three arms run over the frozen sample
4. `experiments/E31-reasoner-3arm/{config,metrics,samples,report}` complete
5. **Per-stratum** results reported
6. Cost, latency and stability measured
7. Task 3.4 criteria evaluated explicitly, each PASS/FAIL
8. ≥3 concrete failure cases quoted with item ids
9. `PHASE_3_REPORT.md` written with a clear recommendation

## Failure conditions → STOP
- Any Task 3.4 criterion fails → **do not silently keep the LLM.** Report, recommend the
  deterministic path, write an ADR. This is a legitimate, valuable outcome.
- Stability <95% → investigate before proceeding; likely a prompt or schema problem

## Gate G3
Reviewer decides whether AI reasoning stays on the critical path. This determines Phase 4.
