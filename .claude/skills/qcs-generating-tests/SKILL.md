---
name: qcs-generating-tests
description: Generate and update pytest tests for QC-Studio using its current fixtures, file-I/O patterns, Pydantic validation, Streamlit state mocking, and regression-testing conventions. Use when writing tests for ui modules, pipelines, bug fixes, boundary cases, or new behavior.
---

# Generating QC-Studio Tests

Use this skill as a practical testing cookbook. Read the target implementation
and nearby tests before selecting a template. Adapt examples to the real public
interface; do not copy them blindly.

## Test-writing workflow

1. State the behavior in plain language:
   `Given <starting state>, when <action>, then <observable result>.`
2. Find the nearest existing test file and reusable fixture.
3. Write the smallest test that would fail if the behavior broke.
4. Add one meaningful boundary, error, or regression case.
5. Run the test file.
6. Read failures before changing assertions. A failure may reveal a production
   defect rather than a bad test.

## Where tests go

| Source | Preferred location |
|---|---|
| `ui/models/<module>.py` | `ui/tests/test_models.py` or matching existing file |
| `ui/utils/<module>.py` | Existing relevant utility test file |
| `ui/managers/<module>.py` | `ui/tests/test_<module>.py` |
| `ui/components/<module>.py` | `ui/tests/test_<module>.py` |
| `ui/views/<module>.py` | Existing layout/view test file |
| Pipeline-specific code | Follow the nearest pipeline test convention |

Add to an existing file when it already owns the behavior. Create
`ui/tests/test_<module>.py` only when no existing file is a natural fit.

## Initial test-file template

Start here when a new test file is necessary:

```python
"""Tests for <module_name>."""

import pytest

from <package>.<module_name> import <public_name>


class Test<PublicName>:
    """Tests for <public behavior>."""

    def test_<action>_<expected_result>(self):
        """Return <expected result> when <condition>."""
        # Arrange
        <input_data> = ...

        # Act
        result = <public_name>(<input_data>)

        # Assert
        assert result == <expected>
```

Replace every placeholder. Remove `pytest` if it is unused. Match the nearby
test style even when it differs slightly from this starter.

## How to choose the first cases

For a new function, begin with this small table:

| Case | Question |
|---|---|
| Normal | What input demonstrates the intended behavior? |
| Boundary | What happens with empty, zero, first, last, or `None` input? |
| Invalid | What malformed input is part of the public contract? |
| Missing data | What happens when a file, task, participant, or session is absent? |
| Regression | What exact input previously triggered the reported bug? |

Do not create every possible case. Choose cases that exercise different
branches or protect important behavior.

## Pattern: pure function

Use direct inputs and outputs. Avoid mocks.

```python
class TestGetActivePanelCount:
    """Tests for counting active panels."""

    def test_returns_two_when_two_panels_are_selected(self):
        selected = {"niivue": True, "montage": False, "iqm": True}

        result = PanelLayoutManager.get_active_panel_count(selected)

        assert result == 2

    def test_returns_zero_when_no_panels_are_selected(self):
        selected = {"niivue": False, "montage": False, "iqm": False}

        result = PanelLayoutManager.get_active_panel_count(selected)

        assert result == 0
```

Why this works: each test names a behavior, invokes the public method, and
asserts an observable result.

## Pattern: temporary JSON or TSV file

Use `temp_dir` from `ui/tests/conftest.py` and write a real small file.

```python
def test_parse_qc_config_reads_montage_layout(temp_dir):
    qc_path = temp_dir / "qc.json"
    qc_path.write_text(
        json.dumps(
            {
                "anat_wf_qc": {
                    "montage_path": [str(temp_dir / "a.svg")],
                    "montage_max_rows": 2,
                    "montage_max_cols": 3,
                }
            }
        )
    )

    result = parse_qc_config(str(qc_path), "anat_wf_qc")

    assert result["montage_max_rows"] == 2
    assert result["montage_max_cols"] == 3
```

Add a failure-path test when the function promises graceful handling:

```python
def test_parse_qc_config_returns_defaults_for_malformed_json(temp_dir):
    qc_path = temp_dir / "qc.json"
    qc_path.write_text("{not valid json")

    result = parse_qc_config(str(qc_path), "anat_wf_qc")

    assert result["base_mri_image_path"] is None
    assert result["montage_path"] is None
```

Prefer this over mocking `open()` because it tests path handling, decoding, and
parsing together. Mock `open()` only for behavior that is difficult to produce
portably, such as a permission error.

## Pattern: Pydantic model

