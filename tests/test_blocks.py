"""Stage B — activity blocks.

Regression tests for the four perception defects Phase 0 fixed, plus the negative
tests that keep the fixes from over-merging.
"""
from __future__ import annotations

from procmine import blocks as B
from conftest import ev, flat


def keys(bl):
    return [b["surface"] for b in bl]


# ---------------------------------------------------------------- surface key (R4)

def test_surface_key_grammar():
    web = flat(ev(1, app="Edge", title="T", url="http://h/#/payroll"))[0]
    assert B.surface_key(web) == "web:http://h/payroll"
    titled = flat(ev(1, app="Word", title="doc"))[0]
    assert B.surface_key(titled) == "app:Word:doc"
    bare = flat(ev(1, app="Word", title=""))[0]
    assert B.surface_key(bare) == "app:Word"


def test_surface_type_is_structural_not_an_app_allow_list():
    """A browser the code has never heard of must still key as a web surface: an
    allow-list of browser names would be a dataset-specific rule (ADR-013)."""
    r = flat(ev(1, app="SomeNewBrowser 2031", title="T", url="http://h/#/x"))[0]
    assert B.surface_key(r) == "web:http://h/x"


# ---------------------------------------------------------------- R1

def test_capture_events_do_not_split_a_run():
    """screenshot_smart fired mid-browsing used to flip the surface to app:<browser>:<title>
    and back, producing a 1-event 0-duration block. 300 of them on dataset_b."""
    bl = B.build_blocks(flat(
        ev(1, app="Edge", title="Sys", url="http://h/#/a"),
        ev(2, app="Edge", title="Sys", layer="L1", et="screenshot_smart"),
        ev(3, app="Edge", title="Sys", url="http://h/#/a"),
    ))
    assert keys(bl) == ["web:http://h/a"]
    assert bl[0]["n_events"] == 3


def test_system_events_do_not_open_a_block():
    """SYSTEM events carry no active_app, which produced the 63 empty-surface blocks."""
    bl = B.build_blocks(flat(
        ev(1, layer="SYSTEM", et="session_start", app="", title=""),
        ev(2, app="Word", title="doc"),
        ev(3, layer="SYSTEM", et="extension_connected", app="", title=""),
        ev(4, app="Word", title="doc"),
        ev(5, layer="SYSTEM", et="session_end", app="", title=""),
    ))
    assert keys(bl) == ["app:Word:doc"]
    assert bl[0]["n_events"] == 5
    assert bl[0]["start_ms"] == 1, "a leading capture event still belongs to the block"


def test_block_identity_comes_from_surface_defining_rows():
    """A leading SYSTEM row carries no app/route; it must not blank out the block."""
    bl = B.build_blocks(flat(
        ev(1, layer="SYSTEM", et="session_start", app="", title=""),
        ev(2, app="Edge", title="Sys", url="http://h/#/a"),
    ))
    assert bl[0]["app"] == "Edge" and bl[0]["route"] == "/a"
    assert bl[0]["operator"] == "op1" and bl[0]["machine"] == "m1"


def test_a_session_of_only_capture_events_still_produces_a_block():
    bl = B.build_blocks(flat(ev(1, layer="SYSTEM", et="session_start", app="", title=""),
                             ev(2, layer="SYSTEM", et="session_end", app="", title="")))
    assert len(bl) == 1 and bl[0]["n_events"] == 2


# ---------------------------------------------------------------- R2

def test_row_without_a_discriminator_joins_the_same_app():
    bl = B.build_blocks(flat(
        ev(1, app="Word", title="doc"),
        ev(2, app="Word", title=""),          # title not captured on this event
        ev(3, app="Word", title="doc"),
    ))
    assert keys(bl) == ["app:Word:doc"]


