from datetime import date

import pytest
from fast_flights import FlightsNotFound
from fast_flights.model import Airport, CarbonEmission, Flights, SimpleDatetime, SingleFlight

from scraper import google_flights
from scraper.common import SourceFailed

TODAY = date(2026, 11, 3)
CONFIG = {
    "routes": ["FRA-JFK", "MUC-BER"],
    "lead_days": [7, 30],
    "currency": "EUR",
    "delay_seconds": 0,
    "max_consecutive_failures": 2,
}


def no_sleep(_):
    pass


def flight(price, airlines=("Lufthansa",), legs=1):
    leg = SingleFlight(
        from_airport=Airport("Frankfurt", "FRA"),
        to_airport=Airport("New York", "JFK"),
        departure=SimpleDatetime(date=(2026, 12, 3), time=(9, 5)),
        arrival=SimpleDatetime(date=(2026, 12, 3), time=(12, 0)),
        duration=540,
        plane_type="A350",
    )
    return Flights(
        type="LH",
        price=price,
        airlines=list(airlines),
        flights=[leg] * legs,
        carbon=CarbonEmission(typical_on_route=1, emission=1),
    )


def test_consent_page_is_reported_as_blocked():
    with pytest.raises(google_flights.Blocked, match="consent"):
        google_flights.parse_html('<a href="https://consent.google.com/save">Before you continue</a>')


def test_page_without_flight_data_is_reported_as_blocked():
    with pytest.raises(google_flights.Blocked, match="no flight data"):
        google_flights.parse_html("<html>unusual traffic</html>")


def test_keeps_the_cheapest_itinerary():
    flights = [flight(500), flight(320, ("Condor", "United"), legs=2), flight(410)]
    row = google_flights.cheapest_row(flights, "FRA", "JFK", "EUR", TODAY)
    assert row == {
        "snapshot_date": "2026-11-03",
        "source": "google_flights",
        "origin": "FRA",
        "destination": "JFK",
        "departure_date": "2026-12-03",
        "departure_time": "09:05",
        "airline": "Condor + United",
        "flight_number": "",
        "stops": 1,
        "price": 320,
        "currency": "EUR",
    }


def test_ignores_itineraries_without_a_price():
    assert google_flights.cheapest_row([flight(0)], "FRA", "JFK", "EUR", TODAY) is None


def test_searches_every_route_at_every_lead_time():
    calls = []

    def run_search(origin, destination, when, currency):
        calls.append((origin, destination, when))
        return [flight(100)]

    rows = google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(rows) == 4
    assert ("MUC", "BER", date(2026, 12, 3)) in calls


def test_blocked_stops_immediately():
    calls = []

    def run_search(*args):
        calls.append(args)
        raise google_flights.Blocked("Google returned its consent page")

    with pytest.raises(SourceFailed, match="consent"):
        google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(calls) == 1


def test_route_without_flights_is_not_a_failure():
    results = [FlightsNotFound("none"), [flight(100)], FlightsNotFound("none"), [flight(200)]]

    def run_search(*args):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    assert len(google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)) == 2


def test_repeated_errors_stop_the_source_early():
    calls = []

    def run_search(*args):
        calls.append(args)
        raise IndexError("layout changed")

    with pytest.raises(SourceFailed):
        google_flights.collect(CONFIG, TODAY, run_search=run_search, sleep=no_sleep)
    assert len(calls) == 2
