# Spec: Exporting over an existing results file needs a second, explicit confirmation

---

**Screen:** complete

**Category:** edge

**Priority:** high

**Why end-to-end:** This is the app's last line of defence against a rater
destroying finished work, and it only exists as an interaction: the first click
*must not* write, and the second one must. `_require_overwrite_confirmation`
can be unit-tested in isolation, but nothing there proves the export button is
wired through it, nor that the confirm button that appears afterwards actually
writes. If that wiring inverted, the first click would overwrite silently --
and the only evidence would be a file that is already gone.

---

### Given

A rater who has finished QC, is on the congratulations page, and has already
clicked "💾 Export Final Results" once, so the export file exists on disk.

### When

The rater clicks "💾 Export Final Results" a second time, at the same path.

### Then

A warning naming the file that would be overwritten is visible, and a
confirm button labelled "Overwrite existing file" is on screen.

### And (optional)

The export has *not* happened yet -- the file on disk is unchanged until the
confirm button is clicked, and clicking it shows
SUCCESS_MESSAGES["records_exported"].

---

### Copy used

MESSAGES["export_results_button"]        "💾 Export Final Results"
SUCCESS_MESSAGES["records_exported"]

The two warnings and the confirm button label are **hardcoded** in
`views/congratulations_page.py` -- there are no `constants.py` keys for them
yet. Add them before writing this test rather than hardcoding the strings in
the test:

  "⚠️ {label} will overwrite the existing file: {target}"   (first click)
  "⚠️ Existing export file will be overwritten: {target}"   (next render)
  "Overwrite existing file"                                 (confirm button)

### Notes

- **Two different warnings are involved**, which is easy to get wrong. The
  first click calls `_require_overwrite_confirmation`, which renders
  `"{label} will overwrite..."` and returns False. On the *next* render the
  page takes a different branch and shows `"Existing export file will be
  overwritten..."` plus the confirm button. Decide which of the two this spec
  asserts on -- the second is the stable one, since it is what the rater is
  actually looking at when they decide.
- The confirm button has an explicit key, `confirm_congrats_overwrite`, so
  `get_by_key` works for it and is preferable to the hardcoded label.
- Reaching the congratulations page means completing the cohort. The demo
  config is a single subject and a single cohort page, so this is one rating
  plus "Confirm and Next" -- not a long journey. Say in the test setup which
  rating is used.
- The export path is editable on the page (`CONGRATS_EXPORT_PATH_KEY`). Leave
  it at its default so the file lands in the test's own `output_dir`, and use
  the `output_files` fixture to check what was written.
- **The viewer's sidebar "💾 Save progress" has no such guard** -- it
  overwrites silently. `_require_overwrite_confirmation` is defined in
  `qc_viewer.py` but never called, and `_save_qc_record`'s `allow_overwrite`
  parameter is never read. This spec deliberately covers the congratulations
  page only; whether the sidebar save *should* be guarded is a product
  question, not something to paper over in a test.
