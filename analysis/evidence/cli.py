"""Step 2.5 evidence layer — one entry point.

reads only:  dataset_b/*/*/events.jsonl, build/dataset_b/{segments_rich,blocks}.jsonl
writes only: build/dataset_b/evidence/**

    python -m analysis.evidence.cli --pass 0 --dataset dataset_b
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, Sequence

from . import common as C
from . import documents as DOCS
from . import ledger as LEDGER
from . import outcomes as OUT
from . import pass0_text as P0
from . import records as REC

log = logging.getLogger("analysis.evidence")


def run_pass0(dataset: str, dataset_root: str) -> Dict[str, Any]:
    text = P0.run(dataset, dataset_root)
    caps = text["rows"]
    docs = DOCS.run(dataset, caps)
    led = LEDGER.run(dataset, docs["documents"])
    rec = REC.run(dataset, caps)
    out = OUT.run(dataset, caps, rec["rows"])

    artifacts = {
        "screen_text.jsonl": text["artifact"],
        "documents.jsonl": docs["artifact"],
        "document_ledger.jsonl": led["artifact"],
        "records.jsonl": rec["artifact"],
        "outcomes.jsonl": out["artifact"],
        "outcome_polarity.json": out["report_artifact"],
    }
    manifest = C.run_manifest(
        dataset, "pass0", artifacts,
        config={"source": "context.extracted_text", "ocr": "NOT USED — tesseract absent, and "
                                                           "ADR-007 rejects global OCR"},
        extra={"counts": {
            "captures": len(caps), "documents": len(docs["documents"]),
            "ledger_rows": len(led["rows"]), "records": len(rec["rows"]),
            "distinct_record_ids": len({r["record_id"] for r in rec["rows"]}),
            "outcomes": len(out["rows"]),
            "documents_with_multiple_titles": docs["n_multi_title"],
            "records_with_module_disagreement": rec["n_disagreements"]},
            "record_prefix_map": rec["prefix_map"],
            "outcome_finding": out["report"]["_finding"]})
    C.merge_manifest(dataset, "pass0", manifest)
    return {"artifacts": artifacts, "manifest": manifest,
            "captures": caps, "documents": docs["documents"], "records": rec["rows"],
            "outcomes": out["rows"], "ledger": led["rows"]}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="analysis.evidence.cli")
    ap.add_argument("--pass", dest="pass_id", required=True,
                    choices=["0", "1", "3"],
                    help="0 telemetry text harvest · 1 screenshot indexing · 3 hypotheses")
    ap.add_argument("--dataset", default="dataset_b")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING)

    dataset = os.path.basename(a.dataset.rstrip("/\\"))
    dataset_root = os.path.join(C.ROOT, dataset)
    if not os.path.isdir(dataset_root):
        print(f"{dataset_root} not present", file=sys.stderr)
        return 1

    if a.pass_id == "0":
        r = run_pass0(dataset, dataset_root)
        print(json.dumps({"pass": "0",
                          "artifacts": {k: {"n_rows": v.get("n_rows"),
                                            "sha256": v["sha256"][:12]}
                                        for k, v in r["artifacts"].items()},
                          "counts": r["manifest"]["counts"],
                          "outcome_finding": r["manifest"]["outcome_finding"]},
                         ensure_ascii=False, indent=1))
        return 0

    if a.pass_id == "1":
        from . import pass1_states as P1
        r = P1.run(dataset, dataset_root, dry_run=a.dry_run)
        print(json.dumps(r["summary"], ensure_ascii=False, indent=1))
        return 0

    if a.pass_id == "3":
        from . import hypotheses as H
        r = H.run(dataset, dataset_root)
        print(json.dumps(r["summary"], ensure_ascii=False, indent=1))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
