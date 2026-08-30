"""Data loading utilities for QC-Studio.

This module loads MRI files, SVG montages, scanner metadata, IQM metrics, and
reference IQM tables from dataset and pipeline outputs.
"""

import json
import os
import re
import pandas as pd

from pathlib import Path

from typing import Optional, Dict, List, Union, Tuple

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Reference-data host is not committed to source; set REFERENCE_DATA_URL in
# the environment (or a .env file) before running the app.
URL_PARENT = os.environ.get("REFERENCE_DATA_URL")

REFERENCE_CACHE_DIR = Path(".streamlit/reference_cache")

MAX_REFERENCE_ROWS = 50_000
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

UNKNOWN_LABELS = {"", "unknown", "nan", "none", "na", "n/a", "null"}

MANUFACTURER_ALIASES = {
    "siemens": "siemens",
    "siemens healthineers": "siemens",
    "siemens healthcare": "siemens",
    "ge": "ge",
    "general electric": "ge",
    "ge healthcare": "ge",
    "ge medical systems": "ge",
    "philips": "philips",
    "philips healthcare": "philips",
    "philips medical systems": "philips",
}

FIELD_STRENGTH_ALIASES = {
    "1": "1",
    "1.0": "1",
    "1t": "1",
    "1.0t": "1",
    "1.5": "1.5",
    "1.5t": "1.5",
    "3": "3",
    "3.0": "3",
    "3t": "3",
    "3.0t": "3",
    "7": "7",
    "7.0": "7",
    "7t": "7",
    "7.0t": "7",
}

from constants import NIIVUE_MAX_FILE_BYTES


def _resolve_all_under_dataset(base_root: Path, rel_path: Union[str, Path, None]) -> list[Path]:
    """Resolve a dataset-relative path to zero or more files (globs return all sorted matches)."""
    if rel_path is None:
        return []
    rel = Path(rel_path)
    direct = base_root / rel
    if "*" in str(rel):
        matches = sorted(p for p in base_root.glob(str(rel)) if p.is_file())
        if matches:
            return matches
    if direct.is_file():
        return [direct]
    no_ses_name = re.sub(r"_ses-[^_]+", "", direct.name)
    fallback = direct.parent / no_ses_name
    if fallback.is_file():
        return [fallback]
    return []


def _expand_dataset_paths(base_root: Path, paths_value: Union[str, Path, list, None]) -> list[Path]:
    """Expand path specs to concrete files; globs include every match."""
    if paths_value is None:
        return []
    specs = paths_value if isinstance(paths_value, list) else [paths_value]
    expanded: list[Path] = []
    seen: set[Path] = set()
    for spec in specs:
        for path in _resolve_all_under_dataset(base_root, spec):
            if path not in seen:
                seen.add(path)
                expanded.append(path)
    return expanded


def _resolve_under_dataset(base_root: Path, rel_path: Union[str, Path, None]) -> Optional[Path]:
    """Resolve a single dataset-relative file (first glob match when multiple exist)."""
    matches = _resolve_all_under_dataset(base_root, rel_path)
    return matches[0] if matches else None


def _nifti_volume_to_bytes(img, vol_index: int = 0) -> bytes:
    """Serialize one 3D volume from a NIfTI image (handles 4D via mmap slice)."""
    import numpy as np
    import nibabel as nib

    shape = img.shape
    if len(shape) == 4:
        vol = np.asanyarray(img.dataobj[..., vol_index])
    elif len(shape) == 3:
        vol = np.asanyarray(img.dataobj)
    else:
        raise ValueError(f"Unsupported NIfTI rank for Niivue preview: {len(shape)}")
    hdr = img.header.copy()
    hdr.set_data_shape(vol.shape)
    out = nib.Nifti1Image(vol, img.affine, hdr)
    return out.to_bytes()


