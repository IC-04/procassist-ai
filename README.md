# ProcMine & ProcAssist — From Desktop Telemetry to Document-Grounded Automation

> **Inferring business-process executions from raw keystroke-level desktop logs, and building a human-in-the-loop AI assistant for back-office regulatory decisions.**

---

## Author

| | |
|---|---|
| **Name** | Indrani Chattopadhyay |
| **University** | Indian Institute of Technology (IIT) Bhubaneswar |
| **Department** | Mechanical Engineering |
| **Email** | indranichattopadhyay635@gmail.com |

---

## Project Overview

A Japanese company's desktop agent captures every keystroke, click, and application switch from back-office staff across HR, Finance, and Logistics. Nothing in the logs indicates *what* work is being done. Management's brief:

> *"Use these logs to tell us where automation would have the greatest impact on our operations. And show us something that actually works."*

This repository delivers a **four-layer system** built over a 7-day engagement (~55 hours):

| Step | Deliverable | Key Result |
|---|---|---|
| **Step 1** — Execution inference | `segments.jsonl` | Boundary **F1 0.690** (2.67× strongest baseline), identity **ARI 0.681**, no LLM on the critical path |
| **Step 2** — Business analysis | 12-module process inventory with automation candidates | Re-performed after a semantic-validation defect was found and corrected |
| **Step 2.5** — Hypothesis testing | 4-gate evidence framework | The strong automation hypothesis was **refuted** — zero negative outcomes in 225 dispositions |
| **Step 3** — ProcAssist | A running document-grounded preparation tool | Resolves regulations, localises clauses, drafts comments — **human decides** |

**449 tests passing, 2 skipped.**

---

## Architecture

```
Raw desktop telemetry (keystrokes · clicks · app switches · screenshots)
  → Normalisation           dissolve recording chunks, canonicalise surfaces
  → Activity blocks         contiguous interaction runs (containers, NOT boundary units)
  → Candidate generation    event-anchored + gap-anchored boundary candidates
  → Candidate scoring       deterministic scoring with structural features
  → Ambiguity gate          routes uncertain tail to adjudicator
  → Constrained decoder     global consistency under hard invariants
  → Process identity        similarity → kNN graph → Louvain community detection
  → Business analysis       modules · effort · operators · variants · dispositions
  → Hypothesis testing      4 declared gates · permutation nulls · pre-registered floors
  → ProcAssist              retrieve · localise · validate · draft · HUMAN DECIDES
```

### Key Design Principles

- **LLMs are bounded**: the model may produce types, relationships, and names — never timestamps, durations, or structural decisions
- **Deterministic safety net**: total LLM failure degrades the system to its deterministic baseline, never breaks it
- **No dataset leakage**: the production pipeline is tested with Dataset A absent from disk — a dependency on it fails the build

---

## Datasets

| Property | Dataset A | Dataset B |
|---|---|---|
| Role | Engineering & validation | **Production analysis target** |
| Sessions | 63 | 15 |
| Events | ~162,000 | ~20,000 |
| Screenshots | 34,563 | 4,746 |
| Ground truth | Yes | **None** |
| Departments | One set | **Different departments, processes, applications** |

All screen text, process names, and application UI are in **Japanese**. Translation tools and LLMs were used where needed.

---

## Quick Start

### Prerequisites

- Python ≥ 3.10

### Setup

```bash
make setup
```

Creates `.venv` with all dependencies. Use `.venv/bin/python` for everything.

### Produce the Step 1 deliverable

```bash
make run-b          # perception artifacts + segments.jsonl
```

Or directly:
```bash
python -m procmine.cli --dataset dataset_b --segment
```

### Run ProcAssist (Step 3)

```bash
.venv/bin/python -m procassist.api
```

Then open:
| Queue | URL | Demonstrates |
|---|---|---|
| HR 経費精算 | http://127.0.0.1:5132/payroll-items | OK / FLAG verdicts against 接待交際費規程 |
| FI 請求書承認 | http://127.0.0.1:5133/payroll-items | **MISS** — no regulation governs an invoice amount |
| FI 経費承認（管理職） | http://127.0.0.1:5133/leave-applications | **REQUIRES_REVIEW** — deciding variable absent |

### Run tests

```bash
make test
```

---

## Make Targets

| Target | Description |
|---|---|
| `make setup` | Create `.venv` and install `procmine` with dev extras |
| `make test` | Run the pytest suite |
| `make build-b` | Build perception + TEKG artifacts for Dataset B |
| `make run-b` | Full pipeline: perception → `segments.jsonl` |
| `make validate-segments` | Check `segments.jsonl` against the data contract |
| `make clean` | Remove `build/` and Python caches |

