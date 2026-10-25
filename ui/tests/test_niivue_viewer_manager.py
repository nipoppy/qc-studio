"""Unit tests for NiivueViewerManager."""

from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

from constants import VIEW_MODES, OVERLAY_COLORMAPS, DEFAULT_OVERLAY_OPACITY
from managers.niivue_viewer_manager import NiivueViewerConfig, NiivueViewerManager

pytestmark = pytest.mark.unit


class TestNiivueViewerConfig:
    """Tests for NiivueViewerConfig class."""

    def test_config_initialization(self):
        """Test initializing a NiivueViewerConfig."""
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="cool",
            show_crosshair=True,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=False,
        )

        assert config.view_mode == "multiplanar"
        assert config.overlay_colormap == "cool"
        assert config.show_crosshair is True
        assert config.show_overlay is False

    def test_config_to_settings_dict(self):
        """Test converting config to settings dictionary."""
        config = NiivueViewerConfig(
            view_mode="axial",
            overlay_colormap="warm",
            show_crosshair=True,
            radiological=True,
            show_colorbar=False,
            interpolation=False,
            show_overlay=True,
        )

        settings = config.to_settings_dict()

        assert isinstance(settings, dict)
        assert settings["crosshair"] is True
        assert settings["radiological"] is True
        assert settings["colorbar"] is False
        assert settings["interpolation"] is False

    def test_config_get_viewer_key(self):
        """Test generating viewer key from config."""
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="grey",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=True,
        )

        key = config.get_viewer_key()

        assert isinstance(key, str)
        assert "multiplanar" in key
        assert "grey" in key
        assert key.startswith("niivue_")

    def test_viewer_key_uniqueness(self):
        """Test that different configs produce different viewer keys."""
        config1 = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="grey",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=True,
        )

        config2 = NiivueViewerConfig(
            view_mode="axial",
            overlay_colormap="cool",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=False,
        )

        key1 = config1.get_viewer_key()
        key2 = config2.get_viewer_key()

        assert key1 != key2


class TestBuildOverlayList:
    """Tests for building overlay configuration."""

    def test_build_overlay_list_with_overlay_enabled(self):
        """Test building overlay list when overlay is enabled."""
        mri_data = {"base_mri_image_bytes": b"fake", "overlay_mri_image_bytes": b"fake_overlay"}
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="cool",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=True,
        )

        overlays = NiivueViewerManager.build_overlay_list(mri_data, config)

        assert len(overlays) == 1
        assert overlays[0]["name"] == "overlay"
        assert overlays[0]["colormap"] == "cool"
        assert overlays[0]["opacity"] == DEFAULT_OVERLAY_OPACITY

    def test_build_overlay_list_with_overlay_disabled(self):
        """Test building overlay list when overlay is disabled."""
        mri_data = {"base_mri_image_bytes": b"fake", "overlay_mri_image_bytes": b"fake_overlay"}
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="cool",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=False,
        )

        overlays = NiivueViewerManager.build_overlay_list(mri_data, config)

        assert len(overlays) == 0

    def test_build_overlay_list_no_overlay_data(self):
        """Test building overlay list when overlay data is missing."""
        mri_data = {"base_mri_image_bytes": b"fake"}
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="cool",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=True,
        )

        overlays = NiivueViewerManager.build_overlay_list(mri_data, config)

        assert len(overlays) == 0


class TestBuildViewerKwargs:
    """Tests for building viewer component kwargs."""

    def test_build_viewer_kwargs_basic(self):
        """Test building basic viewer kwargs."""
        from pathlib import Path

        mri_data = {"base_mri_image_bytes": b"fake_nifti", "base_mri_image_path": Path("/path/to/base.nii")}
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="grey",
            show_crosshair=True,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=False,
        )

        kwargs = NiivueViewerManager.build_viewer_kwargs(mri_data, config)

        assert "nifti_data" in kwargs
        assert "filename" in kwargs
        assert "height" in kwargs
        assert "view_mode" in kwargs
        assert kwargs["view_mode"] == "multiplanar"
        assert kwargs["nifti_data"] == b"fake_nifti"

    def test_build_viewer_kwargs_with_overlay(self):
        """Test building viewer kwargs with overlay."""
        from pathlib import Path

        mri_data = {
            "base_mri_image_bytes": b"fake_nifti",
            "base_mri_image_path": Path("/path/to/base.nii"),
            "overlay_mri_image_bytes": b"fake_overlay",
        }
        config = NiivueViewerConfig(
            view_mode="axial",
            overlay_colormap="warm",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=True,
        )

        kwargs = NiivueViewerManager.build_viewer_kwargs(mri_data, config)

        assert "overlays" in kwargs
        assert len(kwargs["overlays"]) == 1

    def test_build_viewer_kwargs_no_overlay(self):
        """Test that overlays key is not present when no overlay."""
        from pathlib import Path

        mri_data = {"base_mri_image_bytes": b"fake_nifti", "base_mri_image_path": Path("/path/to/base.nii")}
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="grey",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=False,
        )

        kwargs = NiivueViewerManager.build_viewer_kwargs(mri_data, config)

        assert "overlays" not in kwargs or len(kwargs.get("overlays", [])) == 0


