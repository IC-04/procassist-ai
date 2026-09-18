# procmine — Step 1

`README.md` in this directory is the assignment brief and is read-only. This file is the
repository's own README: how to set it up, and how the deliverable is produced.

## Setup

```bash
make setup
```

Creates `.venv` with Python ≥ 3.10 and installs `procmine` with its dependencies. **Use
`.venv/bin/python` for everything.** `numpy`, `scipy`, `networkx`, `scikit-learn` and
`rapidfuzz` are hard requirements, not optional accelerators: the shipped identity method
(`docs/DECISIONS.md` ADR-021) is a graph method and cannot run without them. Running on an
interpreter that lacks them now raises rather than falling back — silently shipping a different
labelling is the defect that behaviour was introduced to prevent.

## Producing the deliverable

```bash
python -m procmine.cli --dataset dataset_b --segment
```

**This is the only command that writes `segments.jsonl`.** `make run-b` calls it (after
`make build-b`); `procmine/emit_segments.py` is the superseded Phase B safety net and writes to
`build/<dataset>/segments_provisional.jsonl` instead. Each run also writes
`build/<dataset>/run_manifest.json`, recording which identity method was used, the deliverable's
sha256, and the resolved dependency versions — so a run made in the wrong environment is visible
in an artifact rather than only by hashing the output.

## Other commands

| | |
|---|---|
| `make test` | the pytest suite |
| `make build-b` | perception + TEKG artifacts for `dataset_b` |
| `make run-b` | `build-b`, then the Step 1 chain → `segments.jsonl` |
| `make validate-segments` | check `segments.jsonl` against `docs/DATA_CONTRACT.md` §6 |

## Where to start reading

Read in this order. Each document states what the next one had to revise.

| # | Document | What it settles |
|---|---|---|
| 1 | `docs/STEP1_REPORT.md` | Step 1 — segmentation. Boundary F1 0.690, identity ARI 0.681, no LLM. **Frozen.** |
| 2 | `docs/STEP2_AUTOMATION_OPPORTUNITY.md` | Step 2 — the module inventory and candidate analysis. **Carries two supersession notices; read them.** |
| 3 | `docs/STEP2_MODULE_KEY_RECONCILIATION.md` | Which module key is authoritative, and why the inventory in (2) is key-dependent (ADR-022) |
| 4 | `docs/STEP2_HYPOTHESIS_VERIFICATION.md` | **The strong hypothesis is refuted.** The four-gate table, 44 verdicts, and what survives |
| 5 | `docs/PHASE4_SCOPE_DECISION.md` | Why the vision-model pass was cancelled: 0 images, $0.00 |
| 6 | `docs/STEP3_TARGET_REFRAME.md` | The revised target, and why **a lookup table beats AI** on current evidence |
| 7 | `docs/GIT_HISTORY_NARRATIVE.md` | The commit history as an engineering narrative, including every refuting commit |

`docs/DECISIONS.md` holds the ADRs (001–024), append-only. Evidence artifacts every claim cites
are under `build/dataset_b/evidence/` and are committed.

**Step 3 is not started.** The programme ends at a decision gate.
