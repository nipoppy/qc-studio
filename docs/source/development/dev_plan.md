# Roadmap

## Design Overview
![overview](https://raw.githubusercontent.com/nipoppy/qc-studio/main/assets/nipoppy-qc-studio_overview.jpg)

## Key requirements: datatypes / formats
- Support visualization of standardized MRI data
    - Raw BIDS

- Support visualization of processed data from these pipelines (i.e. MRI Derivatives)
    - fMRIPrep
    - Freesurfer
    - QSIPrep

- Support image-quality-metrics (IQM) distribution plots
    - MRIQC

## Key requirements: UI
- Visualize 3D MRI using [NiiVue](https://github.com/niivue/niivue)
- Display flat image montages
- Display interactive distribution plots

## Constraints
- User has full access to data either locally or via ssh
- QC UI is populated based on files listed in the `qc.json` (fixed schema)
    - Does allow custom “qc-task” definitions.
- Only single base image and overlay in niivue panel
- Montage panel supports only 2D image files: SVG, PNG, JPG/JPEG. No HTML.
- Only pass | fail | uncertain ratings supported

## Tasks
- Configs
    - Generate MRI modality / pipeline specific `qc.json` (see for example [fmriprep/qc.json](https://github.com/nipoppy/qc-studio/blob/main/pipelines/fmriprep/qc.json))

- UI-data-handler
    - Write Pydantic json parser (see [models/qc_models.py](https://github.com/nipoppy/qc-studio/blob/main/ui/models/qc_models.py))
    - Write data loaders (see [utils/](https://github.com/nipoppy/qc-studio/blob/main/ui/utils/))
        - MRI ([data_loaders.py](https://github.com/nipoppy/qc-studio/blob/main/ui/utils/data_loaders.py))
        - 2D montage images: SVG, PNG, JPG/JPEG ([image_processing.py](https://github.com/nipoppy/qc-studio/blob/main/ui/utils/image_processing.py))
        - TSVs/configs ([config.py](https://github.com/nipoppy/qc-studio/blob/main/ui/utils/config.py))
    - Handle chunking for pagination ([panel_layout_manager.py](https://github.com/nipoppy/qc-studio/blob/main/ui/managers/panel_layout_manager.py))
        - n_subjects per page
        - n_QC tasks per page

- UI-layout (see [managers/](https://github.com/nipoppy/qc-studio/blob/main/ui/managers/))
    - Overall layout manager → [panel_layout_manager.py](https://github.com/nipoppy/qc-studio/blob/main/ui/managers/panel_layout_manager.py)
    - Niivue streamlit integration →  [niivue_viewer_manager.py](https://github.com/nipoppy/qc-studio/blob/main/ui/managers/niivue_viewer_manager.py)
    - Montage panel → [qc_viewer.py](https://github.com/nipoppy/qc-studio/blob/main/ui/components/qc_viewer.py)
    - IQM panel (optional for MVP)
    - Rating controls and save/next flow ([qc_viewer.py](https://github.com/nipoppy/qc-studio/blob/main/ui/components/qc_viewer.py))
    - Sidebar cohort navigation ([sidebar_cohort_nav.py](https://github.com/nipoppy/qc-studio/blob/main/ui/views/sidebar_cohort_nav.py))

- Write `<rater>_<pipeline>_<task>_qc_status.tsv` (see [utils/export.py](https://github.com/nipoppy/qc-studio/blob/main/ui/utils/export.py))
     - Handle overwrite / append


## Pipelines to support
- mriqc
- freesurfer
- fmriprep
- qsiprep
- qsirecon
- xcpd
- [agitation](https://github.com/Neuro-iX/agitation?tab=readme-ov-file)
