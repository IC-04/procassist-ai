> **⏸ DEFERRED — Step 2 / Step 3 scope. Not in effect.**
> The current objective is Step 1 only (`docs/STEP1_SPEC.md`, ADR-016). Do not implement from
> this document until Step 1 exits at S-DONE. Retained because the design may be revived.

---

# PHASE 6 — Interactive AI-native prototype

**Objective** A runnable Streamlit application that demonstrates the whole chain, plus
generated SOPs and workflow skeletons. **Needs Dataset A: NO**
**Estimated time** 1.0 day · **Gate** G6

**Why it exists** `README.md` Step 3 requires something that actually runs. The target systems
(localhost SPAs) are **not available to us**, so the prototype must not depend on actuating
them — it demonstrates the intelligence of the reconstruction instead.

**Read first:** `docs/PROTOTYPE_SPEC.md` (all), `PHASE_5_REPORT.md`.

---

## Task 6.1 — `procmine/sop.py` — procedure and workflow generation
- [ ] Input: a family's executions, dominant variant step sequence, branch points, screenshots
- [ ] Output A: `build/<ds>/sop/<label>.md` — numbered steps, screenshots where available,
      **`REQUIRES_HUMAN` markers** at free-text/decision steps
- [ ] Output B: `build/<ds>/sop/<label>.workflow.json` — machine-readable skeleton:
      `{steps: [{id, action, surface, inputs, requires_human, notes}]}`
- [ ] **Deterministic fallback:** a template-filled SOP with no LLM, so the artifact exists in
      `--no-llm` mode. The LLM improves the prose; it does not create the structure.

The `REQUIRES_HUMAN` markers are the honest answer to `README.md`'s required
"what manual work remains after deployment" — it falls out of the artifact rather than being asserted.

## Task 6.2 — Streamlit app, pages P1–P7
Implement exactly `PROTOTYPE_SPEC.md` §3.
- [ ] `app/main.py` + `app/pages/` + `app/data.py` (cached loaders)
- [ ] P1 Overview · P2 Execution explorer · P3 Temporal graph · P4 AI reasoning/evidence
      P5 Family & variant · P6 Automation opportunity · P7 SOP/workflow
- [ ] Every page degrades gracefully when its input file is absent
- [ ] **No LLM calls at render time**; everything precomputed

## Task 6.3 — The demo path
- [ ] Write `docs/DEMO_SCRIPT.md`: the exact 5-minute click-through
- [ ] It must land the key moment: **select an execution → P4 shows the cited evidence →
      P3 highlights those exact edges**
- [ ] Rehearse it once end to end on a clean clone

## Task 6.4 — Rendering checks
- [ ] Screenshots resolve via `payload.file_reference`; a missing image renders a placeholder,
      never a traceback (SCHEMA §2 / ADR compliance)
- [ ] Japanese text renders correctly in Plotly and Streamlit
- [ ] Timeline is readable with the real number of executions per session

---

## Commands
```bash
python3 -m procmine.sop --dataset dataset_b --all
streamlit run app/main.py
```

## Acceptance criteria
1. SOP + workflow JSON generated for at least the top-ranked family
2. `--no-llm` still produces a (plainer) SOP
3. All seven pages render for Dataset B with no traceback on a fresh clone
4. P2 → P3 → P4 selection stays consistent
5. P4 shows real `evidence_used` values corresponding to edges visible in P3
6. P6 shows no monetary figure; every column carries a class badge
7. P7 offers a downloadable workflow JSON
8. `DEMO_SCRIPT.md` written and rehearsed once
9. `PHASE_6_REPORT.md` written

## Failure conditions → STOP
- The app cannot render without an LLM call at runtime
- The evidence shown in P4 does not correspond to edges in P3 → the explanation is not real

## Gate G6
Reviewer confirms the demo is coherent end to end.
