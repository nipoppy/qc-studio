# Spec: An uploaded QC file naming unknown participants is rejected

---

**Screen:** landing

**Category:** edge

**Priority:** high

**Why end-to-end:** The guard against loading someone else's QC file into this
cohort ends in `st.stop()`, and what `st.stop()` does -- halt the script so the
preview and the load button are never rendered -- has no meaning outside a
running Streamlit app. A unit test can prove the set difference is computed;
only a browser can prove the rater is actually prevented from clicking Load.
If that broke, the app would report an error and offer to load the bad data
anyway.

---

### Given

A rater on a freshly loaded landing page, and a QC file whose rows name at
least one participant that is not in the cohort's participant list.

### When

The rater uploads that file.

### Then

ERROR_MESSAGES["no_participants"] is visible, naming the unknown participant.

### And (optional)

The load button is *not* on screen -- `st.stop()` halted the page before the
preview, so there is no way to commit the bad records.

---

### Copy used

MESSAGES["csv_uploader_label"]         "Choose a QC_status.csv file"
ERROR_MESSAGES["no_participants"]      formats {count} and {participants}
INFO_MESSAGES["load_records_button"]   "📥 Load These Records" -- asserted absent

### Notes

- **Test data:** same export schema as spec 005, but with a participant ID the
  cohort does not know -- something obviously synthetic like `sub-NOTREAL01`,
  so a reader can tell at a glance it is meant to be rejected. Generate it in
  the test, do not commit a fixture.
- `ERROR_MESSAGES["no_participants"]` is a format string with `{count}` and
  `{participants}`. Format it in the test with the same values the app would
  use, or assert on a distinctive fragment -- but never retype the sentence.
- The message begins with "❌", which `st.error` strips out and renders as a
  separate icon. `expect_text_visible` already handles that, so use it rather
  than a raw `get_by_text`.
- Participant IDs are normalised before comparison (`_normalize_participant_id`),
  which is what lets a re-uploaded export without the `sub-` prefix still
  match. Pick an unknown ID that cannot normalise onto a real one, or the
  test proves nothing.
- The negative assertion is the valuable half of this spec and the easy half
  to get wrong: `not_to_be_visible()` passes instantly against the pre-upload
  page, where the load button was never present either. Make sure the upload's
  rerun has settled first -- `upload_file` handles that -- so the absence
  being asserted is the *post-upload* absence.
