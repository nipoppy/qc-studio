# QC-Studio MVP Scope

## Design Overview
![overview](../assets/nipoppy-qc-studio_overview.jpg)

## Key requirements: datatypes / formats
- Support visualization of stardarized MRI data
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
- QC UI is populated based on files listed in the `pipeline_qc.json` (fixed schema) 
    - Does allow custom “qc-task” definitions. 
- Only single base image and overlay in niivue panel 
- Only SVG, JPEG, or PNG support in the montage viewer. No HTMLs. 
- Only pass | fail | uncertain ratings supported 

## Tasks
- Configs
    - Generate MRI modality / pipeline specific `qc.json` (see for example [fmriprep/qc.json](../pipelines/fmriprep/qc.json))

- UI-data-handler 
    - Write Pydantic json parser (see [models/qc_models.py](../ui/models/qc_models.py))
    - Write data loaders (see [utils/](../ui/utils/))
        - MRI ([data_loaders.py](../ui/utils/data_loaders.py))
        - SVGs ([image_processing.py](../ui/utils/image_processing.py))
        - TSVs/configs ([config.py](../ui/utils/config.py))
    - Handle chunking for pagination ([panel_layout_manager.py](../ui/managers/panel_layout_manager.py))
        - n_subjects per page 
        - n_QC tasks per page 

- UI-layout (see [managers/](../ui/managers/))
    - Overall layout manager → [panel_layout_manager.py](../ui/managers/panel_layout_manager.py)
    - Niivue streamlit integration →  [niivue_viewer_manager.py](../ui/managers/niivue_viewer_manager.py)
    - SVG panel → [qc_viewer.py](../ui/components/qc_viewer.py)
    - IQM panel (optional for MVP)
    - Rating controls and save/next flow ([qc_viewer.py](../ui/components/qc_viewer.py))
    - Sidebar cohort navigation ([sidebar_cohort_nav.py](../ui/views/sidebar_cohort_nav.py))

- Write <rater>_qc_scores.tsv (see [utils/export.py](../ui/utils/export.py))
     - Handle overwrite / append  


## Pipelines to support
- mriqc
- freesurfer
- fmriprep
- qsiprep
- qsirecon
- xcpd
- [agitation](https://github.com/Neuro-iX/agitation?tab=readme-ov-file)
