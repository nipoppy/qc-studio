# Streamlit behaviours this repo has already paid for

Hard-won details behind the e2e harness. Change the harness without knowing
these and you will reintroduce bugs that are already fixed.

## Reruns are the whole problem

Streamlit re-executes the entire script on every interaction, so an assertion
made straight after a click tests the *previous* render. Playwright's built-in
retrying hides this most of the time — but not for negative assertions:

```python
expect(error_message).not_to_be_visible()   # passes instantly, against the
                                            # stale page, before the rerun
```

Green test, real bug. Hence `wait_for_app_run`, which asks the app rather than
guessing. Streamlit publishes its own state on the root element:

```html
<div data-testid="stApp"
     data-test-connection-state="CONNECTED"
     data-test-script-state="notRunning">
```

`data-test-script-state` cycles `initial` → `running` → `notRunning` on every
rerun. The helper waits for the websocket, then for `notRunning`, then for zero
`stSkeleton` elements. The interaction helpers in `shared/app_utils.py` call it
for you; interacting with a locator directly means calling it yourself.

## Selectors, strongest first

1. `get_by_key(page, "x")` — a widget given `key="x"` in the source renders
   with CSS class `st-key-x`, which survives copy changes. Most QC-Studio
   widgets have no key yet, so this is currently of limited use.
2. `get_by_test_id("stTextInput").filter(has_text=label)` — a widget test id
   narrowed by its visible label. What Streamlit's own suite uses, and what
   `shared/app_utils.py` is built on.
3. Raw CSS — avoid.

## Form buttons are not buttons

`st.form_submit_button` renders under `stFormSubmitButton`, not `stButton`. The
rater form's "✅ Continue to QC" needs `click_form_submit`; `click_button`
finds nothing.

## Launch paths

`ui/main.py` resolves `--qc_json` relative to its own directory (`ui/`), not the
repository root — hence the `../` prefix in `build_launch_command`. Every other
path is relative to the repo root, which is why `app_server` sets
`cwd=REPO_ROOT`. Getting this wrong produces
`Error: qc_json not found: ./pipelines/...`.

## Copy lives in one place

`ui/constants.py` holds `MESSAGES`, `ERROR_MESSAGES`, `SUCCESS_MESSAGES`,
`INFO_MESSAGES`. Import them; never hardcode a user-facing string.
`e2e/conftest.py` puts `ui/` on `sys.path`, the same way `ui/tests/conftest.py`
does.

## Source

These were derived from streamlit/streamlit's `e2e_playwright/` suite and its
`.claude/skills/fixing-flaky-e2e-tests/SKILL.md`, which is worth reading in
full before debugging a flaky test here.
