# Quickstart

The fastest way to see QC-Studio end to end is the bundled fMRIPrep demo.
It runs against a small BIDS dataset with fMRIPrep derivatives that comes bundled with the directory.

## 1. Install

Follow [Installation](installation.md) if you have not already.

## 2. Run the demo

From the repository root:

```bash
./fmriprep_demo.sh
```

Streamlit starts on port 8501 and prints the launch configuration:

```text
Launching QC-Studio with:
  qc_json=./pipelines/fmriprep/qc_demo.json
  qc_json_for_ui=../pipelines/fmriprep/qc_demo.json
  qc_task=anat_wf_qc
  dataset_dir=sample_data
  participant_list=sample_data/qc_participants_demo.tsv
  session_list=ses-01
  port=8501
```

Open `http://localhost:8501` on a browser.

## 3. Take your first ratings

**Landing page**:

1. **👤 Rater Information** — enter your rater name or ID, and adjust other metadata/autoplay settings as needed.
2. **🖼️ Display Panels** — choose which panels to show, and set the montage grid's maximum rows and columns. At least one panel is required.
3. **📤 Upload Existing QC File** — optional. Pick a previous results or checkpoint file to resume where you left off.

The sidebar lets you choose the QC task to rate and the [default rating](../guides/ratings.md#default-rating)
preselected on unrated pages.

Press **Continue to QC 🚀**.

**QC viewer** — one page per (participant, session):

- Left sidebar: **▶️ Play** / **⏸️ Pause** for [Autoplay](../guides/autoplay.md), **◀️ Previous** /
  **Next ▶️**, the page counter.
- Main area: the selected panels for the task, then **📊 Rate** with choices and a notes box.

Click a rating. It is saved the moment you click.
**Next** saves the page and advances; **🏁 Create checkpoint** writes a timestamped snapshot.

**Final page** — once every page is rated, **Next** opens a summary of your ratings.
Click **💾 Export Final Results** to write the final TSV(s).

## Running QC-Studio on your own data

Run `python ui/main.py --help` for more information on how to run the app with your own setup.
The demo is just a wrapper around this command.

## Next steps

- [Configuration](../guides/configuration.md) — every flag, the `qc.json` schema, substitutions, and output columns.
- [Rating schemes](../guides/ratings.md) — single and multi-facet ratings.
- [Autoplay](../guides/autoplay.md) — timed auto-advance for fast-pass review of large cohorts.
- [Architecture](../development/architecture.md) — how the code is organized, if you plan to contribute.