def test_row_without_a_discriminator_still_splits_a_different_app():
    """R2 repairs missing data; it must not merge two different applications."""
    bl = B.build_blocks(flat(
        ev(1, app="Word", title="doc"),
        ev(2, app="Excel", title=""),
        ev(3, app="Word", title="doc"),
    ), min_events=1, min_ms=0)
    assert keys(bl) == ["app:Word:doc", "app:Excel", "app:Word:doc"]


def test_late_captured_title_merges_forward_into_the_same_application():
    """A window title is not populated until the window finishes activating, so switching
    into an app yields a bare app:<X> run immediately before app:<X>:<title>. One surface,
    not two. 35 of 59 bare-app runs on dataset_b."""
    bl = B.build_blocks(flat(
        ev(0, app="Edge", title="Sys", url="http://h/#/a"),
        ev(1000, app="Word", title="", et="app_switch", new_app="Word", previous_app="Edge"),
        ev(1100, app="Word", title=""),
        ev(2000, app="Word", title="contract"),
    ), min_events=1, min_ms=0)
    assert keys(bl) == ["web:http://h/a", "app:Word:contract"]
    assert bl[1]["n_events"] == 3 and bl[1]["start_ms"] == 1000


def test_an_application_that_never_reports_a_title_keeps_its_own_block():
    """The forward merge requires the same app on both sides, so a title-less dialog is
    not swallowed by whatever follows it. 24 such blocks survive on dataset_b."""
    bl = B.build_blocks(flat(
        ev(0, app="Word", title="doc"),
        ev(1000, app="OpenWith", title=""),
        ev(2000, app="Excel", title="sheet"),
    ), min_events=1, min_ms=0)
    assert keys(bl) == ["app:Word:doc", "app:OpenWith", "app:Excel:sheet"]


def test_row_with_no_application_at_all_attaches_to_the_open_block():
    bl = B.build_blocks(flat(
        ev(1, app="Word", title="doc"),
        ev(2, app="", title="", et="shortcut"),   # nothing to contradict
        ev(3, app="Word", title="doc"),
    ))
    assert keys(bl) == ["app:Word:doc"]


# ---------------------------------------------------------------- D-2 regression

def test_d2_notepad_untitled_is_work_not_noise():
    """D-2: the bare hint "Untitled" was a substring test against the normalised title, so
    Notepad's default document name was flagged as noise. 651 of dataset_a's 652 noise
    blocks came from this one hint."""
    bl = B.build_blocks(flat(
        ev(0, app="Notepad", title="Untitled - Notepad", et="keystroke"),
        ev(1000, app="Notepad", title="Untitled - Notepad", et="keystroke"),
    ))
    assert len(bl) == 1
    assert bl[0]["title"] == "Untitled"          # D-1 strips the " - Notepad" chrome
    assert bl[0]["is_noise"] is False, "genuine Notepad work must not be marked noise"


def test_d2_genuine_browser_chrome_is_still_noise():
    """Removing "Untitled" must not disarm the rest of the seed list."""
    for title in ("Turn off extensions in developer mode", "Restore pages?",
                  "New tab", "Settings | Microsoft Teams"):
        bl = B.build_blocks(flat(ev(0, app="Chrome", title=title),
                                 ev(1000, app="Chrome", title=title)))
        assert bl[0]["is_noise"] is True, title


def test_d2_untitled_is_no_longer_in_the_hint_list():
    assert "Untitled" not in B.NOISE_TITLE_HINTS
    assert len(B.NOISE_TITLE_HINTS) == 5


def test_empty_surface_is_still_noise():
    """The key-based half of _is_noise is untouched by D-2."""
    assert B._is_noise("app:", "") is True
    assert B._is_noise("app:None", "") is True


# ---------------------------------------------------------------- preserved signal

def test_a_document_switch_within_one_application_is_preserved():
    """468 Word->Word 'self-switch' app_switch events on dataset_b carry a NEW window
    title: a real document change. Suppressing self-switches would have destroyed 176
    genuine boundaries, which is why that rule was rejected."""
    bl = B.build_blocks(flat(
        ev(1, app="Word", title="contract_a"),
        ev(2, app="Word", title="contract_a"),
        ev(3, app="Word", title="contract_b", et="app_switch",
           new_app="Word", previous_app="Word"),
        ev(4, app="Word", title="contract_b"),
    ))
    assert keys(bl) == ["app:Word:contract_a", "app:Word:contract_b"]