def _read_nifti_bytes_for_niivue(path: Path) -> Tuple[Optional[bytes], bool, Optional[str]]:
    """Load NIfTI bytes for Niivue; reduce 4D / oversize files to the first volume."""
    size = path.stat().st_size
    try:
        import nibabel as nib
    except ImportError:
        if size > NIIVUE_MAX_FILE_BYTES:
            return None, False, "oversize"
        return path.read_bytes(), False, None

    try:
        img = nib.load(str(path))
        reduce = size > NIIVUE_MAX_FILE_BYTES or len(img.shape) == 4
        if reduce:
            vol_bytes = _nifti_volume_to_bytes(img, vol_index=0)
            if len(vol_bytes) > NIIVUE_MAX_FILE_BYTES:
                return None, True, "oversize"
            return vol_bytes, True, None
        if size > NIIVUE_MAX_FILE_BYTES:
            return None, False, "oversize"
        return path.read_bytes(), False, None
    except Exception:
        if size <= NIIVUE_MAX_FILE_BYTES:
            return path.read_bytes(), False, None
        return None, False, "oversize"


def _attach_nifti_bytes(file_bytes_dict: dict, path: Path, prefix: str) -> None:
    """Read NIfTI bytes for Niivue (first BOLD volume when 4D or file is large)."""
    nbytes, reduced, err = _read_nifti_bytes_for_niivue(path)
    file_bytes_dict[f"{prefix}_mri_image_path"] = path
    if nbytes is not None:
        file_bytes_dict[f"{prefix}_mri_image_bytes"] = nbytes
        if reduced:
            file_bytes_dict[f"{prefix}_mri_preview_reduced"] = True
        return
    if err == "oversize":
        file_bytes_dict[f"{prefix}_mri_oversize"] = True
        file_bytes_dict[f"{prefix}_mri_size_bytes"] = path.stat().st_size


def load_mri_data(
    dataset_dir: Union[str, Path, dict],
    path_dict: Optional[dict] = None,
) -> dict:
    """Load base and overlay MRI image files as bytes.

    Supports ``load_mri_data(dataset_dir, path_dict)`` (paths relative to
    ``dataset_dir``) and ``load_mri_data(path_dict)`` (paths already absolute
    or cwd-relative).

    Args:
            dataset_dir: Root directory containing the dataset, or a path_dict if
                    ``path_dict`` is omitted.
            path_dict: Dictionary with keys 'base_mri_image_path' and 'overlay_mri_image_path'

    Returns:
            dict with keys: 'base_mri_image_bytes', 'base_mri_image_path',
            'overlay_mri_image_bytes', 'overlay_mri_image_path'
            Returns empty dict if files don't exist
    """
    if path_dict is None:
        if not isinstance(dataset_dir, dict):
            raise TypeError("load_mri_data: pass either path_dict only or (dataset_dir, path_dict)")
        path_dict = dataset_dir
        dataset_dir = ""

    base_root = Path(dataset_dir) if dataset_dir else Path()
    base_mri_path = _resolve_under_dataset(base_root, path_dict.get("base_mri_image_path"))
    overlay_mri_path = _resolve_under_dataset(base_root, path_dict.get("overlay_mri_image_path"))

    file_bytes_dict = {}

    if base_mri_path is not None and base_mri_path.is_file():
        _attach_nifti_bytes(file_bytes_dict, base_mri_path, "base")

    if overlay_mri_path is not None and overlay_mri_path.is_file():
        _attach_nifti_bytes(file_bytes_dict, overlay_mri_path, "overlay")

    return file_bytes_dict


def _normalize_svg_paths(svg_paths_value):
    """Normalize montage paths to a list of Path objects."""

    if isinstance(svg_paths_value, (str, Path)):
        return [Path(svg_paths_value)]

    if isinstance(svg_paths_value, list):
        normalized_paths = []
        for p in svg_paths_value:
            if p is None:
                continue
            try:
                normalized_paths.append(Path(p))
            except TypeError:
                # Ignore malformed path entries and keep loading valid montage files.
                continue
        return normalized_paths

    return None


