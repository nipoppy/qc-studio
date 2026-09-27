---
name: qcs-playwright-testing
description: >
  Write an individual Playwright end-to-end test for QC-Studio's Streamlit UI,
  in e2e/tests/. Use when asked for a browser test, an e2e test, or a UI test —
  "test the landing page", "add a Playwright test for the rating flow" — or when
  handed a spec file from e2e/specs/. For orientation on how the e2e suite is
  built, read qcs-understanding-e2e first. For pytest unit tests in ui/tests/,
  use qcs-generating-tests instead.
---

# Writing a QC-Studio Playwright test

Tests live in `e2e/tests/`, run against the real app in a real browser, and are
separate from `ui/tests/`, which mocks Streamlit.

## Before writing

1. **Read the spec** in `e2e/specs/`. If there isn't one, draft it from
   `e2e/specs/TEMPLATE.md` and confirm it first — the "Then" clause is where
   tests go wrong.
2. **Check it belongs here.** Would the test fail if the UI stopped calling the
   logic, and would a `ui/tests/` unit test miss that? If a unit test covers it
   equally well, write that instead. Never test Streamlit's own widget
   behaviour.
3. **Read the source** for the screen (`ui/views/`, `ui/components/`,
   `ui/managers/`) for real labels, keys and validation order. Never infer them.
4. **Read `ui/constants.py`** for exact copy.
5. **Check `e2e/shared/app_utils.py`** for an existing getter. If the widget
   type isn't covered, add one *there* — never inline a locator in a test.

## The harness

```python
def test_something(app: Page):   # `app` is a loaded, settled landing page
    ...
```

Never launch Streamlit in a test, never hardcode a port or URL, never call
`page.goto`. To test another pipeline, override `qc_config` at module level:

```python
@pytest.fixture(scope="module")
def qc_config():
    return QCAppConfig(pipeline="freesurfer", qc_task="fs_wf_qc",
                       qc_json="pipelines/freesurfer/qc_demo.json")
```

For export assertions use the `output_files` fixture, which returns only what
*this* test wrote — tests in a file share one output directory.

## Rules

**Wait after every interaction.** Streamlit re-runs its whole script on each
interaction, so asserting immediately after a click tests the previous render.
The helpers (`click_button`, `click_form_submit`, `check_checkbox`,
`upload_file`) call `wait_for_app_run` for you. If you interact with a locator
directly, call it yourself:

```python
from shared.waits import wait_for_app_run
some_locator.click()
wait_for_app_run(app)
expect(...).to_be_visible()
```

Most important for negative assertions — `not_to_be_visible()` passes instantly
against the stale page, giving a green test for a real bug.

**Never hardcode user-facing copy.**

```python
from constants import MESSAGES, ERROR_MESSAGES
expect_text_visible(app, ERROR_MESSAGES["invalid_rater_id"])
```

**Form buttons are not buttons.** `st.form_submit_button` has a different test
id than `st.button`; "✅ Continue to QC" needs `click_form_submit`.

**Assert on what is visible**, never on session state. Exception: export, via
`output_files`.

**Selector choice.** Use `get_by_key` where the widget actually has an explicit
`key=` in the source — check before assuming, most QC-Studio widgets don't have
one yet. Otherwise use the label-based getters in `app_utils.py`. If a widget
you test often has no key, suggest adding one rather than building on its label.

## Conventions

- Files `e2e/tests/test_<flow>.py`; functions `test_<the_rule>` — named for the
  rule, not the mechanics (`test_empty_rater_id_blocks_submission`, not
  `test_click_button`).
- One spec, one test function, with a docstring restating Given/When/Then.
- Mark with `pytest.mark.smoke`, `.flow`, or `.edge`.

## After writing

Run just that test and report the result:

```bash
pytest e2e/tests/test_<name>.py::<test_name> -v
```

Tell the user the file path, that command, and any test id or label you had to
guess. Call out edge cases you noticed but didn't cover.
