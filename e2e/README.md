# QC-Studio end-to-end tests

Browser-level tests that drive the real Streamlit app with Playwright.

These are **not** a replacement for `ui/tests/`. Those mock Streamlit out and
test logic in isolation -- fast and precise. These start the actual app in a
browser and test the *wiring*: that the UI really calls the logic, with the
right arguments, and shows the result. Any bug living in that seam is invisible
to a mocked unit test.

## Setup

```bash
pip install -r e2e/requirements-e2e.txt
playwright install chromium
```

## Running

From the repository root, with `streamlit` on your PATH (activate your venv):

```bash
pytest e2e/                                   # everything
pytest e2e/ -m smoke                          # just the harness check
pytest e2e/tests/test_smoke.py -v             # one file
pytest e2e/tests/test_smoke.py::test_app_boots -v   # one test

pytest e2e/ --headed                          # watch it run
pytest e2e/ --headed --slowmo 500             # watch it slowly
```

No need to start the app yourself -- the fixtures launch and stop it.

## Start here

Run `pytest e2e/ -m smoke` first. Those two tests exist to prove the harness
works, not to catch bugs:

- `test_app_boots` -- the server started with valid arguments, the browser
  connected, and the first script run finished.
- `test_rater_form_is_reachable` -- the widget getters find real elements.

If the second fails, a test id in `shared/app_utils.py` needs updating for the
installed Streamlit version. Fix it there once; every later test benefits.

Once those are green the backbone is proven, and everything after is writing
scenarios.

## Layout

```
e2e/
├── conftest.py        fixtures: config, port, output dir, server, page
├── pytest.ini         markers and discovery
├── shared/
│   ├── waits.py       wait for Streamlit reruns to settle
│   └── app_utils.py   find and interact with widgets -- all selectors live here
├── specs/             scenarios in English, written before the test code
└── tests/             the tests themselves
```

Each layer hides its mechanics from the one above. A test knows nothing about
ports or subprocesses; `app_utils` knows nothing about how the server starts.
When something breaks, that tells you which file to open.

## Writing a new test

1. Copy `specs/TEMPLATE.md` to `specs/NNN-your-scenario.md` and fill it in.
   The "Then" must be something *visible on screen*.
2. Write the test in `tests/test_<flow>.py`, one test per spec.
3. Use the helpers in `shared/app_utils.py` -- never `page.locator(...)`
   directly, never a hardcoded user-facing string (import from
   `ui/constants.py`).

The conventions are documented for agents in
`.claude/skills/qcs-playwright-testing/SKILL.md`, so an assistant handed a spec
file produces a test that fits this harness.

## The one rule to remember

Streamlit re-runs its entire script on every interaction, so an assertion made
immediately after a click tests the page as it was *before* the click. The
interaction helpers wait for you. If you click a locator directly, call
`wait_for_app_run(app)` before asserting.
