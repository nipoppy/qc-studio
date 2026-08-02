# Sandbox Experiments

This folder keeps shared MRI QC inputs separate from experiment-specific outputs.

## Layout

- `data/qc_inputs/`: shared scan data for experiments. Each scan folder keeps source sidecar JSON, MRIQC JSON, and shared processed `metadata.json`/`iqms.json`.
- `iqms_context/`: shared IQM semantic context files by modality.
- `qc_package.py`: shared Python helpers for loading QC inputs, enriching IQMs, building Markdown template context, and rendering templates.
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

## Adding a New Markdown Package Experiment

Create a new experiment folder with its own template and renderer:

```text
sandbox/cloud_model_experiments/my_new_exp/
  PACKAGE_TEMPLATE.md
  render_package.py
  package/
```

Use `sandbox.qc_package` in `render_package.py` for the shared work:

- `prepare_qc_data(...)`: load BIDS metadata, MRIQC IQMs, reference stats, and semantic context
- `write_shared_qc_data(...)`: write reusable `metadata.json` and `iqms.json` into `data/qc_inputs`
- `build_template_context(...)`: create common placeholders such as `{metadata_table}`, `{iqm_table}`, and `{warnings_section}`
- `render_markdown_template(...)`: render any experiment-specific `PACKAGE_TEMPLATE.md`

For templates with additional placeholders, pass `extra_context`:

```python
context = build_template_context(
    scan_id=args.scan_id,
    participant_id=args.participant_id,
    session_id=args.session_id,
    modality=args.modality,
    acquisition=args.acquisition,
    qc_data=qc_data,
    extra_context={
        "image_section": render_image_section(args.image),
    },
)
```

See `cloud_model_experiments/image_evidence_exp/` for a copyable example that adds an `{image_section}` placeholder.
