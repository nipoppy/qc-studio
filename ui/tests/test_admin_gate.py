"""Admin dashboard gate: only emails in the users config's ``admins`` get in."""

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
    users.write_text(json.dumps({"admins": ["lead@x.org"], "users": {"rater@x.org": {"participant_list": "r.tsv"}}}))
    st_mock = MagicMock()
    st_mock.stop.side_effect = _Stopped
    monkeypatch.setattr(core, "st", st_mock)
    return users, st_mock


def _as_user(monkeypatch, email):
    monkeypatch.setattr(identity, "get_current_user", lambda: UserIdentity(email=email, source="header") if email else None)


def test_admin_gets_in(monkeypatch, setup):
    users, st_mock = setup
    _as_user(monkeypatch, "Lead@X.org".lower())
    email, cfg = core.require_admin(users)
    assert email == "lead@x.org" and "rater@x.org" in cfg.users
    st_mock.stop.assert_not_called()


@pytest.mark.parametrize(
    "email, message", [("rater@x.org", "not a QC-Studio admin"), ("eve@x.org", "not a QC-Studio admin"), (None, "Could not determine")]
)
def test_others_are_stopped(monkeypatch, setup, email, message):
    users, st_mock = setup
    _as_user(monkeypatch, email)
    with pytest.raises(_Stopped):
        core.require_admin(users)
    assert message in st_mock.error.call_args[0][0]


def test_identity_misconfiguration_stops(monkeypatch, setup):
    users, st_mock = setup

    def boom():
        raise IdentityError("only one of CF_ACCESS_* is set")

    monkeypatch.setattr(identity, "get_current_user", boom)
    with pytest.raises(_Stopped):
        core.require_admin(users)
    assert "identity configuration" in st_mock.error.call_args[0][0]


def test_unreadable_config_stops(monkeypatch, setup, tmp_path):
    _, st_mock = setup
    _as_user(monkeypatch, "lead@x.org")
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(_Stopped):
        core.require_admin(bad)
    assert "could not be loaded" in st_mock.error.call_args[0][0]


def test_parse_admin_args():
    args = core.parse_admin_args(["--users_config", "u.json", "--participant_list", "p.tsv"])
    assert args.output_dir is None and args.session_list is None
    with pytest.raises(SystemExit):
        core.parse_admin_args(["--users_config", "u.json"])
