"""Getting the app into a state a test can start from.

`app_utils` works at the level of one widget; this module works at the level
of a rater's journey. Anything more than one test needs in order to *reach*
the scenario it is really about belongs here, so the setup is described once
and each test opens with a single readable line.
"""

from __future__ import annotations

from playwright.sync_api import Page

from constants import MESSAGES, PANEL_CONFIG
from shared.app_utils import (
    click_button,
    click_form_submit,
    fill_text_input,
    set_slider_value,
    uncheck_checkbox,
)

#: The landing page's autoplay slider range. Kept here so a change to it
#: breaks in one place rather than in every test that sets a duration.
AUTOPLAY_SLIDER_MIN = 5
AUTOPLAY_SLIDER_MAX = 15

#: Panels left off by default in `start_qc_session`. Niivue renders a real 3D
#: MRI volume client-side; that takes tens of seconds, and `wait_for_app_run`
#: blocks on the loading skeleton for all of it, on every rerun. Tests that
#: are not about the 3D viewer should not pay for it -- see
#: `notes-autoplay-test-debugging.md`. Spec 014, which is about panel
#: rendering, is the one test that should override this.
SLOW_PANELS = ("niivue",)


def start_qc_session(
    page: Page,
    rater_id: str = "e2e-tester",
    *,
    autoplay_duration: int | None = None,
    panels_off: tuple[str, ...] = SLOW_PANELS,
) -> None:
    """Fill in the rater form and land on the QC viewer, on the first subject.

    Args:
        rater_id: any string without spaces; the app only checks it is
            non-empty once whitespace is stripped.
        autoplay_duration: seconds to set the autoplay slider to before
            submitting. The slider sits inside the form, so it can only be set
            here, before the submit. Leave as None to keep the app's default.
        panels_off: panels to uncheck before submitting. Defaults to leaving
            the slow 3D viewer out; pass an empty tuple to keep every default
            panel.
    """
    fill_text_input(page, MESSAGES["rater_id_prompt"], rater_id)

    for panel in panels_off:
        uncheck_checkbox(page, PANEL_CONFIG[panel]["label"])

    if autoplay_duration is not None:
        set_slider_value(
            page,
            MESSAGES["autoplay_duration_label"],
            autoplay_duration,
            minimum=AUTOPLAY_SLIDER_MIN,
            maximum=AUTOPLAY_SLIDER_MAX,
        )

    click_form_submit(page, MESSAGES["rater_form_button"])


def start_autoplay(page: Page) -> None:
    """Press Play on the viewer, so the countdown is ticking."""
    click_button(page, MESSAGES["play_button"])
