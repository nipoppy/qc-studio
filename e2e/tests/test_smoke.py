"""Smoke tests -- proof that the backbone works.

These are deliberately shallow. Their job is not to catch QC-Studio bugs but
to prove all four layers are wired up: the server starts, the browser reaches
it, the waits settle, and the widget getters find real elements.

Get these green before writing anything else. If a getter below finds nothing,
the test id in shared/app_utils.py needs re-checking against the installed
Streamlit version -- fix it there once and every future test benefits.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from constants import MESSAGES
from shared.app_utils import get_form_submit_button, get_text_input

pytestmark = pytest.mark.smoke


def test_app_boots(app: Page) -> None:
    """The landing page renders its welcome title.

    Proves: server started with valid arguments, browser connected, the
    websocket came up, and the script finished its first run.
    """
    expect(app.get_by_text(MESSAGES["welcome_title"])).to_be_visible()


def test_rater_form_is_reachable(app: Page) -> None:
    """The rater form's input and submit button can be located.

    Proves the selector helpers work. Note the submit button uses the form
    submit test id, not the plain button one.
    """
    get_text_input(app, MESSAGES["rater_id_prompt"])
    get_form_submit_button(app, MESSAGES["rater_form_button"])
