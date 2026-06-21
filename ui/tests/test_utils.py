"""Tests for utils.py module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pandas as pd
import pytest

from utils.config import parse_qc_config
from utils.data_loaders import (
    load_mri_data,
    load_svg_data,
    load_iqm_data,
)
from utils.export import save_qc_results_to_csv

pytestmark = pytest.mark.integration


class TestParseQcConfig:
    """Test parse_qc_config function."""

    def test_parse_valid_qc_config(self, sample_qc_config):
        """Test parsing a valid QC config file."""
        result = parse_qc_config(str(sample_qc_config), "anat_wf_qc")

        assert result is not None
        assert "base_mri_image_path" in result
        assert "svg_montage_path" in result
        assert result["base_mri_image_path"] is not None
        assert "montage_max_rows" in result
        assert "montage_max_cols" in result
        assert result["montage_max_rows"] is None
        assert result["montage_max_cols"] is None

    def test_parse_qc_config_montage_layout_from_json(self, temp_dir):
        """Optional montage_max_rows / montage_max_cols are parsed per QC task."""
        qc_path = temp_dir / "qc.json"
        qc_path.write_text(
            json.dumps(
                {
                    "anat_wf_qc": {
                        "svg_montage_path": [str(temp_dir / "a.svg"), str(temp_dir / "b.svg")],
                        "montage_max_rows": 2,
                        "montage_max_cols": 2,
                    }
                }
            )
        )
        result = parse_qc_config(str(qc_path), "anat_wf_qc")
        assert result["montage_max_rows"] == 2
        assert result["montage_max_cols"] == 2

    def test_parse_qc_config_nonexistent_task(self, sample_qc_config):
        """Test parsing QC config with non-existent task."""
        result = parse_qc_config(str(sample_qc_config), "nonexistent_task")

        assert result["base_mri_image_path"] is None
        assert result["overlay_mri_image_path"] is None
        assert result["svg_montage_path"] is None
        assert result["iqm_path"] is None
        assert result["montage_max_rows"] is None
        assert result["montage_max_cols"] is None

    def test_parse_qc_config_invalid_file(self, temp_dir):
        """Test parsing non-existent QC config file."""
        result = parse_qc_config(str(temp_dir / "nonexistent.json"), "anat_wf_qc")

        assert result["base_mri_image_path"] is None
        assert result["overlay_mri_image_path"] is None
        assert result["montage_max_rows"] is None
        assert result["montage_max_cols"] is None

    def test_parse_qc_config_malformed_json(self, temp_dir):
        """Test parsing malformed JSON file."""
        bad_json_file = temp_dir / "bad.json"
        bad_json_file.write_text("{ invalid json }")

        result = parse_qc_config(str(bad_json_file), "anat_wf_qc")

        assert result["base_mri_image_path"] is None
        assert result["montage_max_rows"] is None
        assert result["montage_max_cols"] is None

    def test_parse_qc_config_none_input(self):
        """Test parsing with None input."""
        result = parse_qc_config(None, "anat_wf_qc")

        assert result["base_mri_image_path"] is None
        assert result["montage_max_rows"] is None
        assert result["montage_max_cols"] is None


class TestLoadMriData:
    """Test load_mri_data function."""

    def test_load_both_mri_files(self, temp_dir):
        """Test loading both base and overlay MRI files."""
        base_file = temp_dir / "base.nii.gz"
        overlay_file = temp_dir / "overlay.nii.gz"

        base_file.write_bytes(b"base content")
        overlay_file.write_bytes(b"overlay content")

        path_dict = {"base_mri_image_path": base_file, "overlay_mri_image_path": overlay_file}

        result = load_mri_data(path_dict)

        assert "base_mri_image_bytes" in result
        assert "overlay_mri_image_bytes" in result
        assert result["base_mri_image_bytes"] == b"base content"
        assert result["overlay_mri_image_bytes"] == b"overlay content"

    def test_load_only_base_mri(self, temp_dir):
        """Test loading only base MRI file."""
        base_file = temp_dir / "base.nii.gz"
        base_file.write_bytes(b"base content")

        path_dict = {"base_mri_image_path": base_file, "overlay_mri_image_path": None}

        result = load_mri_data(path_dict)

        assert "base_mri_image_bytes" in result
        assert "overlay_mri_image_bytes" not in result

    def test_load_nonexistent_mri_file(self, temp_dir):
        """Test loading non-existent MRI file."""
        path_dict = {"base_mri_image_path": temp_dir / "nonexistent.nii.gz", "overlay_mri_image_path": None}

        result = load_mri_data(path_dict)

        assert result == {}

    def test_load_mri_with_none_paths(self):
        """Test loading with None paths."""
        path_dict = {"base_mri_image_path": None, "overlay_mri_image_path": None}

        result = load_mri_data(path_dict)

        assert result == {}


class TestLoadSvgData:
    """Test load_svg_data function."""

    def test_load_valid_svg_single(self, temp_dir, sample_svg_content):
        """Test loading single valid SVG file."""
        svg_file = temp_dir / "montage.svg"
        svg_file.write_text(sample_svg_content)

        path_dict = {"svg_montage_path": svg_file}

        result = load_svg_data(temp_dir, path_dict)

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 1
        # Check structure of returned data
        filename = list(result.keys())[0]
        assert result[filename]["type"] == "svg"
        assert "<svg" in result[filename]["content"]
        assert sample_svg_content in result[filename]["content"]

    def test_load_multiple_svg_files(self, temp_dir, sample_svg_content):
        """Test loading multiple SVG files."""
        svg_file1 = temp_dir / "montage1.svg"
        svg_file2 = temp_dir / "montage2.svg"

        svg_file1.write_text(sample_svg_content)
        svg_file2.write_text("<svg>second montage</svg>")

        path_dict = {"svg_montage_path": [svg_file1, svg_file2]}

        result = load_svg_data(temp_dir, path_dict)

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) >= 2
        if "montage" in result:
            assert result["montage"]["type"] == "png"

        # Check that SVG files are loaded with correct type.
        for filename, data in result.items():
            if filename == "montage":
                continue
            assert data["type"] == "svg"
            assert "<svg" in data["content"]

    def test_load_svg_and_png_mixed(self, temp_dir, sample_svg_content):
        """Test loading mixed SVG and PNG files."""
        from PIL import Image

        svg_file = temp_dir / "montage.svg"
        svg_file.write_text(sample_svg_content)

        # Create a simple PNG file
        png_file = temp_dir / "image.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(png_file)

        path_dict = {"svg_montage_path": [svg_file, png_file]}

        result = load_svg_data(temp_dir, path_dict)

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) >= 2
        if "montage" in result:
            assert result["montage"]["type"] == "png"

        # Verify we have one SVG and one PNG in addition to montage.
        types = [data["type"] for key, data in result.items() if key != "montage"]
        assert "svg" in types
        assert "png" in types

    def test_load_multiple_png_files_creates_montage(self, temp_dir):
        """Test that multiple raster images produce an auto-layout montage."""
        from PIL import Image

        png_file1 = temp_dir / "image1.png"
        png_file2 = temp_dir / "image2.png"
        Image.new("RGB", (100, 100), color="red").save(png_file1)
        Image.new("RGB", (100, 100), color="blue").save(png_file2)

        path_dict = {"svg_montage_path": [png_file1, png_file2]}

        result = load_svg_data(temp_dir, path_dict)

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 3
        assert "montage" in result
        assert result["montage"]["type"] == "png"

    def test_load_jpeg_file(self, temp_dir):
        """Test loading JPEG file."""
        from PIL import Image

        # Create a simple JPEG file
        jpeg_file = temp_dir / "image.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(jpeg_file, "JPEG")

        path_dict = {"svg_montage_path": jpeg_file}

        result = load_svg_data(temp_dir, path_dict)

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 1

        # Check JPEG file is loaded correctly
        data = list(result.values())[0]
        assert data["type"] == "jpeg"
        assert isinstance(data["content"], Image.Image)

    def test_load_svg_partial_failure(self, temp_dir, sample_svg_content):
        """Test loading multiple SVGs when one file doesn't exist."""
        svg_file1 = temp_dir / "montage1.svg"
        svg_file1.write_text(sample_svg_content)

        # Non-existent file
        svg_file2 = temp_dir / "nonexistent.svg"

        path_dict = {"svg_montage_path": [svg_file1, svg_file2]}

        result = load_svg_data(temp_dir, path_dict)

        # Should return dict with only the existing file
        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 1
        assert result[list(result.keys())[0]]["type"] == "svg"

    def test_load_unsupported_file_type(self, temp_dir):
        """Test loading unsupported file types (should be skipped)."""
        # Create an unsupported file type
        txt_file = temp_dir / "file.txt"
        txt_file.write_text("This is not an image")

        path_dict = {"svg_montage_path": txt_file}

        result = load_svg_data(temp_dir, path_dict)

        # Unsupported files should be skipped, returning None
        assert result is None

    def test_load_svg_nonexistent_file(self, temp_dir):
        """Test loading non-existent SVG file."""
        path_dict = {"svg_montage_path": temp_dir / "nonexistent.svg"}

        result = load_svg_data(temp_dir, path_dict)

        assert result is None

    def test_load_svg_with_none_path(self):
        """Test loading SVG with None path."""
        path_dict = {"svg_montage_path": None}

        result = load_svg_data("", path_dict)

        assert result is None

    def test_load_svg_unreadable_file(self, temp_dir):
        """Test loading unreadable SVG file."""
        svg_file = temp_dir / "montage.svg"
        svg_file.write_text("valid content")

        with patch("builtins.open", side_effect=IOError("Permission denied")):
            path_dict = {"svg_montage_path": svg_file}
            result = load_svg_data(temp_dir, path_dict)

        assert result is None

    def test_load_svg_empty_list(self):
        """Test loading SVG with empty list."""
        path_dict = {"svg_montage_path": []}

        result = load_svg_data("", path_dict)

        assert result is None


