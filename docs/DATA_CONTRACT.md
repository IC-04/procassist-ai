# DATA_CONTRACT

Every artifact the pipeline produces. If code and this file disagree, fix one of them and
record why in `WORK_LOG.md`.

`DATA_SCHEMA.md` governs **input**. This file governs **everything we generate**.

## 0. Field trust levels

| Level | Fields | Rule |
|---|---|---|
| **Guaranteed** | everything in `DATA_SCHEMA.md` §2 (`timestamp_ms`, `event_type`, `layer`, `context.active_app`, `context.active_browser_tab`, `correlation.*` as listed, `payload.*`) | may be relied on; still check for `None` |
| **Documented-sparse** | `context.extracted_text` (~4%), screenshots (a chunk may have none) | must handle absence as normal, not as error |
| **Undocumented** | all `extensions.*`, `correlation.correlated_events` | **optional**. Code must produce a valid result when absent. Never a hard dependency. |
| **Unreliable** | `text_input_complete` | flagged `unreliable=True`; never a feature |

## 1. `build/<dataset>/blocks.jsonl` — activity blocks

One JSON object per line, ordered by `(session_id, idx)`.

```jsonc
{
  "block_id": "ses_...#b0042",   // stable, session-scoped
  "session_id": "ses_...",
  "idx": 42,                      // 0-based position within session
  "surface": "web:http://127.0.0.1:5132/payroll-items",  // see §2
  "app": "Microsoft Edge",
  "title": "HR人事給与システム",  // normalised, chrome stripped
  "route": "/payroll-items",
  "origin": "http://127.0.0.1:5132",
  "start_ms": 1782931321374, "end_ms": 1782931329501, "dur_ms": 8127,
  "start_iso": "...Z", "end_iso": "...Z",
  "n_events": 36,
  "event_mix": {"keystroke": 24, "shortcut": 3},
  "n_keystrokes": 24, "n_clicks": 6, "n_form_inputs": 1,
  "n_nav": 0, "n_clipboard": 1,
  "field_keys": ["<stable_key>"],       // extensions.field_identity_v1, may be []
  "element_ids": ["pi-note"], "element_labels": ["処理内容…"],
  "value_hashes": ["<hash>"],           // extensions.dataflow_v2, may be []
  "screenshots": ["scr_smart_...jpg"],  // may be []
  "absorbed_excursions": 2,
  "is_noise": false,
  "operator": "<username_hash>", "machine": "<machine_id>"
}
```

Invariants: `end_ms >= start_ms`; blocks within a session are contiguous and non-overlapping;
`idx` is dense from 0; no block spans two sessions.

## 2. Surface key grammar

```
web:<origin><route>          browser with a URL   e.g. web:http://127.0.0.1:5132/payroll-items
app:<app_name>:<title>       everything else      e.g. app:Microsoft Word:keiyaku_kaijo_tetsuzuki
app:<app_name>               no usable title
```
Deterministic, stable across runs. Never contains a timestamp or an index.

## 3. `build/<dataset>/tekg/<session_id>.json` — graph

```jsonc
{
  "session_id": "ses_...",
  "nodes": ["ses_...#b0000", "..."],
  "edges": [ {"src": "...#b0002", "rel": "returns_to", "dst": "...#b0006",
              "lag": 4, "gap_ms": null, "n": null} ]
}
```
Edge relations are exactly the eight in `TEKG_SPEC.md` §2. No other value is legal.

## 4. `build/<dataset>/windows/<session_id>/w<NNNN>.json` — reasoner payload

Produced by `context.build_payload`. **Contains no absolute timestamp and no global index.**
Schema in `AI_REASONING_SPEC.md` §2. Any payload containing a key matching
`ts_ms|start_ms|end_ms|idx|block_id` is a contract violation and must fail the test suite.

## 5. Ground truth (Dataset A only)

### 5.1 `build/dataset_a/gt_events.jsonl`
Flattened `gt.jsonl`, one record per annotation, `ts_utc` preserved verbatim, plus
`raw_line_no` and `source_file`. **No repairs applied at this level.**

### 5.2 `build/dataset_a/executions.jsonl`
```jsonc
{
  "exec_uid": "ses_...#A#RT-132457-001#1",
  "session_id": "ses_...", "process_code": "A", "family_name": "...",
  "domain": "hr", "case_id": "RT-132457-001", "variant": "std",
  "seq": 1, "phase": 1, "split_id": null,
  "start_ts": "...+00:00", "end_ts": "...+00:00", "apps": ["chrome","excel"],
  "continues_from_prev": false, "continues_to_next": false,
  "source": "manifest" | "stream" | "both",
  "repair_flags": ["chunk_merge_applied"],
  "confidence": "clean" | "repaired" | "disputed",
  "manifest_value": {...}, "stream_value": {...}   // both kept on disagreement
}
```

