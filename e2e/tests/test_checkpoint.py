"""Tests for writing a checkpoint part-way through a QC session.

Spec: e2e/specs/009-checkpoint-during-qc.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from constants import INFO_MESSAGES, MESSAGES, QC_RATINGS, SUCCESS_MESSAGES
from shared.app_utils import choose_radio_option, click_button, expect_text_visible
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow


def test_checkpoint_writes_a_snapshot_of_the_ratings_so_far(app: Page, output_files) -> None:
    """Given a rater who has rated the subject on screen,
    When they click "🏁 Create checkpoint",
    Then the checkpoint-saved message appears and a .tsv holding that rating
    has been written under the output directory.

    And clicking again with nothing changed in between reports that there was
    nothing new to save, and writes no second file.
    """
    start_qc_session(app, "checkpoint-tester")
    choose_radio_option(app, QC_RATINGS[0])

    click_button(app, MESSAGES["create_checkpoint_button"])

    expect_text_visible(app, SUCCESS_MESSAGES["checkpoint_saved"])
    written = {p for p in output_files() if p.suffix == ".tsv"}
    assert len(written) == 1, f"expected one checkpoint, got {sorted(written)}"
    assert QC_RATINGS[0] in written.pop().read_text()

    click_button(app, MESSAGES["create_checkpoint_button"])

    expect_text_visible(app, INFO_MESSAGES["checkpoint_unchanged"])
    assert len({p for p in output_files() if p.suffix == ".tsv"}) == 1
