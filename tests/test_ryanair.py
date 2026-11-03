import json
from datetime import date
from pathlib import Path

import pytest
import requests

from scraper import ryanair
from scraper.common import SourceFailed

FIXTURE = Path(__file__).parent / "fixtures" / "ryanair_one_way.json"
TODAY = date(2026, 11, 3)
CONFIG = {
    "airports": ["BER", "CGN"],
    "weeks_ahead": 2,
    "currency": "EUR",
    "market": "de-de",
    "delay_seconds": 0,
    "max_consecutive_failures": 2,
}


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def no_sleep(_):
    pass


def test_windows_start_tomorrow_and_do_not_overlap():
    assert list(ryanair.departure_windows(TODAY, 2)) == [
        (date(2026, 11, 4), date(2026, 11, 10)),
        (date(2026, 11, 11), date(2026, 11, 17)),
    ]


def test_parses_real_response():
    rows = ryanair.parse_fares(load(), TODAY)
    assert rows[0] == {
        "snapshot_date": "2026-11-03",
        "source": "ryanair",
        "origin": "BER",
        "destination": "BGY",
        "departure_date": "2026-12-06",
        "departure_time": "07:50",
        "airline": "Ryanair",
        "flight_number": "FR2670",
        "stops": 0,
        "price": 17.99,
        "currency": "EUR",
    }


def test_skips_fares_without_a_price():
    payload = load()
    payload["fares"][0]["outbound"]["price"] = None
    assert len(ryanair.parse_fares(payload, TODAY)) == 1


def test_requests_every_airport_and_window():
    calls = []

    def get(url, params):
        calls.append((params["departureAirportIataCode"], params["outboundDepartureDateFrom"]))
        return load()

    rows = ryanair.collect(CONFIG, TODAY, get=get, sleep=no_sleep)
    assert len(calls) == 4
    assert ("CGN", "2026-11-11") in calls
    assert len(rows) == 8


def test_isolated_failure_keeps_the_rest():
    results = [requests.HTTPError("boom"), load(), requests.HTTPError("boom"), load()]

    def get(url, params):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    assert len(ryanair.collect(CONFIG, TODAY, get=get, sleep=no_sleep)) == 4


def test_repeated_failures_stop_the_source_early():
    calls = []

    def get(url, params):
        calls.append(params)
        raise requests.HTTPError("boom")

    with pytest.raises(SourceFailed):
        ryanair.collect(CONFIG, TODAY, get=get, sleep=no_sleep)
    assert len(calls) == 2


def test_no_fares_is_a_failure():
    with pytest.raises(SourceFailed):
        ryanair.collect(CONFIG, TODAY, get=lambda url, params: {"fares": []}, sleep=no_sleep)
