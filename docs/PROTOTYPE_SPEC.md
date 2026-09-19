# Prototype Specification — Streamlit Application

## 1. What It Must Demonstrate

One continuous story, clickable end to end:

```
telemetry → reconstructed execution → graph/context → AI reasoning
         → process family → automation opportunity → generated SOP/workflow
```

The moment that sells it: **click any execution and see which relationships convinced the
system.** That is only possible because `evidence_used` is a required field from Phase 3.

Run: `streamlit run app/main.py` · Data: `build/<dataset>/` only. **The app never calls an LLM
at render time and never re-runs the pipeline.** Everything is precomputed.

## 2. Backend → UI Contract

| UI need | File | Spec |
|---|---|---|
| sessions, blocks | `build/<ds>/blocks.jsonl` | DATA_CONTRACT §1 |
| graph per session | `build/<ds>/tekg/<sid>.json` | DATA_CONTRACT §3 |
| executions + evidence | `build/<ds>/segments_rich.jsonl` | DATA_CONTRACT §6 |
| families + variants | `build/<ds>/families.json` | DATA_CONTRACT §7 |
| automation table | `build/<ds>/automation.json` | DATA_CONTRACT §8 |
| generated SOPs | `build/<ds>/sop/<label>.md` + `.workflow.json` | Phase 6 |
| A metrics (for the evidence page) | `experiments/*/metrics.json` | EXPERIMENT_PROTOCOL |

If a file is missing, the page renders an explicit "not yet generated — run phase N" message.
**No page may crash on missing data.**

## 3. Pages

### P1 · Overview
Dataset picker (A/B). Cards: sessions, events, blocks, executions, families, operators,
median execution duration. One `plotly.express.timeline` of all sessions, colour = family.
Text panel: what the pipeline did, with the compression numbers.

### P2 · Execution explorer
Left: filter by session / family / interrupted / confidence. Centre: `px.timeline` of one
session's executions; interrupted executions drawn as multiple bars sharing a label.
Select an execution → its block table (surface, duration, actions, fields).

### P3 · Temporal graph
The TEKG neighbourhood of the selected execution. Nodes = blocks positioned by time on x;
edges drawn as arcs, colour by relation type, legend naming all eight. Toggle per relation.
Implementation: Plotly scatter + line shapes. **No third-party graph component** (ADR-007).

### P4 · AI reasoning
For each transition inside the selected execution:
`gate route (rule|llm)` · `decision` · `confidence` · **`evidence_used` rendered as the actual
edges, highlighted in P3** · `rationale` · cache hit · latency. Plus a session-level counter:
how many transitions were decided by rule vs by the reasoner.

### P5 · Family & variant analysis
Per family: frequency, share of segmented time, operator count, application count, variant
breakdown (share, n, signature), typical step sequence. If `pm4py` step models exist, show the
DFG image. This page answers `README.md` Step 2 directly.

### P6 · Automation opportunity
The ranked table. **Three visually distinct column groups: MEASURED / DERIVED / ASSUMED**,
with class badges from `automation.json`. Assumptions listed explicitly beneath. A sensitivity
control (±20% weights) that re-ranks live from precomputed values and shows whether the top-3
is stable. **No monetary ROI figure anywhere.**

### P7 · SOP / workflow generation
The generated procedure for the selected family: numbered steps, screenshots where available,
`REQUIRES_HUMAN` markers highlighted, and the workflow-skeleton JSON in a code block with a
download button. A caption states the target system was not available and what that means.

## 4. Non-Goals

No authentication, no database, no live telemetry ingest, no editing, no background jobs,
no deployment. It runs locally for a demo.

## 5. Acceptance Criteria

- [ ] `streamlit run app/main.py` starts with no traceback on a fresh clone + `make build-b`
- [ ] All seven pages render for Dataset B
- [ ] Selecting an execution in P2 updates P3 and P4 consistently
- [ ] P4 shows real `evidence_used` values that correspond to edges visible in P3
- [ ] P6 shows no monetary figure and every column carries a class badge
- [ ] P7 offers a downloadable workflow JSON
- [ ] Every page degrades gracefully when its input file is absent


---

## Submission Integrity

This specification is a **deferred design**, not evidence that the Streamlit prototype has been implemented or validated.

Its intended implementation remains conditional on Step 1 reaching **S-DONE**. The specification therefore does not claim that the listed pages, backend artifacts, generated SOPs/workflows, or acceptance criteria have already been satisfied.

The original implementation boundaries are preserved: the application is a local, precomputed demonstration; it does not run the pipeline or call an LLM at render time, and missing backend artifacts must produce explicit, graceful status messages rather than page crashes.
