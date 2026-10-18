# Spec: Save progress writes the rater's QC results to the output directory

---

**Screen:** viewer

**Category:** functional

**Priority:** high

**Why end-to-end:** This is the "did my work actually get saved" question. The
writer (`save_qc_results_to_csv`) is unit-testable, but nothing there proves
the sidebar button reaches it, nor that the rows it writes are the ones the
rater entered through the widgets rather than a stale or empty snapshot. A
break here is silent and total: the rater sees a success message either way.

---

### Given

A rater part-way through QC who has rated the subject on screen.

### When

The rater clicks "💾 Save progress" in the sidebar.

### Then

SUCCESS_MESSAGES["records_saved"] is visible, naming the file.

### And (optional)

A file has appeared in the test's output directory containing one row for the
subject just rated, with the rating in its `final_qc` column.

---

### Copy used

MESSAGES["save_progress_button"]      "💾 Save progress"
SUCCESS_MESSAGES["records_saved"]     formats {path} with the file *name*
QC_RATINGS                            ["PASS", "FAIL", "UNCERTAIN"]

### Notes

- Use the `output_files` fixture, not a raw listing: tests in a module share
  one `output_dir`, so a bare `iterdir()` can pick up a neighbour's file and
  pass for the wrong reason. Unlike checkpoints (spec 009), this file lands at
  the **top level** of the output dir, which is what `output_files` sees.
- The written file is a TSV whose columns are the export schema -- `pipeline`,
  `qc_task`, `participant_id`, `session_id`, `task_id`, `run_id`, `timestamp`,
  `rater_id`, `rater_experience`, `rater_fatigue`, `final_qc`, `notes`. Assert
  on `final_qc` for the rated participant rather than on the whole file, so the
  test does not break every time a column is added.
- `SUCCESS_MESSAGES["records_saved"]` is formatted with `Path(out_file).name`,
  not the full path, and the app appends a second line ("Saved N record(s)
  across M unique participant(s)") that is **not** in `constants.py`. Assert on
  the constant, not on the appended sentence.
- A rating must be set first. `_record_qc_for_current_participant` returns
  early when the rating is `None`, so saving an untouched page writes nothing
  and shows INFO_MESSAGES["no_export_records"] instead -- which would make a
  carelessly written version of this test pass against an empty file.
- The save path is editable in the sidebar (`qc_save_path`). Leave it at its
  default so the file lands in the test's own output dir.
- This spec was previously numbered 004; that number now covers the final
  export and its overwrite guard.
