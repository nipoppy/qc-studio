"""Tests for the sidebar subject list.

Spec: e2e/specs/016-rated-subject-marked-complete.md
Spec: e2e/specs/015-subject-search-filters-list.md
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from conftest import two_subject_qc_config as qc_config
from constants import MESSAGES, QC_RATINGS, SIDEBAR_SUBJECT_SEARCH_WIDGET_KEY
from shared.app_utils import (
    choose_radio_option,
    expect_text_visible,
    fill_text_input_and_blur,
    get_by_key,
)
from shared.flows import start_qc_session

pytestmark = pytest.mark.flow

#: Hardcoded in views/sidebar_cohort_nav.py -- there are no constants.py keys
#: for the completion marks.
DONE_MARK = "✅"
NOT_DONE_MARK = "⬜"

FIRST_ROW = "sidebar_cohort_nav_0"
SECOND_ROW = "sidebar_cohort_nav_1"


def test_rating_a_subject_marks_it_complete_in_the_list(app: Page) -> None:
    """Given a rater on the viewer where no subject has been rated yet,
    When they rate the subject on screen,
    Then that subject's row in the sidebar list changes to ✅, and the other
    subject's row still shows ⬜.
    """
    start_qc_session(app, "listmark-tester")

    expect(get_by_key(app, FIRST_ROW)).to_contain_text(NOT_DONE_MARK)
    expect(get_by_key(app, SECOND_ROW)).to_contain_text(NOT_DONE_MARK)

    choose_radio_option(app, QC_RATINGS[0])

    expect(get_by_key(app, FIRST_ROW)).to_contain_text(DONE_MARK)
    # Rating one subject must not mark the whole cohort done.
    expect(get_by_key(app, SECOND_ROW)).to_contain_text(NOT_DONE_MARK)


def test_searching_filters_the_subject_list(app: Page) -> None:
    """Given a rater on the viewer with two subjects in the cohort,
    When they type part of one subject's ID into the subject search box,
    Then only the matching subject's row is listed.

    And a query matching nothing shows the empty-search caption instead.
    """
    start_qc_session(app, "search-tester")

    first_subject = get_by_key(app, FIRST_ROW).inner_text()
    # The two demo subjects share no prefix, so either ID filters to one row.
    query = first_subject.split("·")[0].split()[-1]

    fill_text_input_and_blur(app, SIDEBAR_SUBJECT_SEARCH_WIDGET_KEY, query)

    expect(get_by_key(app, FIRST_ROW)).to_contain_text(query)
    expect(get_by_key(app, SECOND_ROW)).to_have_count(0)

    fill_text_input_and_blur(app, SIDEBAR_SUBJECT_SEARCH_WIDGET_KEY, "sub-DOES-NOT-EXIST")

    expect_text_visible(app, MESSAGES["sidebar_subjects_search_empty"])
    expect(get_by_key(app, FIRST_ROW)).to_have_count(0)
