# IMPLEMENTATION_PLAN

**Revised 2026-09-13 (ADR-016).** The eight-phase plan is withdrawn. The current scope is
**Step 1 only**; task detail lives in `docs/STEP1_SPEC.md`, which is authoritative.

## What happened to the phases

| Old | Status |
|---|---|
| Phase 0 — setup, perception layer | **DONE.** Kept. Two surgical fixes remain (D-1, D-2). |
| Phase 1 — GT canonicaliser, evaluation harness, baselines | **DONE.** Kept, frozen. Figures to be restated on the corrected GT population (S-E1). |
| Phase 2 — blocks/TEKG on A, ambiguity gate | **SUPERSEDED** by `STEP1_SPEC.md` §3.2–3.4 and S-E1/S-E2/S-E3. |
| Phase 3 — AI reasoner 3-arm experiment | **SUPERSEDED** by `STEP1_SPEC.md` §3.5 and S-E5. |
| Phase 4 — decoder, reconstruction, `segments.jsonl` | **SUPERSEDED** by `STEP1_SPEC.md` §3.6–4 and S-E4. |
| Phase 5 — B analysis, families, automation | **DEFERRED** — Step 2. |
| Phase 6 — Streamlit prototype, SOP generation | **DEFERRED** — Step 3. |
| Phase 7 — hardening, report, submission | **DEFERRED** — after Step 1 and Step 2. |

Phases 2–7 files carry a banner and must not be implemented from.

## Step 1 order (summary — detail in `STEP1_SPEC.md` §7)

```
1  ship segments.jsonl for B from current blocks        ← the deliverable does not yet exist
2  fixes D-1, D-2 + regression tests
3  S-E1  GT metric correction
4  S-E2  miss attribution                                → is it (A) loss or (B) unsurfaced?
5  candidates.py + S-E3  candidate reachability          ★ HARD GATE
6  score.py, gate.py, decoder.py, label.py  (--no-llm end to end)
7  S-E4  end-to-end evaluation vs the six baselines
8  adjudicate.py + S-E5  LLM ablation                    → keep or remove, with an ADR
9  S-E6 same-process edge case; re-emit B; leakage check → S-DONE
```

## Gates

| Gate | After | Question the reviewer answers |
|---|---|---|
| **S-E3 gate** | step 5 | Does intra-block candidate generation actually lift reachability? High-80s or better → proceed. Below ~75% → **stop and investigate representation loss.** |
| **S-E5 gate** | step 8 | Does the bounded LLM adjudicator earn its place? If not, remove it and record the negative result. |
| **S-DONE** | step 9 | Is `segments.jsonl` valid, produced by frozen code validated on A, with defensible metrics? **Only then may Step 2 be designed.** |

## What changes the plan

- **S-E2 shows a large "information destroyed by preprocessing" fraction** → the perception layer
  is rebuilt before anything else, and S-E3 does not run yet.
- **S-E3 lands below ~75%** → stop. Do not compensate by adding intelligence on top of a
  candidate space that cannot express the answer.
- **S-E4 already beats `B5-dwell` comfortably** → consider shipping deterministic-only and
  spending the remaining budget on Steps 2–3; run S-E5 anyway, because the ablation number is
  itself a reportable result.
