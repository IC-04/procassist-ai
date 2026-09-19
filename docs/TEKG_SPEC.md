# TEKG Specification — Temporal Execution Knowledge Graph

## 1. Purpose and Scope

The Temporal Execution Knowledge Graph (TEKG) has exactly two responsibilities:

1. **Build typed, local evidence** for the reasoner's context window.
2. **Explain decisions retrospectively** by identifying the graph edges that contributed to them.

TEKG is **not an inference engine**. In particular, **connected components must not be interpreted as executions**.

This formulation was tested against the data and rejected in `DECISIONS.md` (ADR-002). The explicit link fields in the log represent capture plumbing and layer de-duplication rather than business relationships:

- `triggered_by` → 99.98% associated with screenshot capture.
- `correlated_events` → de-duplication between `browser_click` and `mouse_click`.

Therefore, deriving execution identity from graph connectivity is a **contract violation**.

---

## 2. Edge Types

TEKG defines **exactly eight edge types**:

| Relation | From → To | Derived From | Evidence Meaning |
|---|---|---|---|
| `temporal_next` | `b_i → b_{i+1}` | ordering | Adjacent blocks; carries `gap_ms` |
| `same_surface_as` | `b_i → b_j`, `i < j` | identical surface key | Same screen revisited |
| `returns_to` | `b_i → b_j`, `j > i+1` | same surface, non-adjacent | **Interruption signature** |
| `same_route_as` | `b_i → b_j` | identical `route` | Same business function |
| `same_system_as` | `b_i → b_j` | identical `origin` | Same backend system |
| `same_field_as` | `b_i → b_j` | shared `field_keys` | Same form field touched |
| `shared_value_with` | `b_i → b_j` | shared `value_hashes` | Same datum handled |
| `dataflow_to` | `b_src → b_dst` | `extensions.dataflow_v2.source_event_id` | Explicit copy-to-paste lineage |

No additional relation may be introduced without an Architecture Decision Record (ADR).

### 2.1 Phase 0 Reference Counts

Observed edge counts on `dataset_b`:

```text
same_surface_as   2150
returns_to        2150
same_field_as      940
same_system_as     235
same_route_as      182
shared_value_with    74
dataflow_to          35
```

`returns_to` and `same_field_as` are approximately 60× more abundant than `dataflow_to`. Consequently, **structural and temporal relations form the primary evidence base**, while provenance is treated as a complementary feature.

---

## 3. Node Schema

| Node | Key | Attributes |
|---|---|---|
| `Block` (primary) | `block_id` | Everything defined in `DATA_CONTRACT.md` §1 |
| `Surface` | surface key | `app`, `title`, `route`, `origin`, `is_noise` |
| `Field` | `stable_key` | First-seen label, count |
| `Session` | `session_id` | Span, operator, machine |
| `Operator` | `source.username_hash` | Session count |
| `Execution` | `exec_uid` | Added in Phase 4, after reconstruction |

### 3.1 Storage

Storage uses plain dictionaries serialized as JSON, as specified in `DATA_CONTRACT.md` §3.

`networkx` is imported only where a graph algorithm is genuinely required.

**No graph database is used** (ADR-007).

---

## 4. Locality Bound

A locality bound is **mandatory**.

Every non-adjacent edge must be bounded by `max_lag` blocks, with a default value of **12**.

A relation between blocks that are 200 positions apart is treated as coincidence rather than evidence. This locality constraint prevents frequently occurring surfaces from becoming hubs that connect unrelated parts of the session.

Additionally:

> **Edges must never cross a session boundary.**

---

## 5. Edge Attributes

The following attributes are defined:

- `lag` — block distance on all non-adjacent edges.
- `gap_ms` — temporal gap on `temporal_next`.
- `n` — cardinality of the shared set on `same_field_as` and `shared_value_with`.
- `op` — operation associated with `dataflow_to`.

### 5.1 Confidence

`confidence` is deliberately **not** an edge attribute in v1.

Every edge represents a deterministic fact derived from a log field and is therefore either present or absent. Weighting is handled by the **gate** and **decoder**, rather than by the graph itself.

---

## 6. Context Builder: Graph → LLM Window

The context builder converts local graph evidence into the reasoner's LLM context.

### 6.1 Local Evidence

```text
context.local_evidence(graph, center_idx, blocks, window=5)
```

This function returns:

- the ±`window` blocks around the selected center;
- only those edges for which **both endpoints are inside the selected window**.

This ensures that the prompt cannot reference a block that is unavailable to the model.

### 6.2 Context Payload

```text
context.build_payload(ev, session_id)
```

The payload follows three mandatory rules:

1. **Timestamps** are converted to relative seconds from the beginning of the window.
2. **Global block IDs** are converted to local IDs (`b0 … bN`).
3. `event_mix` removes `screenshot_smart`, because screenshot capture is treated as capture noise rather than user action.

As a result, the model cannot emit a timestamp or global block index that it has not been shown.

### 6.3 Context Safety Test

The test in `tests/test_context.py` verifies that no payload contains a key or value matching:

```text
ts_ms|start_ms|end_ms|block_id|\d{13}
```

---

## 7. Serialization

TEKG is serialized as **one JSON file per session**:

```text
build/<dataset>/tekg/<session_id>.json
```

This follows the serialization convention specified in `DATA_CONTRACT.md` §3.

Edge ordering is deterministic:

```text
(src, rel, dst)
```

Deterministic ordering ensures that repeated executions produce clean, meaningful diffs.

---

## 8. Contract Summary

The following rules are mandatory for a conforming TEKG implementation:

1. TEKG builds local evidence and supports post-hoc explanation; it is not an inference engine.
2. Connected components must **not** be treated as executions.
3. Exactly eight edge types are permitted.
4. New relation types require an ADR.
5. Non-adjacent edges must respect `max_lag` (default: 12).
6. Edges must never cross session boundaries.
7. Edge confidence is not stored in the v1 graph.
8. The context builder must expose only locally visible evidence.
9. Global timestamps and block IDs must not be exposed in the LLM payload.
10. `screenshot_smart` must be removed from `event_mix`.
11. Serialization must be deterministic and session-scoped.
12. `Execution` nodes are introduced only in Phase 4, after reconstruction.
