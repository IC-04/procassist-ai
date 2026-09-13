# EXPERIMENT_PROTOCOL

No experiment result is reported from memory, from console scrollback, or from a notebook cell.
Every experiment leaves a directory. These directories become the evidence base for the final
report (`README.md` Deliverables §3–4).

## 1. Layout

```
experiments/<exp_id>/
    config.json        exact configuration, including model + prompt version
    metrics.json       output of evaluate_all(), verbatim
    samples.jsonl      per-item records (see §3)
    report.md          the human-readable record (template below)
```

`exp_id` = `E<phase><n>-<slug>`, e.g. `E31-reasoner-3arm`. Immutable once written; a re-run
with changed configuration gets a new id.

## 2. `config.json`

```jsonc
{
  "exp_id": "E31-reasoner-3arm",
  "hypothesis": "Graph evidence improves reasoner accuracy on ambiguous transitions.",
  "dataset": "dataset_a",
  "sample": {"sessions": ["ses_...","..."], "n_transitions": 150,
             "strata": {"easy": 30, "ambiguous": 40, "interruption": 30,
                        "cross_app": 30, "resumption": 20},
             "seed": 7},
  "arms": ["deterministic_rule", "llm_blocks_only", "llm_with_tekg"],
  "model": "<pinned-id>", "temperature": 0.0,
  "prompt_version": "reasoner_system_v1",
  "params": {"window": 5, "max_lag": 12, "gate_threshold": 0.5},
  "git_sha": "<sha>", "started_at": "...", "finished_at": "..."
}
```

## 3. `samples.jsonl`

One line per item, so any result can be re-derived and any disagreement inspected:

```jsonc
{"item_id":"ses_...#t0042","stratum":"interruption",
 "gt":"INTERRUPTION","rule":"PROCESS_SWITCH",
 "llm_blocks":"INTERRUPTION","llm_tekg":"INTERRUPTION",
 "confidence":0.82,"evidence_used":["returns_to","same_field_as"],
 "rationale":"...","cache_hit":false,"latency_ms":940,
 "in_tokens":1743,"out_tokens":61}
```

## 4. `report.md` template

```markdown
# <exp_id> — <title>
**Date** · **Phase** · **Git SHA**

## Hypothesis
## Setup            (dataset, sample, strata, arms, model, prompt version)
## Results          (the table; per-stratum, not just overall)
## Cost & latency   (calls, cache hits, tokens, total cost, p50/p95 latency)
## Stability        (3 runs at temp 0: % identical decisions)
## Qualitative observations
## Failure cases    (>= 3 concrete items with ids, quoted from samples.jsonl)
## Conclusion
## Decision         (what changes in the codebase or plan; link to an ADR if architectural)
```

## 5. Reporting rules

- **Report per-stratum, always.** An overall average hides the effect the experiment exists to
  measure. If AI improves ambiguous/interruption/resumption cases materially, that is valuable
  even when overall F1 moves little.
- Every metric carries its tolerance and its domain (time vs event index).
- Negative results are written up in full. `README.md` grades the work log on failed attempts;
  a clean negative result is a deliverable, not a loss.
- Generative-AI use is recorded here and summarised in `WORK_LOG.md` (assignment requirement).
