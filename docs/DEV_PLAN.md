# QC-Studio MVP Scope

## Design Overview
![overview](../assets/nipoppy-qc-studio_overview.jpg)

## Key requirements: datatypes / formats
- Support visualization of curated data
    - Raw BIDS (TBD: how to handle relative paths not starting from `derivatives`)
    - MRIQC 

- Support visualization of processed data from these pipelines 
    - fMRIPrep 
    - Freesurfer
    - QSIPrep
    - QSIRecon 

## Key requirements: UI
- Visualize 3D MRI using niivue
- Display flat image montages 
- Display IQMs (optional for MVP) 

## Constraints 
- User has full access to data either locally or via ssh 
- QC UI is populated based on files listed in the `pipeline_qc.json` (fixed schema) 
    - Does allow custom “qc-task” definitions. 
- Only single base image and overlay in niivue panel 
- Only SVGs or PNGs for montage viewer. No HTMLs. 
- Only pass | fail | uncertain ratings supported 

## Tasks
- Configs
    - Generate `pipeline_qc.json` (see for example [fmriprep/qc.json](../pipelines/fmriprep/qc.json))

- UI-orchestrator (see [app.py](../ui/app.py))
    - Handle argparse ([main.py](../ui/main.py))
    - Web-app init / global parameters
    - Calls to data handler
    - Calls to layout managers

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
    - Rating panel ([pagination.py](../ui/components/pagination.py))

- Write <rater>_qc_scores.tsv (see [utils/export.py](../ui/utils/export.py))
     - Handle overwrite / append  


## Pipelines to support
- mriqc
- freesurfer
- fmriprep
- qsiprep
- qsirecon
- [agitation](https://github.com/Neuro-iX/agitation?tab=readme-ov-file)
