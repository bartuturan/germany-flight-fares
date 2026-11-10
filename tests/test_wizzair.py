import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

from scraper import wizzair
from scraper.common import SourceFailed

FIXTURE = Path(__file__).parent / "fixtures" / "wizzair_timetable.json"
TODAY = date(2026, 11, 10)
API = "https://be.wizzair.com/29.24.0/Api"
HOMEPAGE = f'<script>x={{envName:"production",apiUrl:"{API}",marathonApiUrl:"https://staging.example"}}</script>'
CONFIG = {
    "airports": ["BER", "STR"],
    "days_ahead": 45,
    "currency": "EUR",
    "delay_seconds": 0,
    "fallback_api_version": "28.0.0",
    "max_consecutive_failures": 3,
    "retry_cooldown_seconds": 60,
}
MAP = {
    "cities": [
        {"iata": "BER", "connections": [{"iata": "BUD"}, {"iata": "KTW"}]},
        {"iata": "BUD", "connections": [{"iata": "BER"}]},
        {"iata": "DTM", "connections": [{"iata": "KTW"}]},
        {"iata": "STR", "connections": [{"iata": "BUD"}]},
    ]
}


def timetable():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_find_api_url_reads_the_version_from_the_homepage():
    assert wizzair.find_api_url(CONFIG, fetch=lambda: HOMEPAGE) == API


def test_find_api_url_falls_back_when_the_homepage_has_no_address():
    url = wizzair.find_api_url(CONFIG, fetch=lambda: "<html>Human Verification</html>")
    assert url == "https://be.wizzair.com/28.0.0/Api"


def test_find_api_url_falls_back_when_the_homepage_is_blocked():
    def blocked():
        raise requests.HTTPError("HTTP 405")

    assert wizzair.find_api_url(CONFIG, fetch=blocked) == "https://be.wizzair.com/28.0.0/Api"


def test_routes_come_only_from_the_configured_airports():
    assert wizzair.routes_from_map(MAP, ["BER", "STR"]) == [("BER", "BUD"), ("BER", "KTW"), ("STR", "BUD")]
    assert wizzair.routes_from_map({}, ["BER"]) == []


def test_date_windows_cover_every_day_in_windows_the_api_accepts():
    windows = wizzair.date_windows(TODAY, 45)
    assert windows == [
        (date(2026, 11, 11), date(2026, 12, 10)),
        (date(2026, 12, 11), date(2026, 12, 25)),
    ]
    assert all((last - first).days <= 38 for first, last in windows)
    assert wizzair.date_windows(TODAY, 10) == [(date(2026, 11, 11), date(2026, 11, 20))]


def test_parse_timetable_keeps_priced_days_and_drops_check_price_days():
    rows, unpriced = wizzair.parse_timetable(timetable(), TODAY)
    assert unpriced == 1
    assert [row["departure_date"] for row in rows] == ["2026-11-11", "2026-11-12", "2026-11-13"]
    assert rows[0] == {
        "snapshot_date": "2026-11-10",
        "source": "wizzair",
        "origin": "STR",
        "destination": "BUD",
        "departure_date": "2026-11-11",
        "departure_time": "",
        "airline": "Wizz Air",
        "flight_number": "",
        "stops": 0,
        "price": 79.99,
        "currency": "EUR",
    }
    assert "2026-11-26" not in {row["departure_date"] for row in rows}


def test_parse_timetable_handles_an_empty_answer():
    assert wizzair.parse_timetable({"outboundFlights": [], "returnFlights": None}, TODAY) == ([], 0)
    assert wizzair.parse_timetable({}, TODAY) == ([], 0)


class FakeApi:
    """Answers the route map, and a timetable of its own for each route.

    `down` lists (origin, destination, window start) requests that always fail. `flaky` lists
    ones that fail on the first attempt only, like a burst of server errors.
    """

    def __init__(self, down=(), flaky=(), cities=None):
        self.down = set(down)
        self.flaky = set(flaky)
        self.cities = cities if cities is not None else MAP
        self.timetable_calls = []

    def get(self, url, params=None):
        assert url == f"{API}/asset/map"
        return self.cities

    def post(self, url, payload):
        assert url == f"{API}/search/timetable"
        flight = payload["flightList"][0]
        call = (flight["departureStation"], flight["arrivalStation"], flight["from"])
        self.timetable_calls.append(call)
        if call in self.down or call in self.flaky:
            self.flaky.discard(call)
            raise requests.HTTPError("HTTP 503")
        answer = timetable()
        window_start = date.fromisoformat(flight["from"])
        for offset, day in enumerate(answer["outboundFlights"]):
            day["departureStation"], day["arrivalStation"] = call[0], call[1]
            # Dates inside the requested window, so two windows never return the same day.
            day["departureDate"] = (window_start + timedelta(days=offset)).isoformat() + "T00:00:00"
        return answer


