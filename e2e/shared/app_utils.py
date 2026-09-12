"""Locating and interacting with QC-Studio's widgets.

Tests should never call `page.locator(...)` directly. Every selector lives
here, so when Streamlit changes its internals there is exactly one file to fix.

Selector strategy, strongest first
----------------------------------
1. `get_by_key(page, "rater_id")` -- Streamlit stamps a stable CSS class
   `st-key-<key>` on any widget given an explicit `key=`. Independent of
   label text, so it survives copy changes. Prefer this where QC-Studio's
   widgets have keys.
2. `get_by_test_id("stTextInput").filter(has_text=label)` -- a widget testid
   narrowed by its visible label. What Streamlit's own test suite uses.
3. Raw CSS selectors -- avoid.

Test IDs below were read from streamlit/streamlit's e2e_playwright/shared/
app_utils.py. They are stable across recent versions, but if a getter finds
nothing, that is the first thing to re-check against the installed Streamlit.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Locator, Page, expect

from shared.waits import wait_for_app_run

LabelType = "str | re.Pattern[str]"


# --------------------------------------------------------------------------
# Finding widgets
# --------------------------------------------------------------------------


def get_by_key(page: Page, key: str) -> Locator:
    """Find a widget by the `key=` it was given in the QC-Studio source.

    Streamlit renders `st.text_input(..., key="rater_id")` with the CSS class
    `st-key-rater_id`. The most robust selector available -- add keys to
    QC-Studio widgets you test often.
    """
    class_name = "st-key-" + re.sub(r"[^a-zA-Z0-9_-]", "-", key.strip())
    return page.locator(f".{class_name}")


def get_text_input(page: Page, label: LabelType) -> Locator:
    """The text input whose label matches (e.g. MESSAGES["rater_id_prompt"])."""
    element = page.get_by_test_id("stTextInput").filter(has_text=label)
    expect(element).to_be_visible()
    return element


def get_text_area(page: Page, label: LabelType) -> Locator:
    element = page.get_by_test_id("stTextArea").filter(has_text=label)
    expect(element).to_be_visible()
    return element


def get_radio_group(page: Page, label: LabelType) -> Locator:
    """A whole radio group, located by its question text.

    e.g. get_radio_group(app, MESSAGES["experience_prompt"])
    """
    label_locator = page.get_by_test_id("stWidgetLabel").filter(has_text=label)
    element = page.get_by_test_id("stRadio").filter(has=label_locator)
    expect(element).to_be_visible()
    return element


def get_radio_option(page: Page, option_label: LabelType) -> Locator:
    """A single option inside a radio group (e.g. an EXPERIENCE_LEVELS entry)."""
    element = page.get_by_test_id("stRadioOption").filter(has_text=option_label)
    expect(element).to_be_visible()
    return element


def get_checkbox(page: Page, label: LabelType) -> Locator:
    """A checkbox, located by its label -- QC-Studio's panel selection."""
    element = page.get_by_test_id("stCheckbox").filter(has_text=label)
    expect(element).to_be_visible()
    return element


def get_button(page: Page, label: LabelType) -> Locator:
    """A standalone button (not a form submit button)."""
    element = page.get_by_test_id("stButton").filter(has_text=label).locator("button")
    expect(element).to_be_visible()
    return element


def get_form_submit_button(page: Page, label: LabelType) -> Locator:
    """A form's submit button.

    QC-Studio's rater form uses st.form_submit_button, which renders with a
    *different* test id than st.button -- using get_button here finds nothing.
    """
    element = page.get_by_test_id("stFormSubmitButton").filter(has_text=label).locator("button")
    expect(element).to_be_visible()
    return element


def get_file_uploader(page: Page) -> Locator:
    """The file uploader's hidden <input type=file>, ready for set_input_files."""
    return page.get_by_test_id("stFileUploaderDropzoneInput")


# --------------------------------------------------------------------------
# Interacting
# --------------------------------------------------------------------------
# Each of these waits for the rerun it causes, so a test can't forget to.


def click_button(page: Page, label: LabelType) -> None:
    """Click a button and wait for the resulting rerun to finish."""
    get_button(page, label).click()
    wait_for_app_run(page)


def click_form_submit(page: Page, label: LabelType) -> None:
    """Submit a form and wait for the resulting rerun to finish."""
    get_form_submit_button(page, label).click()
    wait_for_app_run(page)


def fill_text_input(page: Page, label: LabelType, value: str) -> None:
    """Type into a text input.

    No rerun wait: inside an st.form nothing is submitted until the submit
    button is pressed, so there is nothing to wait for yet.
    """
    get_text_input(page, label).locator("input").fill(value)


def check_checkbox(page: Page, label: LabelType) -> None:
    """Tick a checkbox if it isn't already ticked, then wait for the rerun."""
    checkbox = get_checkbox(page, label).locator("input")
    if not checkbox.is_checked():
        checkbox.check()
        wait_for_app_run(page)


def uncheck_checkbox(page: Page, label: LabelType) -> None:
    checkbox = get_checkbox(page, label).locator("input")
    if checkbox.is_checked():
        checkbox.uncheck()
        wait_for_app_run(page)


def choose_radio_option(page: Page, option_label: LabelType) -> None:
    get_radio_option(page, option_label).click()
    wait_for_app_run(page)


def upload_file(page: Page, file_path: Path) -> None:
    """Attach a file to the uploader and wait for QC-Studio to process it."""
    get_file_uploader(page).set_input_files(str(file_path))
    wait_for_app_run(page)


# --------------------------------------------------------------------------
# Asserting
# --------------------------------------------------------------------------


def expect_text_visible(page: Page, text: LabelType) -> None:
    """Assert some copy is on screen.

    Pass the value from ui/constants.py, never a hand-typed string:

        expect_text_visible(app, ERROR_MESSAGES["invalid_rater_id"])
    """
    expect(page.get_by_text(text)).to_be_visible()
