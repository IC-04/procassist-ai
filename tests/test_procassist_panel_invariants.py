"""The panel prepares; it does not act. These tests read the shipped JavaScript.

There is no JS runtime in this suite, so the invariants are enforced the way they are actually
at risk of being broken: by someone adding a line to panel.js. A source-level assertion that
the file contains no way to fire a click is a stronger guarantee than a DOM test that only
covers the paths the test happens to exercise.
"""
from __future__ import annotations

import os
import re

import pytest

PANEL = os.path.join("procassist", "panel", "panel.js")

#: Every API by which a script could press a button or submit a form on the host's behalf.
FORBIDDEN = (".click(", "dispatchEvent", ".submit(", "requestSubmit", "new Event(",
             "new MouseEvent", "new PointerEvent", "form.submit", "HTMLFormElement")


@pytest.fixture(scope="module")
def source():
    with open(PANEL, encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("api", FORBIDDEN)
def test_the_panel_cannot_fire_a_click_or_submit_a_form(source, api):
    assert api not in source, (
        f"panel.js contains {api!r}: the tool must never operate a host control")


def test_the_panel_never_writes_to_the_host_disposition_control(source):
    """`submitId` may only be read, and only ever to attach a listener or name it in a log."""
    for line in source.splitlines():
        if "ctx.submitId" not in line:
            continue
        ok = ("getElementById(ctx.submitId)" in line          # read the element
              or '"clicked #" + ctx.submitId' in line         # name it in an audit row
              or "submitId:" in line)                         # read it out of the DOM dataset
        assert ok, f"panel.js writes to the disposition control: {line.strip()}"
    # and it is never assigned to
    assert not re.search(r"ctx\.submitId[^\n]*=[^=]", source)
    assert "control.disabled" not in source and "control.value" not in source


def test_the_only_host_element_the_panel_writes_to_is_the_note_field(source):
    """Find every `.value =` assignment and confirm its target is the note textarea."""
    assignments = [l.strip() for l in source.splitlines() if re.search(r"\.value\s*=[^=]", l)]
    assert assignments, "expected the panel to fill the note field"
    for line in assignments:
        assert "field.value" in line, f"unexpected host write: {line}"


def test_no_judgement_chip_is_preselected(source):
    """`chosenJudgement` starts null and is assigned in exactly one place: a click handler."""
    assert "chosenJudgement: null" in source
    assigns = [l for l in source.splitlines() if re.search(r"state\.chosenJudgement\s*=[^=]", l)]
    assert len(assigns) == 1, f"chosenJudgement is set in {len(assigns)} places"
    assert "option.text_ja" in assigns[0]
    # the chip markup carries no selected/checked/default state
    chip_markup = re.findall(r'data-judgement="[^"]*"[^>]*', source)
    for chunk in chip_markup:
        assert "chosen" not in chunk and "selected" not in chunk


def test_the_engine_result_the_panel_renders_never_carries_a_judgement(source):
    """The panel reads `draft.judgement_options`, never a `draft.judgement`."""
    assert "draft.judgement_options" in source
    assert not re.search(r"\.draft\.judgement\b(?!_)", source)


def test_the_replica_renders_the_reject_affordance_that_was_never_used():
    """差戻し is offered by the la-note placeholder and was typed 0 times. Render it anyway."""
    with open(os.path.join("procassist", "replica", "templates", "detail.html"),
              encoding="utf-8") as fh:
        html = fh.read()
    assert "btn-la-reject" in html and "差戻し" in html
