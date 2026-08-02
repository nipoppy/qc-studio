# MRI QC Evidence Package

<!-- **Scan:** n/a -->
**Participant:** sub-000103
**Session:** n/a
**Modality:** T1w
**Acquisition:** standard

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
| `cjv` | 0.308044 | 6.406 | -0.852 | higher_worse | higher values may indicate reduced gray-white matter separability, heavy head motion, or intensity non-uniformity artifacts | not specific to one artifact type; interpret with CNR, SNR, EFC, and visual report | medium |
| `cnr` | 4.293029 | 67.822 | -0.283 | lower_worse | lower values may indicate poor gray-white matter contrast or increased noise | depends on tissue segmentation quality | medium |
| `efc` | 0.576639 | 73.496 | 1.074 | higher_worse | higher values may indicate ghosting, blurring, or motion-related degradation | not specific to motion by itself; interpret with SNR, FWHM, CJV, and visual report | medium |
| `fber` | 22400.111111 | 98.609 | 3.062 | lower_worse | lower values may indicate weak foreground signal relative to background noise | special values can occur when background signal is absent or post-processed | medium |
| `fwhm_avg` | 4.638243 | 95.798 | 1.73 | higher_worse | higher values may indicate a blurrier or less spatially sharp image | interpret with acquisition resolution and preprocessing context | medium |
| `inu_range` | 0.559892 | 33.001 | -0.835 | closer_to_1_or_lower_range_better | values further from uniformity may indicate RF bias-field or intensity inhomogeneity | interpret with CJV and visual intensity shading | medium |
| `qi_1` | 0.0 | 26.226 | -0.767 | higher_worse | higher values may indicate artifactual intensity voxels in the background region | near-zero is expected for clean background; negative or special values may indicate missing background mask context | medium |
| `qi_2` | 0.007512 | 25.464 | -1.319 | higher_worse | higher values may indicate abnormal background noise structure after detected artifacts are removed | less directly interpretable than QI1 | low |
| `snr_gm` | 14.226755 | 34.902 | -1.285 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation | the QC book found SNR-derived metrics informative for motion in a T1w motion dataset; interpret by tissue and with visual evidence | high |
| `snr_total` | 13.543813 | 36.429 | -0.493 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation | the QC book found SNR-derived metrics informative for motion in a T1w motion dataset; interpret by tissue and with visual evidence | high |
| `snr_wm` | 23.034122 | 31.701 | -0.97 | lower_worse | lower values may indicate poor tissue-specific or overall signal quality and can support assessment of motion-related degradation | the QC book found SNR-derived metrics informative for motion in a T1w motion dataset; interpret by tissue and with visual evidence | high |
| `snrd_gm` | 137.326499 | 99.67 | 4.535 | lower_worse | lower values may indicate poor signal quality relative to background air noise | depends on valid air/background estimation | medium |
| `snrd_wm` | 192.219006 | 99.728 | 4.366 | lower_worse | lower values may indicate poor signal quality relative to background air noise | depends on valid air/background estimation | medium |
| `summary_bg_mean` | 4.64011 | 1.92 | -1.452 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_bg_median` | 4.597701 | 4.42 | -0.895 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_bg_stdv` | 4.299209 | 0.218 | -1.411 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_csf_mad` | 88.615309 | 5.215 | -1.394 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_gm_mad` | 48.832441 | 1.14 | -1.115 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_gm_stdv` | 50.216407 | 0.834 | -1.339 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `summary_wm_p95` | 1058.374998 | 1.034 | -0.533 | context_dependent | describes intensity distributions for tissue or background compartments; useful for derived checks but weak as direct model evidence | usually do not send all summary fields to the model unless specifically flagged | low |
| `tpm_overlap_csf` | 0.169594 | 1.645 | -1.315 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template | can reflect anatomy, registration, or segmentation rather than raw image quality alone | low |
| `tpm_overlap_gm` | 0.458758 | 3.274 | -1.193 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template | can reflect anatomy, registration, or segmentation rather than raw image quality alone | low |
| `tpm_overlap_wm` | 0.51196 | 4.686 | -1.108 | lower_worse | lower values may indicate poorer tissue alignment or segmentation consistency with the template | can reflect anatomy, registration, or segmentation rather than raw image quality alone | low |
| `wm2max` | 0.530683 | 74.956 | 0.582 | target_range | values outside the expected range may indicate abnormal high-intensity tails from vessels, fat, or other hyperintense signal | treat as supportive evidence, not a standalone failure criterion | medium |

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
<!-- - Use "uncertain" only when at least one reason cites favorable evidence that conflicts with the unfavorable evidence. Do not use "uncertain" as a default for ambiguity — name the conflict.
- Lean toward "pass" with high confidence only if cjv, cnr, snr_total, efc, fwhm_avg, and tpm_overlap_* are all within normal range. -->
<!--Not sure if there are iqms that are more important for decision making. This probably should change based on the modlity-->