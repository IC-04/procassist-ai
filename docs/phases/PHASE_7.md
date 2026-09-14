> **⏸ DEFERRED — Step 2 / Step 3 scope. Not in effect.**
> The current objective is Step 1 only (`docs/STEP1_SPEC.md`, ADR-016). Do not implement from
> this document until Step 1 exits at S-DONE. Retained because the design may be revived.

---

# PHASE 7 — Hardening, final evaluation, report and submission

**Objective** Turn a working repository into a submission. **Needs Dataset A: for final metrics**
**Estimated time** 1.0 day · **Gate** — final review

**Read first:** `README.md` Deliverables (all four), every `PHASE_N_REPORT.md`.

---

## Task 7.1 — Reproducibility
- [ ] `make all` runs the full pipeline on both datasets from a clean clone
- [ ] `make test` green; `--no-llm` path green
- [ ] Leakage check green (`dataset_a/` absent → `make run-b` succeeds)
- [ ] Pinned dependency versions; LLM cache committed so results replay without an API key

## Task 7.2 — Final evaluation pass
- [ ] Re-run the full A evaluation at the final configuration
- [ ] Tier-1/2/3 table; LOSO spread; ±20% perturbation; downstream ranking stability
- [ ] One consolidated `experiments/FINAL/metrics.json`

## Task 7.3 — Final report (`REPORT.md`)
`README.md` requires these, explicitly:
- [ ] Step 2 analysis of Dataset B and the **prioritised** automation candidates, with reasoning
- [ ] What was built in Step 3, **why that process and scope**
- [ ] **Why that implementation form, including why the alternatives were rejected**
- [ ] **What manual work remains after deployment**, and realistic expected impact
- [ ] **Anticipated implementation and rollout risks, with the evidence in the logs that led to
      anticipating each one** — use the measured findings: no idle gaps, 80% within-browser
      switching, clipboard content absent, free-text decision fields, GT defect rates
- [ ] How the 7 days were allocated, and why
- [ ] A limitations section: **no accuracy claim is made on Dataset B**, and why (ADR-010)

## Task 7.4 — Work log completion
- [ ] `docs/WORK_LOG.md` covers every working session
- [ ] Failed experiments written up — `README.md` grades this
- [ ] Generative-AI use summarised: what, where, how verified

## Task 7.5 — Git history review
- [ ] Phase branches merged with readable messages
- [ ] History shows progression, experiments and fixes — `README.md` says "we review how the
      work progressed"
- [ ] No data, no secrets, no large binaries committed

## Task 7.6 — Submission package
- [ ] `segments.jsonl` at repository root (Dataset B)
- [ ] Repository with full history
- [ ] `REPORT.md`
- [ ] `docs/WORK_LOG.md`
- [ ] `docs/DEMO_SCRIPT.md` and a working `streamlit run app/main.py`

---

## Project definition of done
- [ ] Reproducible pipeline, both datasets, `--no-llm` supported
- [ ] Dataset A evaluation with baselines and tiered GT reporting
- [ ] Dataset B segmentation shipped as valid `segments.jsonl`
- [ ] Family / variant / effort analysis answering all five Step 2 questions
- [ ] Automation candidate ranking with evidence classes and declared assumptions
- [ ] AI reasoning evidence visible and traceable
- [ ] Working prototype
- [ ] Generated SOP + workflow skeleton
- [ ] Tests green
- [ ] Limitations documented honestly
- [ ] ROI argument made comparatively, with no fabricated monetary figure
- [ ] Demo rehearsed

## Failure conditions → STOP
- Any `README.md` deliverable is missing
- A number in `REPORT.md` cannot be traced to an artifact
