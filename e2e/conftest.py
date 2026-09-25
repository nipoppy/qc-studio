"""Pytest fixtures for QC-Studio end-to-end (real browser) tests.

The suite is layered, and each layer hides its mechanics from the one above:

    app_server  ->  a live QC-Studio process on a free port
    app         ->  a browser page already loaded and settled on it
    shared/     ->  helpers for finding widgets and waiting out reruns
    tests/      ->  scenarios, which know about none of the above

Run from the repository root:   pytest e2e/
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import pytest
import requests
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).parent.parent
UI_DIR = REPO_ROOT / "ui"

# Same import style as ui/tests/conftest.py: put `ui/` and this directory on
# the path so tests can write `from constants import MESSAGES` and
# `from shared.app_utils import click_form_button`.
sys.path.insert(0, str(UI_DIR))
sys.path.insert(0, str(Path(__file__).parent))

from shared.waits import wait_for_app_loaded  # noqa: E402


@dataclass(frozen=True)
class QCAppConfig:
    """One QC-Studio launch configuration.

    Paths are relative to the repository root, except `qc_json`, which
    ui/main.py resolves relative to ui/ -- the `../` prefix is added for you
    in `app_server` below.
    """

    pipeline: str = "fmriprep"
    qc_task: str = "anat_wf_qc"
    qc_json: str = "pipelines/fmriprep/qc_demo.json"
    dataset_dir: str = "sample_data"
    participant_list: str = "sample_data/qc_participants_demo.tsv"
    session_list: str = "ses-01"


@pytest.fixture(scope="module")
def qc_config() -> QCAppConfig:
    """The app configuration under test.

    Override in a test module to exercise a different pipeline:

        @pytest.fixture(scope="module")
        def qc_config():
            return QCAppConfig(pipeline="freesurfer", qc_task="fs_wf_qc", ...)
    """
    return QCAppConfig()


@pytest.fixture(scope="module")
def app_port() -> int:
    """An unused TCP port, chosen by the OS."""
    with socket.socket() as sock:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where the app under test writes its QC results.

    Keeps test ratings out of the repository's real ./output folder, and gives
    export tests a directory they own -- so asserting on the written CSV is a
    legitimate end-to-end check.

    Module-scoped of necessity: the app is launched with --output_dir fixed at
    startup, and the server is module-scoped, so every test in a file shares
    this directory. That means an export test can see files an earlier test in
    the same file left behind -- use the `output_files` fixture below rather
    than listing this directory directly.
    """
    return tmp_path_factory.mktemp("qc_output")


@pytest.fixture
def output_files(output_dir: Path):
    """Callable returning the files *this test* created in `output_dir`.

    Snapshots the directory before the test runs, so export assertions are
    about this test's output and not a previous test's leftovers:

        def test_export_writes_one_row_per_rating(app, output_files):
            ...
            written = output_files()
            assert len(written) == 1
    """

    def _listing() -> set[Path]:
        return set(output_dir.iterdir()) if output_dir.exists() else set()

    before = _listing()
    return lambda: _listing() - before


def build_launch_command(config: QCAppConfig, port: int, output_dir: Path) -> list[str]:
    """The `streamlit run` command for one configuration.

    Split out from the fixture so it can be checked without starting anything.
    Run it with cwd set to the repository root: every path here is relative
    to it.
    """
    return [
        "streamlit",
        "run",
        "ui/main.py",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--",
        # ui/main.py resolves --qc_json relative to its own directory (ui/),
        # not the repository root -- hence the ../ prefix.
        "--qc_json",
        f"../{config.qc_json}",
        "--qc_task",
        config.qc_task,
        "--qc_pipeline",
        config.pipeline,
        "--dataset_dir",
        config.dataset_dir,
        "--participant_list",
        config.participant_list,
        "--output_dir",
        str(output_dir),
        "--session_list",
        config.session_list,
    ]


@pytest.fixture(scope="module", autouse=True)
def app_server(
    qc_config: QCAppConfig,
    app_port: int,
    output_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[subprocess.Popen, None, None]:
    """Start QC-Studio before the module's tests and stop it afterwards.

    Module-scoped because booting Streamlit takes seconds and every test in a
    file can safely share one server -- each test still gets a fresh browser
    page, so no session state leaks between them.
    """
    log_path = tmp_path_factory.mktemp("qc_logs") / "streamlit.log"
    command = build_launch_command(qc_config, app_port, output_dir)

    with open(log_path, "w") as log_file:
        # cwd must be the repository root: every path above is relative to it.
        process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=log_file, stderr=subprocess.STDOUT)
        try:
            _wait_for_health(app_port, process, log_path)
            yield process
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def _wait_for_health(port: int, process: subprocess.Popen, log_path: Path, timeout: float = 90.0) -> None:
    """Poll Streamlit's health endpoint until the app is actually serving.

    Polling beats sleeping: the tests never wait longer than they must, and
    never start before the server is ready. If the process dies on startup,
    its log is included in the failure so you see the real cause.
    """
    health_url = f"http://localhost:{port}/_stcore/health"
    deadline = time.time() + timeout

    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"QC-Studio exited during startup (code {process.returncode}).\n\n" f"{_tail(log_path)}")
        try:
            if requests.get(health_url, timeout=1).text.strip() == "ok":
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)

    raise RuntimeError(f"QC-Studio did not become healthy on port {port} within {timeout:.0f}s.\n\n" f"{_tail(log_path)}")


def _tail(log_path: Path, lines: int = 30) -> str:
    try:
        content = log_path.read_text().splitlines()
    except OSError:
        return "(no server log available)"
    return "--- streamlit log (tail) ---\n" + "\n".join(content[-lines:])


@pytest.fixture
def app(page: Page, app_port: int) -> Page:
    """A browser page on a freshly loaded QC-Studio landing page.

    Function-scoped, so every test starts from a clean session.
    """
    page.goto(f"http://localhost:{app_port}")
    wait_for_app_loaded(page)
    return page
