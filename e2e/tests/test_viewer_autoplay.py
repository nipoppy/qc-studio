"""Tests for autoplay behaviour on the QC viewer.

Spec: e2e/specs/011-notes-pause-autoplay.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from conftest import two_subject_qc_config as qc_config
from constants import MESSAGES
from shared.app_utils import click_button, current_subject_id, get_by_key, get_text_area
from shared.flows import AUTOPLAY_SLIDER_MIN, start_autoplay, start_qc_session

pytestmark = pytest.mark.flow


#: Use the slider's minimum to keep this test as short as the app permits.
AUTOPLAY_DURATION_SECONDS = AUTOPLAY_SLIDER_MIN
#: try_autoplay_advance_if_due only fires duration + AUTOPLAY_ADVANCE_GRACE_SECONDS
#: (0.3s) after Play; this is what we wait past to prove a page that *should*
#: have advanced (were autoplay still running) did not.
AUTOPLAY_SETTLE_WAIT_MS = int((AUTOPLAY_DURATION_SECONDS + 0.3 + 3) * 1000)


def test_add_notes_pauses_autoplay(app: Page) -> None:
    """Given a rater part-way through QC on the viewer, with autoplay running,
    When the rater clicks "Add notes" on the task they are rating,
    Then autoplay stops (the countdown banner above the viewer is gone), the
    notes box for that task is no longer disabled, and after the full autoplay
    duration has elapsed the app is still showing the same subject.
    """
    start_qc_session(app, "autoplay-tester", autoplay_duration=AUTOPLAY_DURATION_SECONDS)
    start_autoplay(app)

    banner = get_by_key(app, "autoplay_countdown_banner")
    expect(banner).to_be_visible()
    subject_label = current_subject_id(app)

    click_button(app, MESSAGES["add_notes_button"])

    notes_box = get_text_area(app, MESSAGES["qc_notes_prompt"]).locator("textarea")
    expect(notes_box).to_be_enabled()
    expect(banner).not_to_be_visible()

    app.wait_for_timeout(AUTOPLAY_SETTLE_WAIT_MS)

    expect(banner).not_to_be_visible()
    assert current_subject_id(app) == subject_label
