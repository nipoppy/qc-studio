---
name: qcs-understanding-e2e
description: >
  Orientation for QC-Studio's end-to-end browser suite under e2e/. Use before
  touching anything in e2e/, when the harness or its fixtures misbehave, or
  when deciding whether a test belongs in e2e/ (browser) or ui/tests/ (mocked
  unit tests). For writing an individual Playwright test, use
  qcs-playwright-testing instead; for pytest unit tests, qcs-generating-tests.
---

# Understanding QC-Studio's e2e suite

QC-Studio has two test suites with different jobs. Don't merge them.

| | `ui/tests/` | `e2e/` |
|---|---|---|
| How | Mocks Streamlit, tests logic in isolation | Starts the real app, drives a browser |
| Speed | Milliseconds | Seconds per test |
| Catches | Broken logic | Broken *wiring* — UI not calling the logic |
| Skill | `qcs-generating-tests` | `qcs-playwright-testing` |

`ui/tests/` mocks Streamlit, so it can prove `SessionManager.set_rater_id()`
works but never that clicking the real "Continue to QC" button calls it. Every
bug in that seam is invisible to it. That gap is why `e2e/` exists.

## Structure

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

**Scoping is deliberate.** `app_server` is module-scoped (booting Streamlit
takes seconds, so one server serves a whole file); `app` is function-scoped
(fresh page per test, so no session state leaks). `output_dir` is module-scoped
of necessity — `--output_dir` is fixed at launch — so tests in a file share it;
use the `output_files` fixture for export assertions rather than listing that
directory directly.

## Decisions worth preserving

**Don't test Streamlit.** That a text input accepts typing or a form defers
submission is Streamlit's behaviour, covered by Streamlit's own suite. Test
QC-Studio's rules and wiring: validation, cohort ordering, CSV filtering by QC
task, resume-at-first-incomplete-page, de-duplication, export contents, the
niivue fallback.

**The filter for any proposed e2e test:** would it fail if the UI stopped
calling the logic, *and* would a `ui/tests/` unit test miss that? If a unit test
covers it equally well, write that instead. Pure logic — string cleaning, config
parsing, dataframe filtering — belongs in `ui/tests/`.

**Specs before code.** `e2e/specs/` holds one markdown file per scenario,
written first. `TEMPLATE.md` is the form; `001-rater-form-validation.md` is a
worked example. The "Then" clause must name something *visible on screen*,
never session state — the one exception being export, since the tests own
`output_dir`.

**All selectors live in `shared/app_utils.py`.** Tests never call
`page.locator(...)`. One file to fix when Streamlit changes.

## Not to be confused

`playwright-practice/` is a separate TypeScript Playwright project targeting a
public demo site, kept as personal practice. Unrelated to `e2e/`; leave it
alone. `.venv-agent/` is a throwaway virtualenv (gitignored), not the project
environment — that's `.venv/`.

## References

- `references/status.md` — what is built, what is verified, what to do next.
  **Perishable**; check its date before trusting it.
- `references/streamlit-notes.md` — Streamlit behaviours this repo has already
  paid for: reruns, test ids, `st-key-`, the `--qc_json` path quirk.
- `e2e/README.md` — commands and layout, for humans.
