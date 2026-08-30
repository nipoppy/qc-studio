"""Tests for qc_viewer helper utilities."""

import re
import time
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

from components import qc_viewer as qc_viewer_module
from components.qc_viewer import (
    _clean_filename,
    _render_autoplay_countdown_main_banner,
    try_autoplay_advance_if_due,
    AUTOPLAY_ADVANCE_GRACE_SECONDS,
    _on_rating_change,
    _record_qc_for_current_participant,
    _rating_widget_key,
    _notes_widget_key,
    _record_all_qc_tasks,
)
from managers.session_manager import SessionManager

pytestmark = pytest.mark.unit


@pytest.fixture
def autoplay_session_state():
    """Patch ``st.session_state`` with a real dict seeded for autoplay tests, and mock ``st.rerun``.

    Yields ``(state, mock_rerun)`` so tests can seed/inspect state directly and assert on
    whether ``st.rerun()`` (the app-refresh signal) was actually triggered.
    """
    state = {
        "current_page": 1,
        "qc_records": [],
        "rater_id": "rater1",
        "rater_experience": "Expert (>5 year experience)",
        "rater_fatigue": "Not at all",
        "notes_version": 0,
        "rating_version": 0,
        "autoplay_enabled": True,
        "autoplay_start_time": 0.0,
        "autoplay_duration": 5,
    }
    with patch.object(st, "session_state", state), patch.object(st, "rerun", MagicMock()) as mock_rerun:
        yield state, mock_rerun


class TestCleanFilename:
    """Tests for compact tab label generation."""

    def test_extracts_session_task_run_tokens(self):
        """Functional keys should prefer ses/task/run tokens."""
        filename = "figures_sub-CMH0001_ses-01_task-rest_run-01_svg"
        assert _clean_filename(filename) == "ses-01_task-rest_run-01"

    def test_strips_subject_prefix_for_anatomical_keys(self):
        """Anatomical keys should remove noisy subject-prefixed fragments."""
        filename = "figures_sub-CMH0001_figure_sub-CMH0001_dseg_svg"
        assert _clean_filename(filename) == "dseg"

    def test_removes_extension_suffix_when_no_structured_tokens(self):
        """Fallback path should remove synthetic image-type suffixes."""
        filename = "summary_plot_png"
        assert _clean_filename(filename) == "summary_plot"


# critical
class TestTryAutoplayAdvanceIfDue:
    """Tests for the autoplay poll's save-and-advance decision."""

    def test_does_not_advance_when_start_time_is_zero(self, autoplay_session_state):
        """``autoplay_start_time == 0`` means the countdown never started; nothing should happen."""
        state, mock_rerun = autoplay_session_state
        state["autoplay_start_time"] = 0.0

        try_autoplay_advance_if_due(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_tasks=["anat_wf_qc"],
            total_participants=3,
        )

        assert state["current_page"] == 1
        assert state["qc_records"] == []
        mock_rerun.assert_not_called()

    def test_does_not_advance_during_grace_period(self, autoplay_session_state):
        """Past ``duration`` but still inside the grace window should not advance yet."""
        state, mock_rerun = autoplay_session_state
        state["autoplay_duration"] = 5
        # elapsed ~5.1s: past duration, but inside duration + AUTOPLAY_ADVANCE_GRACE_SECONDS (5.3s)
        state["autoplay_start_time"] = time.time() - 5.1

        try_autoplay_advance_if_due(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_tasks=["anat_wf_qc"],
            total_participants=3,
        )

        assert state["current_page"] == 1
        assert state["qc_records"] == []
        mock_rerun.assert_not_called()

    def test_advances_and_records_all_task_ratings_when_due(self, autoplay_session_state):
        """Past the grace window, every task's pending rating should be saved and the page advances."""
        state, mock_rerun = autoplay_session_state
        state["autoplay_duration"] = 5
        state["autoplay_start_time"] = time.time() - (5 + AUTOPLAY_ADVANCE_GRACE_SECONDS + 1)
        state["qc_rating_anat_wf_qc_0"] = "PASS"
        state["qc_rating_func_wf_qc_0"] = "FAIL"

        try_autoplay_advance_if_due(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_tasks=["anat_wf_qc", "func_wf_qc"],
            total_participants=3,
        )

        saved = {r.qc_task: (r.participant_id, r.session_id, r.final_qc) for r in SessionManager.get_qc_records()}
        assert saved == {
            "anat_wf_qc": ("sub-CMH0001", "ses-01", "PASS"),
            "func_wf_qc": ("sub-CMH0001", "ses-01", "FAIL"),
        }
        assert state["current_page"] == 2
        assert state["autoplay_start_time"] > 0
        mock_rerun.assert_called_once()

    def test_last_page_due_records_and_stops_autoplay(self, autoplay_session_state):
        """On the last page, being due should still save ratings but stop autoplay instead of advancing."""
        state, mock_rerun = autoplay_session_state
        state["current_page"] = 3
        state["autoplay_duration"] = 5
        state["autoplay_start_time"] = time.time() - (5 + AUTOPLAY_ADVANCE_GRACE_SECONDS + 1)
        state["qc_rating_anat_wf_qc_0"] = "UNCERTAIN"

        try_autoplay_advance_if_due(
            participant_id="sub-CMH0003",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_tasks=["anat_wf_qc"],
            total_participants=3,
        )

        saved = {r.qc_task: (r.participant_id, r.session_id, r.final_qc) for r in SessionManager.get_qc_records()}
        assert saved == {"anat_wf_qc": ("sub-CMH0003", "ses-01", "UNCERTAIN")}
        assert state["autoplay_enabled"] is False
        assert state["autoplay_start_time"] == 0.0
        mock_rerun.assert_called_once()


