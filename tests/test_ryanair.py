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
    "days_ahead": 2,
    "currency": "EUR",
    "market": "de-de",
    "delay_seconds": 0,
    "max_consecutive_failures": 2,
}


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def no_sleep(_):
    pass


def test_days_start_tomorrow():
    assert list(ryanair.departure_days(TODAY, 2)) == [date(2026, 11, 4), date(2026, 11, 5)]


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
        "arrival_at": "2026-12-06T09:35",
        "price_updated_at": "2026-11-03T14:31:45Z",
        "previous_price": "",
    }


@pytest.mark.parametrize(
    "previous, expected",
    [(None, ""), (24.99, 24.99), ({"value": 21.5, "currencyCode": "EUR"}, 21.5), ("n/a", ""), (True, "")],
)
def test_previous_price_is_read_from_a_number_or_a_price_object(previous, expected):
    payload = load()
    payload["fares"][0]["outbound"]["previousPrice"] = previous
    assert ryanair.parse_fares(payload, TODAY)[0]["previous_price"] == expected


def test_missing_arrival_and_update_time_leave_the_columns_empty():
    payload = load()
    for key in ("arrivalDate", "priceUpdated"):
        del payload["fares"][0]["outbound"][key]
    row = ryanair.parse_fares(payload, TODAY)[0]
    assert (row["arrival_at"], row["price_updated_at"]) == ("", "")


def test_skips_fares_without_a_price():
    payload = load()
    payload["fares"][0]["outbound"]["price"] = None
    assert len(ryanair.parse_fares(payload, TODAY)) == 1


def test_requests_every_airport_and_day_with_one_day_windows():
    calls = []

    def get(url, params):
        assert params["outboundDepartureDateFrom"] == params["outboundDepartureDateTo"]
        calls.append((params["departureAirportIataCode"], params["outboundDepartureDateFrom"]))
        return load()

    rows = ryanair.collect(CONFIG, TODAY, get=get, sleep=no_sleep)
    assert len(calls) == 4
    assert ("CGN", "2026-11-05") in calls
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
