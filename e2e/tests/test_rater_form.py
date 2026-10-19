"""Tests for the rater form on the landing page.

Spec: e2e/specs/001-rater-form-validation.md
Spec: e2e/specs/002-rater-form-panel-validation.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from constants import ERROR_MESSAGES, MESSAGES, PANEL_CONFIG
from shared.app_utils import (
    click_form_submit,
    expect_text_visible,
    fill_text_input,
    get_form_submit_button,
    uncheck_checkbox,
)

pytestmark = pytest.mark.edge


def test_empty_rater_id_blocks_submission(app: Page) -> None:
    """Given a freshly loaded landing page,
    When the rater form is submitted with the Rater Name / ID field left empty,
    Then ERROR_MESSAGES["invalid_rater_id"] is visible and the rater form is
    still on screen -- the app did not advance to the QC viewer.
    """
    click_form_submit(app, MESSAGES["rater_form_button"])

    expect_text_visible(app, ERROR_MESSAGES["invalid_rater_id"])
    get_form_submit_button(app, MESSAGES["rater_form_button"])


def test_no_panels_selected_blocks_submission(app: Page) -> None:
    """Given a rater on a freshly loaded landing page (where the niivue and
    montage panels are checked by default) who has entered a valid Rater ID
    and unchecked both default panels,
    When the rater submits the rater form with no selected display panel,
    Then ERROR_MESSAGES["no_panel_selected"] is visible and the rater form is
    still on screen -- the app did not advance to the QC viewer.
    """
    fill_text_input(app, MESSAGES["rater_id_prompt"], "test-rater")
    uncheck_checkbox(app, PANEL_CONFIG["niivue"]["label"])
    uncheck_checkbox(app, PANEL_CONFIG["montage"]["label"])

    click_form_submit(app, MESSAGES["rater_form_button"])

    expect_text_visible(app, ERROR_MESSAGES["no_panel_selected"])
    get_form_submit_button(app, MESSAGES["rater_form_button"])
