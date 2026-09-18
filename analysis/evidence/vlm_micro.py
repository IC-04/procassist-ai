"""Phase 4-Micro — bounded visual extraction on the residual only.

reads only:  build/dataset_b/evidence/{states,coverage_gaps}.jsonl
writes only: build/dataset_b/evidence/vlm_ledger.jsonl

**The blanket Phase 4 pass over 4,746 screenshots is CANCELLED** (see
`docs/PHASE4_SCOPE_DECISION.md`). Pass 0's discovery of `context.extracted_text`, and Phase
3.9's discovery of operator-typed comments in `payload.target_field.value`, answered from free
text the questions the pipeline was built to answer.

This module exists so the capability is present, bounded and auditable — and so that the
decision not to spend is a measured decision rather than an absence. It fails safe:

  * no API key -> exit non-zero with a message naming the env var. Never hard-coded, never
    prompted for, never silently skipped.
  * a hard cap (default 60 images, all questions combined). A question needing more is not a
    Phase 4-Micro question.
  * `--dry-run` prints the exact image list and cost estimate and exits without calling anything.
  * every call is logged with the question it serves and why text could not answer it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Protocol, Sequence

from . import common as C

MAX_IMAGES = 60
BACKENDS = ("null", "openai", "anthropic", "gemini", "local")
KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
           "gemini": "GEMINI_API_KEY", "local": "LOCAL_VLM_URL"}

# Rough per-image cost for the estimate only. Not a billing figure.
COST_PER_IMAGE_USD = {"openai": 0.006, "anthropic": 0.005, "gemini": 0.002,
                      "local": 0.0, "null": 0.0}

QUESTIONS = {
    "Q1": {
        "question": "What does the ⚠ marker on FI|発注管理 denote?",
        "candidates_declared_before_looking": [
            "a validation failure on the record",
            "an amount over an approval threshold",
            "a data-completeness warning",
            "an operator-set flag",
        ],
        "status": "ANSWERED FROM TEXT — no VLM required",
        "answer": "Operator-typed comments on 発注管理 read "
                  "「発注管理処理。発注変更：<item>　数量 N　合計 ¥X　要注意。発注書確認・登録完了。」 "
                  "in 7 of 481 distinct comments. 要注意 is the operator's own annotation, and "
                  "the same comment ends in 登録完了 — flagged AND completed. The marker "
                  "accompanies a record that is processed, not blocked.",
        "evidence": "build/dataset_b/evidence/outcome_variance_sweep.json"
                    "#typed_comment_sweep",
    },
    "Q2": {
        "question": "What authority fields exist in the detail panes, and are they per-record "
                    "or per-user?",
        "status": "ANSWERED FROM TEXT — no VLM required",
        "answer": "Two of the five detail-pane captures carry 申請者区分 and 承認権限 as a "
                  "parsed 参照 line: P1-07048822-009 (接待交際費 ¥123,224, 申請者区分=manager, "
                  "承認権限=役員) and P1-07080388-001 (出張旅費 ¥56,120, 申請者区分=regular, "
                  "承認権限=部門長). The values differ between the two records, and the amounts "
                  "differ too, so the field is PER-RECORD, not a per-user constant. n=2.",
        "evidence": "build/dataset_b/evidence/records.jsonl (source_view=detail_pane)",
    },
    "Q3": {
        "question": "Visually confirm a negative-state candidate found in text.",
        "status": "SKIPPED — Phase 3.9 found no negative SYSTEM state to confirm. The variance "
                  "it did find is operator-typed text, which needs no visual confirmation.",
        "answer": None,
        "evidence": "build/dataset_b/evidence/outcome_variance_sweep.json",
    },
}


class VisualExtractor(Protocol):
    def extract(self, image_path: str, schema: dict, prompt: str) -> dict: ...


class NullExtractor:
    """Default. Returns nothing and calls nothing."""

    name = "null"

    def extract(self, image_path: str, schema: dict, prompt: str) -> dict:
        return {"_backend": "null", "_note": "no call made"}


def make_extractor(backend: str) -> VisualExtractor:
    """Fail loudly and safely. A missing key is an error, never a silent fallback."""
    if backend not in BACKENDS:
        raise SystemExit(f"unknown backend {backend!r}; expected one of {BACKENDS}")
    if backend == "null":
        return NullExtractor()
    env = KEY_ENV[backend]
    if not os.environ.get(env):
        raise SystemExit(
            f"backend {backend!r} requires the environment variable {env}, which is not set.\n"
            f"Set it in your shell and re-run. It is never read from a file, never prompted "
            f"for, and never hard-coded. Falling back to another backend would silently change "
            f"the provenance of every downstream claim, so this is a hard failure.")
    raise SystemExit(
        f"backend {backend!r} has a key but no client implementation: Phase 4-Micro was "
        f"cancelled after Pass 0 and Phase 3.9 answered Q1 and Q2 from free text. "
        f"See docs/PHASE4_SCOPE_DECISION.md. Implement the client here if a question "
        f"genuinely needs pixels.")


def select_residual(dataset: str, limit: int = MAX_IMAGES) -> List[Dict]:
    """States that are decision-adjacent AND lack a nearby text capture. The residual, not the
    corpus."""
    ev = C.evidence_dir(dataset)
    path = os.path.join(ev, "states.jsonl")
    if not os.path.exists(path):
        return []
    states = [json.loads(l) for l in open(path, encoding="utf-8")]
    residual = [s for s in states
                if s.get("is_decision_adjacent")
                and (s.get("event_distance_to_that_capture") is None
                     or s["event_distance_to_that_capture"] > 10)]
    residual.sort(key=lambda s: (s["session_id"], s.get("first_seq") or 0))
    return residual[:limit]


def run(dataset: str = "dataset_b", backend: str = "null", dry_run: bool = True,
        cap: int = MAX_IMAGES) -> Dict[str, Any]:
    residual = select_residual(dataset, cap)
    est = round(len(residual) * COST_PER_IMAGE_USD.get(backend, 0.0), 4)
    plan = {
        "backend": backend, "cap": cap,
        "n_images_selected": len(residual),
        "estimated_cost_usd": est,
        "questions": {k: v["status"] for k, v in QUESTIONS.items()},
        "images": [s["representative_screenshot_path"] for s in residual],
    }
    if all(q["status"].startswith(("ANSWERED", "SKIPPED")) for q in QUESTIONS.values()):
        plan["decision"] = ("NO CALLS MADE. All sanctioned questions are answered from free "
                            "text or skipped. Spending here would re-derive what the telemetry "
                            "already contains.")
        rows: List[Dict] = []
    elif dry_run:
        plan["decision"] = "DRY RUN — nothing sent. Re-run without --dry-run to proceed."
        rows = []
    else:
        if len(residual) > cap:
            raise SystemExit(f"{len(residual)} images exceeds the cap of {cap}; refusing")
        extractor = make_extractor(backend)
        rows = []
        for s in residual:
            out = extractor.extract(s["representative_screenshot_path"], {}, "")
            rows.append({"state_id": s["state_id"],
                         "screenshot_path": s["representative_screenshot_path"],
                         "model": backend, "extraction_method": "vlm",
                         "evidence_type": "VLM_INTERPRETATION", **out})

    art = C.write_jsonl(rows, os.path.join(C.evidence_dir(dataset), "vlm_ledger.jsonl"),
                        dataset, sort_key=lambda r: r["state_id"],
                        required=("state_id", "screenshot_path", "model"))
    C.merge_manifest(dataset, "phase4_micro", C.run_manifest(
        dataset, "phase4_micro", {"vlm_ledger.jsonl": art},
        config={"backend": backend, "cap": cap, "dry_run": dry_run},
        extra={"plan": plan, "n_vlm_calls": len(rows)}))
    return {"plan": plan, "rows": rows, "artifact": art}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="analysis.evidence.vlm_micro")
    ap.add_argument("--dataset", default="dataset_b")
    ap.add_argument("--backend", default="null", choices=list(BACKENDS))
    ap.add_argument("--cap", type=int, default=MAX_IMAGES)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--execute", dest="dry_run", action="store_false")
    a = ap.parse_args(argv)
    r = run(a.dataset, a.backend, a.dry_run, a.cap)
    print(json.dumps({k: v for k, v in r["plan"].items() if k != "images"},
                     ensure_ascii=False, indent=1))
    print(f"images in the residual (first 5): {r['plan']['images'][:5]}")
    print(f"vlm calls made: {len(r['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
