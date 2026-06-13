"""QC-Studio data models.

Defines all Pydantic models used throughout QC-Studio.
"""

from datetime import datetime, date
from typing import List, Optional, Dict
from pathlib import Path

try:
    from typing import Annotated, Literal
except ImportError:
    from typing_extensions import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


# Future plans:
# To be used if we want to provide configurable QC scoring options
class MetricQC(BaseModel):
    name: Annotated[
        str, Field(description="Name of the metric, e.g., Euler, segmentation")
    ]
    value: Annotated[
        Optional[float], Field(description="Numeric value if applicable")
    ] = None
    qc: Annotated[
        Optional[str], Field(description="QC decision: PASS, FAIL, UNCERTAIN")
    ] = None
    notes: Annotated[Optional[str], Field(description="Additional comment")] = None


class QCRecord(BaseModel):
    qc_task: Annotated[str, Field(description="QC task identifier, e.g., sdc-wf")]
    participant_id: Annotated[str, Field(description="BIDS subject ID")]
    session_id: Annotated[str, Field(description="Session ID, e.g., ses-01")]
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    pipeline: Annotated[
        str, Field(description="Pipeline name and version, e.g., freesurfer")
    ]
    timestamp: Annotated[
        Optional[str], Field(description="Completion date")
    ] = None
    rater_id: Annotated[str, Field(description="Name of the rater")]
    rater_experience: Annotated[Optional[str], Field(description="Rater experience level")] = None
    rater_fatigue: Annotated[Optional[str], Field(description="Rater fatigue level")] = None
    final_qc: Optional[str] = None
    notes: Annotated[Optional[str], Field(description="Additional comment")] = None
    duration: Annotated[Optional[int], Field(description="Duration of the session resulting in the final annotation")] = None


class QCTask(BaseModel):
    """Represents one QC entry in <pipeline>_qc.json (i.e. single QC task)."""

    # Single file paths for mri and overlay images
    base_mri_image_path: Annotated[Optional[Path], Field(description="Path to base MRI image")] = None
    overlay_mri_image_path: Annotated[Optional[Path], Field(description="Path to overlay MRI image (mask etc.)")] = None

    # List of paths for svg montages
    svg_montage_path: Annotated[Optional[List[Path]], Field(description="List of paths to SVG montages for visual QC")] = None

    # Path for IQMs or other QC files (e.g. CSV, JSON)
    iqm_path: Annotated[Optional[Path], Field(description="Path to an IQM or other QC SVG/file")] = None


class QCConfig(RootModel[Dict[str, QCTask]]):
    """Top-level model for `qc.json`.

    The JSON is expected to be a mapping from QC-task keys (strings) to
    `QCTask` objects. Example:

    {
        "anat_wf_qc": {
            "base_mri_image_path": "...",
            "overlay_mri_image_path": "...",
            "svg_montage_path": "...",
            "iqm_path": "..."
        }
    }
    """
    # RootModel holds the mapping as `.root` (dict[str, QCTask])
    pass


QCDecision = Literal["pass", "fail", "uncertain"]


class QCStatusRow(BaseModel):
    participant_id: Annotated[str, Field(description="BIDS subject ID, e.g., sub-ED01")]
    session: Optional[str] = None
    acq: Optional[str] = None
    run: Optional[int] = None
    qc_task: Annotated[str, Field(description="QC task identifier, e.g., anat_wf_qc")]
    rater_id: Annotated[str, Field(description="Rater identifier")]
    score: Optional[QCDecision] = None
    notes: Optional[str] = None
    timestamp: Optional[date] = None
    duration: Optional[int] = None
