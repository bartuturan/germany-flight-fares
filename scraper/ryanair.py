"""Cheapest one-way Ryanair fare on each route and departure day from German airports.

The endpoint returns the cheapest fare per destination in the window it's given. One-day windows
show every day with a flight, where a wider window shows only that window's cheapest day.
"""

import logging
import time
from datetime import timedelta

import requests

from .common import SourceFailed, get_json

URL = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"

log = logging.getLogger(__name__)


def departure_days(today, days_ahead):
    """Each day from tomorrow, up to `days_ahead` days away."""
    for lead in range(1, days_ahead + 1):
        yield today + timedelta(days=lead)


def parse_fares(payload, snapshot_date):
    rows = []
    for fare in payload.get("fares") or []:
        outbound = fare["outbound"]
        price = outbound.get("price")
        if not price or price.get("value") is None:
            continue
        departure_date, _, departure_time = outbound["departureDate"].partition("T")
        rows.append(
            {
                "snapshot_date": snapshot_date.isoformat(),
                "source": "ryanair",
                "origin": outbound["departureAirport"]["iataCode"],
                "destination": outbound["arrivalAirport"]["iataCode"],
                "departure_date": departure_date,
                "departure_time": departure_time[:5],
                "airline": "Ryanair",
                "flight_number": outbound.get("flightNumber", ""),
                "stops": 0,
                "price": price["value"],
                "currency": price["currencyCode"],
            }
        )
    return rows


def collect(config, today, get=get_json, sleep=time.sleep):
    rows = []
    failed = 0
    consecutive = 0
    for airport in config["airports"]:
        for day in departure_days(today, config["days_ahead"]):
            params = {
                "departureAirportIataCode": airport,
                "outboundDepartureDateFrom": day.isoformat(),
                "outboundDepartureDateTo": day.isoformat(),
                "currency": config["currency"],
                "market": config["market"],
                "limit": 500,
            }
            try:
                rows += parse_fares(get(URL, params=params), today)
                consecutive = 0
            except (requests.RequestException, ValueError, KeyError) as exc:
                failed += 1
                consecutive += 1
                log.warning("ryanair %s %s failed: %s", airport, day, exc)
                if consecutive >= config["max_consecutive_failures"]:
                    raise SourceFailed(f"{consecutive} Ryanair requests failed in a row") from exc
            sleep(config["delay_seconds"])
    if not rows:
        raise SourceFailed("Ryanair returned no fares")
    if failed:
        log.warning("ryanair: %d requests failed, keeping the rest", failed)
    return rows
