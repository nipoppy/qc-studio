"""Synchronisation helpers for testing a Streamlit app.

Why these exist
---------------
Streamlit re-runs the entire Python script on every interaction, so after a
click the browser is still showing the *previous* render for a few hundred
milliseconds. Playwright's built-in retrying hides this most of the time, but
not always -- and the case where it fails silently is the dangerous one:

    expect(error_message).not_to_be_visible()

That passes instantly against the stale page, before the rerun that would have
produced the error. Green test, shipped bug.

Rather than guessing with timeouts, these helpers ask the app. Streamlit
publishes its own status on the root element:

    <div data-testid="stApp"
         data-test-connection-state="CONNECTED"
         data-test-script-state="notRunning">

`data-test-script-state` cycles initial -> running -> notRunning on every
rerun, so waiting for `notRunning` means "the script has finished".

Adapted from streamlit/streamlit's own e2e_playwright/conftest.py.
"""

from __future__ import annotations

from typing import Callable

from playwright.sync_api import Page, expect

DEFAULT_TIMEOUT_MS = 25_000
#: Streamlit debounces some widgets by ~200ms; wait past that before checking.
INITIAL_WAIT_MS = 210


def wait_for_app_run(page: Page, initial_wait_ms: int = INITIAL_WAIT_MS) -> None:
    """Block until Streamlit has finished re-running its script.

    Call this after any interaction that triggers a rerun -- clicking a button,
    ticking a checkbox, changing a selectbox, submitting a form -- and before
    the assertion that checks the result. The interaction helpers in
    `shared.app_utils` already do this for you.
    """
    page.wait_for_timeout(initial_wait_ms)

    # The websocket to the Streamlit server is up.
    page.locator("[data-testid='stApp'][data-test-connection-state='CONNECTED']").wait_for(
        state="attached", timeout=DEFAULT_TIMEOUT_MS
    )

    # The script has finished running.
    page.locator("[data-testid='stApp'][data-test-script-state='notRunning']").wait_for(state="attached", timeout=DEFAULT_TIMEOUT_MS)

    # No loading skeletons left: every element has actually rendered.
    expect(page.get_by_test_id("stSkeleton")).to_have_count(0, timeout=DEFAULT_TIMEOUT_MS)


def wait_for_app_loaded(page: Page) -> None:
    """Block until the app has loaded for the first time.

    Used by the `app` fixture; you rarely need it directly.
    """
    page.wait_for_selector("[data-testid='stAppViewContainer']", state="attached", timeout=30_000)
    wait_for_app_run(page)


def wait_until(page: Page, condition: Callable[[], bool], timeout_ms: int = 5_000, interval_ms: int = 100) -> None:
    """Poll `condition` until it returns True, or fail after `timeout_ms`.

    An escape hatch for states the specific helpers don't cover. Prefer an
    `expect(...)` assertion where one exists -- they give better failure
    messages.
    """
    elapsed = 0
    while elapsed < timeout_ms:
        if condition():
            return
        page.wait_for_timeout(interval_ms)
        elapsed += interval_ms
    raise AssertionError(f"Condition was still false after {timeout_ms}ms")
