"""Tests for entering the viewer and for ratings surviving navigation.

Spec: e2e/specs/006-valid-rater-form-opens-viewer.md
Spec: e2e/specs/003-rating-survives-navigation.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from conftest import two_subject_qc_config as qc_config
from constants import DEFAULT_QC_RATING_NONE, MESSAGES, QC_RATINGS
from shared.app_utils import (
    choose_radio_option,
    click_button,
    current_subject_id,
    expect_radio_selected,
    get_radio_option,
)
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow

PASS_RATING = QC_RATINGS[0]
FAIL_RATING = QC_RATINGS[1]


def test_valid_rater_form_opens_the_viewer(app: Page) -> None:
    """Given a rater on a freshly loaded landing page,
    When they enter a valid Rater ID and submit the rater form,
    Then the QC viewer is on screen and the rater form is gone.

    Specs 001 and 002 only prove the gate blocks. Without this, the success
    branch could break and both of them would still pass.

    Asserts on the rating options rather than MESSAGES["qc_rating_prompt"]:
    that constant is not rendered anywhere -- the viewer writes its own
    "Rate <task>" heading instead -- so it would never match.
    """
    start_qc_session(app, "viewer-tester")

    # The rating input itself is positioned off-screen by Streamlit; its
    # label is what the rater sees, so that is what must be visible.
    expect(get_radio_option(app, PASS_RATING)).to_be_attached()
    # The rater form is the only st.form in the app, so its submit button
    # disappearing is proof the landing page is gone. Located directly rather
    # than via get_form_submit_button, which asserts visibility itself and so
    # cannot express absence.
    expect(app.get_by_test_id("stFormSubmitButton")).to_have_count(0)


def test_rating_survives_navigating_away_and_back(app: Page) -> None:
    """Given a rater who has rated the first subject PASS,
    When they move to the next subject and navigate back,
    Then PASS is still selected for the first subject.
    """
    start_qc_session(app, "rating-tester")
    first_subject = current_subject_id(app)

    choose_radio_option(app, PASS_RATING)
    expect_radio_selected(app, PASS_RATING)

    click_button(app, MESSAGES["next_button"])
    assert current_subject_id(app) != first_subject

    click_button(app, MESSAGES["previous_button"])
    assert current_subject_id(app) == first_subject
    expect_radio_selected(app, PASS_RATING)


def test_unrated_subjects_take_the_configured_default_rating(app: Page) -> None:
    """Given the sidebar "Default QC rating" left at its shipped value of PASS,
    When the rater rates the first subject FAIL and moves to the next one,
    Then the next subject shows PASS -- the configured default, not the FAIL
    carried over from its neighbour.

    Pinned down because the shipped default means pressing Next past a subject
    exports PASS for it without the rater having judged it. That is the
    feature working as built, but it is worth a test that says so out loud.

    The default is not applied to the *first* subject, only to ones reached by
    navigating -- hence rating and advancing rather than asserting on arrival.
    """
    start_qc_session(app, "default-rating-tester")

    choose_radio_option(app, FAIL_RATING)
    click_button(app, MESSAGES["next_button"])

    expect_radio_selected(app, PASS_RATING)
    expect_radio_selected(app, FAIL_RATING, selected=False)


def test_default_rating_of_none_leaves_subjects_unrated(app: Page) -> None:
    """Given the rater sets "Default QC rating" to None before starting,
    When they rate the first subject and move to the next,
    Then nothing is selected for it -- no default, and no carry-over.
    """
    choose_radio_option(app, DEFAULT_QC_RATING_NONE)
    start_qc_session(app, "no-default-tester")

    choose_radio_option(app, PASS_RATING)
    click_button(app, MESSAGES["next_button"])

    for rating in QC_RATINGS:
        expect_radio_selected(app, rating, selected=False)