class TestViewerConfigurationValidation:
    """Tests for viewer configuration validation."""

    def test_valid_view_modes(self):
        """Test that all valid view modes can be used."""
        for view_mode in VIEW_MODES:
            config = NiivueViewerConfig(
                view_mode=view_mode,
                overlay_colormap="grey",
                show_crosshair=False,
                radiological=False,
                show_colorbar=True,
                interpolation=True,
                show_overlay=False,
            )
            assert config.view_mode == view_mode

    def test_valid_colormaps(self):
        """Test that all valid colormaps can be used."""
        for colormap in OVERLAY_COLORMAPS:
            config = NiivueViewerConfig(
                view_mode="multiplanar",
                overlay_colormap=colormap,
                show_crosshair=False,
                radiological=False,
                show_colorbar=True,
                interpolation=True,
                show_overlay=False,
            )
            assert config.overlay_colormap == colormap


class TestNiivueViewerManagerIntegration:
    """Integration tests for NiivueViewerManager."""

    def test_complete_config_workflow(self):
        """Test a complete configuration workflow."""
        from pathlib import Path

        # Create config
        config = NiivueViewerConfig(
            view_mode="sagittal",
            overlay_colormap="cool",
            show_crosshair=True,
            radiological=True,
            show_colorbar=False,
            interpolation=True,
            show_overlay=True,
        )

        # Verify config properties
        settings = config.to_settings_dict()
        assert settings["crosshair"] is True
        assert settings["radiological"] is True

        # Verify key generation
        key = config.get_viewer_key()
        assert "sagittal" in key
        assert "cool" in key

        # Create MRI data
        mri_data = {"base_mri_image_bytes": b"nifti_data", "base_mri_image_path": Path("test.nii"), "overlay_mri_image_bytes": b"overlay_data"}

        # Build kwargs
        kwargs = NiivueViewerManager.build_viewer_kwargs(mri_data, config)

        assert kwargs["view_mode"] == "sagittal"
        assert "overlays" in kwargs
        assert len(kwargs["overlays"]) == 1


class TestBuildConfigFromWidgetState:
    """Tests for reading the config straight from widget session state."""

    @pytest.fixture
    def widget_state(self):
        """Patch ``streamlit.session_state`` with a plain dict."""
        state = {}
        with patch.object(st, "session_state", state):
            yield state

    @pytest.mark.parametrize(
        "state_suffix,expected_key",
        [("", "niivue_config"), ("anat_wf_qc", "niivue_config_anat_wf_qc")],
    )
    def test_config_state_key(self, state_suffix, expected_key):
        """Config keys follow the historical single/task-suffixed format."""
        assert NiivueViewerManager.config_state_key(state_suffix) == expected_key

    def test_control_widget_keys_follow_existing_format(self):
        """Default widget keys follow the existing format."""
        assert NiivueViewerManager.control_widget_keys() == {
            "show_overlay": "niivue_ctrl_show_overlay_default",
            "view_mode": "niivue_ctrl_view_mode_default",
            "overlay_colormap": "niivue_ctrl_overlay_cmap_default",
        }

    def test_returns_current_widget_values(self, widget_state):
        """Widget values already in session state override defaults."""
        keys = NiivueViewerManager.control_widget_keys()
        widget_state[keys["view_mode"]] = "axial"
        widget_state[keys["overlay_colormap"]] = "warm"
        widget_state[keys["show_overlay"]] = False

        config = NiivueViewerManager.build_config_from_widget_state()

        assert config.view_mode == "axial"
        assert config.overlay_colormap == "warm"
        assert config.show_overlay is False

    def test_defaults_before_widget_first_renders(self):
        """On the very first render no widget key exists yet."""
        config = NiivueViewerManager.build_config_from_widget_state(has_overlay=True)

        assert config.view_mode == VIEW_MODES[0]
        assert config.overlay_colormap == OVERLAY_COLORMAPS[0]
        assert config.show_overlay is True

    @pytest.mark.parametrize("has_overlay", [True, False])
    def test_show_overlay_without_overlay(self, has_overlay):
        """has_overlay follows show_overlay by default."""
        assert NiivueViewerManager.build_config_from_widget_state(has_overlay=has_overlay).show_overlay is has_overlay

    def test_show_overlay_falls_back_to_false_when_no_overlay_available(self, widget_state):
        """has_overlay does not override the widget state."""
        keys = NiivueViewerManager.control_widget_keys()
        widget_state[keys["show_overlay"]] = True
        assert NiivueViewerManager.build_config_from_widget_state(has_overlay=False).show_overlay is True

    def test_carries_ui_less_settings_forward(self, widget_state):
        """The four settings with no widgets survive across widget changes."""
        stored = NiivueViewerConfig(
            view_mode="axial",
            overlay_colormap="cool",
            show_crosshair=True,
            radiological=True,
            show_colorbar=False,
            interpolation=False,
            show_overlay=True,
        )
        widget_state[NiivueViewerManager.config_state_key()] = stored
        widget_state[NiivueViewerManager.control_widget_keys()["view_mode"]] = "sagittal"

        config = NiivueViewerManager.build_config_from_widget_state()

        assert config.view_mode == "sagittal"
        assert config.show_crosshair is True
        assert config.radiological is True
        assert config.show_colorbar is False
        assert config.interpolation is False

    def test_task_suffix_uses_isolated_keys(self, widget_state):
        """Multi-task pages keep independent widget values and configs."""
        default_keys = NiivueViewerManager.control_widget_keys()
        task_keys = NiivueViewerManager.control_widget_keys("anat_wf_qc")
        assert task_keys != default_keys

        widget_state[default_keys["view_mode"]] = "axial"
        widget_state[task_keys["view_mode"]] = "sagittal"

        assert NiivueViewerManager.build_config_from_widget_state().view_mode == "axial"
        assert NiivueViewerManager.build_config_from_widget_state("anat_wf_qc").view_mode == "sagittal"
        assert NiivueViewerManager.config_state_key("anat_wf_qc") != NiivueViewerManager.config_state_key()

    def test_ui_less_settings_defaults_without_stored_config(self):
        """The four settings with no widgets fall back to the defaults."""
        config = NiivueViewerManager.build_config_from_widget_state(has_overlay=False)

        assert config.view_mode == VIEW_MODES[0]
        assert config.overlay_colormap == OVERLAY_COLORMAPS[0]
        assert config.show_crosshair is False
        assert config.radiological is False
        assert config.show_colorbar is True
        assert config.interpolation is True
        assert config.show_overlay is False


