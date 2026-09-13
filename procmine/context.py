"""Stage D — reasoner context builder.

Renders a TEKG neighbourhood into the exact JSON the LLM reasoner sees.

HARD RULES (enforced here, not by the prompt):
  * the model never sees a raw timestamp -> only relative seconds
  * the model never sees an absolute index -> only local block ids b0..bN
  * the model can therefore never emit a time, an index, or an interval
"""
from __future__ import annotations
from typing import Dict, List


def _compact_block(b: Dict, t0: int, local_id: str) -> Dict:
    """~40 tokens of legible, decision-relevant summary."""
    mix = {k: v for k, v in b["event_mix"].items()
           if k not in ("screenshot_smart",)}          # capture noise
    return {
        "id": local_id,
        "app": b["app"],
        "surface": b["title"] or b["route"] or b["surface"],
        "route": b["route"] or None,
        "t_start_s": round((b["start_ms"] - t0) / 1000, 1),
        "dur_s": round(b["dur_ms"] / 1000, 1),
        "events": b["n_events"],
        "actions": {k: v for k, v in mix.items() if v},
        "typed": b["n_keystrokes"] > 0,
        "form_inputs": b["n_form_inputs"] or None,
        "copied_or_pasted": b["n_clipboard"] or None,
        "fields": b["field_keys"][:4] or None,
        "ui_labels": b["element_labels"][:3] or None,
        "noise": b["is_noise"] or None,
    }


def build_payload(ev: Dict, session_id: str) -> Dict:
    """TEKG local evidence -> reasoner payload (stable, deterministic)."""
    win: List[Dict] = ev["window"]
    if not win:
        return {}
    t0 = win[0]["start_ms"]
    idmap = {b["block_id"]: f"b{i}" for i, b in enumerate(win)}
    center_local = idmap[win[ev["center_idx"] - win[0]["idx"]]["block_id"]] \
        if 0 <= ev["center_idx"] - win[0]["idx"] < len(win) else idmap[win[0]["block_id"]]

    blocks = [_compact_block(b, t0, idmap[b["block_id"]]) for b in win]

    # gaps between consecutive blocks — the only temporal reasoning input
    gaps = [
        {"between": [idmap[a["block_id"]], idmap[b["block_id"]]],
         "gap_s": round(max(0, b["start_ms"] - a["end_ms"]) / 1000, 1)}
        for a, b in zip(win, win[1:])
    ]

    evidence = [
        {"a": idmap[e["src"]], "rel": e["rel"], "b": idmap[e["dst"]],
         **{k: v for k, v in e.items() if k not in ("src", "rel", "dst")}}
        for e in ev["evidence"] if e["src"] in idmap and e["dst"] in idmap
    ]

    return {
        "session": session_id,
        "question_about": center_local,
        "blocks": blocks,
        "gaps": gaps,
        "relations": evidence,
    }


# ------------------------------------------------------------------ prompt

SYSTEM_PROMPT = """\
You analyse desktop telemetry from back-office work. You are given a short \
window of ACTIVITY BLOCKS (contiguous runs of work on one screen/surface), \
the time gaps between them, and typed RELATIONS derived from the log.

Decide the relationship of the block named in `question_about` to the block \
immediately before it.

Labels:
  SAME_EXECUTION   - continues the same unit of business work
  INTERRUPTION     - a brief detour (lookup/reference); the prior work resumes after
  RESUMPTION       - resumes a unit of work that was suspended earlier in this window
  PROCESS_SWITCH   - the worker moved to a different business process
  NEW_EXECUTION    - a new instance of the SAME process (e.g. the next case)
  UNCERTAIN        - the evidence does not support a confident choice

Guidance:
  - `returns_to` / `same_surface_as` after a detour is strong evidence for INTERRUPTION.
  - `shared_value_with` or `dataflow_to` across blocks is evidence for SAME_EXECUTION.
  - The SAME route repeated after a clean finish (form submit, navigation away and back)
    is usually NEW_EXECUTION, not SAME_EXECUTION.
  - A different business system with no shared fields or values is usually PROCESS_SWITCH.
  - Blocks marked `noise` are browser/OS chrome and are never business work.
  - Prefer UNCERTAIN over guessing. A wrong confident answer is worse than an abstention.

Never output times, dates, indices or durations. Refer only to block ids (b0, b1, ...).
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": [
            "SAME_EXECUTION", "INTERRUPTION", "RESUMPTION",
            "PROCESS_SWITCH", "NEW_EXECUTION", "UNCERTAIN"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "resumes": {"type": ["string", "null"],
                     "description": "block id this resumes, or null"},
        "evidence_used": {"type": "array", "items": {"type": "string"},
                           "description": "relation names that drove the decision"},
        "rationale": {"type": "string", "maxLength": 200},
    },
    "required": ["decision", "confidence", "evidence_used", "rationale"],
    "additionalProperties": False,
}
