"""Tests for a page showing more than one QC task (--qc_task all).

Spec: e2e/specs/013-multi-task-requires-every-rating.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from conftest import QCAppConfig
from constants import DEFAULT_QC_RATING_NONE, MESSAGES, QC_RATINGS
from shared.app_utils import choose_radio_option, click_button, current_subject_id, radio_options
from shared.waits import wait_for_app_run
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow


@pytest.fixture(scope="module")
def qc_config(tmp_path_factory: pytest.TempPathFactory) -> QCAppConfig:
    """Two subjects, and every task in qc_demo.json shown on one page.

    Two subjects matter here: with one, Next has no page to advance to and
    takes a different branch, so "did it advance" would not be a real
    question.
    """
    participants = tmp_path_factory.mktemp("multi_task_participants") / "participants.tsv"
    participants.write_text("participant_id\nsub-CMH0001\nsub-ED01\n")
    return QCAppConfig(qc_task="all", participant_list=str(participants))


def test_several_tasks_are_shown(app: Page) -> None:
    """With qc_task="all", the page shows a rating group per configured task.

    Guards the premise of the xfail below: if multi-task mode stopped
    rendering several tasks, that test would start "passing" for the wrong
    reason.
    """
    start_qc_session(app, "multitask-tester")

    assert radio_options(app, QC_RATINGS[0]).count() > 1


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG: the Next tooltip promises 'When more than one QC task is shown, "
        "set PASS, FAIL, or UNCERTAIN for every task before continuing', but "
        "nothing enforces it. Verified with the default QC rating set to None, "
        "so the unrated tasks really are unrated -- at the shipped default of "
        "PASS every task counts as rated and the gate would never be reached. "
        "Remove this marker once fixed."
    ),
)
def test_next_requires_every_task_to_be_rated(app: Page) -> None:
    """Given a page showing several QC tasks with only the first one rated,
    When the rater clicks Next,
    Then the app does not advance to the next subject.
    """
    # Without this the shipped default (PASS) pre-rates every task, so Next
    # advancing would prove nothing.
    choose_radio_option(app, DEFAULT_QC_RATING_NONE)
    start_qc_session(app, "multitask-gate-tester")
    subject = current_subject_id(app)

    radio_options(app, QC_RATINGS[0]).first.click()
    wait_for_app_run(app)
    click_button(app, MESSAGES["next_button"])

    assert current_subject_id(app) == subject
