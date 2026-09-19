"""Where things live. The evidence directory is opened read-only and never written to."""
from __future__ import annotations

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
EVIDENCE = os.path.join(ROOT, "build", "dataset_b", "evidence")
RECORDS = os.path.join(EVIDENCE, "records.jsonl")
DOCUMENTS = os.path.join(EVIDENCE, "documents.jsonl")
DEFINITIONS = os.path.join(ROOT, "definitions")
OUT = os.path.join(ROOT, "build", "procassist")
AUDIT_DB = os.path.join(OUT, "audit.sqlite3")
AUDIT_JSONL = os.path.join(OUT, "audit.jsonl")
