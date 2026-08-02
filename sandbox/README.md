# Sandbox Experiments

This folder keeps shared MRI QC inputs separate from experiment-specific outputs.

## Layout

- `data/qc_inputs/`: shared scan data for experiments. Each scan folder keeps source sidecar JSON, MRIQC JSON, and shared processed `metadata.json`/`iqms.json`.
- `iqms_context/`: shared IQM semantic context files by modality.
- `cloud_model_experiments/`: experiments that call cloud-hosted models. Each experiment writes evidence bundles, model results, and validation artifacts inside its own folder.
- `local_model_experiments/`: experiments that run local models. Each experiment writes compact prompts, rendered images, raw responses, validation reports, and results inside its own folder.

Shared data folders should stay JSON-only. Markdown evidence bundles (`PACKAGE.md`), raw model responses, validation reports, and result JSON files belong to the experiment that produced them.

## Default Flow

Build the default evidence package from shared raw inputs:

```bash
.venv/bin/python sandbox/cloud_model_experiments/IQMs_only_exp/build_package.py
```

Run the default Claude experiment on generated packages:

```bash
ANTHROPIC_API_KEY=... .venv/bin/python sandbox/cloud_model_experiments/IQMs_only_exp/run_experiment.py
```

Run a local LLaVA experiment from its own folder or from the repo root. Generated files are written back to that experiment folder.
