# Spec: Uploading a previous QC file loads its records back into the session

---

**Screen:** landing

**Category:** functional

**Priority:** high

**Why end-to-end:** This is how a rater picks up work from a previous day, and
it runs through machinery no unit test exercises together: Streamlit's real
file uploader, a pandas parse of the uploaded bytes, participant-ID
normalisation, deduplication, a preview, and only then a button that commits
the records to the session. The parsing can be unit-tested; that the uploader
is wired to it, and that the load button commits what the preview showed,
cannot.

---

### Given

A rater on a freshly loaded landing page, and a previously exported QC file
holding a rating for a participant that is in the cohort.

### When

The rater uploads that file and clicks "📥 Load These Records".

### Then

SUCCESS_MESSAGES["records_loaded"] is visible, reporting the number of records
loaded.

### And (optional)

INFO_MESSAGES["proceed_with_form"] is visible -- the app is telling the rater
to carry on with the rater form, not silently advancing them.

---

### Copy used

MESSAGES["csv_uploader_label"]        "Choose a QC_status.csv file"
SUCCESS_MESSAGES["csv_loaded"]        shown on upload, before the load click
SUCCESS_MESSAGES["records_loaded"]
INFO_MESSAGES["proceed_with_form"]
INFO_MESSAGES["load_records_button"]  "📥 Load These Records"

### Notes

- **Test data:** the file needs the export schema -- `pipeline`, `qc_task`,
  `participant_id`, `session_id`, `task_id`, `run_id`, `timestamp`,
  `rater_id`, `rater_experience`, `rater_fatigue`, `final_qc`, `notes`. The
  participant must be one the cohort knows (`sub-ED01` for the default
  config) and `qc_task` must match the configured task (`anat_wf_qc`), or the
  task filter drops the row and the load reports zero records.
- Write the file from the test into `tmp_path` rather than committing a
  fixture: a checked-in file silently rots when the export schema changes,
  whereas a generated one fails loudly at the point of change.
- The upload is read with `sep=None, engine="python"`, so it sniffs the
  delimiter -- TSV and CSV both work despite the widget's label saying CSV.
  `UPLOAD_FILE_TYPES` gates the extension, so check what it allows before
  naming the file.
- `upload_file` in `app_utils.py` is flagged **UNVERIFIED** -- its test id was
  inferred rather than taken from Streamlit's own suite, because that suite
  has no file-uploader helper. If the uploader cannot be found, that is the
  first thing to check, and fixing it there is part of this spec's work.
- Two success messages appear in sequence. `csv_loaded` fires on upload,
  before any click; `records_loaded` only after the load button. Asserting the
  wrong one passes without proving anything was committed to the session.
