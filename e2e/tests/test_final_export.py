"""Tests for the final export on the congratulations page.

Spec: e2e/specs/004-final-export-overwrite-guard.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from constants import MESSAGES, QC_RATINGS, SUCCESS_MESSAGES
from shared.app_utils import choose_radio_option, click_button, expect_text_visible, get_by_key
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow

#: The default config holds a single subject, so rating it and pressing Next
#: completes the cohort and lands on the congratulations page.
CONFIRM_OVERWRITE_KEY = "confirm_congrats_overwrite"


def _finish_qc(app: Page, rater_id: str) -> None:
    """Rate the only subject and advance, which completes the cohort.

    The rater ID becomes part of the export filename, so each test needs its
    own: tests in a module share one output directory, and `output_files`
    reports only what *this* test added -- re-exporting to a path a previous
    test created would look like nothing was written.
    """
    start_qc_session(app, rater_id)
    choose_radio_option(app, QC_RATINGS[0])
    click_button(app, MESSAGES["next_button"])


def test_export_writes_the_results_file(app: Page, output_files) -> None:
    """Given a rater who has finished QC,
    When they click "💾 Export Final Results",
    Then the exported-results message appears and a file holding the rating
    has been written.
    """
    _finish_qc(app, "export-writes")

    click_button(app, MESSAGES["export_results_button"])

    expect_text_visible(app, SUCCESS_MESSAGES["records_exported"].split("{")[0].strip())
    written = [p for p in output_files() if p.suffix in {".csv", ".tsv"}]
    assert written, "export wrote no file"
    assert any(QC_RATINGS[0] in p.read_text() for p in written)


def test_exporting_over_an_existing_file_needs_confirmation(app: Page, output_files) -> None:
    """Given a rater who has already exported once, so the file exists,
    When they click "💾 Export Final Results" again at the same path,
    Then they are warned the file would be overwritten and offered an
    explicit confirm button, rather than it being overwritten silently.
    """
    _finish_qc(app, "export-overwrite")
    click_button(app, MESSAGES["export_results_button"])
    exported = {p for p in output_files() if p.suffix in {".csv", ".tsv"}}
    assert exported, "setup failed: nothing exported on the first click"

    click_button(app, MESSAGES["export_results_button"])

    expect(get_by_key(app, CONFIRM_OVERWRITE_KEY)).to_be_visible()
    expect_text_visible(app, MESSAGES["overwrite_pending_warning"].split("{")[0].strip())
    # No second file: the guard stops the write until the rater confirms.
    assert {p for p in output_files() if p.suffix in {".csv", ".tsv"}} == exported

    click_button(app, MESSAGES["overwrite_confirm_button"])

    expect_text_visible(app, SUCCESS_MESSAGES["records_exported"].split("{")[0].strip())