def collect(api, config=CONFIG, fetch=lambda: HOMEPAGE):
    sleeps = []
    rows = wizzair.collect(config, TODAY, get=api.get, post=api.post, fetch=fetch, sleep=sleeps.append)
    return rows, sleeps


def test_collect_requests_every_route_in_every_window_and_pauses_between_requests():
    api = FakeApi()
    rows, sleeps = collect(api)
    assert len(api.timetable_calls) == 3 * 2
    assert api.timetable_calls[0] == ("BER", "BUD", "2026-11-11")
    assert api.timetable_calls[1] == ("BER", "BUD", "2026-12-11")
    assert len(rows) == 6 * 3
    assert {(row["origin"], row["destination"]) for row in rows} == {("BER", "BUD"), ("BER", "KTW"), ("STR", "BUD")}
    assert len(sleeps) == 6


def test_collect_retries_failed_requests_once_after_a_pause():
    api = FakeApi(flaky=[("BER", "KTW", "2026-11-11"), ("STR", "BUD", "2026-12-11")])
    rows, sleeps = collect(api)
    assert len(rows) == 6 * 3
    assert len(api.timetable_calls) == 6 + 2
    assert 60 in sleeps
    assert sleeps.index(60) == 6  # after the whole first pass, not between requests


def test_collect_keeps_the_rest_when_some_requests_still_fail_after_the_retry():
    api = FakeApi(down=[("BER", "BUD", "2026-12-11"), ("STR", "BUD", "2026-11-11")])
    rows, _ = collect(api)
    assert len(rows) == 4 * 3
    assert len(api.timetable_calls) == 6 + 2


def test_collect_does_not_pause_for_a_retry_when_nothing_failed():
    _, sleeps = collect(FakeApi())
    assert 60 not in sleeps


def test_collect_gives_up_after_too_many_failures_in_a_row():
    api = FakeApi(down=[("BER", "BUD", "2026-11-11"), ("BER", "BUD", "2026-12-11"), ("BER", "KTW", "2026-11-11")])
    with pytest.raises(SourceFailed, match="3 Wizz Air requests failed in a row"):
        collect(api)
    assert len(api.timetable_calls) == 3


def test_collect_counts_a_route_once_when_the_map_also_lists_its_city_group():
    # Asking for the group code (ROM) returns the airport's flights (FCO) again.
    cities = {"cities": [{"iata": "STR", "connections": [{"iata": "FCO"}, {"iata": "ROM"}]}]}
    api = FakeApi(cities=cities)

    def post(url, payload):
        answer = timetable()
        flight = payload["flightList"][0]
        for day in answer["outboundFlights"]:
            day["departureStation"], day["arrivalStation"] = flight["departureStation"], "FCO"
        return answer

    api.post = post
    rows, _ = collect(api, config={**CONFIG, "airports": ["STR"]})
    assert len(rows) == 3
    assert {row["destination"] for row in rows} == {"FCO"}


def test_collect_fails_when_nothing_has_a_price():
    api = FakeApi()
    api.post = lambda url, payload: {"outboundFlights": [], "returnFlights": None}
    with pytest.raises(SourceFailed, match="no fares"):
        collect(api)


def test_collect_fails_when_the_route_map_fails_or_has_no_routes():
    api = FakeApi()

    def broken_map(url, params=None):
        raise requests.ConnectionError("down")

    api.get = broken_map
    with pytest.raises(SourceFailed, match="route map failed"):
        collect(api)

    api.get = lambda url, params=None: {"cities": []}
    with pytest.raises(SourceFailed, match="no routes"):
        collect(api)


def test_collect_uses_the_fallback_version_when_the_homepage_fails():
    seen = []
    api = FakeApi()
    api.get = lambda url, params=None: seen.append(url) or MAP
    api.post = lambda url, payload: seen.append(url) or timetable()

    def blocked():
        raise requests.HTTPError("HTTP 405")

    collect(api, fetch=blocked)
    assert seen[0] == "https://be.wizzair.com/28.0.0/Api/asset/map"
    assert all(url.startswith("https://be.wizzair.com/28.0.0/Api/") for url in seen)
