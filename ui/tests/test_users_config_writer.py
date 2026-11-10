"""Tests for utils.users_config_writer (safe rater edits from the admin dashboard)."""

import json
import os

import pytest

from utils.user_config import load_users_config
from utils.users_config_writer import (
    BACKUP_DIRNAME,
    ConfigWriteError,
    add_rater,
    apply_change,
    prepare_add_rater,
    prepare_update_rater,
    remove_rater,
    update_rater,
)


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            {
                "rater_root": "raters",
                "admins": ["lead@x.org"],
                "users": {
                    "Alice@x.org": {"rater_id": "alice", "participant_list": "alice.tsv"},
                    "bob@x.org": {"rater_id": "bob", "participant_list": "bob.tsv"},
                },
            },
            indent=2,
        )
    )
    return path


def _raw(path):
    return json.loads(path.read_text())


def _backups(path):
    return sorted((path.parent / BACKUP_DIRNAME).glob("*.json"))


def test_add_rater(config):
    old = config.read_text()
    backup = add_rater(config, "Carol@X.org", {"rater_id": "Carol", "participant_list": "carol.tsv", "session_list": " "})
    raw = _raw(config)
    assert raw["users"]["carol@x.org"] == {"rater_id": "carol", "participant_list": "carol.tsv"}
    assert raw["admins"] == ["lead@x.org"] and raw["rater_root"] == "raters"
    assert backup.read_text() == old and _backups(config) == [backup]
    assert "carol@x.org" in load_users_config(config).users


def test_add_existing_email_refused(config):
    with pytest.raises(ConfigWriteError, match="already"):
        prepare_add_rater(config, "alice@X.org", {"participant_list": "a2.tsv"})


def test_duplicate_rater_id_refused_and_file_unchanged(config):
    old = config.read_text()
    with pytest.raises(ConfigWriteError, match="rater_id"):
        add_rater(config, "carol@x.org", {"rater_id": "bob", "participant_list": "c.tsv"})
    assert config.read_text() == old
    assert _backups(config) == []


@pytest.mark.parametrize(
    "entry, match",
    [
        ({"rater_id": "c"}, "participant_list"),
        ({"participant_list": "c.tsv", "rater_id": "../x"}, "rater_id"),
        ({"participant_list": "c", "role": "admin"}, "unknown"),
    ],
)
def test_invalid_entries_refused(config, entry, match):
    with pytest.raises(ConfigWriteError, match=match):
        prepare_add_rater(config, "carol@x.org", entry)


def test_invalid_email_refused(config):
    with pytest.raises(ConfigWriteError):
        prepare_add_rater(config, "not-an-email", {"participant_list": "c.tsv"})


def test_update_rater_keeps_original_key(config):
    update_rater(config, "alice@x.org", {"rater_id": "alice", "participant_list": "alice_v2.tsv", "session_list": "ses-BL"})
    raw = _raw(config)
    assert raw["users"]["Alice@x.org"] == {"rater_id": "alice", "participant_list": "alice_v2.tsv", "session_list": "ses-BL"}
    assert list(raw["users"]) == ["Alice@x.org", "bob@x.org"]


def test_update_unknown_rater(config):
    with pytest.raises(ConfigWriteError, match="not in"):
        prepare_update_rater(config, "eve@x.org", {"participant_list": "e.tsv"})


def test_remove_rater(config):
    remove_rater(config, "BOB@x.org")
    assert set(_raw(config)["users"]) == {"Alice@x.org"}


def test_change_refused_if_file_changed_since_prepare(config):
    change = prepare_add_rater(config, "carol@x.org", {"participant_list": "c.tsv"})
    raw = _raw(config)
    raw["users"]["dave@x.org"] = {"participant_list": "d.tsv"}
    config.write_text(json.dumps(raw))
    st_ = config.stat()
    os.utime(config, ns=(st_.st_atime_ns, st_.st_mtime_ns + 1_000_000_000))
    with pytest.raises(ConfigWriteError, match="changed"):
        apply_change(change)
    assert "dave@x.org" in _raw(config)["users"] and "carol@x.org" not in _raw(config)["users"]


def test_diff_shows_only_the_change(config):
    change = prepare_add_rater(config, "carol@x.org", {"participant_list": "c.tsv"})
    added = [line for line in change.diff().splitlines() if line.startswith("+") and not line.startswith("+++")]
    assert any("carol@x.org" in line for line in added)
    assert not any("alice" in line.lower() for line in added)


def test_duplicate_keys_in_file_refused(config):
    config.write_text('{"users": {"a@x.org": {"participant_list": "1.tsv"}, "a@x.org": {"participant_list": "2.tsv"}}}')
    with pytest.raises(ConfigWriteError, match="duplicate"):
        prepare_add_rater(config, "c@x.org", {"participant_list": "c.tsv"})


def test_file_permissions_kept(config):
    os.chmod(config, 0o640)
    add_rater(config, "carol@x.org", {"participant_list": "c.tsv"})
    assert (config.stat().st_mode & 0o777) == 0o640
