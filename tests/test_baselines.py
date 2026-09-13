"""Baseline segmenters (EVALUATION_PROTOCOL §6). Synthetic rows only."""
from __future__ import annotations
import pytest

from procmine import baselines as BL
from conftest import ev, flat


def rows_two_chunks():
    """6 events: 3 in chunk_a on surface X, 3 in chunk_b on surface Y."""
    out = []
    for i in range(3):
        e = ev(1000 + i * 1000, app="Word", title="X")
        e["correlation"]["chunk_id"] = "chunk_a"
        out.append(e)
    for i in range(3):
        e = ev(10000 + i * 1000, app="Excel", title="Y")
        e["correlation"]["chunk_id"] = "chunk_b"
        out.append(e)
    return flat(*out)


def test_registry_has_exactly_the_six_specified_baselines():
    assert set(BL.REGISTRY) == {"B0-single", "B1-chunk", "B2-gap",
                                "B3-random", "B4-surface", "B5-dwell"}


def test_b0_single_is_one_segment_spanning_the_session():
    r = rows_two_chunks()
    iv, lb = BL.b0_single(r, [])
    assert len(iv) == 1
    assert iv[0] == (r[0]["ts_ms"], r[-1]["ts_ms"])
    assert len(lb) == 1


def test_b1_chunk_cuts_exactly_at_chunk_changes():
    """Two chunks -> two segments. This baseline exists to prove chunks are meaningless."""
    iv, _ = BL.b1_chunk(rows_two_chunks(), [])
    assert len(iv) == 2
    assert iv[0][1] == 3000 and iv[1][0] == 10000


def test_b2_gap_cuts_at_the_largest_gaps_and_honours_k():
    """Gaps are 1s,1s,7s,1s,1s -> the 7s gap is the single largest."""
    r = rows_two_chunks()
    iv, _ = BL.b2_gap(r, [], k=2)
    assert len(iv) == 2
    assert iv[1][0] == 10000, "the cut must land at the 7s gap"
    assert len(BL.b2_gap(r, [], k=1)[0]) == 1
    assert len(BL.b2_gap(r, [], k=4)[0]) == 4


def test_b3_random_is_count_matched_and_seed_deterministic():
    r = rows_two_chunks()
    a, _ = BL.b3_random(r, [], k=3, seed=1)
    b, _ = BL.b3_random(r, [], k=3, seed=1)
    c, _ = BL.b3_random(r, [], k=3, seed=2)
    assert len(a) == 3
    assert a == b, "same seed must reproduce"
    assert isinstance(c, list)


def test_b4_surface_cuts_at_every_context_state_change():
    """The over-segmentation ceiling: one segment per surface run."""
    iv, _ = BL.b4_surface(rows_two_chunks(), [])
    assert len(iv) == 2
    r = flat(ev(0, app="A", title="a"), ev(100, app="B", title="b"),
             ev(200, app="C", title="c"))
    assert len(BL.b4_surface(r, [])[0]) == 3


def test_b5_dwell_returns_the_blocks_verbatim():
    blocks = [{"start_ms": 0, "end_ms": 100, "surface": "app:A:x"},
              {"start_ms": 100, "end_ms": 200, "surface": "app:B:y"}]
    iv, lb = BL.b5_dwell([], blocks)
    assert iv == [(0, 100), (100, 200)]
    assert lb == ["app:A:x", "app:B:y"]


def test_every_baseline_returns_aligned_intervals_and_labels():
    r = rows_two_chunks()
    blocks = [{"start_ms": 1000, "end_ms": 3000, "surface": "app:Word:X"}]
    for name in BL.REGISTRY:
        iv, lb = BL.run_baseline(name, r, blocks, k=2, seed=0)
        assert len(iv) == len(lb), name
        for a, b in iv:
            assert b >= a, name


def test_every_baseline_handles_empty_input():
    for name in BL.REGISTRY:
        iv, lb = BL.run_baseline(name, [], [], k=1, seed=0)
        assert iv == [] and lb == [], name


def test_intervals_are_ordered_and_non_overlapping():
    r = rows_two_chunks()
    for name in ("B1-chunk", "B2-gap", "B4-surface"):
        iv, _ = BL.run_baseline(name, r, [], k=3, seed=0)
        for x, y in zip(iv, iv[1:]):
            assert y[0] >= x[1], name


def test_oracle_arms_are_declared():
    """B2 and B3 receive the true segment count; that must be explicit, not hidden."""
    assert BL.ORACLE_K == {"B2-gap", "B3-random"}
    assert BL.N_RANDOM_SEEDS == 20


def test_to_segments_matches_the_deliverable_shape():
    """DATA_CONTRACT §6: exactly four keys, ISO-8601 UTC ending in Z, second precision."""
    segs = BL.to_segments("ses_x", [(1782820800000, 1782820830000)], ["lab"])
    assert len(segs) == 1
    s = segs[0]
    assert set(s) == {"session_id", "start", "end", "label"}
    assert s["start"].endswith("Z") and s["end"].endswith("Z")
    assert s["start"] == "2026-06-30T12:00:00Z"
    assert s["start"] < s["end"]
