"""Cheapest one-way fare per route and lead time on Google Flights, via fast-flights."""

import logging
import time
from datetime import timedelta

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from fast_flights.parser import parse

from .common import SourceFailed

log = logging.getLogger(__name__)


class Blocked(Exception):
    """Google returned a page with no flight results, such as a consent or bot check."""


def parse_html(html):
    if 'class="ds:1"' not in html:
        if "consent.google" in html:
            raise Blocked("Google returned its consent page")
        raise Blocked("Google returned a page with no flight data")
    return parse(html)


def cheapest_row(flights, origin, destination, currency, snapshot_date):
    priced = [flight for flight in flights if flight.price]
    if not priced:
        return None
    best = min(priced, key=lambda flight: flight.price)
    year, month, day = best.flights[0].departure.date
    hour, minute = best.flights[0].departure.time
    return {
        "snapshot_date": snapshot_date.isoformat(),
        "source": "google_flights",
        "origin": origin,
        "destination": destination,
        "departure_date": f"{year:04d}-{month:02d}-{day:02d}",
        "departure_time": f"{hour:02d}:{minute:02d}",
        "airline": " + ".join(best.airlines),
        "flight_number": "",
        "stops": len(best.flights) - 1,
        "price": best.price,
        "currency": currency,
    }


def search(origin, destination, date, currency):
    query = create_query(
        flights=[FlightQuery(date=date.isoformat(), from_airport=origin, to_airport=destination)],
        seat="economy",
        trip="one-way",
        passengers=Passengers(adults=1),
        language="en-US",
        currency=currency,
    )
    return parse_html(fetch_flights_html(query))


def search_with_retries(run_search, config, sleep, *search_args):
    """Retry errors, except a block, which more requests would not resolve."""
    for attempt in range(1, config["attempts"] + 1):
        try:
            return run_search(*search_args)
        except Blocked:
            raise
        except Exception as exc:
            if attempt == config["attempts"]:
                raise
            log.info("google_flights %s retrying after: %r", search_args[:3], exc)
            sleep(config["retry_delay_seconds"])


def collect(config, today, run_search=search, sleep=time.sleep):
    rows = []
    failed = 0
    consecutive = 0
    searches = len(config["routes"]) * len(config["lead_days"])
    for route in config["routes"]:
        origin, destination = route.split("-")
        for lead in config["lead_days"]:
            date = today + timedelta(days=lead)
            try:
                flights = search_with_retries(
                    run_search, config, sleep, origin, destination, date, config["currency"]
                )
                row = cheapest_row(flights, origin, destination, config["currency"], today)
                if row:
                    rows.append(row)
                consecutive = 0
            except Blocked as exc:
                raise SourceFailed(str(exc)) from exc
            # FlightsNotFound means Google's page reported an error, not that a route is empty.
            # Other error types are how fast-flights surfaces layout changes.
            except Exception as exc:
                failed += 1
                consecutive += 1
                log.warning("google_flights %s %s failed: %r", route, date, exc)
                if consecutive >= config["max_consecutive_failures"]:
                    raise SourceFailed(f"{consecutive} Google searches failed in a row") from exc
            sleep(config["delay_seconds"])
    if not rows:
        raise SourceFailed("Google Flights returned no fares")
    log.info("google_flights: %d of %d searches gave a fare, %d failed", len(rows), searches, failed)
    return rows
