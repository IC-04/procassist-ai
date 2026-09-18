"""Shared provenance, hashing, atomic writes and the run manifest.

reads only:  nothing (helpers)
writes only: paths under build/<dataset>/evidence/, enforced by `guard_path`

Conventions follow docs/DATA_CONTRACT.md: one JSON object per line, ordered by a stated key,
with stated invariants; an artifact is validated before it is considered written, and an invalid
artifact is a hard failure rather than a warning.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import CODE_VERSION

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Provenance fields every emitted row must carry. Asserted by test.
PROVENANCE_FIELDS = ("extraction_method", "evidence_type")

EVIDENCE_TYPES = ("OBSERVED", "DERIVED", "VLM_INTERPRETATION", "INFERENCE")


class ArtifactInvalid(RuntimeError):
    """An artifact failed its contract check. Never downgraded to a warning."""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def evidence_dir(dataset: str) -> str:
    return os.path.join(ROOT, "build", os.path.basename(dataset.rstrip("/\\")), "evidence")


def guard_path(path: str, dataset: str) -> str:
    """Refuse to write anywhere but the evidence directory.

    The constraint is the point of this layer: Step 1 is frozen and Step 2 is written. A stray
    write into `build/dataset_b/*.jsonl` would corrupt an input that nothing downstream can
    re-derive, so the guard is enforced in code rather than trusted to discipline.
    """
    root = os.path.abspath(evidence_dir(dataset))
    target = os.path.abspath(path)
    if not (target == root or target.startswith(root + os.sep)):
        raise ArtifactInvalid(
            f"refusing to write outside the evidence directory: {target!r} is not under {root!r}")
    return target


def serialise_jsonl(rows: Sequence[Dict], sort_key=None, required: Sequence[str] = (),
                    name: str = "artifact") -> bytes:
    """Validate and serialise. Separated from the write so determinism can be asserted without
    writing anywhere — `guard_path` refuses paths outside the evidence directory, including a
    pytest tmp_path, and weakening it for a test would defeat its purpose.

    Deterministic: rows are sorted by the caller's key and each row's keys are emitted in
    insertion order, so two runs on the same input produce identical bytes.
    """
    if sort_key is not None:
        rows = sorted(rows, key=sort_key)
    out = bytearray()
    for i, r in enumerate(rows):
        missing = [k for k in tuple(required) + PROVENANCE_FIELDS if k not in r]
        if missing:
            raise ArtifactInvalid(f"{name} row {i}: missing {missing}")
        if r["evidence_type"] not in EVIDENCE_TYPES:
            raise ArtifactInvalid(
                f"{name} row {i}: evidence_type {r['evidence_type']!r} "
                f"is not one of {EVIDENCE_TYPES}")
        out += (json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n").encode("utf-8")
    return bytes(out)


def write_jsonl(rows: Sequence[Dict], path: str, dataset: str,
                sort_key=None, required: Sequence[str] = ()) -> Dict[str, Any]:
    """Validate, then write. An invalid artifact is a hard failure, never a warning."""
    path = guard_path(path, dataset)
    payload = serialise_jsonl(rows, sort_key, required, os.path.basename(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(payload)
    os.replace(tmp, path)
    return {"path": os.path.relpath(path, ROOT), "n_rows": len(rows),
            "sha256": sha256_bytes(payload)}


def write_json(obj: Any, path: str, dataset: str) -> Dict[str, Any]:
    path = guard_path(path, dataset)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, path)
    return {"path": os.path.relpath(path, ROOT), "sha256": sha256_file(path)}


def _version(mod: str) -> Optional[str]:
    try:
        import importlib.metadata as md
        return md.version({"PIL": "pillow"}.get(mod, mod))
    except Exception:                                          # noqa: BLE001
        return None


def git_sha() -> Optional[str]:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                           cwd=ROOT, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:                                          # noqa: BLE001
        return None


def run_manifest(dataset: str, pass_id: str, artifacts: Dict[str, Dict],
                 config: Optional[Dict] = None, extra: Optional[Dict] = None) -> Dict:
    """Provenance for one evidence pass, in the shape `build/<dataset>/run_manifest.json` uses.

    A run made under a different interpreter or a different code version must be visible HERE,
    not inferable only by hashing the outputs — the lesson of the S-E9 incident.
    """
    return {
        "_purpose": "provenance of one evidence pass. Which code, which interpreter, which "
                    "inputs, and the sha256 of every artifact written.",
        "dataset": os.path.basename(dataset.rstrip("/\\")),
        "pass_id": pass_id,
        "code_version": CODE_VERSION,
        "git_sha": git_sha(),
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "dependencies": {m: _version(m) for m in ("numpy", "PIL")},
        "config": config or {},
        "artifacts": artifacts,
        **(extra or {}),
    }


def merge_manifest(dataset: str, pass_id: str, manifest: Dict) -> str:
    """Manifests accumulate per pass in one file, so a later pass never erases an earlier one's
    provenance."""
    path = guard_path(os.path.join(evidence_dir(dataset), "run_manifest.json"), dataset)
    doc: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            doc = {}
    doc[pass_id] = manifest
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({k: doc[k] for k in sorted(doc)}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)
    return path
