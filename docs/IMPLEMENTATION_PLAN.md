# IMPLEMENTATION_PLAN

Index of phases, gates and dependencies. Task detail lives in `phases/PHASE_N.md`.

## Phase map

| Phase | Objective | Needs A? | Ends with | Gate | Est. |
|---|---|---|---|---|---|
| **0** | Engineering setup; stabilise the perception layer | no | `make test` green; blocks rebuilt on B with improved quality | **G0** | 0.5 d |
| **1** | A ingestion, GT canonicaliser, evaluation harness, baselines | **yes** | baseline scorecard on A | **G1** | 1.0 d |
| **2** | Blocks + TEKG validated on A; ambiguity gate | **yes** | gate routing report; block quality A vs B | **G2** | 0.75 d |
| **3** | AI execution reasoner experiment (E1) | **yes** | 3-arm comparison with metrics, cost, stability | **G3** | 0.75 d |
| **4** | Constrained decoder; full reconstruction; `segments.jsonl` | **yes** | `segments.jsonl` for A **and** B | **G4** | 1.0 d |
| **5** | Dataset B analysis: family, variant, effort, automation | no | automation opportunity table | **G5** | 1.0 d |
| **6** | Streamlit prototype + SOP/workflow generation | no | runnable demo | **G6** | 1.0 d |
| **7** | Hardening, final evaluation, report, demo rehearsal | no | submission package | — | 1.0 d |

Total ≈ 7.0 days. Phases 5–6 are the ones to compress if earlier phases over-run; Phase 4's
`segments.jsonl` is the contractual deliverable and must not be sacrificed.

## Critical path

```
P0 ──► P1 ──► P2 ──► P3 ──► P4 ──► P5 ──► P6 ──► P7
        ▲
        └── BLOCKER: dataset_a/ must be on disk
```

`dataset_a/` is not present as of the start of Phase 0. **Phase 1 cannot start without it.**
Phase 0 is deliberately A-free so work can begin immediately.

## Human review gates

Claude Code **STOPS** at each gate and reports. It does not begin the next phase.

| Gate | After | Question the reviewer answers |
|---|---|---|
| **G0** | Phase 0 | Is the repo runnable, tested, and is block quality acceptable? |
| **G1** | Phase 1 | Does the GT representation reflect the schema? Are baseline numbers plausible? |
| **G2** | Phase 2 | Do blocks/TEKG behave on A as on B (risk R1)? Is the gate routing a sane fraction? |
| **G3** | Phase 3 | **Does AI reasoning earn its place on the critical path?** Decides Phase 4's shape. |
| **G4** | Phase 4 | Is `segments.jsonl` schema-valid and are the metrics defensible? |
| **G5** | Phase 5 | Are automation claims supported by measurements, with assumptions declared? |
| **G6** | Phase 6 | Is the demo coherent end to end? |

## Decision points that change the plan

- **G2 says A's blocks are poor (R1):** Phase 3 adds a `ruptures` arm; the gate routes more
  transitions to the reasoner. The AI layer becomes *more* central, not less.
- **G3 says the reasoner does not beat the rule (R3):** Phase 4 ships the deterministic
  decoder alone; the LLM moves to naming, SOP and automation rationale. Record as an ADR.
- **Phase 1 over-runs:** cut the A sample to 3 sessions and proceed; expand later.