def load_svg_data(dataset_dir, path_dict: dict, max_montage_rows=None, max_montage_cols=None) -> Optional[dict]:
    """Normalize montage paths from a QC config and return cached image data.

    This public wrapper keeps the config-dictionary API used by callers while
    delegating expensive file reads, image conversion, and montage creation to
    ``_load_svg_data_cached``.

    Args:
            dataset_dir: Base directory path for resolving relative paths.
            path_dict: Dictionary containing 'svg_montage_path' key with:
                    - None (no montage)
                    - Single Path/str object
                    - List of Path/str objects
            max_montage_rows: Maximum rows for grid montage.
            max_montage_cols: Maximum columns for grid montage.

    Returns:
            Cached display data from ``_load_svg_data_cached``, or None if no
            montage paths are configured.
    """
    svg_paths_value = path_dict.get("svg_montage_path")
    if not svg_paths_value:
        return None

    # Normalize to list of paths
    svg_paths_value = _normalize_svg_paths(svg_paths_value)

    if not svg_paths_value:
        return None

    base_root = Path(dataset_dir) if dataset_dir else Path()
    resolved_paths = _expand_dataset_paths(base_root, svg_paths_value)
    if not resolved_paths:
        return None

    return _load_svg_data_cached(
        tuple(str(path) for path in resolved_paths),
        max_montage_rows,
        max_montage_cols,
    )


def _create_unique_id_from_path(file_path: Path) -> str:
    """Create a unique identifier from the last 2-3 components of a file path.

    Args:
            file_path: Path object for the file.

    Returns:
            Unique identifier string based on the last 2-3 path components.
    """
    path_parts = file_path.parts

    if len(path_parts) >= 3:
        # Use last 3 path components (grandparent dir + parent dir + stem)
        grandparent = path_parts[-3]
        parent = path_parts[-2]
        stem = file_path.stem
        return f"{grandparent}_{parent}_{stem}"
    elif len(path_parts) >= 2:
        # Fallback: use parent dir + stem
        parent = path_parts[-2]
        stem = file_path.stem
        return f"{parent}_{stem}"
    else:
        return file_path.stem


def _load_svg_entry(full_path: Path, unique_id: str):
    try:
        with open(full_path, encoding="utf-8") as f:
            svg_content = f.read()

        filename = f"{unique_id}_svg"
        data_content = {
            "type": "svg",
            "content": svg_content,
        }

        # Convert SVG to image for montage (optional - if conversion fails, SVG is still available as string)
        try:
            pil_img = _load_image_from_file(full_path)
        except Exception:
            # SVG conversion not critical; skip but keep the SVG string version for rendering
            pil_img = None

        return filename, data_content, pil_img

    except Exception:
        return None


def _load_raster_entry(full_path: Path, unique_id: str, raster_type: str):
    try:
        pil_img = _load_image_from_file(full_path)

        filename = f"{unique_id}_{raster_type}"
        data_content = {"type": raster_type, "content": pil_img}
        return filename, data_content, pil_img

    except ValueError:
        return None


def _add_montage_if_available(
    image_data_dict: dict,
    images_for_montage: list,
    max_montage_rows=None,
    max_montage_cols=None,
) -> dict:
    if len(images_for_montage) <= 1:
        # Return individual images (no montage for single image)
        return image_data_dict

    try:
        from .image_processing import create_grid_montage

        montage_img = create_grid_montage(
            images_for_montage,
            max_rows=max_montage_rows,
            max_cols=max_montage_cols,
        )
        # Insert montage at the beginning of result dict
        result_dict = {"montage": {"type": "png", "content": montage_img}}
        result_dict.update(image_data_dict)
        return result_dict
    except Exception:
        # Return individual images if montage creation fails
        return image_data_dict


