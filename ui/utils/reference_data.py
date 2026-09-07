"""Reference IQM data: download, caching, and scanner-metadata normalization.

Split out of ``data_loaders.py`` so that module doesn't need ``requests`` or
the reference-data config maps for its unrelated MRI/SVG loading duties.
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import streamlit as st

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
