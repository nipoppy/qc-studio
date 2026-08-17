"""Tests for sidebar cohort navigation layout."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from constants import MESSAGES, SIDEBAR_SUBJECT_LIST_HEIGHT

pytestmark = pytest.mark.unit


def _ctx_manager():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


@contextmanager
def _patch_sidebar_streamlit(order):
    mock_st = MagicMock()
    mock_st.sidebar = _ctx_manager()
    mock_st.container.return_value = _ctx_manager()
    mock_st.button.return_value = False

    def caption(text, *args, **kwargs):
        order.append(("caption", text))

    def divider():
        order.append(("divider", None))

    mock_st.caption.side_effect = caption
    mock_st.divider.side_effect = divider

    with (
        patch("views.sidebar_cohort_nav.st", mock_st),
        patch("views.sidebar_cohort_nav.SessionManager") as mock_sm,
    ):
        mock_sm.is_landing_page_complete.return_value = True
        mock_sm.get_current_page.return_value = 1
        mock_sm.participant_has_decided_qc.return_value = False
        mock_sm.is_autoplay_enabled.return_value = False
        yield mock_st, mock_sm


class TestSidebarCohortNavOrder:
    """Playback and page controls stay above a scrollable subject list."""

    def test_controls_render_before_subject_list(self):
        from views.sidebar_cohort_nav import render_sidebar_cohort_subjects

        order = []
        cohort = [
            {"participant_id": "sub-CMH0001", "session_id": "ses-01"},
            {"participant_id": "sub-CMH0001", "session_id": "ses-02"},
        ]
        nav_kwargs = {
            "current_page": 1,
            "total_participants": 2,
            "participant_id": "sub-CMH0001",
            "session_id": "ses-01",
            "qc_pipeline": "fmriprep",
            "qc_tasks": ["sdc_wf_qc"],
            "participant_ids": ["sub-CMH0001"],
            "qc_cohort": cohort,
        }

        def header(*args, **kwargs):
            order.append(("header", None))

        def controls(**kwargs):
            order.append(("controls", None))

        with _patch_sidebar_streamlit(order) as (mock_st, _mock_sm):
            with (
                patch("components.qc_viewer._display_qc_pagination_header", side_effect=header),
                patch("components.qc_viewer._display_qc_pagination_controls", side_effect=controls),
            ):
                render_sidebar_cohort_subjects(
                    qc_cohort=cohort,
                    total_participants=2,
                    qc_task="sdc_wf_qc",
                    qc_tasks=["sdc_wf_qc"],
                    prepend_navigation=True,
                    navigation_kwargs=nav_kwargs,
                )

        names = [name for name, _ in order]
        assert names[:3] == ["header", "controls", "divider"]
        assert "caption" in names
        assert names.index("controls") < names.index("caption")
        mock_st.container.assert_called_once_with(height=SIDEBAR_SUBJECT_LIST_HEIGHT, border=True)
        mock_st.caption.assert_called_with(MESSAGES["sidebar_subjects_header"])
        assert mock_st.button.call_count == 2
