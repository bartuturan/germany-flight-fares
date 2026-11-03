"""Cheapest one-way fare per route and lead time on Google Flights.

Requests go through fast-flights, but the response is parsed here. Its parser reads only the
"other flights" section, so it misses cheaper fares under "best flights", and it loses the whole
search if any itinerary has no price.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

from .common import SourceFailed

log = logging.getLogger(__name__)

BEST_FLIGHTS, OTHER_FLIGHTS = 2, 3


class Blocked(Exception):
    """Google returned a page with no flight results, such as a consent or bot check."""


class SearchFailed(Exception):
    """Google's response had no usable fare. This is often temporary."""


@dataclass
class Itinerary:
    price: float
    airlines: list[str]
    stops: int
    departure_date: str
    departure_time: str


def _parse_time(value):
    """Google omits zero components, so [8] means 08:00 and [None, 31] means 00:31."""
    hour, minute = [*(value or []), None, None][:2]
    return f"{hour or 0:02d}:{minute or 0:02d}"


def _parse_itinerary(entry):
    """One itinerary, or None if it has no price, which Google does for some of them."""
    flight, offer = entry[0], entry[1]
    price = offer[0][1] if offer and offer[0] else None
    if not price:
        return None
    legs = flight[2]
    year, month, day = legs[0][20]
    return Itinerary(
        price=price,
        airlines=flight[1],
        stops=len(legs) - 1,
        departure_date=f"{year:04d}-{month:02d}-{day:02d}",
        departure_time=_parse_time(legs[0][8]),
    )


def parse_payload(payload):
    """All priced itineraries from both sections of Google's results."""
    itineraries = []
    for number in (BEST_FLIGHTS, OTHER_FLIGHTS):
        section = payload[number]
        for entry in (section[0] or []) if section else []:
            try:
                itinerary = _parse_itinerary(entry)
            except (IndexError, TypeError, ValueError) as exc:
                log.warning("google_flights skipped a malformed itinerary: %r", exc)
                continue
            if itinerary:
                itineraries.append(itinerary)
    if not itineraries:
        raise SearchFailed("no priced itineraries")
    return itineraries


def parse_html(html):
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        if "consent.google" in html:
            raise Blocked("Google returned its consent page")
        raise Blocked("Google returned a page with no flight data")
    data = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        raise SearchFailed("Google's page reported an error")
    return parse_payload(json.loads(data))


def cheapest_row(itineraries, origin, destination, currency, snapshot_date):
    best = min(itineraries, key=lambda itinerary: (itinerary.price, itinerary.stops))
    return {
        "snapshot_date": snapshot_date.isoformat(),
        "source": "google_flights",
        "origin": origin,
        "destination": destination,
        "departure_date": best.departure_date,
        "departure_time": best.departure_time,
        "airline": " + ".join(best.airlines),
        "flight_number": "",
        "stops": best.stops,
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
                itineraries = search_with_retries(
                    run_search, config, sleep, origin, destination, date, config["currency"]
                )
                rows.append(cheapest_row(itineraries, origin, destination, config["currency"], today))
                consecutive = 0
            except Blocked as exc:
                raise SourceFailed(str(exc)) from exc
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
