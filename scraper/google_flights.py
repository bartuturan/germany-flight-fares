"""One-way fares for tracked departures on Google Flights: the cheapest, and every itinerary.

fast-flights builds the query, but the request and the response are handled here. Its parser reads
only the "other flights" section, so it misses cheaper fares under "best flights", and it loses
the whole search if any itinerary has no price. It also starts a new session for every search.
"""

import json
import logging
import re
import time
from dataclasses import dataclass

import primp
from fast_flights import FlightQuery, Passengers, create_query
from selectolax.lexbor import LexborHTMLParser

from .common import SourceFailed, tracked_departures

log = logging.getLogger(__name__)

URL = "https://www.google.com/travel/flights"
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
        code = re.match(r"\[(\d+),", data)
        raise SearchFailed(f"Google's page reported an error (code {code.group(1) if code else '?'})")
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


def itinerary_rows(itineraries, origin, destination, currency, snapshot_date):
    return [
        {
            "snapshot_date": snapshot_date.isoformat(),
            "source": "google_flights",
            "origin": origin,
            "destination": destination,
            "departure_date": itinerary.departure_date,
            "departure_time": itinerary.departure_time,
            "airline": " + ".join(itinerary.airlines),
            "stops": itinerary.stops,
            "price": itinerary.price,
            "currency": currency,
        }
        for itinerary in itineraries
    ]


def make_search():
    """A search function that keeps one browser session, and its cookies, for a whole run.

    Google answers some requests with an internal error. In a test of 120 requests on a GitHub
    runner, a new session for every search (as fast-flights does) errored on 8 of 20 and on 39 of
    80 across the profiles tried, while reusing one session errored on 6 of 40. Pauses between
    requests and other browser profiles made no difference.
    """
    session = primp.Client(
        impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True
    )

    def search(origin, destination, date, currency):
        query = create_query(
            flights=[FlightQuery(date=date.isoformat(), from_airport=origin, to_airport=destination)],
            seat="economy",
            trip="one-way",
            passengers=Passengers(adults=1),
            language="en-US",
            currency=currency,
        )
        return parse_html(session.get(URL, params=query.params()).text)

    return search


def _build_result(searches, found, currency, today):
    rows = []
    all_itineraries = []
    for key in searches:
        if key in found:
            origin, destination = key[0].split("-")
            rows.append(cheapest_row(found[key], origin, destination, currency, today))
            all_itineraries += itinerary_rows(found[key], origin, destination, currency, today)
    return rows, all_itineraries


def collect(config, today, run_search=None, sleep=time.sleep, clock=time.monotonic):
    """Returns the cheapest fare per search, and every itinerary that was on offer.

    Google's errors come in waves, so a failed search is tried again in a later pass, after a
    pause, instead of straight away. If the run is blocked or runs out of time, it raises
    SourceFailed with what it collected attached, so that can still be saved.
    """
    started = clock()
    run_search = run_search or make_search()
    requests = errors = 0
    searches = [
        (route, date)
        for route in config["routes"]
        for date in tracked_departures(route, today, config["min_lead_days"], config["max_lead_days"])
    ]
    found = {}
    pending = searches
    stopped = None
    for number in range(1, config["passes"] + 1):
        if number > 1:
            if not pending:
                break
            log.info("google_flights: pass %d, %d searches to try again", number, len(pending))
            sleep(config["pass_cooldown_seconds"])
        unfinished = []
        consecutive = 0
        for key in pending:
            if clock() - started > config["time_budget_minutes"] * 60:
                stopped = f"out of time after {config['time_budget_minutes']} minutes"
                break
            route, date = key
            origin, destination = route.split("-")
            requests += 1
            try:
                found[key] = run_search(origin, destination, date, config["currency"])
                consecutive = 0
            except Blocked as exc:
                stopped = str(exc)
                break
            except Exception as exc:
                errors += 1
                log.warning("google_flights %s %s failed in pass %d: %r", route, date, number, exc)
                unfinished.append(key)
                consecutive += 1
                if consecutive >= config["max_consecutive_failures"] and not found:
                    stopped = f"{consecutive} Google searches failed in a row and none has worked"
                    break
            sleep(config["delay_seconds"])
        if stopped:
            break
        pending = unfinished

    rows, all_itineraries = _build_result(searches, found, config["currency"], today)
    if stopped:
        raise SourceFailed(stopped, partial=(rows, all_itineraries) if rows else None)
    if not rows:
        raise SourceFailed("Google Flights returned no fares")
    log.info(
        "google_flights: %d of %d searches gave a fare, %d failed (%d of %d requests errored)",
        len(rows),
        len(searches),
        len(searches) - len(rows),
        errors,
        requests,
    )
    return rows, all_itineraries