@st.cache_data(show_spinner=False, max_entries=128)
def _load_svg_data_cached(svg_paths: tuple, max_montage_rows=None, max_montage_cols=None) -> Optional[dict]:
    """Load montage image files and build display data.

    This cached helper does the expensive work: resolving paths, reading SVG
    text, loading raster images, converting images for montage creation, and
    building an optional grid montage.

    Args:
            svg_paths: Tuple of SVG/PNG/JPEG paths to load.
            max_montage_rows: Maximum rows for grid montage.
            max_montage_cols: Maximum columns for grid montage.

    Returns:
            Dict with image keys mapped to ``{"type": ..., "content": ...}``.
            SVG content is returned as a string; PNG/JPEG content is returned as a
            PIL Image. If multiple images can be converted for montage display, a
            ``"montage"`` entry is inserted first. Returns None if no valid image
            files are found.

    Notes:
            - Unsupported formats are silently skipped.
            - SVG-to-image conversion is optional; if conversion fails, the SVG text
              is still returned for direct rendering.
    """
    image_data_dict = {}
    images_for_montage = []  # Collect PIL Images for montage creation

    for svg_path in svg_paths:
        full_path = Path(svg_path)
        if not full_path.is_file():
            continue
        file_ext = full_path.suffix.lower()

        # Create unique identifier using last 3 path components to avoid collisions
        # E.g., "screenshots/sub-CMH0001/sub-CMH0001.png" -> "screenshots_sub-CMH0001_sub"
        unique_id = _create_unique_id_from_path(full_path)

        if file_ext == ".svg":
            # Return SVG as string content (use open() so tests can mock builtins.open)
            loaded_entry = _load_svg_entry(full_path, unique_id)
            if loaded_entry is None:
                continue
            filename, data_content, pil_img = loaded_entry
            image_data_dict[filename] = data_content
            if pil_img is not None:
                images_for_montage.append(pil_img)

        elif file_ext in [".png", ".jpg", ".jpeg"]:
            # Return PNG/JPEG as PIL Image
            raster_type = "jpeg" if file_ext in (".jpg", ".jpeg") else file_ext.lstrip(".")
            loaded_entry = _load_raster_entry(full_path, unique_id, raster_type)
            if loaded_entry is None:
                continue
            filename, data_content, pil_img = loaded_entry
            image_data_dict[filename] = data_content
            images_for_montage.append(pil_img)

    if not image_data_dict:
        return None

    return _add_montage_if_available(
        image_data_dict,
        images_for_montage,
        max_montage_rows=max_montage_rows,
        max_montage_cols=max_montage_cols,
    )


def _load_image_from_file(file_path, dpi=96):
    """Load image from file path, supporting both raster and SVG formats.

    Args:
            file_path: Path to image file (SVG, PNG, JPG, JPEG)
            dpi: DPI for SVG rendering (default: 96)

    Returns:
            PIL.Image: Image object in RGB mode

    Raises:
            ValueError: If file format is not supported or conversion fails
    """
    from io import BytesIO
    from PIL import Image

    file_path = Path(file_path)
    file_ext = file_path.suffix.lower()

    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")

    if file_ext == ".svg":
        try:
            import cairosvg

            # Convert SVG to PNG in memory
            png_data = cairosvg.svg2png(bytestring=file_path.read_bytes(), dpi=dpi)
            img = Image.open(BytesIO(png_data))
        except ImportError:
            raise ValueError("cairosvg library required for SVG support. " "Install it with: pip install cairosvg")
        except Exception as e:
            raise ValueError(f"Failed to convert SVG file {file_path}: {e}")
    elif file_ext in [".png", ".jpg", ".jpeg"]:
        try:
            img = Image.open(file_path)
        except Exception as e:
            raise ValueError(f"Failed to load image file {file_path}: {e}")
    else:
        raise ValueError(f"Unsupported image format: {file_ext}. " f"Supported formats: SVG, PNG, JPG, JPEG")

    # Ensure image is in RGB mode
    if img.mode != "RGB":
        img = img.convert("RGB")

    return img


def _resolve_metadata_path(image_path: Union[Path, str]) -> Path:
    """Returning the JSON sidecar path for a BIDS image file."""
    if not image_path:
        return None
    image_path = Path(image_path)
    image_name = image_path.name
    if image_name.endswith(".nii.gz"):
        json_name = image_name.replace(".nii.gz", ".json")
    elif image_name.endswith(".nii"):
        json_name = image_name.replace(".nii", ".json")
    else:
        return None

    return image_path.parent / json_name


