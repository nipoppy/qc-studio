# Spec: Creating a checkpoint mid-session writes a snapshot of the ratings so far

---

**Screen:** viewer

**Category:** functional

**Priority:** medium

**Why end-to-end:** `_create_qc_checkpoint` can be unit-tested on its own, but
nothing proves the sidebar button is wired to it, nor that the records it
snapshots are the ones the rater actually entered through the widgets. This is
the app's crash-recovery story: if the button stopped reaching the writer, a
rater would keep clicking it, keep seeing a success message, and still lose
everything when the tab closed.

---

### Given

A rater part-way through QC who has rated the subject currently on screen.

### When

The rater clicks "🏁 Create checkpoint" in the sidebar.

### Then

SUCCESS_MESSAGES["checkpoint_saved"] is visible, and a `.tsv` file has been
written under `<output_dir>/checkpoints/` containing the rating just entered.

### And (optional)

Clicking "🏁 Create checkpoint" a second time without changing any rating in
between shows INFO_MESSAGES["checkpoint_unchanged"] and leaves the number of
checkpoint files unchanged.

---

### Copy used

MESSAGES["create_checkpoint_button"]     "🏁 Create checkpoint"
SUCCESS_MESSAGES["checkpoint_saved"]
INFO_MESSAGES["checkpoint_unchanged"]

### Notes

- Checkpoints land in `<output_dir>/checkpoints/`, a **subdirectory**, named
  `<rater_id>_<task>_checkpoint_<timestamp>.tsv` with the rater ID lowercased.
  The `output_files` fixture only lists the top level of `output_dir`, so it
  reports the `checkpoints` directory, not the file inside it. Either look
  inside that directory or extend the fixture -- decide before writing, and
  keep whatever you choose in `conftest.py`, not in the test.
- The timestamp has **one-second** granularity. Two checkpoints written inside
  the same second resolve to the same filename and the second overwrites the
  first. That does not affect this spec (the second click is a no-op by
  design), but it does mean a future "two real checkpoints" test cannot assume
  two files.
- SUCCESS_MESSAGES["checkpoint_saved"] does not interpolate the path -- it is
  a fixed string naming the directory, so assert on it as-is.
- Both messages render through the sidebar status banner and are popped from
  session state on the next rerun, so assert on them before interacting again.