Test successful construction, normalization, serialization when relevant, and
one invalid case.

```python
from pydantic import ValidationError


def test_qc_task_converts_string_path_to_path(temp_dir):
    task = QCTask(base_mri_image_path=str(temp_dir / "base.nii.gz"))

    assert task.base_mri_image_path == temp_dir / "base.nii.gz"


def test_qc_task_rejects_invalid_montage_rows(temp_dir):
    with pytest.raises(ValidationError):
        QCTask(
            montage_path=str(temp_dir / "montage.svg"),
            montage_max_rows=99,
        )
```

Do not assert that Pydantic internals were called. Assert the model's public
result or documented validation error.

## Pattern: Streamlit session state

Patch the Streamlit object imported by the module under test. Initialize state
through the manager when testing manager behavior.

```python
import streamlit as st
from unittest.mock import patch


def test_set_rater_id_updates_session_state():
    state = {}

    with patch.object(st, "session_state", state):
        SessionManager.init_session_state()
        SessionManager.set_rater_id("rater-02")

        assert SessionManager.get_rater_id() == "rater-02"
```

If the existing test module provides a `mock_session_state` fixture, reuse it:

```python
def test_get_rater_id_defaults_to_empty_string(mock_session_state):
    st.session_state = mock_session_state.data

    assert SessionManager.get_rater_id() == ""
```

When testing a view, patch the name where it is used:

```python
@patch("views.landing_page.pd.read_csv")
def test_landing_page_reports_missing_participant_file(mock_read_csv, tmp_path):
    mock_read_csv.side_effect = FileNotFoundError
    mock_st = MagicMock()

    with patch("views.landing_page.st", mock_st):
        show_landing_page(
            participant_list_path=tmp_path / "missing.tsv",
            qc_config_path=tmp_path / "qc.json",
        )

    mock_st.error.assert_called()
```

Adapt the call signature to the current implementation.

## Pattern: parametrized cases

Use parametrization when the setup and assertion are the same:

```python
@pytest.mark.parametrize(
    ("selected", "expected"),
    [
        ({"niivue": True, "montage": False, "iqm": False}, 1),
        ({"niivue": True, "montage": True, "iqm": False}, 2),
        ({"niivue": False, "montage": False, "iqm": False}, 0),
    ],
)
def test_get_active_panel_count(selected, expected):
    assert PanelLayoutManager.get_active_panel_count(selected) == expected
```

Keep separate tests when cases have different meaning, setup, or expected
failure behavior.

## Pattern: regression test

Name the behavior, not an issue number alone. Reproduce the smallest input that
caused the bug.

```python
def test_add_qc_record_keeps_different_sessions_separate(mock_session_state):
    st.session_state = mock_session_state.data
    SessionManager.init_session_state()
    first = make_record(participant_id="sub-01", session_id="ses-01")
    second = make_record(participant_id="sub-01", session_id="ses-02")

    SessionManager.add_qc_record(first)
    SessionManager.add_qc_record(second)

    assert SessionManager.get_qc_records() == [first, second]
```

A useful regression test should fail before the fix and pass after it.

## Avoid weak tests

Do not add placeholders:

```python
def test_page_config_is_wide():
    pass
```

Do not reimplement production logic inside the test:

```python
def test_current_page_lower_bound():
    current_page = 0
    if current_page < 1:
        current_page = 1
    assert current_page == 1
```

Instead, call the application function responsible for that behavior. If no
callable boundary exists, report that the code may need a small extraction
before it can be tested cleanly.

Avoid assertions too broad to catch regressions:

```python
assert result is not None
```

Prefer the contract:

```python
assert result == {"base_mri_image_bytes": b"base content"}
```

## Fixture decision

- Keep setup inside one test when it is short and unique.
- Add a fixture to the test module when several tests in that module reuse it.
- Add a fixture to `ui/tests/conftest.py` only when multiple test modules need it.
- Prefer built-in `tmp_path` or the existing `temp_dir` fixture for files.
- Keep fixtures focused; avoid one giant fixture that hides important setup.

## Verification

Run the narrowest command first:

```bash
python -m pytest ui/tests/test_<module>.py -q
```

Run one test while developing:

```bash
python -m pytest ui/tests/test_<module>.py::TestClass::test_name -q
```

For shared behavior, expand to:

```bash
python -m pytest ui/tests -q
```

Use coverage to discover untested branches, not as proof of test quality:

```bash
python -m pytest ui/tests --cov=ui --cov-report=term-missing
```

Report the exact command and result. Separate test-code errors, production
failures, pre-existing failures, and missing-dependency failures.