def _infer_bids_ids_from_path(image_path: Union[Path, str]) -> tuple:
    """Infer BIDS participant/session IDs from a file path string."""
    if not image_path:
        return None, None

    path_str = str(image_path)
    participant_match = re.search(r"(sub-[A-Za-z0-9]+)", path_str)
    session_match = re.search(r"(ses-[A-Za-z0-9]+)", path_str)

    participant_id = participant_match.group(1) if participant_match else None
    session_id = session_match.group(1) if session_match else None
    return participant_id, session_id


def _infer_dataset_root_from_path(image_path: Union[Path, str]) -> Optional[Path]:
    """Infer dataset root from a path containing BIDS-like folders."""
    if not image_path:
        return None

    path_obj = Path(image_path)
    parts = path_obj.parts

    if "derivatives" in parts:
        idx = parts.index("derivatives")
        return Path(*parts[:idx]) if idx > 0 else Path(".")

    if "bids" in parts:
        idx = parts.index("bids")
        return Path(*parts[:idx]) if idx > 0 else Path(".")

    return None


# Folder + filename-suffix to search for, per BIDS modality.
MODALITY_SIDECAR_HINTS = {
    "anat": ("anat", "T1w"),
    "t1w": ("anat", "T1w"),
    "func": ("func", "bold"),
    "bold": ("func", "bold"),
    "dwi": ("dwi", "dwi"),
    "diffusion": ("dwi", "dwi"),
}


def _infer_bids_folder_from_path(path: Union[Path, str]) -> Optional[str]:
    """Infer a BIDS modality folder from a path or filename."""
    if not path:
        return None

    path_str = str(path).lower()
    name = Path(path).name.lower()

    if "/func/" in path_str or re.search(r"_(bold|sbref)\.", path_str) or "bold" in name:
        return "func"
    if "/dwi/" in path_str or re.search(r"_dwi\.", path_str) or "dwi" in name:
        return "dwi"
    if "/anat/" in path_str or "t1w" in name:
        return "anat"
    return None


def _find_bids_metadata_sidecar(
    dataset_root: Union[Path, str],
    participant_id: str = None,
    session_id: str = None,
    modality: str = "anat",
) -> Optional[Path]:
    """Find a likely scanner-metadata sidecar for a participant."""
    if not dataset_root or not participant_id:
        return None

    dataset_root = Path(dataset_root)
    folder, suffix = MODALITY_SIDECAR_HINTS.get(str(modality).lower(), ("anat", "T1w"))

    if not participant_id.startswith("sub-"):
        participant_id = f"sub-{participant_id}"
    if session_id and not session_id.startswith("ses-"):
        session_id = f"ses-{session_id}"

    def _patterns_for(prefix: str) -> list:
        patterns = []
        if session_id:
            patterns.extend(
                [
                    f"{prefix}{participant_id}/{session_id}/{folder}/*{suffix}*.json",
                    f"{prefix}{participant_id}/{session_id}/{folder}/*.json",
                    f"{prefix}{participant_id}/{session_id}/**/*{suffix}*.json",
                ]
            )
        patterns.extend(
            [
                f"{prefix}{participant_id}/**/*{suffix}*.json",
                f"{prefix}{participant_id}/**/{folder}/*.json",
            ]
        )
        return patterns

    # Raw BIDS sidecars are the authoritative source when present.
    bids_root = dataset_root / "bids"
    if not bids_root.is_dir():
        bids_root = dataset_root
    search_roots = [(bids_root, "")]

    # Fall back to derivative sidecars when raw BIDS metadata is unavailable.
    derivatives_root = dataset_root / "derivatives"
    if derivatives_root.is_dir():
        search_roots.append((derivatives_root, "**/"))

    for root, prefix in search_roots:
        for pattern in _patterns_for(prefix):
            matches = sorted(root.glob(pattern))
            for match in matches:
                if match.is_file():
                    return match

    return None


