# RETRIEVAL_SPEC — Execution Memory

# RETRIEVAL_SPEC — Execution memory

Lightweight case-based memory. **No vector database** (ADR-007): the corpus is hundreds of
items, so `sentence-transformers` + `sklearn.neighbors` is faster to build and to run.

## 1. What Is Stored

One record per reconstructed execution:

```jsonc
{
  "exec_uid": "...", "dataset": "dataset_b", "session_id": "...",
  "signature": ["web:/payroll-items", "app:Excel:expense_calc", "web:/payroll-items"],
  "surface_types": ["business_system", "spreadsheet", "business_system"],
  "apps": ["Microsoft Edge", "Microsoft Excel"],
  "field_keys": ["<hash>"], "n_blocks": 7, "dur_s": 62.0,
  "n_form_inputs": 2, "n_clipboard": 1, "interrupted": true,
  "text": "Edge payroll-items form entry; Excel expense_calc typing; return to payroll-items",
  "label": "payroll_item_processing" | null
}
```

`text` is a deterministic template rendering of the signature — **not** LLM-generated, so the
embedding is reproducible.

## 2. Similarity Model

Two channels, combined:

- **Structural**: `rapidfuzz` normalised similarity over the surface-key `signature` sequence.
- **Semantic**: cosine over `sentence-transformers` embeddings of `text`
  (`all-MiniLM-L6-v2`; small, CPU-fast, permissive licence).

`score = 0.6 * structural + 0.4 * semantic`. The weight is a parameter, reported, and included
in the ±20% perturbation sweep.

## 3. Retrieval API

```python
class ExecutionMemory:
    def add(self, records: list[dict]) -> None
    def query(self, record: dict, k: int = 3, exclude_session: str | None = None) -> list[tuple[dict, float]]
    def save(self, path) -> None
    def load(self, path) -> "ExecutionMemory"
```

`exclude_session` prevents trivially retrieving neighbours from the same session — required
when retrieved examples become few-shot context.

## 4. Intended Uses

1. **Few-shot context** for the reasoner (Phase 3, arm 3): retrieve *resolved* similar windows.
2. **Family assignment** (Phase 5): nearest-neighbour label transfer as an alternative to blind
   clustering; compared against clustering, not assumed better.

## 5. Leakage Prevention — Hard Rule

`ExecutionMemory` for Dataset B is built **only from Dataset B**. A's memory file is never
loaded in a B run. Enforced by: the memory file path is derived from the dataset name, and
`make run-b` is tested with `dataset_a/` absent (`CLAUDE.md` §5).

## 6. Choosing the Number of Families (Phase 5)

Do not default to silhouette. In priority order:

1. **Stability under resampling** — bootstrap subsamples, choose the `k` whose partition is
   most reproducible (ARI between runs).
2. **Minimum support** — a family must recur ≥3 times across ≥2 sessions to be called a process.
3. **Semantic coherence** — members share a surface/route signature a human would accept.
4. **Downstream stability** — does the choice change the automation ranking?
5. Silhouette only as a tiebreak.

Report the **oracle-k** experiment on A (k = true family count) separately from the
**unknown-k** experiment on B. Conflating them inflates the apparent result.