### 5.3 `build/dataset_a/executions_canonical.jsonl`
```jsonc
{
  "canonical_exec_id": "ses_...#A#RT-132457-001",
  "session_id": "...", "process_code": "A", "variant": "std",
  "intervals": [["...start","...end"], ["...start","...end"]],  // >1 ⇒ interrupted
  "n_fragments": 2, "total_duration_s": 91.4, "wall_span_s": 240.0,
  "confidence": "clean"
}
```
`intervals` is the representation `segments.jsonl` cannot express. It exists so the evaluator
can score discontinuous executions (`EVALUATION_PROTOCOL.md` §5).

### 5.4 `build/dataset_a/expected_boundaries.json`
Verbatim copy of `gt_manifest.json.expected_boundaries` per session, plus a note on whether
its semantics match our boundary definition. **Phase 1 must inspect this before choosing the
alignment target.**

## 6. `segments.jsonl` — THE DELIVERABLE

Exactly as `README.md` specifies. One JSON object per line, nothing more:

```json
{"session_id": "ses_20260701-183232-LAPTOP-76QMG9DE", "start": "2026-07-01T18:32:32Z", "end": "2026-07-01T18:35:41Z", "label": "expense_processing"}
```

Hard constraints, enforced by `procmine/decoder.py` and asserted in tests:

1. `session_id` is the **exact session directory name**.
2. `start`/`end` are ISO-8601 UTC ending in `Z`, second precision, `start < end`.
3. Exactly four keys. No extras.
4. Segments within a session are ordered by `start` and do not overlap.
5. No segment shorter than the duration floor observed in A's canonical executions.
6. `label` is stable: the same process gets the same string in every session.
7. No segment boundary coincides with a chunk boundary *because* of the chunk.

A separate `segments_rich.jsonl` (same rows plus `exec_uid`, `confidence`, `evidence`,
`fragments`) is written for the prototype. **It is never submitted.**

## 7. Family / variant

`build/<dataset>/families.json`
```jsonc
{"label": "payroll_item_processing", "n_executions": 47, "sessions": 11,
 "operators": 4, "median_dur_s": 62.0, "share_of_segmented_time": 0.21,
 "surfaces": ["web:.../payroll-items"], "variants": [
   {"variant_id": "v1", "share": 0.68, "n": 32, "signature": ["...","..."]}],
 "name_source": "llm" | "manual", "name_model": "<model-id>"}
```

## 8. Automation opportunity

`build/<dataset>/automation.json` — every field carries a class:
`"class": "measured" | "derived" | "assumed" | "unknown"`. A field with class `assumed`
must carry `"assumption"` text. No monetary ROI field may exist (`README.md` *Notes*:
waiting time is compressed; judge comparatively).

## 9. Experiments

`experiments/<exp_id>/{config.json,metrics.json,samples.jsonl,report.md}` —
see `EXPERIMENT_PROTOCOL.md`.

---

## 10. Step 1 additions (2026-09-13, ADR-015)

### 10.1 Blocks must expose their events

`blocks.jsonl` records gain two fields so a boundary can be placed **between two events inside a
block** (ADR-015):

```jsonc
"first_seq": 8107,   // global event index of the block's first row, from normalise's `seq`
"last_seq":  8142    // inclusive
```

Invariant: `first_seq <= last_seq`; `last_seq` of block `i` is `first_seq - 1` of block `i+1`
within a session. Consumers recover the rows deterministically from the same session load.
Nothing else about the block record changes.

### 10.2 `build/<dataset>/candidates.jsonl` — boundary candidates

One JSON object per line, ordered by `(session_id, at_seq)`.

```jsonc
{
  "cand_id": "ses_...#c00412",
  "session_id": "ses_...",
  "at_seq": 8123,                 // the boundary sits BEFORE this event index
  "at_ms": 1782931329501,
  "block_id": "ses_...#b0042",    // the enclosing block
  "kind": "block_edge" | "intra_block",
  "features": {"...": 0.0},       // deterministic, numeric or boolean only
  "score": 0.41,                  // added by score.py, [0,1]
  "top_features": ["browser_navigation_w2", "rel_gap"],
  "route": "rule" | "llm",        // added by gate.py
  "ambiguity": 0.37,
  "decision": true                // final boundary / no-boundary
}
```

Invariants: every block edge appears as a `block_edge` candidate (the old candidate space is a
strict subset); `at_seq` is strictly increasing within a session; no candidate is generated at a
chunk boundary *because* of the chunk (ADR-001); no field is derived from any GT artifact.

### 10.3 `segments_rich.jsonl`

The four `segments.jsonl` keys plus `exec_uid`, `confidence`, `evidence`, `fragments`,
`candidate_ids`. Internal only — **never submitted**.