def test_brief_but_distinct_work_between_different_surfaces_is_not_merged():
    """A|x|B is never absorbed: only a run bracketed by the SAME surface is."""
    bl = B.build_blocks(flat(
        ev(1, app="Word", title="a"),
        ev(2, app="Excel", title="b"),
        ev(3, app="Notepad", title="c"),
    ), min_events=5, min_ms=10_000)
    assert keys(bl) == ["app:Word:a", "app:Excel:b", "app:Notepad:c"]


# ---------------------------------------------------------------- absorption

def test_micro_excursion_is_absorbed():
    bl = B.build_blocks(flat(
        ev(0, app="Word", title="a"), ev(100, app="Word", title="a"),
        ev(200, app="Excel", title="b"),                       # brief detour
        ev(300, app="Word", title="a"), ev(400, app="Word", title="a"),
    ), min_events=3, min_ms=1500)
    assert keys(bl) == ["app:Word:a"]
    assert bl[0]["absorbed_excursions"] == 1
    assert bl[0]["n_events"] == 5


def test_a_long_excursion_is_not_absorbed():
    bl = B.build_blocks(flat(
        ev(0, app="Word", title="a"),
        ev(100, app="Excel", title="b"), ev(200, app="Excel", title="b"),
        ev(300, app="Excel", title="b"), ev(400, app="Excel", title="b"),
        ev(500, app="Word", title="a"),
    ), min_events=3, min_ms=1500)
    assert keys(bl) == ["app:Word:a", "app:Excel:b", "app:Word:a"]


def test_absorption_thresholds_are_honoured():
    rows = flat(
        ev(0, app="Word", title="a"),
        ev(100, app="Excel", title="b"), ev(5000, app="Excel", title="b"),
        ev(5100, app="Word", title="a"),
    )
    # excursion is 2 events but spans 4.9s: the ms threshold must block absorption
    assert len(B.build_blocks(rows, min_events=3, min_ms=1500)) == 3
    assert len(B.build_blocks(rows, min_events=3, min_ms=10_000)) == 1


# ---------------------------------------------------------------- shape

def test_empty_input():
    assert B.build_blocks([]) == []


def test_block_record_shape_and_invariants():
    bl = B.build_blocks(flat(
        ev(0, app="Edge", title="Sys", url="http://h/#/a", et="keystroke",
           field="fk1", vhash="vh1"),
        ev(500, app="Edge", title="Sys", url="http://h/#/a", et="browser_click"),
    ))
    b = bl[0]
    assert b["block_id"] == "ses_test#b0000" and b["idx"] == 0
    assert b["start_ms"] == 0 and b["end_ms"] == 500 and b["dur_ms"] == 500
    assert b["n_events"] == 2 and b["n_keystrokes"] == 1 and b["n_clicks"] == 1
    assert b["field_keys"] == ["fk1"] and b["value_hashes"] == ["vh1"]
    assert b["is_noise"] is False


def test_idx_is_dense_and_blocks_do_not_overlap():
    bl = B.build_blocks(flat(*[ev(i * 1000, app=f"A{i}", title="t") for i in range(6)]),
                        min_events=1, min_ms=0)
    assert [b["idx"] for b in bl] == list(range(len(bl)))
    for a, b in zip(bl, bl[1:]):
        assert b["start_ms"] >= a["end_ms"]


def test_block_stats_reports_the_degeneracy_counters():
    s = B.block_stats(B.build_blocks(flat(ev(0, app="A", title="t"))))
    assert s["n_blocks"] == 1 and s["n_one_event"] == 1 and s["n_zero_duration"] == 1
    assert s["n_empty_surface"] == 0
    assert B.block_stats([]) == {}
