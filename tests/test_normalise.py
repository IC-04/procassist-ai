"""Stage A — normalisation contract."""
from __future__ import annotations
import json
import pytest

from procmine import normalise as N
from conftest import ev, flat


# ---------------------------------------------------------------- _g

def test_g_returns_default_on_missing_and_none_links():
    d = {"a": {"b": {"c": 1}}, "dead": None}
    assert N._g(d, "a", "b", "c") == 1
    assert N._g(d, "a", "nope", "c") is None
    assert N._g(d, "dead", "b", default="fallback") == "fallback"
    assert N._g(None, "a") is None
    assert N._g("not a dict", "a", default=7) == 7
    assert N._g({"a": 5}, "a", "b") is None          # scalar mid-path, must not raise


# ---------------------------------------------------------------- titles

@pytest.mark.parametrize("raw,want", [
    ("受発注在庫管理システム - Profile 1 - Microsoft\u200b Edge", "受発注在庫管理システム"),
    ("expense_calc - Excel", "expense_calc"),
    ("keiyaku [Compatibility Mode] ", "keiyaku [Compatibility Mode]"),
    ("*unsaved", "unsaved"),
    ("a  b", "a b"),
    ("", ""),
    (None, ""),
])
def test_normalise_title(raw, want):
    assert N.normalise_title(raw) == want


# ---------------------------------------------------------------- D-1 regression

@pytest.mark.parametrize("title,want", [
    # the same page, as three different browsers render the window title
    ("HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0 - Profile 1 - Microsoft\u200b Edge", "HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0"),
    ("HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0 - Google Chrome", "HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0"),
    ("HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0 - Profile 2 - Google Chrome", "HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0"),
    ("HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0 \u2014 Mozilla Firefox", "HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0"),
    ("HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0 - Brave", "HR\u4eba\u4e8b\u7d66\u4e0e\u30b7\u30b9\u30c6\u30e0"),
])
def test_d1_browser_chrome_is_stripped_whichever_browser_appended_it(title, want):
    """D-1: the Edge suffix was stripped and the Chrome one was not, so the SAME page keyed
    as two different surfaces. The rule is structural — no browser allow-list (ADR-013)."""
    assert N.normalise_title(title) == want


def test_d1_one_page_yields_one_surface_across_browsers():
    """The defect stated as the property that matters, not as a string comparison."""
    titles = ["\u53d7\u767a\u6ce8\u5728\u5eab\u7ba1\u7406\u30b7\u30b9\u30c6\u30e0 - Profile 1 - Microsoft\u200b Edge",
              "\u53d7\u767a\u6ce8\u5728\u5eab\u7ba1\u7406\u30b7\u30b9\u30c6\u30e0 - Google Chrome",
              "\u53d7\u767a\u6ce8\u5728\u5eab\u7ba1\u7406\u30b7\u30b9\u30c6\u30e0"]
    assert len({N.normalise_title(t) for t in titles}) == 1


def test_d1_does_not_eat_a_real_title_that_merely_contains_a_dash():
    """The structural rule must not strip a tail that is part of the document name."""
    for t in ("Mixed Multi-Domain (HR / Finance / Ops)",
              "Q3 report - final draft",          # lower-case tail -> not app chrome
              "\u4f4f\u6c11\u7a0e\u901a\u77e5\u78ba\u8a8d",
              "budget - 2026 q1 revision"):
        assert N.normalise_title(t) == t.strip()


def test_d1_leaves_a_bare_title_untouched():
    assert N.normalise_title("Untitled") == "Untitled"
    assert N.normalise_title("expense_calc") == "expense_calc"


def test_normalise_title_strips_the_zero_width_space_in_edge_titles():
    # The recorder writes "Microsoft\u200b Edge" (U+200B). A strip rule that assumed a
    # plain space would leave the whole browser chrome in the surface key.
    assert "Edge" not in N.normalise_title("X - Profile 2 - Microsoft\u200b Edge")


# ---------------------------------------------------------------- URLs (R5)

@pytest.mark.parametrize("url,origin,route", [
    ("http://127.0.0.1:5132/#/payroll-items", "http://127.0.0.1:5132", "/payroll-items"),
    ("http://127.0.0.1:5132/#payroll", "http://127.0.0.1:5132", "/payroll"),
    ("http://127.0.0.1:5132/", "http://127.0.0.1:5132", "/"),
    ("https://h.example/a/b?q=1", "https://h.example", "/a/b"),
    ("https://h.example", "https://h.example", "/"),
    ("", "", ""),
    (None, "", ""),
    ("not a url", "", ""),
    ("file:///C:/x.docx", "", ""),
])
def test_route_and_origin(url, origin, route):
    assert N.origin_of(url) == origin
    assert N.route_of(url) == route


