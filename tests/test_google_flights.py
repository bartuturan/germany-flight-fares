import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from scraper import google_flights
from scraper.common import SourceFailed
from scraper.google_flights import Itinerary, SearchFailed

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 3)
CONFIG = {
    "routes": ["FRA-JFK", "MUC-BER"],
    "min_lead_days": 1,
    "max_lead_days": 2,
    "currency": "EUR",
    "delay_seconds": 0,
    "attempts": 2,
    "retry_delay_seconds": 0,
    "max_consecutive_failures": 2,
}


@pytest.fixture(autouse=True)
def search_every_day_in_range(monkeypatch):
    """Which departures get tracked is tested in test_common.py."""
    monkeypatch.setattr(
        google_flights,
        "tracked_departures",
        lambda route, today, low, high: [today + timedelta(days=lead) for lead in range(low, high + 1)],
    )


def no_sleep(_):
    pass


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def page(payload):
    data = json.dumps(payload)
    return f"""<html><script class="ds:1" nonce="x">AF_initDataCallback({{key: 'ds:1', hash: '2', data:{data}, sideChannel: {{}}}});</script></html>"""


def itinerary(price, airlines=("Lufthansa",), stops=0):
    return Itinerary(
        price=price,
        airlines=list(airlines),
        stops=stops,
        departure_date="2026-12-03",
        departure_time="09:05",
    )


def row_from(name, origin, destination):
    parsed = google_flights.parse_html(page(load(name)))
    return google_flights.cheapest_row(parsed, origin, destination, "EUR", TODAY)


def test_finds_a_cheaper_fare_in_the_best_flights_section():
    # Real response: fast-flights read only "other flights" and reported 149 here.
    row = row_from("google_fra_lhr_2026_12_03.json", "FRA", "LHR")
    assert row == {
        "snapshot_date": "2026-11-03",
        "source": "google_flights",
        "origin": "FRA",
        "destination": "LHR",
        "departure_date": "2026-12-03",
        "departure_time": "07:20",
        "airline": "British Airways",
        "flight_number": "",
        "stops": 0,
        "price": 102,
        "currency": "EUR",
    }


def test_itinerary_without_a_price_does_not_lose_the_search():
    # Real response: an entry with an empty price made fast-flights raise IndexError.
    payload = load("google_muc_ber_2026_11_10.json")
    assert payload[3][0][-1][1][0] == []
    row = row_from("google_muc_ber_2026_11_10.json", "MUC", "BER")
    assert (row["price"], row["airline"], row["stops"]) == (183, "Condor", 1)


def test_reads_every_priced_itinerary_from_both_sections():
    parsed = google_flights.parse_payload(load("google_muc_ber_2026_11_10.json"))
    assert [item.price for item in parsed] == [220, 220, 220, 183, 220, 230]


@pytest.mark.parametrize(
    "value, expected",
    [([8], "08:00"), ([None, 31], "00:31"), ([17, 5], "17:05"), (None, "00:00"), ([], "00:00")],
)
def test_time_with_omitted_components(value, expected):
    assert google_flights._parse_time(value) == expected


def test_missing_section_is_tolerated():
    payload = load("google_fra_lhr_2026_12_03.json")
    payload[3] = None
    assert [item.price for item in google_flights.parse_payload(payload)] == [102, 119, 149]
    payload = load("google_fra_lhr_2026_12_03.json")
    payload[2] = [None]
    assert [item.price for item in google_flights.parse_payload(payload)] == [149, 149, 149]


def test_malformed_itinerary_is_skipped_and_logged(caplog):
    payload = load("google_fra_lhr_2026_12_03.json")
    payload[2][0][0] = [[], [[None, 1]]]
    parsed = google_flights.parse_payload(payload)
    assert min(item.price for item in parsed) == 119
    assert "malformed" in caplog.text


def test_no_priced_itineraries_is_a_failed_search():
    with pytest.raises(SearchFailed):
        google_flights.parse_payload([None, None, [None], [None]])


def test_google_error_page_is_a_failed_search():
    html = """<script class="ds:1">AF_initDataCallback({key: 'ds:1', hash: '2', data:function(){return []}, errorHasStatus: true, sideChannel: {}});</script>"""
    with pytest.raises(SearchFailed, match="reported an error"):
        google_flights.parse_html(html)


