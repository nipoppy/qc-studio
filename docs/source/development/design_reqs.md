# Design Requirements

## Key requirements: datatypes / formats
- Support visualization of standardized MRI data
    - Raw BIDS datatypes: `anat`, `dwi`, `func`, `fmap`

- Support visualization of processed data from these pipelines (MRI derivatives)
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

## Pipelines to support
- mriqc
- freesurfer
- fmriprep
- qsiprep
- qsirecon
- xcpd
- [agitation](https://github.com/Neuro-iX/agitation?tab=readme-ov-file)