class TestOnRatingChange:
    pass


class TestRecordQcForCurrentParticipant:
    pass


class TestRecordAllQcTasks:
    pass


class TestSaveQcRecord:
    @pytest.mark.skip(reason="Save CSV doesn't persist partial progress to disk — see filed issue (TODO: add issue #)")
    def test_save_qc_record_behavior_pending_issue_resolution(self):
        pass


class TestRatingPersistenceNearAutoAdvance:

    def test_saved_rating_servives_a_later_none_read(self, autoplay_session_state):
        """A saved rating should survive a later read of None (e.g. from a stale widget key)."""
        state, _ = autoplay_session_state

        state["rating_version"] = 0
        state[_rating_widget_key("anat_wf_qc", 0)] = "PASS"
        state[_notes_widget_key("anat_wf_qc", 0)] = "Good quality scan"

        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        saved = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert saved.final_qc == "PASS"
        assert saved.notes == "Good quality scan"

        state["rating_version"] = 1
        _record_qc_for_current_participant("sub-CMH0001", "ses-01", "fmriprep", "anat_wf_qc", rating=None, notes="")
        saved = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert saved.final_qc == "PASS"
        assert saved.notes == "Good quality scan"

    def test_record_all_qc_tasks_does_not_overwrite_saved_rating_after_version_bump(self, autoplay_session_state):
        """A saved rating should survive a later version bump and a None read from _record_all_qc_tasks."""
        state, _ = autoplay_session_state

        state["rating_version"] = 0
        state[_rating_widget_key("anat_wf_qc", 0)] = "PASS"
        state[_notes_widget_key("anat_wf_qc", 0)] = "Good quality scan"

        test_cohort = [
            {"participant_id": "sub-CMH0001", "session_id": "ses-01"},
            {"participant_id": "sub-CMH0002", "session_id": "ses-01"},
            {"participant_id": "sub-CMH0003", "session_id": "ses-01"},
        ]

        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        state["rating_version"] = 1
        state["autoplay_duration"] = 5
        state["autoplay_start_time"] = time.time() - (5 + AUTOPLAY_ADVANCE_GRACE_SECONDS + 1)

        try_autoplay_advance_if_due(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_tasks=["anat_wf_qc", "func_wf_qc"],
            total_participants=3,
            qc_cohort=test_cohort,
        )

        saved = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert saved.final_qc == "PASS"
        assert saved.notes == "Good quality scan"

    def test_full_advance_does_not_lose_rating_saved_via_on_change(self, autoplay_session_state):
        """A rating saved via _on_rating_change should survive a full advance (save + next page)."""
        state, mock_rerun = autoplay_session_state

        state["rating_version"] = 0
        state[_rating_widget_key("anat_wf_qc", 0)] = "PASS"
        state[_notes_widget_key("anat_wf_qc", 0)] = "Good quality scan"
        state["autoplay_duration"] = 5
        # Comfortably past duration + AUTOPLAY_ADVANCE_GRACE_SECONDS, same margin as the
        # sibling tests in TestTryAutoplayAdvanceIfDue above.
        state["autoplay_start_time"] = time.time() - (5 + AUTOPLAY_ADVANCE_GRACE_SECONDS + 1)

        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        try_autoplay_advance_if_due(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_tasks=["anat_wf_qc", "func_wf_qc"],
            total_participants=3,
        )

        saved = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert saved.final_qc == "PASS"
        assert saved.notes == "Good quality scan"
        assert state["current_page"] == 2
        mock_rerun.assert_called_once()

    def test_unrated_task_does_not_affect_a_different_tasks_saved_rating(self, autoplay_session_state):
        """On a multi-task page, one task's saved rating survives a flush that finds another task unrated."""
        state, _ = autoplay_session_state

        state["rating_version"] = 0
        state[_rating_widget_key("anat_wf_qc", 0)] = "PASS"
        state[_notes_widget_key("anat_wf_qc", 0)] = "Good quality scan"
        # func_wf_qc is never rated: no qc_rating_func_wf_qc_0 key is ever set in state.

        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        _record_all_qc_tasks("sub-CMH0001", "ses-01", "fmriprep", ["anat_wf_qc", "func_wf_qc"])

        rated = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert rated.final_qc == "PASS"
        assert rated.notes == "Good quality scan"
        unrated = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "func_wf_qc")
        assert unrated is None

    def test_notes_typed_after_rating_saved_are_merged_on_flush(self, autoplay_session_state):
        """Notes have no on_change; a later flush should merge them with the already-saved rating."""
        state, _ = autoplay_session_state

        state["rating_version"] = 0
        state[_rating_widget_key("anat_wf_qc", 0)] = "PASS"
        state[_notes_widget_key("anat_wf_qc", 0)] = ""

        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        saved = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert saved.final_qc == "PASS"
        assert saved.notes == ""

        # User types notes afterward; only a flush (not on_change) picks notes up.
        state[_notes_widget_key("anat_wf_qc", 0)] = "Motion artifact, borderline."
        _record_all_qc_tasks("sub-CMH0001", "ses-01", "fmriprep", ["anat_wf_qc"])

        saved = SessionManager.get_qc_record_for_participant("sub-CMH0001", "ses-01", "anat_wf_qc")
        assert saved.final_qc == "PASS"
        assert saved.notes == "Motion artifact, borderline."

    def test_changing_rating_before_advance_keeps_only_the_latest_value(self, autoplay_session_state):
        """Picking a different rating before advance should replace, not duplicate, the saved record."""
        state, _ = autoplay_session_state

        state["rating_version"] = 0
        state[_rating_widget_key("anat_wf_qc", 0)] = "PASS"
        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        state[_rating_widget_key("anat_wf_qc", 0)] = "FAIL"
        _on_rating_change(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            rver=0,
            nver=0,
        )

        matching = [
            r for r in SessionManager.get_qc_records() if r.participant_id == "sub-CMH0001" and r.session_id == "ses-01" and r.qc_task == "anat_wf_qc"
        ]
        assert len(matching) == 1
        assert matching[0].final_qc == "FAIL"


