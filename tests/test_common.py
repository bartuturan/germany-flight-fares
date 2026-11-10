import pytest
import requests

from scraper import common
from datetime import date, timedelta

from scraper.common import tracked_departures


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


def test_post_json_sends_the_body_and_retries_like_get_json(monkeypatch):
    sent = []

    def fake_post(url, **kwargs):
        sent.append((url, kwargs["json"], kwargs["headers"]["User-Agent"]))
        return responses.pop(0)

    responses = [FakeResponse(503), FakeResponse(200, {"ok": 1})]
    monkeypatch.setattr(common.requests, "post", fake_post)
    assert common.post_json("u", {"a": 1}, sleep=lambda _: None) == {"ok": 1}
    assert sent == [("u", {"a": 1}, common.USER_AGENT)] * 2


def test_post_json_does_not_retry_client_errors(monkeypatch):
    responses = [FakeResponse(400)]
    monkeypatch.setattr(common.requests, "post", lambda url, **kwargs: responses.pop(0))
    with pytest.raises(requests.HTTPError):
        common.post_json("u", {}, sleep=lambda _: None)
    assert responses == []


def test_does_not_retry_client_errors(monkeypatch):
    calls = queue_responses(monkeypatch, [FakeResponse(403)])
    with pytest.raises(requests.HTTPError):
        common.get_json("u", sleep=lambda _: None)
    assert len(calls) == 1


def test_tracked_departures_are_about_one_a_week_within_the_range():
    today = date(2026, 11, 3)
    departures = tracked_departures("FRA-JFK", today, 1, 60)
    assert 8 <= len(departures) <= 10
    assert all(today < day <= today + timedelta(days=60) for day in departures)
    blocks = [day.toordinal() // 7 for day in departures]
    assert len(blocks) == len(set(blocks))


def test_a_tracked_departure_stays_tracked_until_it_leaves():
    today = date(2026, 11, 3)
    for departure in tracked_departures("FRA-JFK", today, 1, 60):
        for lead in range(1, (departure - today).days + 1):
            assert departure in tracked_departures("FRA-JFK", departure - timedelta(days=lead), 1, 60)


def test_a_new_departure_joins_at_the_far_end_only():
    day_one = set(tracked_departures("FRA-JFK", date(2026, 11, 3), 1, 60))
    day_two = set(tracked_departures("FRA-JFK", date(2026, 11, 4), 1, 60))
    assert day_two - day_one <= {date(2026, 11, 4) + timedelta(days=60)}


def test_tracked_weekdays_rotate_and_routes_differ():
    today = date(2026, 11, 3)
    departures = tracked_departures("FRA-JFK", today, 1, 365)
    assert {day.weekday() for day in departures} == set(range(7))
    assert departures != tracked_departures("MUC-HAM", today, 1, 365)
