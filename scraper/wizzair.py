"""Cheapest one-way Wizz Air fare on each route and departure day from German airports.

Wizz Air has no public API. This uses the one its own website calls, which is versioned in the URL
and changes every few weeks. The current version is written in the homepage, so each run reads it
from there, and falls back to the last version known to work if the homepage can't be read.

The route map lists every route from each airport. The timetable endpoint then returns the
cheapest fare for each day with a flight in a window of up to 38 days.
"""

import logging
import re
import time
from datetime import timedelta

import requests

from .common import SourceFailed, get_json, post_json

HOME_URL = "https://www.wizzair.com/en-gb"
API_URL = re.compile(r'apiUrl:"(https://be\.wizzair\.com/[\d.]+/Api)"')
API_TEMPLATE = "https://be.wizzair.com/{version}/Api"
# The homepage answers a plain scraper user agent with a "Human Verification" page. The API doesn't.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
# A timetable window of 44 days is rejected with InvalidTimeDateRange, 38 days is accepted.
MAX_WINDOW_DAYS = 30
FARE_PRICE_TYPE = "price"

log = logging.getLogger(__name__)


def fetch_homepage():
    response = requests.get(HOME_URL, headers={"User-Agent": BROWSER_USER_AGENT}, timeout=60)
    response.raise_for_status()
    return response.text


def extract_api_url(html):
    match = API_URL.search(html or "")
    return match.group(1) if match else None


def find_api_url(config, fetch=fetch_homepage):
    """The versioned API address from the homepage, or the configured fallback version."""
    try:
        found = extract_api_url(fetch())
        if found:
            return found
        reason = "no API address in the homepage"
    except requests.RequestException as exc:
        reason = str(exc)
    fallback = API_TEMPLATE.format(version=config["fallback_api_version"])
    log.warning("wizzair: %s, using version %s", reason, config["fallback_api_version"])
    return fallback


def routes_from_map(payload, airports):
    """(origin, destination) for each route leaving one of `airports`, in the map's order."""
    wanted = set(airports)
    routes = []
    for city in payload.get("cities") or []:
        if city.get("iata") in wanted:
            routes += [(city["iata"], connection["iata"]) for connection in city["connections"]]
    return routes


def date_windows(today, days_ahead, max_days=MAX_WINDOW_DAYS):
    """Consecutive (first, last) day windows covering tomorrow up to `days_ahead` days away."""
    windows = []
    first = 1
    while first <= days_ahead:
        last = min(first + max_days - 1, days_ahead)
        windows.append((today + timedelta(days=first), today + timedelta(days=last)))
        first = last + 1
    return windows


def timetable_request(origin, destination, first, last):
    return {
        "flightList": [
            {
                "departureStation": origin,
                "arrivalStation": destination,
                "from": first.isoformat(),
                "to": last.isoformat(),
            }
        ],
        "priceType": "regular",
        "adultCount": 1,
        "childCount": 0,
        "infantCount": 0,
    }


def parse_timetable(payload, snapshot_date):
    """Fare rows from one timetable answer, and how many days listed no usable price.

    A day marked `checkPrice` has a price of 0 and no real fare, so it is left out, not stored.
    """
    rows = []
    unpriced = 0
    for day in payload.get("outboundFlights") or []:
        price = day.get("price") or {}
        if day.get("priceType") != FARE_PRICE_TYPE or not price.get("amount"):
            unpriced += 1
            continue
        rows.append(
            {
                "snapshot_date": snapshot_date.isoformat(),
                "source": "wizzair",
                "origin": day["departureStation"],
                "destination": day["arrivalStation"],
                "departure_date": day["departureDate"][:10],
                # The answer gives the day's cheapest price and its flight times, not which time.
                "departure_time": "",
                "airline": "Wizz Air",
                "flight_number": "",
                "stops": 0,
                "price": price["amount"],
                "currency": price["currencyCode"],
            }
        )
    return rows, unpriced


def drop_duplicates(rows):
    """One row per route and day.

    The route map lists city-group codes beside real airports, such as ROM beside FCO and MIL
    beside MXP. Asking for the group returns the airport's flights again, under the airport's
    code, so those routes would be counted twice.
    """
    unique = {}
    for row in rows:
        unique.setdefault((row["origin"], row["destination"], row["departure_date"]), row)
    return list(unique.values())


def collect(
    config,
    today,
    get=get_json,
    post=post_json,
    fetch=fetch_homepage,
    sleep=time.sleep,
):
    api_url = find_api_url(config, fetch)
    try:
        routes = routes_from_map(
            get(f"{api_url}/asset/map", params={"languageCode": "en-gb"}), config["airports"]
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise SourceFailed(f"Wizz Air route map failed: {exc}") from exc
    if not routes:
        raise SourceFailed("Wizz Air route map has no routes from the configured airports")

    def request(job):
        origin, destination, first, last = job
        payload = timetable_request(origin, destination, first, last)
        return parse_timetable(post(f"{api_url}/search/timetable", payload), today)

    jobs = [
        (origin, destination, first, last)
        for origin, destination in routes
        for first, last in date_windows(today, config["days_ahead"])
    ]
    rows = []
    unpriced = 0
    failed = []
    consecutive = 0
    for job in jobs:
        try:
            found, skipped = request(job)
            rows += found
            unpriced += skipped
            consecutive = 0
        except (requests.RequestException, ValueError, KeyError) as exc:
            failed.append(job)
            consecutive += 1
            log.warning("wizzair %s-%s %s..%s failed: %s", *job, exc)
            if consecutive >= config["max_consecutive_failures"]:
                raise SourceFailed(f"{consecutive} Wizz Air requests failed in a row") from exc
        sleep(config["delay_seconds"])

    # Server errors come in bursts that outlast the retries inside one request, so try the
    # requests that failed once more after a pause.
    if failed:
        log.info("wizzair: retrying %d failed requests after a pause", len(failed))
        sleep(config["retry_cooldown_seconds"])
        retried, failed = failed, []
        for job in retried:
            try:
                found, skipped = request(job)
                rows += found
                unpriced += skipped
            except (requests.RequestException, ValueError, KeyError) as exc:
                failed.append(job)
                log.warning("wizzair %s-%s %s..%s failed again: %s", *job, exc)
            sleep(config["delay_seconds"])

    if not rows:
        raise SourceFailed("Wizz Air returned no fares")
    if failed:
        log.warning("wizzair: %d requests failed twice, keeping the rest", len(failed))
    unique = drop_duplicates(rows)
    log.info(
        "wizzair: %d fares from %d routes, %d duplicates dropped, %d days listed no price",
        len(unique),
        len(routes),
        len(rows) - len(unique),
        unpriced,
    )
    return unique
