"""Admin dashboard gate: ``admins`` get full access, ``viewers`` view-only, everyone else is stopped."""

import json
from unittest.mock import MagicMock

import pytest

from admin import core
from utils import identity
from utils.identity import IdentityError, UserIdentity


class _Stopped(Exception):
    pass


@pytest.fixture
def setup(monkeypatch, tmp_path):
    users = tmp_path / "users.json"
    users.write_text(json.dumps({"admins": ["lead@x.org"], "viewers": ["pi@x.org"], "users": {"rater@x.org": {"participant_list": "r.tsv"}}}))
    st_mock = MagicMock()
    st_mock.stop.side_effect = _Stopped
    monkeypatch.setattr(core, "st", st_mock)
    return users, st_mock


def _as_user(monkeypatch, email):
    monkeypatch.setattr(identity, "get_current_user", lambda: UserIdentity(email=email, source="header") if email else None)


def test_admin_gets_in(monkeypatch, setup):
    users, st_mock = setup
    _as_user(monkeypatch, "Lead@X.org".lower())
    email, cfg, role = core.require_dashboard_access(users)
    assert email == "lead@x.org" and "rater@x.org" in cfg.users and role == "admin"
    st_mock.stop.assert_not_called()


def test_viewer_gets_in_view_only(monkeypatch, setup):
    users, st_mock = setup
    _as_user(monkeypatch, "pi@x.org")
    email, cfg, role = core.require_dashboard_access(users)
    assert (email, role) == ("pi@x.org", "viewer")
    st_mock.stop.assert_not_called()


@pytest.mark.parametrize(
    "email, message",
    [("rater@x.org", "not a QC-Studio admin or viewer"), ("eve@x.org", "not a QC-Studio admin or viewer"), (None, "Could not determine")],
)
def test_others_are_stopped(monkeypatch, setup, email, message):
    users, st_mock = setup
    _as_user(monkeypatch, email)
    with pytest.raises(_Stopped):
        core.require_dashboard_access(users)
    assert message in st_mock.error.call_args[0][0]


def test_identity_misconfiguration_stops(monkeypatch, setup):
    users, st_mock = setup

    def boom():
        raise IdentityError("only one of CF_ACCESS_* is set")

    monkeypatch.setattr(identity, "get_current_user", boom)
    with pytest.raises(_Stopped):
        core.require_dashboard_access(users)
    assert "identity configuration" in st_mock.error.call_args[0][0]


def test_unreadable_config_stops(monkeypatch, setup, tmp_path):
    _, st_mock = setup
    _as_user(monkeypatch, "lead@x.org")
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(_Stopped):
        core.require_dashboard_access(bad)
    assert "could not be loaded" in st_mock.error.call_args[0][0]


REQUIRED = ["--users_config", "u.json", "--participant_list", "p.tsv", "--qc_json", "qc.json"]


def test_parse_admin_args():
    args = core.parse_admin_args(REQUIRED)
    assert args.output_dir is None and args.session_list is None and args.qc_task == "all" and args.qc_pipeline is None
    for i in range(0, len(REQUIRED), 2):  # every one of them is required
        with pytest.raises(SystemExit):
            core.parse_admin_args(REQUIRED[:i] + REQUIRED[i + 2 :])


@pytest.fixture
def qc_json(tmp_path):
    p = tmp_path / "qc.json"
    p.write_text(json.dumps({"task_a": {}, "task_b": {}, "task_c": {}}))
    return p


def test_expected_tasks_all_in_file_order(qc_json):
    assert core.expected_tasks(qc_json) == ["task_a", "task_b", "task_c"]
    assert core.expected_tasks(qc_json, "ALL") == ["task_a", "task_b", "task_c"]


def test_expected_tasks_subset(qc_json):
    assert core.expected_tasks(qc_json, " task_c, task_a ") == ["task_c", "task_a"]
    with pytest.raises(ValueError, match="task_x"):
        core.expected_tasks(qc_json, "task_a,task_x")


@pytest.mark.parametrize("content", [None, "not json", "[1, 2]", "{}"])
def test_expected_tasks_unusable_qc_json(tmp_path, content):
    p = tmp_path / "qc.json"
    if content is not None:
        p.write_text(content)
    with pytest.raises(ValueError, match="no QC tasks"):
        core.expected_tasks(p)


def test_resolve_qc_json(qc_json, monkeypatch, tmp_path):
    assert core.resolve_qc_json(str(qc_json)) == qc_json.resolve()
    monkeypatch.chdir(tmp_path)
    # a relative path that doesn't exist here is resolved against ui/, like the rater app
    assert core.resolve_qc_json("../pipelines/fsqc/qc.json") == (core.UI_DIR.parent / "pipelines" / "fsqc" / "qc.json").resolve()


def test_build_context_stops_on_bad_qc_json(monkeypatch, setup, tmp_path):
    users, st_mock = setup
    from utils.user_config import load_users_config

    args = core.parse_admin_args(REQUIRED[:4] + ["--qc_pipeline", "fsqc", "--qc_json", str(tmp_path / "missing.json")])
    with pytest.raises(_Stopped):
        core.build_context(args, "lead@x.org", load_users_config(users))
    assert "QC tasks could not be loaded" in st_mock.error.call_args[0][0]


def test_build_context_stops_on_unreadable_dataset_list(monkeypatch, setup, tmp_path):
    users, st_mock = setup
    from utils.user_config import load_users_config

    qc = tmp_path / "qc.json"
    qc.write_text('{"__pipeline__": "fsqc", "task_a": {}}')
    args = core.parse_admin_args(["--users_config", str(users), "--participant_list", str(tmp_path / "missing.tsv"), "--qc_json", str(qc)])
    with pytest.raises(_Stopped):
        core.build_context(args, "lead@x.org", load_users_config(users))
    assert "Dataset participant list cannot be read" in st_mock.error.call_args[0][0]


def test_require_editor_refuses_viewers(monkeypatch):
    st_mock = MagicMock()
    st_mock.stop.side_effect = _Stopped
    monkeypatch.setattr(core, "st", st_mock)
    admin = core.AdminContext(
        users_config=None, participant_list=None, pool=None, output_dir=None, session_list=None, email="lead@x.org", cfg=None, role="admin"
    )
    core.require_editor(admin)  # no error
    assert admin.can_edit
    viewer = core.AdminContext(
        users_config=None, participant_list=None, pool=None, output_dir=None, session_list=None, email="pi@x.org", cfg=None, role="viewer"
    )
    assert not viewer.can_edit
    with pytest.raises(_Stopped):
        core.require_editor(viewer)
    assert "View-only" in st_mock.error.call_args[0][0]
