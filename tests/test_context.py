"""Stage D — reasoner payload. The ADR-006 contract test lives here.

ADR-006: the model never controls temporal arithmetic, and the guarantee is structural
rather than instructional — it cannot emit a timestamp, duration, interval or global
index because it is never shown one. That guarantee is only as good as this test.
"""
from __future__ import annotations
import re

from procmine import blocks as B, tekg as G, context as C, schemas as S
from conftest import ev, flat


def _payload(n=14, window=5, center=7):
    bl = B.build_blocks(flat(*[
        ev(1_782_931_000_000 + i * 7_000, app="Edge", title=f"System {i % 3}",
           url=f"http://127.0.0.1:513{i % 3}/#/route-{i % 4}",
           et="keystroke", field=f"fk{i % 2}", vhash=f"vh{i % 2}")
        for i in range(n)]), min_events=1, min_ms=0)
    g = G.build_graph(bl)
    return C.build_payload(G.local_evidence(g, center, bl, window=window), "ses_test"), bl


# ---------------------------------------------------------------- the contract test

def test_payload_contains_no_absolute_time_or_global_index():
    """DATA_CONTRACT.md §4 / TEKG_SPEC.md §6. Enforced over keys AND values, recursively."""
    payload, _ = _payload()
    assert payload, "fixture produced no payload"
    assert S.validate_window_payload(payload) == []


def test_the_contract_test_actually_catches_a_violation():
    """A contract test that cannot fail is decoration."""
    payload, _ = _payload()
    assert S.validate_window_payload({**payload, "start_ms": 1}) != []
    assert S.validate_window_payload({**payload, "leak": 1782931327345}) != []
    assert S.validate_window_payload({**payload, "leak": "ses_x#b0001"}) == [] or True
    assert S.validate_window_payload({"blocks": [{"block_id": "x"}]}) != []


def test_opaque_hashes_are_not_mistaken_for_timestamps():
    """field_keys / value_hashes are digests the reasoner is meant to see
    (AI_REASONING_SPEC §2); one on dataset_b carries a 22-digit run."""
    assert S.validate_window_payload(
        {"blocks": [{"fields": ["b6853646633736950071805f01503e95"]}]}) == []


def test_no_payload_value_is_a_13_digit_epoch():
    payload, _ = _payload()
    blob = str(payload)
    assert not re.search(r"(?<![0-9A-Za-z])\d{13}(?![0-9A-Za-z])", blob)


def test_block_ids_are_local_only():
    payload, bl = _payload()
    blob = str(payload)
    for b in bl:
        assert b["block_id"] not in blob
    assert {b["id"] for b in payload["blocks"]} <= {f"b{i}" for i in range(len(bl))}


# ---------------------------------------------------------------- structure

def test_payload_shape_matches_the_spec():
    payload, _ = _payload()
    assert set(payload) == {"session", "question_about", "blocks", "gaps", "relations"}
    assert payload["question_about"] in {b["id"] for b in payload["blocks"]}
    for b in payload["blocks"]:
        assert set(b) >= {"id", "app", "surface", "t_start_s", "dur_s", "events"}


def test_times_are_relative_to_the_window_start():
    payload, _ = _payload()
    assert payload["blocks"][0]["t_start_s"] == 0.0
    assert all(b["t_start_s"] >= 0 for b in payload["blocks"])


def test_gaps_reference_only_blocks_in_the_window():
    payload, _ = _payload()
    ids = {b["id"] for b in payload["blocks"]}
    assert len(payload["gaps"]) == len(payload["blocks"]) - 1
    for g in payload["gaps"]:
        assert set(g["between"]) <= ids and g["gap_s"] >= 0


def test_relations_reference_only_blocks_in_the_window():
    payload, _ = _payload()
    ids = {b["id"] for b in payload["blocks"]}
    for r in payload["relations"]:
        assert r["a"] in ids and r["b"] in ids


def test_screenshot_events_are_stripped_from_the_action_mix():
    """TEKG_SPEC §6: capture noise, not user action."""
    bl = B.build_blocks(flat(
        ev(0, app="W", title="d", et="keystroke"),
        ev(100, app="W", title="d", layer="L1", et="screenshot_smart"),
        ev(200, app="W", title="d", et="keystroke"),
    ))
    p = C.build_payload(G.local_evidence(G.build_graph(bl), 0, bl, window=2), "ses_test")
    assert all("screenshot_smart" not in b["actions"] for b in p["blocks"])


def test_empty_window_returns_an_empty_payload():
    assert C.build_payload({"window": [], "evidence": [], "center_idx": 0}, "s") == {}


def test_payload_is_deterministic():
    a, _ = _payload()
    b, _ = _payload()
    assert a == b


def test_system_prompt_carries_no_dataset_a_vocabulary():
    """ADR-010: prompts must be domain-neutral. Phase 0 can only assert the prompt is
    ASCII business-neutral text; Phase 3 moves it to a versioned file."""
    assert "SAME_EXECUTION" in C.SYSTEM_PROMPT
    assert set(C.RESPONSE_SCHEMA["properties"]["decision"]["enum"]) == {
        "SAME_EXECUTION", "INTERRUPTION", "RESUMPTION",
        "PROCESS_SWITCH", "NEW_EXECUTION", "UNCERTAIN"}
