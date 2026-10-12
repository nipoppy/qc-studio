"""Tests for shared cache helpers."""

import os

import pytest

from utils.cache import file_signature, files_signature, freeze

pytestmark = pytest.mark.unit


class TestFileSignature:
    def test_changes_when_file_is_rewritten(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(b"one")
        before = file_signature(path)

        path.write_bytes(b"three")
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

        after = file_signature(path)
        assert before[0] == after[0] == str(path.resolve())
        assert before != after
        assert after[2] == 5

    def test_missing_file_has_no_stat(self, tmp_path):
        assert file_signature(tmp_path / "missing.png") == (str((tmp_path / "missing.png").resolve()), None, None)

    def test_files_signature_keeps_order(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.write_bytes(b"a")
        b.write_bytes(b"b")
        assert [sig[0] for sig in files_signature([b, a])] == [str(b.resolve()), str(a.resolve())]


class TestFreeze:
    def test_nested_containers_are_read_only(self):
        frozen = freeze({"montage": {"type": "png", "content": b"x"}, "list": [1, [2]]})

        assert frozen["montage"]["content"] == b"x"
        assert frozen["list"] == (1, (2,))
        with pytest.raises(TypeError):
            frozen["new"] = 1
        with pytest.raises(TypeError):
            frozen["montage"]["content"] = b"y"

    def test_leaves_pass_through(self):
        data = b"bytes"
        assert freeze(data) is data
        assert freeze(None) is None
