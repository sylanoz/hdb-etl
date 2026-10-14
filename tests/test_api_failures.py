"""Tests for stage src_to_raw: how the download code behaves when the data.gov.sg API fails.

The functions are taken from the notebook itself, so these tests check the code that actually runs.
The API is replaced by a fake that fails on purpose; waits are skipped so the tests run instantly.

Run from the notebook folder:  pytest tests
"""
import json
import logging
from pathlib import Path
from unittest import mock

import nbformat
import pytest
import requests

NOTEBOOK = Path(__file__).resolve().parents[1] / "hdb_resale_etl.ipynb"


class FakeResponse:
    def __init__(self, status=200, body=None, chunks=(), drop_after=None):
        self.status_code, self.body, self.chunks, self.drop_after = status, body, list(chunks), drop_after

    def json(self):
        if self.body is None:  # e.g. an HTML error page
            raise json.JSONDecodeError("not JSON", "<html>", 0)
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def iter_content(self, chunk_size):
        for i, chunk in enumerate(self.chunks):
            if i == self.drop_after:
                raise requests.ConnectionError("connection dropped mid-download")
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


OK = FakeResponse(body={"code": 0, "data": {}})
RATE_LIMITED = FakeResponse(status=429, body={"code": 24})
NOT_READY = FakeResponse(body={"code": 0, "data": {"status": "PENDING"}})
READY = FakeResponse(body={"code": 0, "data": {"url": "https://files.example/file.csv"}})
FILE = FakeResponse(chunks=[b"month,town\n", b"2012-01,ANG MO KIO\n"])


@pytest.fixture
def stage(tmp_path):
    """The notebook's src_to_raw functions, with RAW_DIR pointing at a temporary folder."""
    nb = nbformat.read(NOTEBOOK, as_version=4)
    source = next(c.source for c in nb.cells if c.cell_type == "code" and "def get_json" in c.source)
    namespace = {
        "requests": requests, "time": __import__("time"), "Path": Path, "pd": __import__("pandas"),
        "log_src_to_raw": logging.getLogger("src_to_raw"), "RAW_DIR": tmp_path,
        "DOWNLOAD_URL": "https://api.example/{dataset_id}",
        "COLLECTION_URL": "https://api.example/collections/{collection_id}",
        "DATASET_URL": "https://api.example/datasets/{dataset_id}",
    }
    exec(source, namespace)
    return namespace


def fake_api(*replies):
    """Patch requests.get to return (or raise) the given replies in order; skip all waits."""
    replies = iter(replies)

    def get(url, **kwargs):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return mock.patch("requests.get", side_effect=get), mock.patch("time.sleep")


def test_rate_limit_is_retried_with_longer_waits(stage):
    get, sleep = fake_api(RATE_LIMITED, RATE_LIMITED, OK)
    with get, sleep as waits:
        assert stage["get_json"]("https://api.example/x") == OK.body
    assert [c.args[0] for c in waits.call_args_list] == [10, 20]


def test_rate_limit_in_response_body_is_retried(stage):
    get, sleep = fake_api(FakeResponse(body={"code": 24}), OK)
    with get, sleep:
        assert stage["get_json"]("https://api.example/x") == OK.body


def test_gives_up_after_six_attempts(stage):
    get, sleep = fake_api(*[RATE_LIMITED] * 6)
    with get, sleep, pytest.raises(RuntimeError, match="still failing after 6 attempts"):
        stage["get_json"]("https://api.example/x")


def test_server_error_with_html_page_is_retried(stage):
    get, sleep = fake_api(FakeResponse(status=503), OK)
    with get, sleep:
        assert stage["get_json"]("https://api.example/x") == OK.body


def test_network_error_is_retried(stage):
    get, sleep = fake_api(requests.ConnectionError("network unreachable"), OK)
    with get, sleep:
        assert stage["get_json"]("https://api.example/x") == OK.body


def test_not_found_fails_at_once_without_retry(stage):
    get, sleep = fake_api(FakeResponse(status=404, body={"code": 404}))
    with get, sleep as waits, pytest.raises(requests.HTTPError, match="404"):
        stage["get_json"]("https://api.example/x")
    waits.assert_not_called()


def test_download_that_never_becomes_ready_fails(stage, tmp_path):
    get, sleep = fake_api(OK, *[NOT_READY] * 24)
    with get, sleep, pytest.raises(RuntimeError, match="not ready"):
        stage["download_dataset"]("d_test")
    assert list(tmp_path.iterdir()) == []


def test_interrupted_download_leaves_no_csv(stage, tmp_path):
    get, sleep = fake_api(OK, READY, FakeResponse(chunks=[b"month\n", b"2012-01\n"], drop_after=1))
    with get, sleep, pytest.raises(requests.ConnectionError):
        stage["download_dataset"]("d_test")
    assert not (tmp_path / "d_test.csv").exists()  # only d_test.part is left; the next run downloads again


def test_successful_download(stage, tmp_path):
    get, sleep = fake_api(OK, NOT_READY, READY, FILE)
    with get, sleep:
        path = stage["download_dataset"]("d_test")
    assert path.read_bytes() == b"month,town\n2012-01,ANG MO KIO\n"
    assert not (tmp_path / "d_test.part").exists()


def test_existing_file_is_not_downloaded_again(stage, tmp_path):
    (tmp_path / "d_test.csv").write_text("already here")
    get, sleep = fake_api()  # any API call would fail: no replies
    with get, sleep:
        assert stage["download_dataset"]("d_test").read_text() == "already here"
