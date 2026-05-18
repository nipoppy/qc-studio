# MRI QC Evidence Package

<!-- **Scan:** n/a -->
**Participant:** sub-1003
**Session:** n/a
**Modality:** T1w
**Acquisition:** headmotion1

---

## Scanner Metadata

| Field | Value |
|---|---|
| `Manufacturer` | `Siemens` |
| `ManufacturersModelName` | `Prisma` |
| `MagneticFieldStrength` | `3` |
| `ScanningSequence` | `GR\IR` |
| `SequenceVariant` | `SK\SP\MP` |
| `MRAcquisitionType` | `3D` |
| `RepetitionTime` | `2.3` |
| `EchoTime` | `0.00303` |
| `InversionTime` | `0.9` |
| `FlipAngle` | `9` |
| `ReceiveCoilName` | `HeadNeck_20` |

---

## Highlighted IQMs

Metrics are flagged if they are clinically important for this modality, or statistically extreme (percentile ≤10 or ≥90, |z-score| ≥1.5) relative to a matched reference population.

| Metric | Value | Percentile | Z-Score | Direction of Concern | Interpretation |
|---|---|---|---|---|---|
| `cjv` | 0.373972 | 15.022 | -0.851 | higher_worse | higher values may indicate reduced gray-white matter separability, heavy head motion, or intensity non-uniformity artifacts |
| `cnr` | 3.633567 | 58.933 | -0.319 | lower_worse | lower values may indicate poor gray-white matter contrast or increased noise |
| `efc` | 0.586791 | 75.02 | 1.107 | higher_worse | higher values may indicate ghosting, blurring, or motion-related degradation |
| `fber` | 8524.744964 | 96.635 | 1.06 | lower_worse | lower values may indicate weak foreground signal relative to background noise |
| `fwhm_avg` | 4.67722 | 95.961 | 1.753 | higher_worse | higher values may indicate a blurrier or less spatially sharp image |
| `fwhm_y` | 4.87416 | 90.281 | 0.994 | higher_worse | higher values may indicate a blurrier or less spatially sharp image |
| `inu_range` | 0.403934 | 22.997 | -0.845 | closer_to_1_or_lower_range_better | values further from uniformity may indicate RF bias-field or intensity inhomogeneity |
| `qi_1` | 0.0 | 26.226 | -0.767 | higher_worse | higher values may indicate artifactual intensity voxels in the background region |
| `qi_2` | 0.011596 | 28.475 | -1.298 | higher_worse | higher values may indicate abnormal background noise structure after detected artifacts are removed |
| `size_y` | 256 | 94.552 | 1.207 | not_quality_metric | describes image dimensions; useful for comparability but not direct artifact evidence |
| `snr_gm` | 13.448548 | 33.702 | -1.288 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation |
| `snr_total` | 12.515561 | 32.07 | -0.532 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation |
| `snr_wm` | 20.696235 | 26.906 | -1.036 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation |
| `snrd_gm` | 120.118467 | 99.28 | 3.857 | lower_worse | lower values may indicate poor signal quality relative to background air noise |
| `snrd_wm` | 163.680743 | 99.474 | 3.639 | lower_worse | lower values may indicate poor signal quality relative to background air noise |
| `spacing_y` | 1.0 | 90.244 | 1.034 | not_quality_metric | describes image resolution; useful for comparability but not direct artifact evidence |
| `summary_bg_mean` | 7.019242 | 4.538 | -1.43 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_bg_median` | 5.309336 | 5.33 | -0.895 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_bg_stdv` | 7.26005 | 3.353 | -1.38 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_csf_k` | 0.013908 | 8.02 | -0.962 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_gm_k` | -0.003978 | 6.306 | -1.764 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_gm_mad` | 54.634477 | 4.305 | -1.115 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_gm_p05` | 647.109124 | 91.287 | 1.502 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_gm_stdv` | 54.566946 | 2.79 | -1.312 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `summary_wm_p95` | 1075.500584 | 9.402 | -0.532 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence |
| `tpm_overlap_csf` | 0.167053 | 1.484 | -1.315 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template |
| `tpm_overlap_gm` | 0.457527 | 3.141 | -1.193 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template |
| `tpm_overlap_wm` | 0.511256 | 4.523 | -1.109 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template |
| `wm2max` | 0.490671 | 69.17 | 0.499 | target_range | values outside the expected range may indicate abnormal high-intensity tails from vessels, fat, or other hyperintense signal |

---

## Task

You are a neuroimage QC assistant. Based solely on the evidence above, return a JSON object with this exact structure:

```json
{
  "decision": "pass" | "fail" | "uncertain",
  "confidence": 0.0–1.0,
  "summary": "one sentence",
  "flagged_metrics": ["metric_name", ...],
  "reasons": ["reason tied to a specific metric or metadata field", ...],
  "recommended_followup": ["action if needed", ...]
}
```

Rules:
- Base every reason on a metric or field present in this package. Do not invent evidence.
- Use "uncertain" if the evidence is mixed or insufficient to decide.
- Keep reasons short and grounded (e.g. "cjv=0.82, percentile=94 — elevated cortex/WM boundary blur").
- If no metrics are flagged, lean toward "pass" with high confidence only if key metrics are present and normal.
