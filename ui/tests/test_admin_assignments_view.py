"""Admin Assignments tab: choosing the source pool for a new participant list."""

import io
from unittest.mock import MagicMock

import pytest

from admin.views import assignments

POOL = ["sub-01", "sub-02", "sub-03", "sub-04"]


def _upload(text, name="custom.tsv"):
    f = io.BytesIO(text.encode())
    f.name = name
    return f


@pytest.fixture
def st_mock(monkeypatch):
    m = MagicMock()
    m.expander.return_value.__enter__ = lambda *_: None
    m.expander.return_value.__exit__ = lambda *_: None
    monkeypatch.setattr(assignments, "st", m)
    return m


def test_dataset_source_is_the_whole_pool(st_mock):
    st_mock.radio.return_value = "dataset"
    ids, label = assignments._source_pool(POOL)
    assert ids is POOL and "dataset" in label
    st_mock.file_uploader.assert_not_called()


def test_custom_source_keeps_only_pool_participants(st_mock):
    st_mock.radio.return_value = "custom"
    st_mock.file_uploader.return_value = _upload("participant_id\nsub-03\nsub-99\nsub-01\nsub-03\n")
    ids, label = assignments._source_pool(POOL)
    assert ids == ["sub-03", "sub-01"]
    assert "custom.tsv" in label
    assert "2 of 3" in st_mock.caption.call_args[0][0]
    st_mock.write.assert_called_once()  # the left-out participant is listed
    assert "sub-99" in st_mock.write.call_args[0][0]


def test_custom_source_without_upload(st_mock):
    st_mock.radio.return_value = "custom"
    st_mock.file_uploader.return_value = None
    assert assignments._source_pool(POOL) == (None, "")


@pytest.mark.parametrize(
    "text, message",
    [("participant_id\nsub-98\nsub-99\n", "None of the uploaded"), ("subject\nsub-01\n", "cannot be read")],
)
def test_custom_source_unusable(st_mock, text, message):
    st_mock.radio.return_value = "custom"
    st_mock.file_uploader.return_value = _upload(text)
    assert assignments._source_pool(POOL) == (None, "")
    assert message in st_mock.error.call_args[0][0]
