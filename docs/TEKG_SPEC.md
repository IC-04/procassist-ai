# TEKG_SPEC — Temporal Execution Knowledge Graph

## 1. Purpose, and what it is not

The TEKG does exactly two jobs:

1. **Build typed, local evidence** for the reasoner's context window.
2. **Explain** a decision afterwards, by naming the edges that drove it.

It is **NOT** an inference engine. **Connected components are NOT executions.** That
formulation was tested against the data and rejected (`DECISIONS.md` ADR-002): the explicit
link fields in the log are capture plumbing (`triggered_by` → 99.98% screenshot capture) and
layer de-duplication (`correlated_events` → `browser_click`↔`mouse_click`), not business
relationships. Any code that derives identity from connectivity is a contract violation.

## 2. Edge types — exactly eight

| Relation | From→To | Derived from | Evidence meaning |
|---|---|---|---|
| `temporal_next` | b_i → b_{i+1} | ordering | adjacency; carries `gap_ms` |
| `same_surface_as` | b_i → b_j, i<j | identical surface key | same screen revisited |
| `returns_to` | b_i → b_j, j>i+1 | same surface, non-adjacent | **the interruption signature** |
| `same_route_as` | b_i → b_j | identical `route` | same business function |
| `same_system_as` | b_i → b_j | identical `origin` | same backend system |
| `same_field_as` | b_i → b_j | shared `field_keys` | same form field touched |
| `shared_value_with` | b_i → b_j | shared `value_hashes` | same datum handled |
| `dataflow_to` | b_src → b_dst | `extensions.dataflow_v2.source_event_id` | explicit copy→paste lineage |

No other relation may be added without an ADR.

### Observed edge counts on `dataset_b` (Phase 0 reference)
```
same_surface_as 2150 · returns_to 2150 · same_field_as 940
same_system_as 235 · same_route_as 182 · shared_value_with 74 · dataflow_to 35
```
`returns_to` and `same_field_as` are ~60× more abundant than `dataflow_to`. Structural and
temporal relations are the evidence base; provenance is a weak complementary feature.

## 3. Node schema

| Node | Key | Attributes |
|---|---|---|
| `Block` (primary) | `block_id` | everything in `DATA_CONTRACT.md` §1 |
| `Surface` | surface key | `app`, `title`, `route`, `origin`, `is_noise` |
| `Field` | `stable_key` | first-seen label, count |
| `Session` | `session_id` | span, operator, machine |
| `Operator` | `source.username_hash` | session count |
| `Execution` | `exec_uid` | added in Phase 4, after reconstruction |

Storage is plain dicts + JSON (`DATA_CONTRACT.md` §3). `networkx` is imported only where an
algorithm is genuinely needed. **No graph database** (ADR-007).

## 4. Locality bound — mandatory

Every non-adjacent edge is bounded by `max_lag` blocks (default **12**). A relation between
blocks 200 apart is coincidence, not evidence. This is the hub control: without it, common
surfaces produce hubs that connect everything to everything.

Additionally: **edges never cross a session boundary.**

## 5. Edge attributes

`lag` (block distance) on all non-adjacent edges · `gap_ms` on `temporal_next` ·
`n` (cardinality of the shared set) on `same_field_as` / `shared_value_with` ·
`op` on `dataflow_to`.

`confidence` is deliberately **not** an edge attribute in v1: every edge is a deterministic
fact derived from a log field, so it is either present or not. Weighting belongs in the gate
and the decoder, not the graph.

## 6. Context builder — graph → LLM window

`context.local_evidence(graph, center_idx, blocks, window=5)` returns the ±`window` blocks and
**only the edges whose both endpoints are inside that window** — the prompt can never reference
a block the model cannot see.

`context.build_payload(ev, session_id)` then renders it under three hard rules:

1. timestamps → **relative seconds from window start**
2. global block ids → **local ids `b0…bN`**
3. `event_mix` strips `screenshot_smart` (capture noise, not user action)

Therefore the model cannot emit a timestamp or a global index: it has never seen one.

A test in `tests/test_context.py` asserts no payload contains a key or value matching
`ts_ms|start_ms|end_ms|block_id|\d{13}`.

## 7. Serialization

One file per session: `build/<dataset>/tekg/<session_id>.json` (`DATA_CONTRACT.md` §3).
Deterministic ordering: edges sorted by `(src, rel, dst)` so two runs diff cleanly.
