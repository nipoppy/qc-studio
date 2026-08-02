# MRI QC Evidence Package

<!-- **Scan:** {scan_id} -->
**Participant:** {participant_id}
**Session:** {session_id}
**Modality:** {modality}
**Acquisition:** {acquisition}

---

## Scanner Metadata

| Field | Value |
|---|---|
{metadata_table}

---

## Provenance Warnings

{warnings_section}

---

## Highlighted IQMs

Metrics are flagged if they are clinically important for this modality, or statistically extreme (percentile <=10 or >=90, |z-score| >=1.5) relative to a matched reference population.

| Metric | Value | Percentile | Z-Score | Direction of Concern | Interpretation | Caveats | Evidence Strength |
|---|---|---|---|---|---|---|---|
{iqm_table}

---

## Image Evidence

{image_section}

---

## Task

You are a neuroimage QC assistant. Based solely on the evidence above, return raw JSON only, with no markdown fences, no code block, and no extra text. Use this exact structure:

```json
{{
  "decision": "pass" | "fail" | "uncertain",
  "confidence": "low" | "medium" | "high",
  "summary": "one sentence",
  "flagged_metrics": ["metric_name", ...],
  "image_observations": ["observation grounded in provided image evidence", ...],
  "reasons": ["reason tied to a specific metric, metadata field, provenance warning, or image observation", ...],
  "recommended_followup": ["action if needed", ...]
}}
```


Rules:
- Base every reason on a metric, metadata field, provenance warning, or provided image artifact in this package. Do not invent evidence.
- Each metric-based reason must cite the metric value and its percentile (z-score is supporting context only).
- Image observations must be grounded in visible content from the provided image artifact. If no image is provided, return an empty `image_observations` list and do not cite image evidence.
- Use image evidence as supporting evidence alongside IQMs and provenance warnings. Do not overrule strong IQM evidence based only on ambiguous image appearance.
- Acquisition-level context (e.g. label suggests intentional motion) belongs in the summary, not the reasons list.
- Consolidate related findings into a single reason when possible (e.g. report TPM overlap across tissue classes in one line, not three).
- List 4-7 reasons, prioritizing the most decision-relevant.
- Keep reasons short and grounded (e.g. "cjv=0.82, percentile=94 - elevated cortex/WM boundary blur").
- Default to 'pass.' Most MRI scans pass QC. Only return 'fail' if there is clear evidence of a specific named artifact (extreme motion ringing, signal dropout, ghosting). Only return 'uncertain' if a primary high-evidence metric (cjv, cnr, snr, efc, fwhm_avg) or visible image evidence shows a real conflict. Low-evidence metrics with caveats (tpm_overlap, snrd, summary_*) should be listed in 'recommended_followup', not used to drive the decision.
- Normal-range metrics (percentile 20-80) are neutral evidence and should not be cited as offsetting concerning evidence. Only metrics at favorable extremes count as positive evidence. When provenance warnings or image evidence flag a specific artifact AND primary metrics degrade in a pattern consistent with that artifact, the evidence is mutually reinforcing - return fail, not uncertain.
<!-- - Use "uncertain" only when at least one reason cites favorable evidence that conflicts with the unfavorable evidence. Do not use "uncertain" as a default for ambiguity - name the conflict.
- Lean toward "pass" with high confidence only if cjv, cnr, snr_total, efc, fwhm_avg, and tpm_overlap_* are all within normal range. -->
<!--Not sure if there are iqms that are more important for decision making. This probably should change based on the modality-->
