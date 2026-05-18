# MRI QC Evidence Package

<!-- **Scan:** n/a -->
**Participant:** sub-000103
**Session:** n/a
**Modality:** T1w
**Acquisition:** headmotion2

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

## Provenance Warnings

- `large_rot_frame`: **true**
- `small_air_mask`: false

---

## Highlighted IQMs

Metrics are flagged if they are clinically important for this modality, or statistically extreme (percentile ≤10 or ≥90, |z-score| ≥1.5) relative to a matched reference population.

| Metric | Value | Percentile | Z-Score | Direction of Concern | Interpretation | Caveats | Evidence Strength |
|---|---|---|---|---|---|---|---|
| `cjv` | 0.43698 | 22.359 | -0.85 | higher_worse | higher values may indicate reduced gray-white matter separability, heavy head motion, or intensity non-uniformity artifacts | not specific to one artifact type; interpret with CNR, SNR, EFC, and visual report | medium |
| `cnr` | 3.045743 | 49.057 | -0.352 | lower_worse | lower values may indicate poor gray-white matter contrast or increased noise | depends on tissue segmentation quality | medium |
| `efc` | 0.598473 | 76.755 | 1.144 | higher_worse | higher values may indicate ghosting, blurring, or motion-related degradation | not specific to motion by itself; interpret with SNR, FWHM, CJV, and visual report | medium |
| `fber` | 4317.500828 | 94.703 | 0.454 | lower_worse | lower values may indicate weak foreground signal relative to background noise | special values can occur when background signal is absent or post-processed | medium |
| `fwhm_avg` | 4.58138 | 95.568 | 1.698 | higher_worse | higher values may indicate a blurrier or less spatially sharp image | interpret with acquisition resolution and preprocessing context | medium |
| `inu_range` | 0.666813 | 34.766 | -0.829 | closer_to_1_or_lower_range_better | values further from uniformity may indicate RF bias-field or intensity inhomogeneity | interpret with CJV and visual intensity shading | medium |
| `qi_1` | 0.0 | 26.226 | -0.767 | higher_worse | higher values may indicate artifactual intensity voxels in the background region | near-zero is expected for clean background; negative or special values may indicate missing background mask context | medium |
| `qi_2` | 0.007546 | 25.5 | -1.318 | higher_worse | higher values may indicate abnormal background noise structure after detected artifacts are removed | less directly interpretable than QI1 | low |
| `snr_gm` | 12.00402 | 28.729 | -1.292 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation | the QC book found SNR-derived metrics informative for motion in a T1w motion dataset; interpret by tissue and with visual evidence | high |
| `snr_total` | 10.550384 | 22.519 | -0.607 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation | the QC book found SNR-derived metrics informative for motion in a T1w motion dataset; interpret by tissue and with visual evidence | high |
| `snr_wm` | 16.076774 | 11.938 | -1.165 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation | the QC book found SNR-derived metrics informative for motion in a T1w motion dataset; interpret by tissue and with visual evidence | high |
| `snrd_gm` | 64.124988 | 93.47 | 1.652 | lower_worse | lower values may indicate poor signal quality relative to background air noise | depends on valid air/background estimation | medium |
| `snrd_wm` | 87.69702 | 92.862 | 1.704 | lower_worse | lower values may indicate poor signal quality relative to background air noise | depends on valid air/background estimation | medium |
| `summary_bg_mean` | 12.55268 | 8.9 | -1.379 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_bg_median` | 7.579607 | 7.779 | -0.895 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_csf_median` | 387.660925 | 90.773 | 1.469 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_gm_mad` | 60.331165 | 9.354 | -1.115 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_gm_stdv` | 60.915211 | 7.582 | -1.273 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_wm_median` | 1000.042388 | 96.726 | 1.315 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `tpm_overlap_csf` | 0.163676 | 1.261 | -1.315 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template | can reflect anatomy, registration, or segmentation rather than raw image quality alone | low |
| `tpm_overlap_gm` | 0.457232 | 3.12 | -1.193 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template | can reflect anatomy, registration, or segmentation rather than raw image quality alone | low |
| `tpm_overlap_wm` | 0.510265 | 4.353 | -1.109 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template | can reflect anatomy, registration, or segmentation rather than raw image quality alone | low |
| `wm2max` | 0.486281 | 68.589 | 0.49 | target_range | values outside the expected range may indicate abnormal high-intensity tails from vessels, fat, or other hyperintense signal | treat as supportive evidence, not a standalone failure criterion | medium |

---

## Task

You are a neuroimage QC assistant. Based solely on the evidence above, return raw JSON only, with no markdown fences, no code block, and no extra text. Use this exact structure:

```json
{
  "decision": "pass" | "fail" | "uncertain",
  "confidence": "low" | "medium" | "high",
  "summary": "one sentence",
  "flagged_metrics": ["metric_name", ...],
  "reasons": ["reason tied to a specific metric or metadata field", ...],
  "recommended_followup": ["action if needed", ...]
}
```


Rules:
- Base every reason on a metric or metadata field present in this package. Do not invent evidence.
- Each reason must cite the metric value and its percentile (z-score is supporting context only).
- Acquisition-level context (e.g. label suggests intentional motion) belongs in the summary, not the reasons list.
- Consolidate related findings into a single reason when possible (e.g. report TPM overlap across tissue classes in one line, not three).
- List 4–7 reasons, prioritizing the most decision-relevant.
- Keep reasons short and grounded (e.g. "cjv=0.82, percentile=94 — elevated cortex/WM boundary blur").
- Default to 'pass.' Most MRI scans pass QC. Only return 'fail' if there is clear evidence of a specific named artifact (extreme motion ringing, signal dropout, ghosting). Only return 'uncertain' if a primary high-evidence metric (cjv, cnr, snr, efc, fwhm_avg) shows a real conflict. Low-evidence metrics with caveats (tpm_overlap, snrd, summary_*) should be listed in 'recommended_followup', not used to drive the decision.
- Normal-range metrics (percentile 20–80) are neutral evidence and should not be cited as offsetting concerning evidence. Only metrics at favorable extremes count as positive evidence. When provenance warnings flag a specific artifact AND primary metrics degrade in a pattern consistent with that artifact, the evidence is mutually reinforcing — return fail, not uncertain.