def load_scanner_metadata(
    image_path: Union[Path, str], participant_id: str = None, session_id: str = None, modality: str = None, dataset_dir: Union[Path, str] = None
) -> dict:
    """Load scanner metadata from the JSON sidecar of a BIDS image file.

    If the direct sidecar is unavailable, look for a participant/session sidecar
    under raw BIDS or derivatives and fall back to "Unknown" values.
    """
    if dataset_dir and image_path:
        image_path = Path(dataset_dir) / image_path

    json_path = _resolve_metadata_path(image_path)
    dataset_root = _infer_dataset_root_from_path(image_path)

    # Prefer IDs inferred from image path when explicit IDs are not provided.
    inferred_participant, inferred_session = _infer_bids_ids_from_path(image_path)
    participant_id = participant_id or inferred_participant
    session_id = session_id or inferred_session
    modality = modality or _infer_bids_folder_from_path(image_path) or "anat"

    if not json_path or not Path(json_path).is_file():
        json_path = _find_bids_metadata_sidecar(dataset_root, participant_id, session_id, modality=modality)

    # Metadata sidecar may be absent for derivative images. Fall back to
    # unknown values instead of failing the whole IQM panel.
    if not json_path or not Path(json_path).is_file():
        return {
            "Manufacturer": "Unknown",
            "MagneticFieldStrength": "Unknown",
            "ProtocolName": "Unknown",
        }

    with open(json_path, "r") as f:
        metadata = json.load(f)

    # MRIQC sidecars may nest original BIDS metadata under "bids_meta".
    bids_meta = metadata.get("bids_meta") or {}

    return {
        "Manufacturer": metadata.get("Manufacturer") or bids_meta.get("Manufacturer", "Unknown"),
        "MagneticFieldStrength": metadata.get("MagneticFieldStrength") or bids_meta.get("MagneticFieldStrength", "Unknown"),
        "ProtocolName": metadata.get("ProtocolName") or bids_meta.get("ProtocolName", "Unknown"),
    }


def resolve_iqm_data_path(
    modality_path: str,
    qc_config_path: str = None,
    dataset_dir: str = None,
) -> Path:
    """Resolve an IQM dataset TSV path across common runtime contexts."""
    path = Path(modality_path)

    if path.is_absolute() and path.is_file():
        return path

    candidates = [Path.cwd() / path]

    if dataset_dir:
        candidates.append(Path(dataset_dir) / path)

    if qc_config_path:
        candidates.append(Path(qc_config_path).parent / path)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    # Return original path so callers can surface it in error messages.
    return path


def resolve_reference_data_path(ref_path: str, base_dir: Optional[Path] = None) -> Path:
    """Resolve a reference population TSV path across runtime contexts.

    Args:
            ref_path: Relative or absolute path to the reference TSV.
            base_dir: Optional caller-supplied directory (e.g. the importing
                      module's own directory) added as an additional candidate.
    """
    path = Path(ref_path)

    if path.is_absolute() and path.is_file():
        return path

    candidates = [Path.cwd() / path]

    if base_dir:
        candidates.append(Path(base_dir) / path)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return path


@st.cache_data(show_spinner="Downloading reference data...", ttl=CACHE_TTL_SECONDS)
def _download_reference_parquet_bytes(url: str) -> bytes:
    """Download reference Parquet content and cache bytes in memory."""
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def _get_reference_cache_dir() -> Path:
    """Create and return the reference-data cache directory when needed."""
    REFERENCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return REFERENCE_CACHE_DIR


def download_reference_parquet(modality: str, url_parent: str = URL_PARENT) -> str:
    """Ensure a reference Parquet file exists locally and return its path."""
    cache_file_path = REFERENCE_CACHE_DIR / f"{modality}.parquet"

    if cache_file_path.exists():
        return str(cache_file_path)

    if not url_parent:
        raise RuntimeError("REFERENCE_DATA_URL is not set. Set it in the environment to enable " "downloading reference IQM data.")

    url = url_parent.rstrip("/") + f"/{modality}.parquet"
    cache_file_path = _get_reference_cache_dir() / f"{modality}.parquet"
    cache_file_path.write_bytes(_download_reference_parquet_bytes(url))

    return str(cache_file_path)


