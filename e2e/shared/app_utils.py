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
    """A single option inside a radio group (e.g. an EXPERIENCE_LEVELS entry).

    UNVERIFIED test id, corrected: the installed Streamlit version renders
    each option as a BaseWeb `<label data-baseweb="radio">`, not with a
    `stRadioOption` test id -- there's no such test id anywhere in this
    version's DOM. Re-check against the installed Streamlit if this stops
    matching.
    """
    element = page.locator('[data-baseweb="radio"]').filter(has_text=option_label)
    expect(element).to_be_visible()
    return element


def get_checkbox(page: Page, label: LabelType) -> Locator:
    """A checkbox, located by its label -- QC-Studio's panel selection."""
    element = page.get_by_test_id("stCheckbox").filter(has_text=label)
    expect(element).to_be_visible()
    return element


def get_slider(page: Page, label: LabelType) -> Locator:
    """A slider, located by its label (e.g. the autoplay duration slider)."""
    element = page.get_by_test_id("stSlider").filter(has_text=label)
    expect(element).to_be_visible()
    return element


def get_button(page: Page, label: LabelType) -> Locator:
    """A standalone button (not a form submit button).

    A button with a `help=` tooltip (e.g. Next, Previous) renders a second,
    hidden `<button>` alongside the real one -- part of Streamlit's tooltip
    positioning, not two widgets. ``:visible`` keeps this a single-element
    locator so strict mode (and `.click()`) still works for those buttons.
    """
    element = page.get_by_test_id("stButton").filter(has_text=label).locator("button:visible")
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
    """The file uploader's hidden <input type=file>, ready for set_input_files.

    UNVERIFIED: every other test id in this file was taken from Streamlit's own
    test suite, but that suite has no file-uploader helper, so this one is
    inferred. If CSV upload tests can't find the input, this is the first line
    to check -- inspect the DOM of st.file_uploader in the running app.
    """
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


def fill_text_area_and_blur(page: Page, label: LabelType, value: str) -> None:
    """Type into a text area and commit the value, then wait for the rerun.

    `st.text_area`'s `on_change` fires on blur or Ctrl+Enter, not on every
    keystroke -- `fill()` alone changes the DOM value but never notifies
    Streamlit. Tab moves focus to the next element, which blurs this one and
    triggers the commit.
    """
    box = get_text_area(page, label).locator("textarea")
    box.fill(value)
    box.press("Tab")
    wait_for_app_run(page)


def check_checkbox(page: Page, label: LabelType) -> None:
    """Tick a checkbox if it isn't already ticked, then wait for the rerun.

    Streamlit positions the native `<input>` off-screen (its styled `<label>`
    sibling is what's shown), which fails Playwright's actionability checks
    even with force=True. Clicking the visible `<label>` instead lets the
    browser's own label-forwards-to-input behaviour toggle it, which is what
    actually notifies Streamlit -- a raw dispatch_event on the hidden input
    changes its DOM `checked` property but never reaches the app's session
    state.
    """
    container = get_checkbox(page, label)
    checkbox = container.locator("input")
    if not checkbox.is_checked():
        container.locator("label").click()
        wait_for_app_run(page)


def uncheck_checkbox(page: Page, label: LabelType) -> None:
    container = get_checkbox(page, label)
    checkbox = container.locator("input")
    if checkbox.is_checked():
        container.locator("label").click()
        wait_for_app_run(page)


def set_slider_value(page: Page, label: LabelType, value: int, minimum: int, maximum: int) -> None:
    """Set a slider to an exact value with the keyboard, regardless of its current one.

    No rerun wait: like `fill_text_input`, this is meant for a slider still
    inside an `st.form` -- nothing reruns until the form is submitted. Drives
    the handle all the way to `minimum` first (ArrowLeft `maximum - minimum`
    times covers the whole range, so this works from any starting value, not
    just the widget's default), then steps up to `value` with ArrowRight.
    """
    handle = get_slider(page, label).get_by_role("slider")
    handle.focus()
    for _ in range(maximum - minimum):
        handle.press("ArrowLeft")
    for _ in range(value - minimum):
        handle.press("ArrowRight")


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


#: st.error/st.warning/st.success auto-extract a single leading emoji from
#: the message and render it as a separate icon, stripping it from the text
#: node -- so a constant like ERROR_MESSAGES["no_panel_selected"] (which is
#: authored with that emoji baked in) never appears verbatim in the DOM.
_LEADING_EMOJI_RE = re.compile(r"^[\U0001F300-\U0001FAFF☀-➿←-⇿️‍]+\s*")


def get_current_subject_label(page: Page) -> Locator:
    """The participant/session heading atop the QC viewer (e.g. "sub-01 · ses-01").

    Matches the format of ``utils.cohort.compact_session_label``, which is the
    only copy in the app that joins participant and session with "·" -- a
    stable marker for "which subject is currently on screen" without
    depending on any specific dataset's IDs.
    """
    element = page.get_by_text(re.compile(r"^sub-.*·.*$"))
    expect(element).to_be_visible()
    return element


def expect_text_visible(page: Page, text: LabelType) -> None:
    """Assert some copy is on screen.

    Pass the value from ui/constants.py, never a hand-typed string:

        expect_text_visible(app, ERROR_MESSAGES["invalid_rater_id"])

    Handles messages authored with a leading emoji (e.g.
    ERROR_MESSAGES["no_panel_selected"]) that Streamlit strips out and
    renders as a separate icon instead.
    """
    if isinstance(text, re.Pattern):
        expect(page.get_by_text(text)).to_be_visible()
        return

    stripped = _LEADING_EMOJI_RE.sub("", text)
    if stripped == text:
        expect(page.get_by_text(text)).to_be_visible()
        return

    pattern = re.compile("|".join(re.escape(candidate) for candidate in (text, stripped)))
    expect(page.get_by_text(pattern)).to_be_visible()