def test_consent_page_is_reported_as_blocked():
    with pytest.raises(google_flights.Blocked, match="consent"):
        google_flights.parse_html('<a href="https://consent.google.com/save">Before you continue</a>')


def test_page_without_flight_data_is_reported_as_blocked():
    with pytest.raises(google_flights.Blocked, match="no flight data"):
        google_flights.parse_html("<html>unusual traffic</html>")


def test_keeps_the_cheapest_itinerary_and_joins_airlines():
    options = [itinerary(500), itinerary(320, ("Condor", "United"), stops=1), itinerary(410)]
    row = google_flights.cheapest_row(options, "FRA", "JFK", "EUR", TODAY)
    assert (row["price"], row["airline"], row["stops"]) == (320, "Condor + United", 1)


def test_tied_price_prefers_fewer_stops():
    options = [itinerary(149, ("KLM",), stops=1), itinerary(149, ("Lufthansa",), stops=0)]
    assert google_flights.cheapest_row(options, "FRA", "LHR", "EUR", TODAY)["airline"] == "Lufthansa"


def test_searches_every_tracked_departure_on_every_route():
    calls = []

    def run_search(origin, destination, when, currency):
        calls.append((origin, destination, when))
        return [itinerary(100)]

    rows, _ = google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(rows) == 4
    assert ("MUC", "BER", date(2026, 11, 5)) in calls


def test_keeps_every_itinerary_as_well_as_the_cheapest():
    options = [itinerary(500), itinerary(320, ("Condor", "United"), stops=1), itinerary(410)]
    config = {**CONFIG, "routes": ["FRA-JFK"], "max_lead_days": 1}

    rows, itineraries = google_flights.collect(
        config, TODAY, run_search=lambda *args: options, sleep=no_sleep
    )

    assert [row["price"] for row in rows] == [320]
    assert [row["price"] for row in itineraries] == [500, 320, 410]
    assert itineraries[1] == {
        "snapshot_date": "2026-11-03",
        "source": "google_flights",
        "origin": "FRA",
        "destination": "JFK",
        "departure_date": "2026-12-03",
        "departure_time": "09:05",
        "airline": "Condor + United",
        "stops": 1,
        "price": 320,
        "currency": "EUR",
    }


def test_failed_search_keeps_no_itineraries_for_it():
    results = [SearchFailed("x"), SearchFailed("x"), [itinerary(100)]]

    def run_search(*args):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    config = {**CONFIG, "routes": ["FRA-JFK"]}
    rows, itineraries = google_flights.collect(config, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(rows) == len(itineraries) == 1


def test_blocked_stops_immediately():
    calls = []

    def run_search(*args):
        calls.append(args)
        raise google_flights.Blocked("Google returned its consent page")

    with pytest.raises(SourceFailed, match="consent"):
        google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(calls) == 1


def test_failed_search_is_retried_and_recovers():
    config = {**CONFIG, "routes": ["FRA-JFK"], "max_lead_days": 1}
    results = [SearchFailed("Google's page reported an error"), [itinerary(100)]]

    def run_search(*args):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    rows, _ = google_flights.collect(config, TODAY, run_search=run_search, sleep=no_sleep)
    assert [row["price"] for row in rows] == [100]
    assert results == []


def test_failed_search_after_retries_counts_as_failed_and_keeps_the_rest(caplog):
    config = {**CONFIG, "routes": ["FRA-JFK"]}
    results = [
        SearchFailed("Google's page reported an error"),
        SearchFailed("Google's page reported an error"),
        [itinerary(100)],
    ]

    def run_search(*args):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with caplog.at_level("INFO"):
        rows, _ = google_flights.collect(config, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(rows) == 1
    assert "1 of 2 searches gave a fare, 1 failed" in caplog.text


def test_repeated_errors_stop_the_source_early():
    calls = []

    def run_search(*args):
        calls.append(args)
        raise IndexError("layout changed")

    with pytest.raises(SourceFailed):
        google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)
    # Two searches in a row fail, each after two attempts.
    assert len(calls) == 4