def normalize_manufacturer(value: object) -> str:
    normalized = str(value or "").strip().lower()

    if normalized in UNKNOWN_LABELS:
        return "unknown"

    return MANUFACTURER_ALIASES.get(normalized, normalized)


def normalize_field_strength(value: object) -> Optional[str]:
    normalized = str(value or "").strip().lower()

    if normalized in UNKNOWN_LABELS:
        return None

    if normalized in FIELD_STRENGTH_ALIASES:
        return FIELD_STRENGTH_ALIASES[normalized]

    if normalized.endswith("t"):
        normalized = normalized[:-1].strip()

    try:
        numeric_value = float(normalized)
    except (TypeError, ValueError):
        return normalized or None

    return f"{numeric_value:g}"


@st.cache_data(show_spinner="Loading reference data...", ttl=CACHE_TTL_SECONDS)
def _load_reference_parquet(modality: str) -> pd.DataFrame:
    """Load and cache the full, unfiltered reference Parquet table for a modality."""
    local_parquet_path = REFERENCE_CACHE_DIR / f"{modality}.parquet"
    if not local_parquet_path.exists():
        download_reference_parquet(url_parent=URL_PARENT, modality=modality)

    return pd.read_parquet(local_parquet_path, engine="pyarrow")


def load_reference_iqm_for_subject(
    modality: str,
    manufacturer: str,
    field_strength: Optional[object] = None,
    max_rows: int = MAX_REFERENCE_ROWS,
) -> pd.DataFrame:
    """Load and filter reference data for a given subject's scanner."""
    manufacturer_subject_norm = normalize_manufacturer(manufacturer)
    field_strength_subject_norm = normalize_field_strength(field_strength)

    return _load_reference_iqm_filtered(modality, manufacturer_subject_norm, field_strength_subject_norm, max_rows)


@st.cache_data(show_spinner="Loading reference data...", ttl=CACHE_TTL_SECONDS)
def _load_reference_iqm_filtered(
    modality: str,
    manufacturer_subject_norm: str,
    field_strength_subject_norm: Optional[str],
    max_rows: int,
) -> pd.DataFrame:
    """Filter the cached reference table by already-normalized scanner values.

    Cached on the normalized values (not the raw subject metadata) so that
    different raw spellings that mean the same thing (e.g. "", "N/A", and
    "Unknown", or "GE" and "General Electric") share one cache entry.
    """
    data = _load_reference_parquet(modality)

    # TODO: Add a dedicated reference-data cleaning step before filtering.
    if manufacturer_subject_norm != "unknown" and "Manufacturer" in data.columns:
        manufacturer_norm = data["Manufacturer"].map(normalize_manufacturer)
        data = data[manufacturer_norm == manufacturer_subject_norm]

    if field_strength_subject_norm is not None and "MagneticFieldStrength" in data.columns:
        field_strength_norm = data["MagneticFieldStrength"].map(normalize_field_strength)
        data = data[field_strength_norm == field_strength_subject_norm]

    if len(data) > max_rows:
        data = data.sample(n=max_rows, random_state=42)

    return data


@st.cache_data(ttl=3600, show_spinner=False)
def load_iqm_distribution_table(resolved_path) -> pd.DataFrame:
    """Load a TSV/CSV distribution table and return a DataFrame. Raises on failure -
    the caller decides how to surface that (st.cache_data doesn't cache a raised
    exception, so a transient/fixable failure gets retried on the next rerun
    instead of silently returning a cached None for up to `ttl` seconds)."""

    suffix = resolved_path.suffix.lower()
    return pd.read_csv(resolved_path, sep="," if suffix == ".csv" else "\t")


def load_iqm_metrics_subject_level(resolved_path) -> dict:
    """Read a single per-subject IQM metrics file. Raises on failure."""
    return json.loads(Path(resolved_path).read_text(encoding="utf-8"))
