"""Helpers to interpret MRIQC IQMs and flag likely image artifacts.

This module provides a conservative, configurable heuristic function
`detect_image_artifacts` that inspects IQM dictionaries produced by MRIQC
and returns a small report describing which artifact types are likely.

Notes
- The heuristics are intentionally simple and intended as a starting point
  for triage. They are NOT clinical-grade or guaranteed accurate. Use them
  to prioritize images for manual review.
"""

from typing import Dict, Any, Optional


def _get_value(iqm: Dict[str, Any], keys):
	"""Return the first found value for a sequence of possible keys.

	Keys are compared case-insensitively. Returns None if no key found.
	"""
	lower = {k.lower(): v for k, v in iqm.items()}
	for key in keys:
		v = lower.get(key.lower())
		if v is not None:
			return v
	return None


def detect_image_artifacts(iqm: Dict[str, Any], modality: str = "T1w", thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
	"""Detect likely image artifacts from MRIQC IQMs.

	Parameters
	----------
	iqm
		A dictionary loaded from an MRIQC JSON file (IQMs for one image).
	modality
		One of "T1w", "T2w", or "func" (case-insensitive). Determines
		which heuristics/thresholds to apply. Defaults to "T1w".
	thresholds
		Optional mapping of metric->threshold to override defaults. Use
		metric names like "fd_mean", "snr", "cjv", "efc", "dvars".

	Returns
	-------
	dict with keys:
	  - flags: list of short artifact keys (e.g. "motion", "low_snr")
	  - scores: mapping of observed metric values used in decision
	  - explanations: human-readable reasons for each flag

	Heuristics (defaults)
	- Motion (func): mean framewise displacement (fd_mean/mean_fd) > 0.2 mm
	  or DVARS (dvars) markedly high.
	- Low SNR (T1/T2): SNR < 20 flagged as low SNR (conservative).
	- High CJV (T1): CJV > 0.5 indicates contrast/in-homogeneity problems.
	- High EFC: elevated EFC can indicate ghosting/blur; default threshold 0.35.

	These numbers are conservative heuristics — tune with `thresholds`.
	"""

	mod = (modality or "T1w").lower()
	# Default thresholds (conservative)
	default_thresholds = {
		"fd_mean": 0.2,  # mm (functional motion)
		"dvars": 1.5,  # relative units (dataset dependent)
		"snr": 20.0,
		"cjv": 0.5,
		"efc": 0.35,
	}

	if thresholds:
		default_thresholds.update(thresholds)

	flags = []
	scores = {}
	explanations = {}

	# Motion-related (primarily for functional runs)
	fd = _get_value(iqm, ["fd_mean", "mean_fd", "framewise_displacement", "fd"])
	if fd is not None:
		scores["fd_mean"] = float(fd)
		if mod == "func" and float(fd) > default_thresholds["fd_mean"]:
			flags.append("motion")
			explanations.setdefault("motion", []).append(f"fd_mean={fd} > {default_thresholds['fd_mean']}")

	# DVARS (many MRIQC outputs include 'dvars' or 'dvars_std')
	dvars = _get_value(iqm, ["dvars", "dvars_std", "std_dvars"])
	if dvars is not None:
		scores["dvars"] = float(dvars)
		# Use a relative heuristic for DVARS: large value -> motion-like
		if mod == "func" and float(dvars) > default_thresholds["dvars"]:
			if "motion" not in flags:
				flags.append("motion")
			explanations.setdefault("motion", []).append(f"dvars={dvars} > {default_thresholds['dvars']}")

	# SNR (structural/functional may provide different SNR keys)
	snr = _get_value(iqm, ["snr", "snr_total", "snr_gm", "snr_whole"])
	if snr is not None:
		scores["snr"] = float(snr)
		if mod in ("t1w", "t2w") and float(snr) < default_thresholds["snr"]:
			flags.append("low_snr")
			explanations.setdefault("low_snr", []).append(f"snr={snr} < {default_thresholds['snr']}")

	# CJV (coefficient of joint variation) — higher can indicate issues
	cjv = _get_value(iqm, ["cjv"])
	if cjv is not None:
		scores["cjv"] = float(cjv)
		if mod in ("t1w", "t2w") and float(cjv) > default_thresholds["cjv"]:
			flags.append("high_cjv")
			explanations.setdefault("high_cjv", []).append(f"cjv={cjv} > {default_thresholds['cjv']}")

	# EFC (entropy focus criterion) — can indicate blurring/ghosting when high
	efc = _get_value(iqm, ["efc"])
	if efc is not None:
		scores["efc"] = float(efc)
		if float(efc) > default_thresholds["efc"]:
			flags.append("high_efc")
			explanations.setdefault("high_efc", []).append(f"efc={efc} > {default_thresholds['efc']}")

	# Add a small rule for extreme outliers: very low spatial resolution or very high smoothness
	fwhm = _get_value(iqm, ["fwhm", "fwhm_x", "fwhm_y", "fwhm_z"])
	if fwhm is not None:
		# take max if per-axis values provided
		if isinstance(fwhm, (list, tuple)):
			fwhm_val = max(map(float, fwhm))
		else:
			fwhm_val = float(fwhm)
		scores["fwhm"] = fwhm_val
		if fwhm_val > 10.0:
			flags.append("very_high_smoothness")
			explanations.setdefault("very_high_smoothness", []).append(f"fwhm={fwhm_val} > 10.0")

	return {
		"flags": sorted(set(flags)),
		"scores": scores,
		"explanations": {k: "; ".join(v) for k, v in explanations.items()},
	}


def detect_scanner_info(iqm: Dict[str, Any]) -> Dict[str, Any]:
	"""Extract scanner manufacturer and model from an MRIQC IQM dict.

	This function looks first under the `bids_meta` block (the standard place
	for DICOM/BIDS metadata produced by MRIQC). It performs case-insensitive
	lookups for common keys and returns a small report with the discovered
	values and which keys were matched.

	Returns a dict with keys:
	  - manufacturer: str | None
	  - model: str | None
	  - source: where the values were found (e.g., 'bids_meta' or 'top')
	  - matched_keys: mapping of which keys provided the values
	"""
	manufacturer_keys = [
		"manufacturer",
		"scanner_manufacturer",
		"device_manufacturer",
	]
	model_keys = [
		"manufacturersmodelname",
		"manufacturers_model_name",
		"manufacturermodelname",
		"model",
		"manufacturers_model",
		"device_model",
	]

	# Helper to search a mapping case-insensitively
	def _ci_lookup(mapping, candidates):
		if not mapping:
			return None, None
		lower = {k.lower(): v for k, v in mapping.items()}
		for cand in candidates:
			v = lower.get(cand.lower())
			if v is not None:
				return v, cand
		return None, None

	# Primary location: bids_meta
	bids_meta = iqm.get("bids_meta") if isinstance(iqm.get("bids_meta"), dict) else {}
	manuf, manuf_key = _ci_lookup(bids_meta, manufacturer_keys)
	model, model_key = _ci_lookup(bids_meta, model_keys)
	if manuf or model:
		return {
			"manufacturer": manuf,
			"model": model,
			"source": "bids_meta",
			"matched_keys": {"manufacturer_key": manuf_key, "model_key": model_key},
		}

	# Fallback: top-level IQM fields
	manuf, manuf_key = _ci_lookup(iqm, manufacturer_keys)
	model, model_key = _ci_lookup(iqm, model_keys)
	if manuf or model:
		return {
			"manufacturer": manuf,
			"model": model,
			"source": "top",
			"matched_keys": {"manufacturer_key": manuf_key, "model_key": model_key},
		}

	# Nothing found
	return {"manufacturer": None, "model": None, "source": None, "matched_keys": {}}
