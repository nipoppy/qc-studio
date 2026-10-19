"""Tests for uploading a previously saved QC file on the landing page.

Spec: e2e/specs/005-upload-resumes-session.md
Spec: e2e/specs/007-upload-rejects-unknown-participants.md
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from constants import ERROR_MESSAGES, INFO_MESSAGES, MESSAGES, SUCCESS_MESSAGES
from shared.app_utils import click_button, expect_text_visible, upload_file

pytestmark = pytest.mark.edge

#: The export schema, as written by save_qc_results_to_csv.
COLUMNS = [
    "pipeline",
    "qc_task",
    "participant_id",
    "session_id",
    "task_id",
    "run_id",
    "timestamp",
    "rater_id",
    "rater_experience",
    "rater_fatigue",
    "final_qc",
    "notes",
]

#: Matches the default qc_config: these must line up with the configured
#: pipeline and task or the workflow filter drops the row and nothing loads.
KNOWN_PARTICIPANT = "sub-ED01"
UNKNOWN_PARTICIPANT = "sub-NOTREAL01"
#: Participant IDs are normalised before the cohort comparison, so the error
#: names the ID without its "sub-" prefix.
UNKNOWN_PARTICIPANT_AS_REPORTED = "NOTREAL01"

#: Hardcoded in views/landing_page.py; INFO_MESSAGES["load_records_button"]
#: is a stale constant that is no longer rendered anywhere.
CONFIRM_IMPORT_BUTTON = "📥 Confirm Import"


def _write_qc_file(directory: Path, participant_id: str) -> Path:
    """A previously exported QC file holding one rating for one participant.

    Generated rather than committed: a checked-in fixture rots silently when
    the export schema changes, while this fails loudly at the point of change.
    """
    row = {
        "pipeline": "fmriprep",
        "qc_task": "anat_wf_qc",
        "participant_id": participant_id,
        "session_id": "ses-01",
        "task_id": "",
        "run_id": "",
        "timestamp": "2026-01-01T00:00:00",
        "rater_id": "previous-rater",
        "rater_experience": "",
        "rater_fatigue": "",
        "final_qc": "PASS",
        "notes": "from an earlier session",
    }
    path = directory / "QC_status.tsv"
    path.write_text("\t".join(COLUMNS) + "\n" + "\t".join(row[c] for c in COLUMNS) + "\n")
    return path


def test_uploading_a_previous_qc_file_loads_its_records(app: Page, tmp_path: Path) -> None:
    """Given a rater on a fresh landing page and a previously exported QC file,
    When they upload it and click "📥 Load These Records",
    Then the records-loaded message appears and the app tells them to carry on
    with the rater form.
    """
    upload_file(app, _write_qc_file(tmp_path, KNOWN_PARTICIPANT))

    # csv_loaded fires on upload alone; it is not proof anything was committed.
    expect_text_visible(app, SUCCESS_MESSAGES["csv_loaded"].format(count=1, filename="QC_status.tsv"))

    click_button(app, CONFIRM_IMPORT_BUTTON)

    expect_text_visible(app, SUCCESS_MESSAGES["records_loaded"].format(count=1))
    expect_text_visible(app, INFO_MESSAGES["proceed_with_form"])


def test_uploading_unknown_participants_is_rejected(app: Page, tmp_path: Path) -> None:
    """Given a QC file naming a participant that is not in the cohort,
    When the rater uploads it,
    Then the unknown-participant error names it, and the load button is not
    offered -- st.stop() halts the page before the preview.
    """
    upload_file(app, _write_qc_file(tmp_path, UNKNOWN_PARTICIPANT))

    expect_text_visible(
        app,
        ERROR_MESSAGES["no_participants"].format(count=1, participants=UNKNOWN_PARTICIPANT_AS_REPORTED),
    )
    # Absence only means anything after the upload's rerun has settled, which
    # upload_file waits for: before it, the button was never present either.
    expect(app.get_by_test_id("stButton").filter(has_text=CONFIRM_IMPORT_BUTTON)).to_have_count(0)