---

## Repository Structure

```
├── procmine/                  # Step 1: segmentation & identity pipeline
│   ├── normalise.py           #   telemetry normalisation
│   ├── blocks.py              #   activity block construction
│   ├── candidates.py          #   boundary candidate generation
│   ├── score.py               #   candidate scoring
│   ├── gate.py                #   ambiguity gate
│   ├── decoder.py             #   constrained global decoder
│   ├── identity.py            #   process identity (kNN + Louvain)
│   ├── label.py               #   consistent labelling
│   ├── evaluate.py            #   evaluation metrics
│   ├── cli.py                 #   command-line interface
│   └── ...
├── procassist/                # Step 3: ProcAssist automation tool
│   ├── core/                  #   pure logic: rules, lookup, engine, comments
│   ├── adapters/              #   I/O: documents, records, audit trail
│   ├── replica/               #   business-system screen replicas (Jinja2)
│   ├── panel/                 #   injected side panel (JS + CSS)
│   ├── api/                   #   FastAPI server
│   ├── challenger/            #   local retriever (BM25 + char-3-gram)
│   ├── i18n/                  #   JA→EN glossary
│   └── measured/              #   action budget from telemetry
├── analysis/                  # Step 2 inventory & figure scripts
├── definitions/               # process definition TOMLs (the artifact that executes)
├── experiments/               # numbered experiments (E01, SE1–SE8)
├── tests/                     # 28 test modules (449 tests)
├── docs/                      # all technical documentation & ADRs
├── figures/                   # generated analysis figures
├── reports/                   # Step 2 analysis report
├── segments.jsonl             # THE deliverable
├── pyproject.toml             # project metadata & dependencies
├── Makefile                   # build automation
└── FINAL_REPORT.md            # comprehensive submission report
```

---

## Documentation Reading Order

| # | Document | What it covers |
|---|---|---|
| 0 | `FINAL_REPORT.md` | **Start here.** The full engagement end-to-end |
| 1 | `docs/STEP1_REPORT.md` | Segmentation: boundary F1 0.690, identity ARI 0.681 |
| 2 | `docs/STEP2_AUTOMATION_OPPORTUNITY.md` | Module inventory and candidate analysis |
| 3 | `docs/STEP2_MODULE_KEY_RECONCILIATION.md` | Authoritative module keys (ADR-022) |
| 4 | `docs/STEP2_HYPOTHESIS_VERIFICATION.md` | **The strong hypothesis is refuted** — 4-gate table |
| 5 | `docs/PHASE4_SCOPE_DECISION.md` | Vision-model pass cancelled: 0 images, $0.00 |
| 6 | `docs/STEP3_TARGET_REFRAME.md` | Why a lookup table beats AI on current evidence |
| 7 | `procassist/README.md` | **ProcAssist** — how to run and what to click |
| 8 | `docs/GIT_HISTORY_NARRATIVE.md` | Commit history as an engineering narrative |
| 9 | `docs/WORK_LOG.md` | 7-day postmortem: hypotheses, experiments, 8 pivots |

ADRs (001–025) are in `docs/DECISIONS.md`, append-only. Evidence artifacts are under `build/dataset_b/evidence/`.

---

## Key Results

### Step 1 — Execution Inference

- **Boundary F1 0.690** at τ=2s (precision 0.680, recall 0.702)
- **2.67×** improvement over the strongest of six baselines
- Segment-count ratio of **0.98** — gains are not from over-segmenting
- Candidate reachability: **88.0%** against a measured ceiling of **90.0%**

### Step 1 — Process Identity

- **ARI 0.681 / NMI 0.738** via kNN similarity graph + Louvain community detection
- 17 discovered labels vs. 51 from structural signatures (ARI 0.431)
- LLM was sized three times and declined three times, each against a measured ceiling

### Step 3 — ProcAssist

- Resolves governing regulation → localises clause → evaluates record → drafts operator comment
- **Judgement slot left empty** — human completes and submits
- Agent mode: 23 documents, 120 drafts, **0 dispositions taken**
- Impact measured in **operator actions**, not time (compressed waiting times preclude absolute claims)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Inference | NumPy, SciPy, scikit-learn, NetworkX, RapidFuzz, segeval |
| Product | FastAPI, Pydantic v2, Jinja2, SQLite, vanilla JS |
| **Not used** | No vector database, no model API, no agent framework |

---

## License

This repository is a recruitment submission. All rights reserved.