class TestRenderControlsPanel:
    """Tests for the controls panel's initial values."""

    @staticmethod
    def _run_panel(session_state, has_overlay=False):
        """Run the panel against ``session_state`` with Streamlit-like widget stubs."""

        def _checkbox(label, value=False, key=None, **kwargs):
            return session_state.get(key, value)

        def _selectbox(label, options, index=0, key=None, **kwargs):
            return session_state.get(key, options[index])

        mock_st = MagicMock()
        mock_st.session_state = session_state
        mock_st.checkbox.side_effect = _checkbox
        mock_st.selectbox.side_effect = _selectbox

        with patch("managers.niivue_viewer_manager.st", mock_st):
            return NiivueViewerManager.render_controls_panel(has_overlay=has_overlay)

    @pytest.mark.parametrize("has_overlay", [True, False])
    def test_first_render_overlay_toggle_follows_has_overlay(self, has_overlay):
        """The toggle use use has_overlay as its default."""
        config = self._run_panel({}, has_overlay=has_overlay)

        assert config.show_overlay is has_overlay

    def test_first_render_uses_option_list_defaults(self):
        """The other controls fall back to the first entry of their option lists."""
        config = self._run_panel({})

        assert config.view_mode == VIEW_MODES[0]
        assert config.overlay_colormap == OVERLAY_COLORMAPS[0]

    def test_stored_config_seeds_the_widgets(self):
        """A stored config supplies the value/index hints for the widgets."""
        state = {
            NiivueViewerManager.config_state_key(): NiivueViewerConfig(
                view_mode="axial",
                overlay_colormap="warm",
                show_crosshair=False,
                radiological=False,
                show_colorbar=True,
                interpolation=True,
                show_overlay=True,
            )
        }

        config = self._run_panel(state, has_overlay=False)

        assert config.view_mode == "axial"
        assert config.overlay_colormap == "warm"
        assert config.show_overlay is True
        assert state[NiivueViewerManager.config_state_key()] is config

    def test_widget_state_wins_over_stored_config(self):
        """Hints are ignored once the widget already holds a value."""
        keys = NiivueViewerManager.control_widget_keys()
        state = {
            NiivueViewerManager.config_state_key(): NiivueViewerConfig(
                view_mode="axial",
                overlay_colormap="warm",
                show_crosshair=False,
                radiological=False,
                show_colorbar=True,
                interpolation=True,
                show_overlay=True,
            ),
            keys["view_mode"]: "sagittal",
            keys["overlay_colormap"]: "cool",
            keys["show_overlay"]: False,
        }

        config = self._run_panel(state, has_overlay=True)

        assert config.view_mode == "sagittal"
        assert config.overlay_colormap == "cool"
        assert config.show_overlay is False

    @pytest.mark.parametrize("has_overlay", [True, False])
    def test_panel_and_builder_agree_on_first_render(self, has_overlay):
        """Rendering the panel must not change what the viewer sees on that rerun."""
        state = {}
        with patch("managers.niivue_viewer_manager.st.session_state", state):
            panel_config = self._run_panel(state, has_overlay=has_overlay)
            builder_config = NiivueViewerManager.build_config_from_widget_state(has_overlay=has_overlay)

        assert builder_config.view_mode == panel_config.view_mode
        assert builder_config.overlay_colormap == panel_config.overlay_colormap
        assert builder_config.show_overlay is panel_config.show_overlay
