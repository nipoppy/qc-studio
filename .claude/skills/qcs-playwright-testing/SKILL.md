---
name: qcs-playwright-testing
description: >
  Write Playwright end-to-end tests for QC-Studio's Streamlit UI. Use this
  skill whenever the user asks for a browser test, an end-to-end test, a UI
  test, or says things like "test the landing page", "write an e2e test for
  the rating flow", "add a Playwright test for X", or hands over a spec file
  from e2e/specs/. Also use it when a UI change needs its end-to-end coverage
  updated. This skill knows QC-Studio's test harness, its Streamlit-specific
  waiting rules, and its selector conventions, so the tests it produces run
  against the existing fixtures without rework.
---

# QC-Studio Playwright testing

You are writing browser-level tests for **QC-Studio**, a Streamlit app for
rating neuroimaging quality control. They live in `e2e/` and are separate from
`ui/tests/`, which mocks Streamlit and never opens a browser.

The selector test ids in `e2e/shared/app_utils.py` were taken from
streamlit/streamlit's own `e2e_playwright/shared/app_utils.py`; the smoke
tests confirm they work against this repo's installed Streamlit. If a getter
ever finds nothing after a Streamlit upgrade, fix the test id in
`e2e/shared/app_utils.py` once, rather than working around it in a test.

## What to test, and what not to

Test **QC-Studio's rules and its wiring**: validation that blocks submission,
cohort ordering, CSV filtering by QC task, resume-at-first-incomplete-page,
record de-duplication, export contents, the niivue fallback.

Do **not** test Streamlit itself. That a text input accepts typing, a radio
selects one option, or a form defers submission is Streamlit's behaviour,
covered by Streamlit's own suite. A test asserting it is pure maintenance cost.

Before writing any test, apply this filter: *would it fail if the UI stopped
calling the logic, and would a unit test miss that?* If a `ui/tests/` unit test
covers the behaviour equally well, write that instead -- it is faster and more
precise. Pure logic (string cleaning, config parsing, dataframe filtering)
belongs there, not here.

## Workflow

1. **Read the spec.** Specs live in `e2e/specs/`. If the user hasn't written
   one, draft it first using `e2e/specs/TEMPLATE.md` and confirm it before
   writing code -- the Then clause is where tests go wrong.
2. **Read the source** for the screen under test (`ui/views/`,
   `ui/components/`, `ui/managers/`) to learn the real widget labels, keys and
   validation order. Never infer them.
3. **Read `ui/constants.py`** for the exact copy. It is the single source of
   truth for every user-facing string.
4. **Check `e2e/shared/app_utils.py`** for an existing getter. If the widget
   type isn't covered, add a getter there -- do not inline a locator in a test.
5. **Write the test**, one spec per test function.
6. **Run just that test** and report the result:
   `pytest e2e/tests/test_<name>.py::<test_name> -v`

## Harness

```python
def test_something(app: Page):   # `app` is a loaded, settled landing page
    ...
```

The `app` fixture handles the server and the first load. Never launch Streamlit
inside a test, never hardcode a port or URL, never call `page.goto`.

To test a different pipeline, override `qc_config` at module level:

```python
@pytest.fixture(scope="module")
def qc_config():
    return QCAppConfig(pipeline="freesurfer", qc_task="fs_wf_qc",
                       qc_json="pipelines/freesurfer/qc_demo.json")
```

Write files into the `output_dir` fixture's directory only; never the repo's
real `./output`.

## The rules that matter

**Wait after every interaction.** Streamlit re-runs its whole script on each
interaction, so an assertion made immediately after a click tests the *previous*
render. The helpers in `shared/app_utils.py` (`click_button`,
`click_form_submit`, `check_checkbox`, `upload_file`) already call
`wait_for_app_run`. If you interact with a locator directly, call it yourself:

```python
from shared.waits import wait_for_app_run
some_locator.click()
wait_for_app_run(app)
expect(...).to_be_visible()
```

This matters most for negative assertions -- `not_to_be_visible()` passes
instantly against the stale page, producing a green test for a real bug.

**Never hardcode user-facing copy.** Import it:

```python
from constants import MESSAGES, ERROR_MESSAGES
expect_text_visible(app, ERROR_MESSAGES["invalid_rater_id"])
```

`e2e/conftest.py` puts `ui/` on `sys.path`, matching `ui/tests/conftest.py`.

**Form buttons are not buttons.** `st.form_submit_button` renders with a
different test id than `st.button`. The rater form's "✅ Continue to QC" needs
`click_form_submit`, not `click_button`.

**Assert on what is visible**, never on session state. The one exception is
export: the tests own `output_dir`, so asserting on the written CSV is valid
and is the strongest assertion in the suite.

**Prefer `get_by_key`** where the widget has an explicit `key=` in the source
-- `st-key-<key>` survives copy changes, label-based lookup does not. If a
widget you test often has no key, suggest adding one rather than relying on
its label.

## Conventions

- Files: `e2e/tests/test_<flow>.py`; functions: `test_<the_rule>`, named after
  the rule, not the mechanics (`test_empty_rater_id_blocks_submission`, not
  `test_click_button`).
- One spec, one test function. A docstring restating the Given/When/Then.
- Mark with `pytest.mark.smoke`, `.flow`, or `.edge`.

## After writing

Tell the user the file path, the command to run that one test, and any test id
or label you had to guess. Call out edge cases you noticed but didn't cover, so
they can decide whether to add specs for them.