class TestDisplayQcPagination:
    @pytest.mark.skip(reason="Save CSV doesn't persist partial progress to disk — see filed issue (TODO: add issue #)")
    def test_save_csv_button_calls_save_qc_record(self):
        pass


# pure autoplay
class TestAutoplayCountdownTiming:
    """Tests for the countdown banner's time math (``_render_autoplay_countdown_main_banner``)."""

    FIXED_NOW = 1_700_000_000.0

    @staticmethod
    def _extract_secs_now(html: str) -> int:
        match = re.search(r'id="qc_autoplay_sec"[^>]*>(\d+)</span>', html)
        assert match, "countdown span not found in rendered HTML"
        return int(match.group(1))

    @staticmethod
    def _extract_deadline_ms(html: str) -> int:
        match = re.search(r"const deadline = (\d+);", html)
        assert match, "deadline constant not found in rendered HTML"
        return int(match.group(1))

    def test_secs_now_counts_down_correctly_mid_interval(self, autoplay_session_state, monkeypatch):
        """2s into a 5s countdown, the banner should show 3s remaining."""
        state, _ = autoplay_session_state
        monkeypatch.setattr(qc_viewer_module.time, "time", lambda: self.FIXED_NOW)
        mock_html = MagicMock()
        monkeypatch.setattr(qc_viewer_module.components, "html", mock_html)
        state["autoplay_duration"] = 5
        state["autoplay_start_time"] = self.FIXED_NOW - 2

        _render_autoplay_countdown_main_banner()

        assert self._extract_secs_now(mock_html.call_args.args[0]) == 3

    def test_secs_now_clamped_to_zero_past_duration(self, autoplay_session_state, monkeypatch):
        """Elapsed time past the configured duration should never show negative seconds."""
        state, _ = autoplay_session_state
        monkeypatch.setattr(qc_viewer_module.time, "time", lambda: self.FIXED_NOW)
        mock_html = MagicMock()
        monkeypatch.setattr(qc_viewer_module.components, "html", mock_html)
        state["autoplay_duration"] = 5
        state["autoplay_start_time"] = self.FIXED_NOW - 10

        _render_autoplay_countdown_main_banner()

        assert self._extract_secs_now(mock_html.call_args.args[0]) == 0

    def test_secs_now_equals_duration_at_countdown_start(self, autoplay_session_state, monkeypatch):
        """At elapsed == 0, the banner should show the full configured duration."""
        state, _ = autoplay_session_state
        monkeypatch.setattr(qc_viewer_module.time, "time", lambda: self.FIXED_NOW)
        mock_html = MagicMock()
        monkeypatch.setattr(qc_viewer_module.components, "html", mock_html)
        state["autoplay_duration"] = 5
        state["autoplay_start_time"] = self.FIXED_NOW

        _render_autoplay_countdown_main_banner()

        assert self._extract_secs_now(mock_html.call_args.args[0]) == 5

    def test_deadline_ms_matches_start_time_plus_duration(self, autoplay_session_state, monkeypatch):
        """The client-side JS deadline should be (start_time + duration) in milliseconds."""
        state, _ = autoplay_session_state
        monkeypatch.setattr(qc_viewer_module.time, "time", lambda: self.FIXED_NOW)
        mock_html = MagicMock()
        monkeypatch.setattr(qc_viewer_module.components, "html", mock_html)
        state["autoplay_duration"] = 7
        state["autoplay_start_time"] = self.FIXED_NOW - 1

        _render_autoplay_countdown_main_banner()

        expected_deadline_ms = int((state["autoplay_start_time"] + 7) * 1000)
        assert self._extract_deadline_ms(mock_html.call_args.args[0]) == expected_deadline_ms

    def test_does_not_render_when_autoplay_disabled(self, autoplay_session_state, monkeypatch):
        """No banner should be drawn once autoplay is turned off."""
        state, _ = autoplay_session_state
        mock_html = MagicMock()
        monkeypatch.setattr(qc_viewer_module.components, "html", mock_html)
        state["autoplay_enabled"] = False
        state["autoplay_start_time"] = time.time()

        _render_autoplay_countdown_main_banner()

        mock_html.assert_not_called()

    def test_does_not_render_when_start_time_not_set(self, autoplay_session_state, monkeypatch):
        """Autoplay enabled but not yet started (start_time == 0) should not draw a banner."""
        state, _ = autoplay_session_state
        mock_html = MagicMock()
        monkeypatch.setattr(qc_viewer_module.components, "html", mock_html)
        state["autoplay_enabled"] = True
        state["autoplay_start_time"] = 0.0

        _render_autoplay_countdown_main_banner()

        mock_html.assert_not_called()
