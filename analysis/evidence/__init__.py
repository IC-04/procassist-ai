"""Step 2.5 — evidence extraction layer.

Reads the raw Dataset B telemetry and the FROZEN Step 1 output. Writes only under
`build/dataset_b/evidence/`. Modifies nothing under `procmine/`, `build/dataset_b/*.jsonl`,
`dataset_b/`, `docs/STEP*.md` or `reports/`.

This layer produces EVIDENCE and hypothesis verdicts. It selects no automation candidate and is
not Step 3.
"""

CODE_VERSION = "step2_5-evidence-v1"
