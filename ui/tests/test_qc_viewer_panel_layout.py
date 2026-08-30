"""Tests for display_qc_viewers' panel-layout branch selection.

Kept separate from test_qc_viewer.py, which currently fails to collect
(pre-existing, unrelated: missing AUTOPLAY_ADVANCE_GRACE_SECONDS import).
"""

from unittest.mock import MagicMock, patch

import pytest

from components import qc_viewer
from managers.session_manager import SessionManager

pytestmark = pytest.mark.unit


@pytest.fixture
def patched_layout(monkeypatch):
    """Stub every collaborator display_qc_viewers calls into, so only the
    branch-selection logic itself is under test."""
    monkeypatch.setattr(qc_viewer, "parse_qc_config", lambda *a, **k: {"display_name": "Task", "base_mri_image_path": None})
    monkeypatch.setattr(qc_viewer, "_display_svg_panel", MagicMock())
    monkeypatch.setattr(qc_viewer, "display_iqm_distribution_panel", MagicMock())
    monkeypatch.setattr(qc_viewer, "_display_niivue_with_secondary_panel", MagicMock())
    monkeypatch.setattr(qc_viewer, "_display_niivue_full_width", MagicMock())
    monkeypatch.setattr(qc_viewer, "_display_qc_rating_for_task", MagicMock())
    monkeypatch.setattr(qc_viewer, "_render_autoplay_countdown_main_banner", MagicMock())
    monkeypatch.setattr(qc_viewer.st, "subheader", MagicMock())
    monkeypatch.setattr(qc_viewer.st, "divider", MagicMock())
    return qc_viewer


def _call(selected_panels):
    with patch.object(SessionManager, "get_selected_panels", return_value=selected_panels):
        qc_viewer.display_qc_viewers(
            dataset_dir="sample_data",
            qc_config_path="qc.json",
            substitution_values={},
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="mriqc",
            qc_task="dwi_iqm_qc",
        )


def test_svg_and_iqm_both_render_when_no_niivue_image(patched_layout):
    """A task with no base_mri_image_path (so task_has_niivue is False) and
    both SVG and IQM panels selected should render both, not just SVG.

    Regression test: the elif-chain used to only have single-panel branches
    for the no-niivue case, so SVG (checked by default) always won and IQM
    silently never rendered even when its checkbox was also checked."""
    _call({"niivue": False, "svg": True, "iqm": True})

    patched_layout._display_svg_panel.assert_called_once()
    patched_layout.display_iqm_distribution_panel.assert_called_once()


def test_svg_only_renders_svg_when_no_niivue_image(patched_layout):
    _call({"niivue": False, "svg": True, "iqm": False})

    patched_layout._display_svg_panel.assert_called_once()
    patched_layout.display_iqm_distribution_panel.assert_not_called()


def test_iqm_only_renders_iqm_when_no_niivue_image(patched_layout):
    _call({"niivue": False, "svg": False, "iqm": True})

    patched_layout._display_svg_panel.assert_not_called()
    patched_layout.display_iqm_distribution_panel.assert_called_once()


def test_neither_renders_when_no_niivue_image_and_nothing_selected(patched_layout):
    _call({"niivue": False, "svg": False, "iqm": False})

    patched_layout._display_svg_panel.assert_not_called()
    patched_layout.display_iqm_distribution_panel.assert_not_called()
