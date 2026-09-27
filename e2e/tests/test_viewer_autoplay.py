"""Tests for autoplay behaviour on the QC viewer.

Spec: e2e/specs/011-notes-pause-autoplay.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from conftest import two_subject_qc_config as qc_config
from constants import MESSAGES, PANEL_CONFIG
from shared.app_utils import (
    click_button,
    click_form_submit,
    fill_text_input,
    get_by_key,
    get_current_subject_label,
    get_text_area,
    set_slider_value,
    uncheck_checkbox,
)

pytestmark = pytest.mark.flow


AUTOPLAY_DURATION_SECONDS = 3
#: try_autoplay_advance_if_due only fires duration + AUTOPLAY_ADVANCE_GRACE_SECONDS
#: (0.3s) after Play; this is what we wait past to prove a page that *should*
#: have advanced (were autoplay still running) did not.
AUTOPLAY_SETTLE_WAIT_MS = int((AUTOPLAY_DURATION_SECONDS + 0.3 + 3) * 1000)


def _start_qc_with_autoplay_running(app: Page) -> None:
    """Submit the rater form with a short autoplay duration, then press Play.

    Every viewer spec needs a rater on a subject with autoplay ticking; this is
    the shared path to that state.

    Unchecks the Niivue panel: it renders a real 3D MRI volume client-side,
    which takes tens of seconds to finish loading -- far longer than the
    whole autoplay window (2-10s) -- and keeps `wait_for_app_run`'s skeleton
    check blocked that whole time. Montage-only keeps each rerun fast enough
    that the standard helpers stay usable and the timing in this test means
    what it says.
    """
    fill_text_input(app, MESSAGES["rater_id_prompt"], "autoplay-tester")
    # Niivue is intentionally not loaded for this test -- see docstring above.
    uncheck_checkbox(app, PANEL_CONFIG["niivue"]["label"])
    set_slider_value(app, MESSAGES["autoplay_duration_label"], AUTOPLAY_DURATION_SECONDS, minimum=2, maximum=10)
    click_form_submit(app, MESSAGES["rater_form_button"])

    click_button(app, MESSAGES["play_button"])


def test_add_notes_pauses_autoplay(app: Page) -> None:
    """Given a rater part-way through QC on the viewer, with autoplay running,
    When the rater clicks "Add notes" on the task they are rating,
    Then autoplay stops (the countdown banner above the viewer is gone), the
    notes box for that task is no longer disabled, and after the full autoplay
    duration has elapsed the app is still showing the same subject.
    """
    _start_qc_with_autoplay_running(app)

    banner = get_by_key(app, "autoplay_countdown_banner")
    expect(banner).to_be_visible()
    subject_label = get_current_subject_label(app).inner_text()

    click_button(app, MESSAGES["add_notes_button"])

    notes_box = get_text_area(app, MESSAGES["qc_notes_prompt"]).locator("textarea")
    expect(notes_box).to_be_enabled()
    expect(banner).not_to_be_visible()

    app.wait_for_timeout(AUTOPLAY_SETTLE_WAIT_MS)

    expect(banner).not_to_be_visible()
    assert get_current_subject_label(app).inner_text() == subject_label
