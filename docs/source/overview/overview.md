# Overview

QC-Studio is a web-based quality control (QC) application for neuroimaging data. It gives raters
one place to look at raw BIDS data, processed pipeline derivatives, and image quality metrics
(IQMs), assign a structured QC decision with optional notes, and export the result as a
tab-separated table.

![QC-Studio design overview](https://raw.githubusercontent.com/nipoppy/qc-studio/main/assets/nipoppy-qc-studio_overview.jpg)

## Why it exists

Neuroimaging pipelines produce volumes, figures, and summary metrics for every subject and session.
Reviewing those outputs usually means opening files by hand, in one tool per output type, and keeping ratings in a spreadsheet.
That is slow and hard to reproduce.

QC-Studio streamlines the process by providing a unified, flexible QC interface compatible with multiple pipelines.

## Vocabulary

These terms are used throughout the documentation.

| Term | Definition |
|------|------------|
| **Cohort page** | One review unit: a single (participant, session) pair. |
| **QC task** | One key in `qc.json` mapping to the files displayed for that task. |
| **Pipeline** | The neuroimaging pipeline whose outputs are being reviewed. |
| **Panel** | One of the three optional views on the QC viewer: the Niivue 3D MRI viewer, the Montage, or QC Metrics (IQM distributions). |
| **Montage** | A 2D grid of images (SVG, PNG, JPG/JPEG). |
| **IQM** | Image quality metric, typically an MRIQC group-level table or a per-subject JSON sidecar, shown as a distribution plot. |
| **Rating** | A QC decision (by default **PASS**, **FAIL**, or **UNCERTAIN**), recorded per QC task per cohort page. See also [Rating schemes](../guides/ratings.md). |
| **Facet** | A named aspect of the image, rated separately in a multi-facet task. |
| **Checkpoint** | A timestamped snapshot of the current QC records`, which can be loaded later to resume. |
| **Autoplay** | Timed auto-advance through the cohort. See [Autoplay](../guides/autoplay.md). |

## Panels

| Panel | Default | Contents |
|-------|---------|----------|
| **3D MRI (Niivue)** | on | Interactive 3D rendering of a base NIfTI (and optional overlay) |
| **Montage** | on | 2D image montage for the task |
| **QC Metrics** | off | IQM distribution plots and a metrics table |

## Supported pipelines

Ready-made `qc.json` files are available in the [`pipelines/`](https://github.com/nipoppy/qc-studio/tree/main/pipelines) directory. See also [Bundled pipeline configurations](../guides/configuration.md#bundled-pipeline-configurations).

## Related projects

- [Nipoppy](https://github.com/nipoppy/nipoppy) — standardized organization and processing of
  neuroimaging-clinical datasets.
- [NiiVue](https://github.com/niivue/niivue) — the 3D medical image viewer behind the Niivue
  panel.
- [Streamlit](https://streamlit.io/) — the Python web app framework QC-Studio is built on.
- [MRIQC](https://github.com/nipreps/mriqc) — the usual source of image quality metrics.

## Next steps

Continue with [Installation](installation.md), or jump straight to the
[Quickstart](quickstart.md) if you already have an environment.
