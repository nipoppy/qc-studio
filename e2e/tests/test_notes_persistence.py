"""Tests for QC notes surviving a round trip away from and back to a subject.

Spec: e2e/specs/010-notes-are-saved.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from conftest import two_subject_qc_config as qc_config
from constants import MESSAGES, QC_RATINGS
from shared.app_utils import (
    choose_radio_option,
    click_button,
    current_subject_id,
    fill_text_area_and_blur,
    get_text_area,
)
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow

NOTE_TEXT = "flagged: motion artifact on frontal slices"


def test_note_survives_navigating_away_and_back(app: Page) -> None:
    """Given a rater on a subject whose notes box they made editable by
    clicking "Add notes",
    When they type a note for that task and commit it by moving focus out of
    the box,
    Then navigating to the next subject and back again, the note is still
    shown in the notes box for that subject.

    Also selects a rating first: `_record_qc_for_current_participant` no-ops
    silently when the task has no rating yet (`if rating is None: return`),
    so a note typed against an unrated task is never persisted at all -- not
    a bug, but a real precondition for this spec that isn't obvious from the
    "Given" clause alone.
    """
    start_qc_session(app, "notes-tester")
    subject_label = current_subject_id(app)

    choose_radio_option(app, QC_RATINGS[0])
    click_button(app, MESSAGES["add_notes_button"])
    fill_text_area_and_blur(app, MESSAGES["qc_notes_prompt"], NOTE_TEXT)

    click_button(app, MESSAGES["next_button"])
    assert current_subject_id(app) != subject_label

    click_button(app, MESSAGES["previous_button"])
    assert current_subject_id(app) == subject_label

    notes_box = get_text_area(app, MESSAGES["qc_notes_prompt"]).locator("textarea")
    expect(notes_box).to_have_value(NOTE_TEXT)
