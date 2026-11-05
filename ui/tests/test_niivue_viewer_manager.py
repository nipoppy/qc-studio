"""Unit tests for NiivueViewerManager."""

import pytest
from managers.niivue_viewer_manager import NiivueViewerConfig, NiivueViewerManager
from constants import VIEW_MODES, OVERLAY_COLORMAPS, DEFAULT_OVERLAY_OPACITY

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


class TestNiftiCache:
    """Per-file NIfTI cache used by render_viewer."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from managers import niivue_viewer_manager

        niivue_viewer_manager._read_nifti_cached.clear()
        yield
        niivue_viewer_manager._read_nifti_cached.clear()

    @staticmethod
    def _write_nifti(path, shape):
        import nibabel as nib
        import numpy as np

        nib.save(nib.Nifti1Image(np.arange(np.prod(shape), dtype=np.int16).reshape(shape), np.eye(4)), str(path))
        return path

    def test_unchanged_file_is_read_once(self, tmp_path):
        from unittest.mock import patch
        from managers import niivue_viewer_manager as mgr

        path = self._write_nifti(tmp_path / "t1.nii.gz", (4, 4, 4))
        with patch.object(mgr, "read_nifti_bytes_for_niivue", wraps=mgr.read_nifti_bytes_for_niivue) as reader:
            first = mgr._read_nifti_for_niivue_cached(path)
            second = mgr._read_nifti_for_niivue_cached(path)

        assert reader.call_count == 1
        assert first[0] is second[0]
        assert first == (path.read_bytes(), False, None)

    def test_rewritten_file_is_reloaded(self, tmp_path):
        import os
        from managers import niivue_viewer_manager as mgr

        path = self._write_nifti(tmp_path / "t1.nii.gz", (4, 4, 4))
        before = mgr._read_nifti_for_niivue_cached(path)[0]
        self._write_nifti(path, (5, 5, 5))
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

        after = mgr._read_nifti_for_niivue_cached(path)[0]

        assert after != before
        assert after == path.read_bytes()

    def test_4d_reduced_and_oversize_flags_pass_through(self, tmp_path):
        from unittest.mock import patch
        from managers import niivue_viewer_manager as mgr

        bold = self._write_nifti(tmp_path / "bold.nii.gz", (4, 4, 4, 3))
        nbytes, reduced, err = mgr._read_nifti_for_niivue_cached(bold)
        assert nbytes is not None and reduced is True and err is None

        big = self._write_nifti(tmp_path / "big.nii.gz", (6, 6, 6))
        with patch("utils.data_loaders.NIIVUE_MAX_FILE_BYTES", 10):
            assert mgr._read_nifti_for_niivue_cached(big) == (None, True, "oversize")

    def test_render_viewer_uses_cache_for_base_and_overlay(self, tmp_path):
        from unittest.mock import MagicMock, patch
        from managers import niivue_viewer_manager as mgr

        self._write_nifti(tmp_path / "t1.nii.gz", (4, 4, 4))
        self._write_nifti(tmp_path / "mask.nii.gz", (4, 4, 4))
        qc_config = {"base_mri_image_path": "t1.nii.gz", "overlay_mri_image_path": "mask.nii.gz"}
        config = NiivueViewerConfig(
            view_mode="multiplanar",
            overlay_colormap="cool",
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=True,
        )
        viewer = MagicMock()

        with (
            patch.object(mgr, "niivue_viewer", viewer),
            patch.object(mgr, "read_nifti_bytes_for_niivue", wraps=mgr.read_nifti_bytes_for_niivue) as reader,
        ):
            # st.fragment skips its body outside a script run; call the undecorated function.
            render = NiivueViewerManager.render_viewer.__wrapped__
            for _ in range(3):
                render(str(tmp_path), qc_config, config, "sub-01", "ses-01")

        # Two files, each read once across three reruns.
        assert reader.call_count == 2
        assert viewer.call_count == 3
        kwargs = viewer.call_args.kwargs
        assert kwargs["nifti_data"] == (tmp_path / "t1.nii.gz").read_bytes()
        assert kwargs["overlays"][0]["data"] == (tmp_path / "mask.nii.gz").read_bytes()
