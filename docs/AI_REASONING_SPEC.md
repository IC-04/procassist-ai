# AI_REASONING_SPEC — Execution Reasoner

## 1. Job

Given a local TEKG window, decide the relationship of one block to the block before it.
Nothing else. It does not produce segments; the decoder does that.

## 2. Input payload

Produced by `context.build_payload`. Verbatim structure:

```jsonc
{
  "session": "ses_...",
  "question_about": "b5",
  "blocks": [ {"id":"b0","app":"Microsoft Excel","surface":"expense_calc",
               "route":null,"t_start_s":3.3,"dur_s":8.1,"events":36,
               "actions":{"keystroke":24,"shortcut":3},"typed":true,
               "form_inputs":null,"copied_or_pasted":null,
               "fields":["<hash>"],"ui_labels":["処理内容…"],"noise":null} ],
  "gaps":      [ {"between":["b2","b3"],"gap_s":0.0} ],
  "relations": [ {"a":"b2","rel":"returns_to","b":"b6","lag":4} ]
}
```

Size: ~1.7k tokens at `window=5` (measured on B). **This is why the ambiguity gate is
mandatory** — 1,767 windows × 1.7k ≈ 3M tokens for B alone if ungated.

## 3. Output schema — enforced, not requested

```python
class Decision(str, Enum):
    SAME_EXECUTION = "SAME_EXECUTION"
    INTERRUPTION   = "INTERRUPTION"
    RESUMPTION     = "RESUMPTION"
    PROCESS_SWITCH = "PROCESS_SWITCH"
    NEW_EXECUTION  = "NEW_EXECUTION"
    UNCERTAIN      = "UNCERTAIN"

class ReasonerOutput(BaseModel):
    decision: Decision
    confidence: float = Field(ge=0.0, le=1.0)
    resumes: str | None = None          # a block id from THIS window, or None
    evidence_used: list[str]            # relation names actually used
    rationale: str = Field(max_length=200)
```

Validated by `instructor`. Post-validation in `reasoner.py`:

- `resumes` must be a block id present in the payload and earlier than `question_about`;
  otherwise coerce to `None` and log `invalid_resumes`.
- Every `evidence_used` entry must be one of the eight relation names; unknown entries dropped.
- `decision == RESUMPTION` with `resumes is None` → downgrade to `UNCERTAIN`.

## 4. What the model must never do

It never sees, and therefore can never emit: a timestamp, a date, a duration in absolute
terms, a global index, a `block_id`, a count of anything outside its window, or a metric.
Enforced structurally in `context.py` (`TEKG_SPEC.md` §6), not by instruction.

## 5. System prompt

Canonical text lives in `procmine/prompts/reasoner_system_v1.txt` and is **versioned in git**.
Changing it bumps the version and invalidates the cache. The prompt must be
**domain-neutral**: it may describe relation semantics and decision criteria, but must contain
**no Dataset A process name, code or vocabulary** (`DECISIONS.md` ADR-010).

Current v1 content is in `procmine/context.py::SYSTEM_PROMPT` — move it to the prompts
directory in Phase 3, do not rewrite it from scratch.

## 6. Model configuration

```python
REASONER_CONFIG = {
  "model": "<pinned-model-id>",   # pinned; never "latest"
  "temperature": 0.0,
  "max_tokens": 400,
  "seed": 7,                      # where supported
  "prompt_version": "reasoner_system_v1",
  "schema_version": "ReasonerOutput/v1",
}
```

## 7. Caching — the reproducibility mechanism

Key: `sha256(prompt_version + schema_version + model + json.dumps(payload, sort_keys=True))`.
Store at `build/<dataset>/llm_cache/<key>.json` with request, response, latency, token counts.
**Committed to git** so the experiment is replayable without API access.

A cache hit is used unconditionally. `--no-cache` exists only for stability testing.

## 8. Retries and failure

- `instructor` handles schema-violation retries (max 2).
- Transient API error: exponential backoff, 3 attempts.
- Persistent failure: return `UNCERTAIN` with `confidence=0.0` and `rationale="llm_unavailable"`.
  **The pipeline must complete.** A dead API degrades quality, never correctness.
- `--no-llm` skips the reasoner entirely and the decoder uses the deterministic rule.
  This mode is tested in CI.

## 9. Cost and latency tracking

Every call appends to `build/<dataset>/llm_calls.jsonl`:
`{call_id, cache_hit, model, prompt_version, in_tokens, out_tokens, latency_ms, decision, confidence}`.
`experiments/<exp_id>/metrics.json` reports totals. Cost is a reported metric, not an afterthought.

## 10. Few-shot strategy

Phase 3 tests two arms: zero-shot, and **retrieved** few-shot (2–3 resolved similar windows
from `RETRIEVAL_SPEC.md`). Hand-written few-shot examples drawn from Dataset A are
**forbidden for the B pipeline** — that is leakage. Retrieved examples for B must come from B.

## 11. Agentic tools — minimal, capped

Implement **only if Phase 3 shows the zero-tool reasoner is confidence-limited** rather than
knowledge-limited. One reasoner, three tools, no framework, no orchestration library.

```python
expand_window(n: int) -> Payload          # n ∈ {8, 12}; more temporal context
similar_executions(k: int = 3) -> list    # from execution memory
look_at_screen(block_id: str) -> str      # selective vision, see §12
```

Rules: invoked **only** when first-pass `confidence < 0.6`; **maximum 2 tool calls per
transition**; every call logged with its effect on the final decision; if the budget is
exhausted the answer stands as-is. If tool use does not change the decision in >20% of the
cases where it fires, remove the tool and record the finding.

## 12. Vision — selective, never global

No OCR pass. No VLM sweep. Screenshots enter reasoning only via `look_at_screen`.

- **Location:** `blocks[].screenshots[0]` → `<chunk_dir>/screenshots/<filename>`.
  A missing file is "no capture available" (SCHEMA §2), **not an error**.
- **Ask:** "Describe the business purpose of this screen in one sentence. Name any visible
  record identifier, form title, or workflow step. Do not guess."
- **Output:** a string ≤200 chars, appended to the payload as `visual_evidence`.
- **Budget:** ≤5% of routed transitions per run, hard-capped; counter in `llm_calls.jsonl`.
- **Fallback:** on any failure, proceed without visual evidence.

Phase 3 measures whether vision changes the decision. If the answer is no, it is dropped.

## 13. The ambiguity gate (deterministic, `procmine/gate.py`)

The gate decides **what the reasoner is even asked**. It is not optional.

Score each transition `b_{i-1} → b_i` on:

| Signal | Direction |
|---|---|
| surface change class: none / route / system / app | none ⇒ confident SAME |
| `returns_to` edge spanning the transition | ⇒ ambiguous (possible interruption) |
| `same_field_as` across the transition | ⇒ evidence for SAME |
| gap relative to the session's rolling median gap | large ⇒ evidence for a boundary |
| block size (events, duration) | tiny blocks ⇒ ambiguous |
| `is_noise` on either side | ⇒ confident, route to rule |

Output per transition: `{"route": "rule" | "llm", "rule_decision": ..., "ambiguity": 0.0-1.0}`.
Target routing fraction: **10–20%**. If >40% routes to the LLM, the gate is too weak — fix
the gate before spending on calls. Report the routing histogram every run.
