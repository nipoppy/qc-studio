"""Tests for iqm_viewer.py module."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import plotly.graph_objects as go
import pytest


class _StreamlitStub:
    def __init__(self):
        self.warning = MagicMock()
        self.error = MagicMock()
        self.info = MagicMock()
        self.subheader = MagicMock()
        self.selectbox = MagicMock()
        self.radio = MagicMock()
        self.plotly_chart = MagicMock()
        self.segmented_control = MagicMock()
        self.write = MagicMock()
        self.session_state = {}

    def cache_data(self, *args, **kwargs):
        def decorator(func):
            return func

        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        return decorator


@pytest.fixture
def iqm_viewer_module(monkeypatch):
    """Import iqm_viewer with lightweight module stubs."""
    streamlit_stub = _StreamlitStub()
    ui_dir = Path(__file__).resolve().parents[1]
    components_dir = ui_dir / "components"

    if str(components_dir) not in sys.path:
        sys.path.insert(0, str(components_dir))
    if str(ui_dir) not in sys.path:
        sys.path.insert(0, str(ui_dir))

    monkeypatch.setitem(sys.modules, "streamlit", streamlit_stub)
    sys.modules.pop("iqm_viewer", None)
    module = importlib.import_module("iqm_viewer")

    yield module, streamlit_stub

    sys.modules.pop("iqm_viewer", None)


def test_load_iqm_config_reads_selected_block(iqm_viewer_module, temp_dir):
    module, streamlit_stub = iqm_viewer_module

    qc_config = {
        "iqm_distributions": {
            "t1w": "reference.tsv",
            "bold": "bold.tsv",
        }
    }
    config_path = temp_dir / "qc_config.json"
    config_path.write_text(json.dumps(qc_config))

    result = module._load_iqm_config(str(config_path))

    assert result == qc_config["iqm_distributions"]
    streamlit_stub.warning.assert_not_called()


def test_load_iqm_config_warns_when_missing(iqm_viewer_module, temp_dir):
    module, streamlit_stub = iqm_viewer_module

    config_path = temp_dir / "qc_config.json"
    config_path.write_text(json.dumps({}))

    result = module._load_iqm_config(str(config_path))

    assert result == {}
    streamlit_stub.warning.assert_called_once()


def test_extract_subject_data_filters_participant_and_session(iqm_viewer_module):
    module, _ = iqm_viewer_module

    data = pd.DataFrame(
        {
            "bids_name": [
                "sub-01_ses-01_T1w",
                "sub-01_ses-02_T1w",
                "sub-02_ses-01_T1w",
            ],
            "efc": [0.1, 0.2, 0.3],
            "snr_total": [10, 20, 30],
        }
    )

    result = module._extract_subject_data(data, "sub-01", ["efc", "snr_total"], session_id="ses-02")

    assert len(result) == 1
    assert result.iloc[0]["efc"] == 0.2
    assert result.iloc[0]["snr_total"] == 20


def test_extract_subject_data_requires_bids_name(iqm_viewer_module):
    module, _ = iqm_viewer_module

    data = pd.DataFrame({"efc": [0.1]})

    with pytest.raises(ValueError, match="bids_name"):
        module._extract_subject_data(data, "sub-01", ["efc"])


def test_extract_subject_data_rejects_invalid_session_prefix(iqm_viewer_module):
    module, _ = iqm_viewer_module

    data = pd.DataFrame({"bids_name": ["sub-01_ses-01_T1w"], "efc": [0.1]})

    with pytest.raises(ValueError, match="ses-"):
        module._extract_subject_data(data, "sub-01", ["efc"], session_id="01")


def test_add_box_traces_adds_one_trace_per_metric(iqm_viewer_module):
    module, _ = iqm_viewer_module

    fig = go.Figure()
    data = pd.DataFrame(
        {
            "efc": [0.1, 0.2, None],
            "snr_total": [10, 20, 30],
        }
    )

    module._add_box_traces(fig, data, module.DATASET_STYLE, offsetgroup="Dataset")

    assert len(fig.data) == 2
    assert fig.data[0].name == "Dataset"
    assert "Source: Dataset" in fig.data[0].hovertemplate
    assert "Metric: efc" in fig.data[0].hovertemplate


def test_add_subject_overlay_draws_all_points_and_keeps_first_legend(iqm_viewer_module):
    module, _ = iqm_viewer_module

    fig = go.Figure()
    subject_rows = pd.DataFrame({"efc": [0.4], "snr_total": [15.0]})

    module._add_subject_overlay(fig, subject_rows, "sub-01", offsetgroup="Dataset", label_suffix=" (dataset)")

    assert len(fig.data) == 2
    assert fig.data[0].showlegend is True
    assert fig.data[1].showlegend is False
    assert "Source: sub-01 (dataset)" in fig.data[0].hovertemplate


def test_infer_iqm_modality_from_anat_task(iqm_viewer_module):
    module, _ = iqm_viewer_module

    modality = module._infer_iqm_modality(
        "anat_wf_qc",
        {},
        {"t1w": "group_T1w.tsv", "bold": "group_bold.tsv"},
    )

    assert modality == "t1w"


def test_infer_iqm_modality_from_func_task(iqm_viewer_module):
    module, _ = iqm_viewer_module

    modality = module._infer_iqm_modality(
        "func_wf_qc",
        {},
        {"t1w": "group_T1w.tsv", "bold": "group_bold.tsv"},
    )

    assert modality == "bold"


def test_infer_iqm_modality_from_config_path_list(iqm_viewer_module):
    module, _ = iqm_viewer_module

    modality = module._infer_iqm_modality(
        "preproc_qc",
        {
            "base_mri_image_path": "derivatives/fmriprep/sub-01/anat/sub-01_T1w.nii.gz",
            "svg_montage_path": [
                "figures/sub-01_desc-reconall_T1w.svg",
                "figures/sub-01_space-MNI152NLin2009cAsym_T1w.svg",
            ],
        },
        {"t1w": "group_T1w.tsv", "bold": "group_bold.tsv"},
    )

    assert modality == "t1w"


def test_infer_iqm_modality_returns_none_when_ambiguous(iqm_viewer_module):
    module, _ = iqm_viewer_module

    modality = module._infer_iqm_modality(
        "preproc_qc",
        {},
        {"t1w": "group_T1w.tsv", "bold": "group_bold.tsv"},
    )

    assert modality is None


def test_render_iqm_distributions_dataset_only(iqm_viewer_module, temp_dir, monkeypatch):
    module, streamlit_stub = iqm_viewer_module

    dataset_path = temp_dir / "dataset.tsv"
    pd.DataFrame(
        {
            "bids_name": ["sub-01_ses-01_T1w", "sub-02_ses-01_T1w"],
            "efc": [0.11, 0.22],
        }
    ).to_csv(dataset_path, sep="\t", index=False)

    monkeypatch.setitem(module.IQM_DISTRIBUTION_GROUPS, "t1w", {"EFC": ["efc"]})

    streamlit_stub.selectbox.return_value = "EFC"
    streamlit_stub.radio.return_value = "Dataset"
    streamlit_stub.segmented_control.return_value = "Detail"

    module._render_iqm_distributions(
        {"t1w": str(dataset_path)},
        {"Manufacturer": "Siemens"},
        "sub-01",
        None,
        qc_task="anat_wf_qc",
    )

    streamlit_stub.plotly_chart.assert_called_once()
    streamlit_stub.selectbox.assert_called_once()
    fig = streamlit_stub.plotly_chart.call_args.args[0]
    assert len(fig.data) == 2


def test_render_iqm_distributions_comparison_mode_uses_reference(iqm_viewer_module, temp_dir, monkeypatch):
    module, streamlit_stub = iqm_viewer_module

    dataset_path = temp_dir / "dataset.tsv"

    pd.DataFrame(
        {
            "bids_name": ["sub-01_ses-01_T1w", "sub-02_ses-01_T1w"],
            "efc": [0.11, 0.22],
        }
    ).to_csv(dataset_path, sep="\t", index=False)

    reference_df = pd.DataFrame(
        {
            "Manufacturer": ["Siemens", "GE"],
            "efc": [0.5, 0.9],
        }
    )

    monkeypatch.setitem(module.IQM_DISTRIBUTION_GROUPS, "t1w", {"EFC": ["efc"]})
    # Reference loading now goes through data_loaders.load_reference_iqm_for_subject
    # (Parquet download + filter), not a REFERENCE_DATA_PATHS TSV; mock it directly.
    monkeypatch.setattr(
        module, "load_reference_iqm_for_subject", MagicMock(return_value=reference_df)
    )

    streamlit_stub.selectbox.return_value = "EFC"
    streamlit_stub.radio.return_value = "Dataset + reference"
    streamlit_stub.segmented_control.return_value = "Detail"

    module._render_iqm_distributions(
        {"t1w": str(dataset_path)},
        {"Manufacturer": "Siemens"},
        "sub-01",
        None,
        qc_task="anat_wf_qc",
    )

    streamlit_stub.plotly_chart.assert_called_once()
    fig = streamlit_stub.plotly_chart.call_args.args[0]
    assert len(fig.data) == 3


def test_display_iqm_panel_calls_loader_and_renderer(iqm_viewer_module, monkeypatch):
    module, _ = iqm_viewer_module

    load_config = MagicMock(return_value={"T1w": "dataset.tsv"})
    load_scanner_metadata = MagicMock(return_value={"Manufacturer": "Siemens"})
    render = MagicMock()

    monkeypatch.setattr(module, "_load_iqm_config", load_config)
    monkeypatch.setattr(module, "_load_scanner_metadata", load_scanner_metadata)
    monkeypatch.setattr(module, "_render_iqm_distributions", render)

    qc_config = {"base_mri_image_path": "sub-01_T1w.nii.gz"}

    module._display_iqm_panel(qc_config, "qc_config.json", "sub-01", "ses-01")

    load_config.assert_called_once_with("qc_config.json")
    load_scanner_metadata.assert_called_once_with(
        "sub-01_T1w.nii.gz",
        participant_id="sub-01",
        session_id="ses-01",
    )
    render.assert_called_once_with(
        {"T1w": "dataset.tsv"},
        {"Manufacturer": "Siemens"},
        "sub-01",
        "ses-01",
        qc_config_path="qc_config.json",
        dataset_dir=None,
        qc_task=None,
        qc_config=qc_config,
    )
