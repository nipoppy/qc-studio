---
name: qcs-reviewing-code
description: Review QC-Studio diffs, pull requests, commits, and files using concrete correctness checks and project-specific Python, Streamlit, Pydantic, BIDS, file-handling, and testing examples. Use to distinguish real defects from style preferences and report actionable findings by severity.
---

# Reviewing QC-Studio Code

Use this skill to find defects, not to produce a generic quality checklist.
Inspect the current implementation, callers, and tests before deciding that a
pattern is wrong.

## Review process

1. Identify the changed behavior and affected public interfaces.
2. Read the complete diff and surrounding functions.
3. Trace important inputs through callers to outputs or side effects.
4. Compare with current nearby patterns and tests.
5. Form a concrete failure hypothesis.
6. Confirm it by reasoning, search, or a focused command.
7. Report only findings that have a realistic trigger and impact.

## Source priority

Prefer:

1. Current implementation and callers
2. Current tests and CI configuration
3. Current architecture documentation
4. Historical summaries and proposals

Do not enforce a documented convention that the current codebase clearly does
not use. Do not excuse a correctness bug merely because similar code exists.

## Project map

Use this as orientation, then verify against the current tree:

- `ui/models/`: structured data, validation, serialization
- `ui/utils/`: parsing, file handling, export, and reusable helpers
- `ui/managers/`: application logic and state coordination
- `ui/components/`: reusable Streamlit rendering and orchestration
- `ui/views/`: page-level layouts
- `ui/pages/`: Streamlit page entrypoints
- `pipelines/`: pipeline-specific behavior and configuration
- `ui/tests/`: pytest suite and current behavioral expectations

## Severity

- `P1`: security, data loss, corruption, or broadly broken core behavior
- `P2`: concrete bug or regression under realistic conditions
- `P3`: smaller but real reliability or maintainability defect

Missing tests are usually not a standalone defect. Report them when the change
introduces risky, unverified behavior or when a missing regression test makes a
known bug likely to return.

## Finding template

```text
[P2] Preserve session ID when deduplicating QC records
File: ui/utils/export.py:84
Problem: Records are keyed by participant and task but not session. When one
participant has ses-01 and ses-02 for the same task, the later row replaces the
earlier row.
Impact: A valid QC result is silently lost during export.
Fix: Include session_id in the deduplication key and add a two-session test.
```

Every finding must answer:

- What input or state triggers the problem?
- What does the code do?
- What should it do?
- Why does that difference matter?

## Example: real finding versus preference

Valid:

```text
[P2] Handle malformed QC JSON without crashing the landing page
File: ui/utils/config.py:42
Problem: json.load() can raise JSONDecodeError, but this path is called during
page rendering without a handler. Selecting a malformed qc.json terminates the
Streamlit run instead of returning the existing empty configuration shape.
Fix: Catch JSONDecodeError at the configuration boundary and add a malformed
JSON test.
```

Not a finding:

```text
[P3] Rename `cfg` to `configuration`
```

Why not: the existing name is understandable and creates no demonstrated bug,
enforced-style violation, or meaningful maintenance risk.

## File and path handling

Preferred pattern:

```python
path = Path(config_path)
if not path.exists():
    return default_config()

try:
    with path.open() as file:
        return json.load(file)
except (OSError, json.JSONDecodeError):
    return default_config()
```

Potentially defective pattern:

```python
data = json.load(open(config_path))
```

Do not report it only because it looks different. Report the concrete issue
that applies: unmanaged resource, unhandled missing file, malformed JSON crash,
or inconsistent return contract.

Check:

- `Path` and string interoperability at public boundaries
- missing and malformed input behavior
- parent-directory creation before export
- deterministic TSV/CSV ordering when output stability matters
- accidental overwrite or deduplication across participant/session/task/run
- binary versus text mode
- partial data behavior for optional MRI, montage, and IQM inputs

## Pydantic models

Preferred tests and use:

```python
task = QCTask(base_mri_image_path="base.nii.gz")
assert task.base_mri_image_path == Path("base.nii.gz")

with pytest.raises(ValidationError):
    QCTask(montage_max_rows=99)
```

Check:

- required fields are truly required
- optional fields have intentional defaults
- validators accept and reject the intended range
- path or enum normalization matches callers
- serialization preserves fields consumed by exports or session state
- code uses Pydantic v2 APIs consistently with the installed version

A stylistic difference in annotation syntax is not automatically a defect.
Show an actual validation, compatibility, or serialization consequence.

## Streamlit and session state

Manager-mediated state is an established pattern in much of QC-Studio:

```python
SessionManager.set_rater_id(rater_id)
current = SessionManager.get_rater_id()
```

Direct mutation may deserve investigation:

```python
st.session_state["rater_id"] = value
```

Before reporting it, inspect nearby code. The defect is not “a rule was
violated”; it may be inconsistent key initialization, duplicated defaults,
state that is lost on rerun, or bypassed upsert/validation behavior.

Check:

- key initialization before reads
- widget keys remaining stable across reruns
- mutable defaults shared unexpectedly
- expensive file loading repeated on every rerun
- callbacks mutating the same state rendered in the current pass
- tests patching the object where it is imported and used

## BIDS and QC identity

Trace identity fields together:

```text
participant_id + session_id + pipeline + qc_task + optional task/run
```

Check for:

- collisions between sessions or runs
- inconsistent `sub-` and `ses-` prefixes
- filtering a participant while accidentally ignoring session
- sorting or export keys that omit part of the identity
- optional session handling for single-session datasets

Example finding:

```text
[P2] Do not treat different runs as the same QC record
File: ui/managers/session_manager.py:133
Problem: The upsert comparison omits run_id. Two functional runs with the same
participant, session, pipeline, and task replace each other.
Impact: The rater can save only one result for a multi-run acquisition.
Fix: Include run_id when the task is run-specific and cover run-1/run-2 in a
regression test.
```

Only report this if callers can actually create distinct run-specific records.

## Testing review

Good test:

```python
def test_load_mri_data_returns_empty_dict_when_file_is_missing(temp_dir):
    paths = {
        "base_mri_image_path": temp_dir / "missing.nii.gz",
        "overlay_mri_image_path": None,
    }

    assert load_mri_data(paths) == {}
```

Weak test:

```python
def test_current_page_bounds():
    current_page = 0
    if current_page < 1:
        current_page = 1
    assert current_page == 1
```

The weak test reproduces logic inside the test and never calls production code.
It can pass even if the application is broken.

Also flag placeholder tests:

```python
def test_page_config_is_wide():
    pass
```

Explain their impact accurately: they create false confidence or leave a new
behavior unverified; they do not directly break production.

## Compatibility and CI

The project CI currently targets Python 3.10 and runs:

```bash
black --check --config pyproject.toml ui pipelines
flake8 --config .flake8 ui pipelines --count --show-source --statistics
codespell --config .codespellrc README.md docs ui pipelines
python -m pytest ui/tests -q
```

Check new syntax and dependencies against Python 3.10. A formatter difference
is actionable when CI will fail, but label it as a CI/build issue rather than a
runtime correctness bug.

## Verification commands

Choose only commands relevant to the diff:

```bash
python -m pytest ui/tests/test_<module>.py -q
black --check --config pyproject.toml <changed-python-paths>
flake8 --config .flake8 <changed-python-paths>
```

Use a focused reproducer when a full test does not isolate the suspected
condition. Do not modify production files during a review.

## Avoid false positives

Do not report:

- personal naming or formatting preferences
- speculative failures with no reachable trigger
- architecture differences without a concrete consequence
- pre-existing issues outside the reviewed change, unless the change makes
  them newly reachable or materially worse
- missing documentation when behavior is clear and no project requirement
  applies
- “add more tests” without naming the risky behavior and expected assertion

If uncertain, state a question rather than presenting speculation as a defect.
