import os
import streamlit as st
from niivue_component import niivue_viewer
# from niivue_component import niivue_component


def niivue_viewer_from_path(baseimage_fpath: str, overlay_fpath: str, height: int = 600, key: str | None = None) -> None:
    """Load a local NIFTI file from `filepath` and display it with `niivue_viewer`.

    This helper reads the file bytes and calls the existing component.

    Args:
        filepath: Path to a local .nii or .nii.gz file.
        height: Viewer height in pixels (default 600).
        key: Optional Streamlit key for the component instance.
    """
    if not os.path.isfile(baseimage_fpath):
        raise FileNotFoundError(f"File not found: {baseimage_fpath}")

    with open(baseimage_fpath, "rb") as f:
        baseimage_bytes = f.read()

    if key is None:
        key = f"niivue_viewer_path_{os.path.basename(baseimage_fpath)}"

    if not os.path.isfile(overlay_fpath):
        raise FileNotFoundError(f"File not found: {overlay_fpath}")

    with open(overlay_fpath, "rb") as f:
        overlay_bytes = f.read()

    niivue_viewer(
        nifti_data=baseimage_bytes,        
        filename=os.path.basename(baseimage_fpath),
        height=height,
        key=key,
        overlays=[
        {
            "data": overlay_bytes,
            "name": "activation.nii.gz",
            "colormap": "hot",
            "opacity": 0.7
        }
        ],
        view_mode="multiplanar",
        styled=True,
        settings={
            "crosshair": True,
            "radiological": False,
            "colorbar": True,
            "interpolation": True
        }
        )


# Text inputs so any user can specify local filepaths without editing the source
baseimage_input = st.text_input(
    "Path to base NIfTI image",
    placeholder="e.g. sample_data/derivatives/fmriprep/.../sub-ED01_ses-01_run-1_desc-preproc_T1w.nii.gz",
)
overlay_input = st.text_input(
    "Path to overlay NIfTI image",
    placeholder="e.g. sample_data/derivatives/fmriprep/.../sub-ED01_ses-01_run-1_desc-brain_mask.nii.gz",
)

if baseimage_input and overlay_input:
    try:
        niivue_viewer_from_path(baseimage_input, overlay_input, height=600, key="niivue_viewer_path")
    except Exception as e:
        st.error(f"Failed to load file: {e}")



