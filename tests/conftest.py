"""Shared synthetic fixtures.

Tests are built on synthetic events, not on a dataset, so the suite passes with
`dataset_a/` **and** `dataset_b/` absent (CLAUDE.md §8, ADR-010). Only
`test_smoke_b.py` touches real data, and it skips itself when the data is not there.
"""
from __future__ import annotations
import os
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_A = os.path.join(REPO, "dataset_a")
DATASET_B = os.path.join(REPO, "dataset_b")

needs_b = pytest.mark.skipif(not os.path.isdir(DATASET_B),
                             reason="dataset_b/ not on disk")


def ev(ts: int, *, layer: str = "L2", et: str = "mouse_click", app: str = "App",
       title: str = "Doc", url: str = "", session: str = "ses_test",
       field: str = "", vhash: str = "", **extra) -> dict:
    """A raw event, shaped like DATA_SCHEMA.md §2, with only what a test needs."""
    e = {
        "event_id": f"evt_{ts}",
        "session_id": session,
        "timestamp_ms": ts,
        "timestamp_iso": "2026-07-01T00:00:00.000Z",
        "layer": layer,
        "event_type": et,
        "context": {
            "active_app": {"app_name": app, "process_name": f"{app}.exe",
                           "window_title": title},
            "active_browser_tab": {"url": url} if url else {},
        },
        "correlation": {"chunk_id": "chunk_x", "sequence_number": ts},
        "payload": {},
        "source": {"username_hash": "op1", "machine_id": "m1"},
        "extensions": {},
    }
    if field:
        e["extensions"]["field_identity_v1"] = {"stable_key": field}
    if vhash:
        e["extensions"]["dataflow_v2"] = {"normalized_value_hashes": [{"hash": vhash}]}
    for k, v in extra.items():
        e["payload"][k] = v
    return e


def flat(*events):
    """Raw events -> normalised rows, in the order given (no re-sorting)."""
    from procmine import normalise as N
    rows = [N.flatten_event(e) for e in events]
    rows = N.carry_forward_tab_state(rows)
    for i, r in enumerate(rows):
        r["seq"] = i
    return rows
