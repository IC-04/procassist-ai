"""Artifact conformance checks (DATA_CONTRACT.md).

Light, dependency-free validators. Every artifact the CLI writes is checked before it
is considered written; an invalid artifact is a hard failure, never a warning, because
a malformed block file silently corrupts every downstream phase.

Each validator returns a list of human-readable problems. Empty list == valid.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Iterable, List

# ---------------------------------------------------------------- blocks

# DATA_CONTRACT.md §1
BLOCK_REQUIRED = (
    "block_id", "session_id", "idx", "surface", "app", "title", "route", "origin",
    "start_ms", "end_ms", "dur_ms", "start_iso", "end_iso", "n_events", "event_mix",
    "n_keystrokes", "n_clicks", "n_form_inputs", "n_nav", "n_clipboard",
    "field_keys", "element_ids", "element_labels", "value_hashes", "screenshots",
    "absorbed_excursions", "is_noise", "operator", "machine",
)

# DATA_CONTRACT.md §2 — the surface grammar:
#     web:<origin><route>  |  app:<app_name>:<title>  |  app:<app_name>
# Window titles legitimately contain spaces and punctuation ("Windows PowerShell",
# "... [Compatibility Mode]"), so only the prefix is constrained. What the grammar
# forbids is a timestamp or an index, which is checked separately.
SURFACE_RE = re.compile(r"^(?:web:https?://\S|app:)[^\n\t]*$")
SURFACE_FORBIDDEN_RE = re.compile(r"(?<![0-9A-Za-z])\d{13}(?![0-9A-Za-z])")


def validate_blocks(blocks: List[Dict]) -> List[str]:
    """Field presence plus the §1 invariants: ordering, density, containment."""
    problems: List[str] = []
    by_session: Dict[str, List[Dict]] = {}
    for b in blocks:
        missing = [k for k in BLOCK_REQUIRED if k not in b]
        if missing:
            problems.append(f"{b.get('block_id', '<no id>')}: missing fields {missing}")
            continue
        if b["end_ms"] < b["start_ms"]:
            problems.append(f"{b['block_id']}: end_ms < start_ms")
        if b["dur_ms"] != b["end_ms"] - b["start_ms"]:
            problems.append(f"{b['block_id']}: dur_ms inconsistent with start/end")
        if b["n_events"] < 1:
            problems.append(f"{b['block_id']}: n_events < 1")
        if not SURFACE_RE.match(b["surface"]):
            problems.append(f"{b['block_id']}: surface {b['surface']!r} violates the §2 grammar")
        elif SURFACE_FORBIDDEN_RE.search(b["surface"]):
            problems.append(f"{b['block_id']}: surface {b['surface']!r} embeds a timestamp")
        if not b["block_id"].startswith(f"{b['session_id']}#b"):
            problems.append(f"{b['block_id']}: block_id is not scoped to its session")
        by_session.setdefault(b["session_id"], []).append(b)

    for sid, bl in by_session.items():
        for i, b in enumerate(bl):
            if b["idx"] != i:
                problems.append(f"{sid}: idx not dense at position {i} (got {b['idx']})")
                break
        for a, b in zip(bl, bl[1:]):
            if b["start_ms"] < a["end_ms"]:
                problems.append(f"{sid}: blocks {a['idx']}/{b['idx']} overlap")
                break
    return problems


# ---------------------------------------------------------------- tekg

# TEKG_SPEC.md §2 — exactly eight, no other value is legal.
RELATIONS = frozenset({
    "temporal_next", "same_surface_as", "returns_to", "same_route_as",
    "same_system_as", "same_field_as", "shared_value_with", "dataflow_to",
})


def validate_tekg(doc: Dict, max_lag: int | None = None) -> List[str]:
    """Relation vocabulary, node/edge referential integrity, locality, ordering."""
    problems: List[str] = []
    for k in ("session_id", "nodes", "edges"):
        if k not in doc:
            problems.append(f"tekg: missing {k!r}")
    if problems:
        return problems

    nodes = set(doc["nodes"])
    sid = doc["session_id"]
    for n in doc["nodes"]:
        if not str(n).startswith(f"{sid}#b"):
            problems.append(f"tekg {sid}: node {n!r} does not belong to this session")
            break

    keys = []
    for e in doc["edges"]:
        if e.get("rel") not in RELATIONS:
            problems.append(f"tekg {sid}: illegal relation {e.get('rel')!r}")
            continue
        if e.get("src") not in nodes or e.get("dst") not in nodes:
            problems.append(f"tekg {sid}: edge references an unknown node: {e}")
            continue
        if max_lag is not None and e.get("lag") is not None and e["lag"] > max_lag:
            problems.append(f"tekg {sid}: lag {e['lag']} exceeds max_lag {max_lag}")
        keys.append((e["src"], e["rel"], e["dst"]))
    if keys != sorted(keys):
        problems.append(f"tekg {sid}: edges are not sorted by (src, rel, dst) — TEKG_SPEC §7")
    return problems


# ---------------------------------------------------------------- reasoner windows

# ADR-006 / DATA_CONTRACT.md §4 / TEKG_SPEC.md §6. The union of the two regexes the docs
# give: DATA_CONTRACT lists `idx`, TEKG_SPEC lists `\d{13}`. The stricter union is enforced.
#
# Two refinements over the literal text in the docs, both to remove false positives that
# would reject conforming payloads:
#   * the named identifiers are matched as whole words, so a label containing "index"
#     is not a violation;
#   * `\d{13}` is anchored to token boundaries, so it catches a standalone epoch
#     millisecond value but not 13 digits embedded in an opaque hash. `field_keys` and
#     `value_hashes` are hex digests the reasoner is *meant* to see
#     (AI_REASONING_SPEC.md §2) and one of them in dataset_b —
#     b6853646633736950071805f01503e95 — carries a 22-digit run.
FORBIDDEN_RE = re.compile(
    r"\b(?:ts_ms|start_ms|end_ms|idx|block_id)\b"
    r"|(?<![0-9A-Za-z])\d{13}(?![0-9A-Za-z])"
)


def _walk(node: Any, path: str = "") -> Iterable[tuple]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield ("key", str(k), path)
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    elif node is not None:
        yield ("value", str(node), path)


def validate_window_payload(payload: Dict) -> List[str]:
    """ADR-006 contract: the reasoner may never see an absolute time or a global index.

    Scans keys *and* values, recursively. A hit is a contract violation, not a warning:
    the guarantee that the model cannot emit a timestamp rests entirely on it never
    having received one.
    """
    problems: List[str] = []
    for kind, text, path in _walk(payload):
        if FORBIDDEN_RE.search(text):
            problems.append(f"window{path}: forbidden {kind} {text!r} (ADR-006)")
    return problems
