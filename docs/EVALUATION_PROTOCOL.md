# EVALUATION_PROTOCOL

The harness is built **before** the first segmenter (Phase 1). Every later experiment reuses it.
Do not over-engineer it: one module, pure functions, no framework.

## 1. What is scored

`README.md` scores two independent things. They are never combined into one number.

| | Question | Metrics |
|---|---|---|
| **(a) Boundaries** | are the boundaries between units of work correct? | boundary F1 @ tolerance, segmental F1 @ IoU, WindowDiff, count ratio |
| **(b) Label consistency** | does the same process get the same label? | ARI / NMI on matched segments, plus match rate |

## 2. Two coordinate systems — compute both

The event rate is wildly non-uniform, so a fixed second-tolerance is not a fixed difficulty.

- **Time domain**: tolerance τ ∈ {1s, 2s, 5s, 10s}. Report the whole curve, never one τ.
- **Event-index domain**: tolerance κ ∈ {1, 2, 5, 10} events. Requires mapping every timestamp
  to its global event index within the session (`normalise` already assigns `seq`).

τ must be **calibrated against A's observed execution durations** (Phase 1, Task 1.5), not assumed.

## 3. Interfaces

```python
# procmine/evaluate.py
Interval = tuple[int, int]              # (start_ms, end_ms), inclusive-exclusive

def boundary_f1(ref: list[int], hyp: list[int], tol: int) -> dict
    # ref/hyp are boundary positions in ONE domain (ms or event index).
    # Greedy one-to-one matching within tol. -> {"precision","recall","f1","tp","fp","fn"}

def segmental_f1(ref: list[Interval], hyp: list[Interval], iou: float) -> dict
    # Interval matching above an IoU threshold. -> {"precision","recall","f1","matched"}

def count_ratio(ref: list, hyp: list) -> float          # len(hyp)/len(ref)

def windowdiff(ref_masses: list[int], hyp_masses: list[int], k: int|None) -> float
def pk(ref_masses: list[int], hyp_masses: list[int], k: int|None) -> float
    # Thin wrappers over `segeval`. Atomic unit = EVENT INDEX, not time bin.

def identity_scores(ref_labels: list, hyp_labels: list) -> dict   # ARI, NMI, homogeneity, completeness

def matched_identity(ref: list[Interval], ref_labels, hyp: list[Interval], hyp_labels,
                     iou: float = 0.5) -> dict
    # Match intervals at IoU, then ARI over matched pairs ONLY.
    # MUST return "match_rate" alongside. ARI without match_rate is meaningless.

def interruption_recall(canonical: list[dict], hyp: list[Interval], hyp_labels: list) -> dict
    # Of canonical executions with n_fragments > 1, what fraction had ALL fragments
    # assigned the same label? This is the only metric that measures M2b.

def task_agreement(gt_tasks: list, hyp_steps: list, tol: int) -> dict
    # Optional (Phase 5): boundary F1 of recovered steps against gt task_started.

def evaluate_all(ref_bundle, hyp_bundle, config) -> dict   # the one entry point
```

`evaluate_all` returns a nested dict written verbatim to `metrics.json`. It never prints
conclusions and never mutates its inputs.

## 4. Ground-truth tiers — report all three

Repairs are declared in `gt.py` **before** any segmenter runs (`DECISIONS.md` ADR-011).

| Tier | Contents | Used for |
|---|---|---|
| **clean** | executions with no `repair_flags` | **tuning** — never tune on repaired or disputed records |
| **clean + repaired** | plus deterministic repairs | **headline reporting** |
| **all** | plus `disputed` | sensitivity line |

Divergence between tier 1 and tier 3 is itself a finding and belongs in the final report.

### Repair policy (fixed)

| Class | Rule | Flag |
|---|---|---|
| untouched | `process_code`, `case_id`, `variant`, `ts_utc`, `task_id` | — |
| deterministic | dissolve `continues_from_prev/next` into one interval | `chunk_merge_applied` |
| deterministic | collapse consecutive duplicate `process_started` with same `(code, case_id)` and no intervening annotation (SCHEMA §3 names this defect) | `duplicate_start_collapsed` |
| disputed | `process_switched_out` with no matching open process | `unpaired_switch_out` |
| disputed | manifest vs stream interval disagreement beyond τ | `manifest_stream_disagreement` |
| disputed | `end_ts <= start_ts` | `zero_duration` |
| **never repaired** | overlapping executions of different families — this is the phenomenon under study | — |

Neither GT source dominates. The **stream** is authoritative for semantics (switch vs suspend,
`split_id`, `phase`, tasks). The **manifest** is authoritative for interval extents and is the
likely origin of `expected_boundaries`. Both values are retained on disagreement.

## 5. Scoring discontinuous executions

Compute and report all three conventions. State which is the headline.

1. **Fragment-level (headline).** Each reference fragment is a separate target interval.
2. **Canonical-level (lenient).** Union the fragments; credit a prediction covering the union.
3. **Stitch-aware (diagnostic).** Boundaries at fragment level **plus `interruption_recall`.**

Rationale: the external scorer's convention is unknown. Reporting under more than one
convention is honest and means our number cannot be dismissed as convention-shopping.

## 6. Baselines — implement in Phase 1, keep forever

| ID | Baseline | Why it exists |
|---|---|---|
| `B0-single` | one segment per session | absolute floor |
| `B1-chunk` | one segment per chunk | proves chunks are meaningless (SCHEMA §1) |
| `B2-gap` | top-k largest `ms_since_last_event` gaps, k = true count | the time-threshold method, kept as a **documented floor** |
| `B3-random` | random boundaries, count-matched, 20 seeds, mean ± sd | chance level |
| `B4-surface` | boundary at every context-state change | the over-segmentation ceiling |
| `B5-dwell` | blocks after excursion absorption | the deterministic candidate |

`README.md` FAQ says defining "good enough" is part of the task. **The baseline scorecard is
therefore a graded deliverable, not internal scaffolding.**

## 7. Stability and reporting discipline

- **Leave-one-session-out** across the A sample; report the spread, not just the mean.
- **Parameter perturbation**: ±20% on every threshold; report metric movement.
- **Downstream stability** (Phase 5): does the automation ranking survive perturbation?
- Any number quoted without its metric **and** its tolerance is invalid.
- Dataset B produces **no accuracy figures**. Only output, internal consistency, and stability.