def test_route_never_repeats_the_origin():
    """Regression: route_of used to fall back to the origin, so the surface key became
    web:http://hosthttp://host (54 blocks on dataset_b)."""
    for url in ("http://127.0.0.1:5132/", "http://h/a", "https://h.example/x/y"):
        assert not N.route_of(url).startswith("http")
        key = f"web:{N.origin_of(url)}{N.route_of(url)}"
        assert key.count("http") == 1, key


# ---------------------------------------------------------------- tab carry-forward (R3)

def test_carry_forward_fills_a_gap_within_one_app():
    rows = flat(
        ev(1, app="Edge", url="http://h/#/a"),
        ev(2, app="Edge", layer="L1", et="screenshot_smart"),   # no tab reported
        ev(3, app="Edge", url="http://h/#/a"),
    )
    assert rows[1]["url"] == "http://h/#/a"
    assert rows[1]["route"] == "/a" and rows[1]["origin"] == "http://h"
    assert rows[1]["url_observed"] is False
    assert rows[0]["url_observed"] is True


def test_carry_forward_resets_when_the_application_changes():
    rows = flat(
        ev(1, app="Edge", url="http://h/#/a"),
        ev(2, app="Word", title="doc"),         # different app: tab state unknown
        ev(3, app="Word", title="doc"),
    )
    assert rows[1]["url"] == "" and rows[2]["url"] == ""


def test_carry_forward_is_not_seeded_by_l3_events():
    """The browser extension's active_app lags the OS foreground. Seeding from L3 leaked
    a browser URL onto 87 non-browser events on dataset_b."""
    rows = flat(
        ev(1, app="Notepad", title="memo"),
        ev(2, app="Notepad", title="memo", layer="L3", et="browser_navigation",
           url="http://h/#/a"),
        ev(3, app="Notepad", title="memo"),
    )
    assert rows[2]["url"] == "", "an L3 URL must not become Notepad's tab state"
    assert rows[1]["url"] == "http://h/#/a", "the L3 event keeps its own observed URL"


def test_carry_forward_is_pure():
    src = [N.flatten_event(ev(1, app="Edge", url="http://h/#/a")),
           N.flatten_event(ev(2, app="Edge", layer="L1", et="screenshot_smart"))]
    before = json.dumps(src, sort_keys=True)
    N.carry_forward_tab_state(src)
    assert json.dumps(src, sort_keys=True) == before


# ---------------------------------------------------------------- loading

def test_flatten_tolerates_a_completely_empty_event():
    r = N.flatten_event({})
    assert r["app_name"] == "" and r["url"] == "" and r["ts_ms"] is None
    assert r["unreliable"] is False


def test_text_input_complete_is_flagged_unreliable():
    # DATA_SCHEMA.md §2 Caveats: the field is not trustworthy and is never a feature.
    assert N.flatten_event(ev(1, et="text_input_complete"))["unreliable"] is True
    assert N.flatten_event(ev(1, et="keystroke"))["unreliable"] is False


def test_load_session_skips_malformed_lines_and_dissolves_chunks(tmp_path):
    """ADR-001: chunks are recording artifacts; order is rebuilt from timestamp_ms."""
    sess = tmp_path / "ses_x"
    for name, evs in (("chunk_b", [ev(30), ev(10)]), ("chunk_a", [ev(20)])):
        d = sess / name
        d.mkdir(parents=True)
        lines = [json.dumps(e) for e in evs]
        lines.insert(1, "{not json")          # malformed: must be skipped, not raise
        lines.append("")                       # blank line
        (d / "events.jsonl").write_text("\n".join(lines), encoding="utf-8")

    rows = N.load_session(str(sess))
    assert [r["ts_ms"] for r in rows] == [10, 20, 30]   # global order, chunks dissolved
    assert [r["seq"] for r in rows] == [0, 1, 2]
    assert len({r["chunk_dir"] for r in rows}) == 2


def test_load_session_on_an_empty_directory(tmp_path):
    (tmp_path / "ses_empty").mkdir()
    assert N.load_session(str(tmp_path / "ses_empty")) == []


def test_app_switch_payload_is_exposed_in_both_shapes():
    a = N.flatten_event(ev(1, et="app_switch", new_app="Word", previous_app="Edge"))
    b = N.flatten_event(ev(1, et="app_switch",
                           new_app={"app_name": "Word"}, previous_app={"app_name": "Edge"}))
    assert a["new_app"] == b["new_app"] == "Word"
    assert a["prev_app"] == b["prev_app"] == "Edge"
