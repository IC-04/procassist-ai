"""Artifact conformance validators (DATA_CONTRACT.md)."""
from __future__ import annotations
import copy

from procmine import blocks as B, schemas as S
from conftest import ev, flat


def good_blocks():
    return B.build_blocks(flat(
        ev(0, app="Edge", title="Sys", url="http://h/#/a"),
        ev(1000, app="Edge", title="Sys", url="http://h/#/a"),
        ev(2000, app="Word", title="doc"),
        ev(3000, app="Word", title="doc"),
    ), min_events=1, min_ms=0)


def good_tekg():
    return {
        "session_id": "ses_test",
        "nodes": ["ses_test#b0000", "ses_test#b0001"],
        "edges": [{"src": "ses_test#b0000", "rel": "temporal_next",
                   "dst": "ses_test#b0001", "lag": None, "gap_ms": 0, "n": None}],
    }


# ---------------------------------------------------------------- blocks

def test_valid_blocks_pass():
    assert S.validate_blocks(good_blocks()) == []
    assert S.validate_blocks([]) == []


def test_missing_field_is_reported():
    bl = good_blocks()
    del bl[0]["n_events"]
    assert any("missing fields" in p for p in S.validate_blocks(bl))


def test_reversed_interval_is_reported():
    bl = good_blocks()
    bl[0]["end_ms"] = bl[0]["start_ms"] - 1
    assert any("end_ms < start_ms" in p for p in S.validate_blocks(bl))


def test_inconsistent_duration_is_reported():
    bl = good_blocks()
    bl[0]["dur_ms"] += 5
    assert any("dur_ms inconsistent" in p for p in S.validate_blocks(bl))


def test_non_dense_idx_is_reported():
    bl = good_blocks()
    bl[1]["idx"] = 7
    assert any("idx not dense" in p for p in S.validate_blocks(bl))


def test_overlapping_blocks_are_reported():
    bl = good_blocks()
    bl[1]["start_ms"] = bl[0]["end_ms"] - 10
    assert any("overlap" in p for p in S.validate_blocks(bl))


def test_block_id_must_be_session_scoped():
    bl = good_blocks()
    bl[0]["block_id"] = "ses_other#b0000"
    assert any("not scoped to its session" in p for p in S.validate_blocks(bl))


def test_surface_grammar():
    bl = good_blocks()
    bl[0]["surface"] = "something-else"
    assert any("grammar" in p for p in S.validate_blocks(bl))


def test_window_titles_with_spaces_are_valid_surfaces():
    """Regression: an over-tight grammar rejected 753 legitimate blocks such as
    'app:WindowsTerminal:Windows PowerShell'."""
    for surface in ("app:WindowsTerminal:Windows PowerShell",
                    "app:Microsoft Word:x [Compatibility Mode]",
                    "app:Microsoft Word", "web:http://127.0.0.1:5132/payroll-items",
                    "app:Microsoft Edge:受発注在庫管理システム"):
        bl = good_blocks()
        bl[0]["surface"] = surface
        assert S.validate_blocks(bl) == [], surface


def test_surface_may_not_embed_a_timestamp():
    bl = good_blocks()
    bl[0]["surface"] = "app:Rec:capture 1782931327345"
    assert any("timestamp" in p for p in S.validate_blocks(bl))


# ---------------------------------------------------------------- tekg

def test_valid_tekg_passes():
    assert S.validate_tekg(good_tekg()) == []


def test_illegal_relation_is_reported():
    d = good_tekg()
    d["edges"][0]["rel"] = "caused_by"
    assert any("illegal relation" in p for p in S.validate_tekg(d))


def test_relation_set_is_exactly_the_spec_eight():
    assert S.RELATIONS == {
        "temporal_next", "same_surface_as", "returns_to", "same_route_as",
        "same_system_as", "same_field_as", "shared_value_with", "dataflow_to"}


def test_dangling_edge_is_reported():
    d = good_tekg()
    d["edges"][0]["dst"] = "ses_test#b0099"
    assert any("unknown node" in p for p in S.validate_tekg(d))


def test_foreign_node_is_reported():
    d = good_tekg()
    d["nodes"] = ["ses_other#b0000"] + d["nodes"]
    assert any("does not belong" in p for p in S.validate_tekg(d))


def test_unsorted_edges_are_reported():
    d = good_tekg()
    d["nodes"].append("ses_test#b0002")
    d["edges"] = [
        {"src": "ses_test#b0001", "rel": "temporal_next", "dst": "ses_test#b0002",
         "lag": None, "gap_ms": 0, "n": None},
        copy.deepcopy(d["edges"][0]),
    ]
    assert any("not sorted" in p for p in S.validate_tekg(d))


def test_lag_beyond_max_lag_is_reported():
    d = good_tekg()
    d["edges"][0].update(rel="returns_to", lag=99)
    assert any("exceeds max_lag" in p for p in S.validate_tekg(d, max_lag=12))


def test_missing_top_level_key_is_reported():
    assert any("missing" in p for p in S.validate_tekg({"nodes": [], "edges": []}))


# ---------------------------------------------------------------- windows

def test_clean_payload_passes():
    assert S.validate_window_payload(
        {"session": "s", "question_about": "b2",
         "blocks": [{"id": "b0", "t_start_s": 1.2, "dur_s": 3.0, "events": 4}],
         "gaps": [], "relations": []}) == []


def test_forbidden_keys_and_values_are_reported():
    for bad in ({"start_ms": 1}, {"x": {"block_id": "y"}}, {"idx": 0},
                {"a": [{"ts_ms": 3}]}, {"v": "at 1782931327345"}):
        assert S.validate_window_payload(bad) != [], bad


def test_ordinary_words_containing_a_forbidden_substring_are_allowed():
    assert S.validate_window_payload({"note": "index of items", "n": 123}) == []