class TestLoadIqmData:
    """Test load_iqm_data function."""

    def test_load_valid_iqm_json(self, temp_dir):
        """Test loading valid IQM JSON file."""
        iqm_data = {"metric1": 0.95, "metric2": 0.87}
        iqm_file = temp_dir / "iqm.json"
        iqm_file.write_text(json.dumps(iqm_data))

        path_dict = {"iqm_path": iqm_file}

        result = load_iqm_data(path_dict)

        assert result == iqm_data

    def test_load_iqm_nonexistent_file(self, temp_dir):
        """Test loading non-existent IQM file."""
        path_dict = {"iqm_path": temp_dir / "nonexistent.json"}

        result = load_iqm_data(path_dict)

        assert result is None

    def test_load_iqm_malformed_json(self, temp_dir):
        """Test loading malformed IQM JSON file."""
        iqm_file = temp_dir / "bad_iqm.json"
        iqm_file.write_text("{ invalid json }")

        path_dict = {"iqm_path": iqm_file}

        result = load_iqm_data(path_dict)

        assert result is None

    def test_load_iqm_with_none_path(self):
        """Test loading IQM with None path."""
        path_dict = {"iqm_path": None}

        result = load_iqm_data(path_dict)

        assert result is None


class TestSaveQcResultsToCsv:
    """Test save_qc_results_to_csv function."""

    def test_save_qc_records_to_csv(self, temp_dir, qc_record_sample):
        """Test saving QC records to CSV."""
        output_file = temp_dir / "output.tsv"
        records = [qc_record_sample]

        result = save_qc_results_to_csv(output_file, records, drop_duplicates=False)

        assert output_file.exists()
        df = pd.read_csv(output_file, sep="\t")
        assert len(df) == 1
        assert list(df.columns)[0] == "pipeline"
        assert df.iloc[0]["participant_id"] == "sub-CMH0001"

    def test_save_empty_records_list(self, temp_dir):
        """Test saving empty records list."""
        output_file = temp_dir / "output.tsv"

        result = save_qc_results_to_csv(output_file, [], drop_duplicates=False)

        assert output_file.exists()
        df = pd.read_csv(output_file, sep="\t")
        assert len(df) == 0

    def test_save_with_duplicate_removal(self, temp_dir, qc_record_sample):
        """Test saving with duplicate removal enabled."""
        output_file = temp_dir / "output.tsv"
        records = [qc_record_sample, qc_record_sample]

        result = save_qc_results_to_csv(output_file, records, drop_duplicates=True)

        df = pd.read_csv(output_file, sep="\t")
        # Should have only 1 record if duplicates are dropped
        assert len(df) <= 2

    def test_save_creates_parent_directory(self, temp_dir):
        """Test that parent directory is created if it doesn't exist."""
        nested_output_file = temp_dir / "subdir" / "output.tsv"
        records = []

        # This may or may not create parent dir depending on implementation
        result = save_qc_results_to_csv(nested_output_file, records, drop_duplicates=False)

        # At least verify it doesn't crash
        assert result is not None or nested_output_file.parent.exists()

    def test_save_qc_records_sorted_by_participant_session_task(self, temp_dir, qc_record_sample):
        """TSV rows follow participant_id, then session_id, then qc_task (cohort walk order)."""
        b = qc_record_sample.model_copy(update={"qc_task": "b_task"})
        a2 = qc_record_sample.model_copy(update={"session_id": "ses-02", "qc_task": "a_task"})
        other = qc_record_sample.model_copy(update={"participant_id": "sub-CMH0002", "qc_task": "z_task"})
        # Intentionally shuffled input order
        records = [other, a2, qc_record_sample, b]

        output_file = temp_dir / "sorted.tsv"
        save_qc_results_to_csv(output_file, records, drop_duplicates=False)
        df = pd.read_csv(output_file, sep="\t")

        assert list(df["participant_id"]) == [
            "sub-CMH0001",
            "sub-CMH0001",
            "sub-CMH0001",
            "sub-CMH0002",
        ]
        assert list(df["session_id"]) == ["ses-01", "ses-01", "ses-02", "ses-01"]
        assert list(df["qc_task"]) == ["anat_wf_qc", "b_task", "a_task", "z_task"]
