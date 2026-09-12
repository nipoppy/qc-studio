---
name: qcs-understanding-e2e
description: >
  Orientation for QC-Studio's end-to-end browser test suite in e2e/. Use when
  picking up or continuing the e2e work, when the harness or its fixtures
  misbehave, when deciding whether something belongs in e2e/ or ui/tests/, or
  when the user asks about Playwright, browser tests, the app_server fixture,
  Streamlit rerun waits, or why a selector isn't matching. Read this before
  changing anything under e2e/; use qcs-playwright-testing to write an actual
  test.
---

# Understanding QC-Studio's e2e suite

QC-Studio has two test suites with different jobs. Don't merge them.

| | `ui/tests/` | `e2e/` |
|---|---|---|
| What it does | Mocks Streamlit entirely, tests logic in isolation | Starts the real app, drives a real browser |
| Speed | Milliseconds | Seconds per test |
| Catches | Broken logic | Broken *wiring* — UI not calling the logic |
| Conventions | `qcs-generating-tests` skill | `qcs-playwright-testing` skill |

The e2e suite exists for one reason: `ui/tests/` mocks Streamlit, so it can
prove `SessionManager.set_rater_id()` works but never that clicking the real
"Continue to QC" button calls it. Every bug in that seam is invisible to the
unit tests.

## How the suite is built

Four layers, each hiding its mechanics from the one above:

```
tests/          scenarios — know nothing about ports or subprocesses
shared/         find widgets; wait out Streamlit reruns
app fixture     a browser page, loaded and settled
app_server      a live QC-Studio process on a free port
```

When something breaks, the layer tells you which file to open: server won't
start → `conftest.py`; locator finds nothing → `shared/app_utils.py`;
assertion wrong but everything else worked → a real QC-Studio bug.

Scoping is deliberate: `app_server` is **module**-scoped (booting Streamlit
takes seconds, so one server serves a whole file) while `app` is
**function**-scoped (fresh page per test, so no session state leaks). Don't
change either without understanding that trade-off.

## Decisions worth preserving

**Don't test Streamlit.** That a text input accepts typing or a form defers
submission is Streamlit's behaviour, covered by Streamlit's own suite. Test
QC-Studio's rules and wiring: validation, cohort ordering, CSV filtering by QC
task, resume-at-first-incomplete-page, record de-duplication, export contents,
the niivue fallback.

**The filter for any proposed e2e test:** would it fail if the UI stopped
calling the logic, *and* would a `ui/tests/` unit test miss that? If a unit
test covers it equally well, write that instead — faster and more precise.
Pure logic (string cleaning, config parsing, dataframe filtering) belongs in
`ui/tests/`.

**Specs before code.** `e2e/specs/` holds one markdown file per scenario,
written before the test. `TEMPLATE.md` is the form;
`001-rater-form-validation.md` is a worked example. The "Then" clause must name
something *visible on screen*, never session state — the single exception being
export, since the tests own `output_dir` and can assert on the written CSV.

**All selectors live in `shared/app_utils.py`.** Tests never call
`page.locator(...)`. One file to fix when Streamlit changes.

## Streamlit facts this repo has already paid for

- **Reruns.** Streamlit re-executes the whole script on every interaction, so an
  assertion made straight after a click tests the *previous* render. The
  interaction helpers (`click_button`, `click_form_submit`, `check_checkbox`,
  `upload_file`) call `wait_for_app_run` internally. Interacting with a locator
  directly means calling it yourself. This matters most for negative assertions
  — `not_to_be_visible()` passes instantly against the stale page, giving a
  green test for a real bug.
- **Form buttons ≠ buttons.** `st.form_submit_button` renders under a different
  test ID than `st.button`. The rater form's "✅ Continue to QC" needs
  `click_form_submit`.
- **`--qc_json` is resolved relative to `ui/`**, not the repo root, so the
  fixture prefixes it with `../`. Everything else is relative to the repo root,
  which is why `app_server` sets `cwd=REPO_ROOT`.
- **`st-key-` classes.** A widget given `key="x"` in the source renders with CSS
  class `st-key-x`, which survives label/copy changes. `get_by_key()` uses this.
  Most landing-page widgets have no explicit key yet; adding them is a small
  source change purely for testability and worth proposing.
- **User-facing copy lives in `ui/constants.py`** (`MESSAGES`, `ERROR_MESSAGES`,
  `SUCCESS_MESSAGES`, `INFO_MESSAGES`). Import it; never hardcode a string.
  `e2e/conftest.py` puts `ui/` on `sys.path`, same as `ui/tests/conftest.py`.

## Roadmap

1. ~~Fixture chain and helpers~~ — done.
2. ~~Get the smoke tests green~~ — done (September 2026). Both `test_app_boots`
   and `test_rater_form_is_reachable` pass against a real Chromium browser and
   this repo's Streamlit; the test IDs in `shared/app_utils.py` needed no
   changes.
3. Landing-page scenarios: rater validation, panel validation, CSV upload and
   resume.
4. Rating flow: rate → navigate → complete; then export (assert on the CSV in
   `output_dir` — the strongest assertion available).
5. Parametrize the smoke test across pipelines by overriding `qc_config`
   (fMRIPrep, FreeSurfer, QSIPrep, XCP-D, NODDIreg, DWI-IQM).
6. CI job running `pytest e2e/ -m smoke` on PRs, traces uploaded on failure.

## Two things not to be confused by

**`playwright-practice/`** is a separate TypeScript Playwright project that
targets a public demo site, kept as personal practice. It is unrelated to
`e2e/` and is not part of the repo's test strategy. Leave it alone.

**`.venv-agent/`** is a throwaway virtualenv (gitignored) created to verify the
app's dependencies install and the launch command works. It is not the
project's environment — that's `.venv/`.

## Related

- `qcs-playwright-testing` — conventions for writing an e2e test. Use it for
  the actual writing.
- `qcs-generating-tests` — the pytest/unit-test cookbook for `ui/tests/`.
- `e2e/README.md` — commands and layout for humans.
