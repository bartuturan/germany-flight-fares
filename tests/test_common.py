import pytest
import requests

from scraper import common


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def queue_responses(monkeypatch, responses):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(common.requests, "get", fake_get)
    return calls


def test_retries_rate_limits_and_server_errors_with_backoff(monkeypatch):
    calls = queue_responses(monkeypatch, [FakeResponse(429), FakeResponse(503), FakeResponse(200, {"ok": 1})])
    sleeps = []
    assert common.get_json("u", sleep=sleeps.append) == {"ok": 1}
    assert len(calls) == 3
    assert sleeps == [5.0, 10.0]


def test_retries_connection_errors(monkeypatch):
    queue_responses(monkeypatch, [requests.ConnectionError("down"), FakeResponse(200, {"ok": 1})])
    assert common.get_json("u", sleep=lambda _: None) == {"ok": 1}


def test_gives_up_after_the_last_attempt(monkeypatch):
    calls = queue_responses(monkeypatch, [FakeResponse(500), FakeResponse(500), FakeResponse(500)])
    with pytest.raises(requests.HTTPError):
        common.get_json("u", sleep=lambda _: None)
    assert len(calls) == 3


def test_does_not_retry_client_errors(monkeypatch):
    calls = queue_responses(monkeypatch, [FakeResponse(403)])
    with pytest.raises(requests.HTTPError):
        common.get_json("u", sleep=lambda _: None)
    assert len(calls) == 1
