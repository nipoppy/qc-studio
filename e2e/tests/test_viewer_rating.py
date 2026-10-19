"""Tests for entering the viewer and for ratings surviving navigation.

Spec: e2e/specs/006-valid-rater-form-opens-viewer.md
Spec: e2e/specs/003-rating-survives-navigation.md
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
    expect_radio_selected,
    get_radio_option,
)
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow

PASS_RATING = QC_RATINGS[0]


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

    expect(get_radio_option(app, PASS_RATING)).to_be_visible()
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG: an unrated subject inherits the previous subject's rating in the "
        "radio. Nothing is recorded on arrival (its sidebar row still shows ⬜), "
        "but the rater sees PASS pre-selected, and pressing Next records that "
        "rating for a subject they never judged. Remove this marker once fixed."
    ),
)
def test_next_subject_does_not_inherit_the_previous_rating(app: Page) -> None:
    """Given a rater who has rated the first subject PASS,
    When they move to the next subject, which they have never rated,
    Then no rating is selected for it.

    This is the rule the landing page already honours by leaving every rating
    unset: a rating must never be assumed on a rater's behalf.
    """
    start_qc_session(app, "inherit-tester")

    choose_radio_option(app, PASS_RATING)
    click_button(app, MESSAGES["next_button"])

    expect_radio_selected(app, PASS_RATING, selected=False)
