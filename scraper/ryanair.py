"""Cheapest one-way Ryanair fares from German airports, by weekly departure window."""

import logging
import time
from datetime import timedelta

import requests

from .common import SourceFailed, get_json

URL = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"

log = logging.getLogger(__name__)


def departure_windows(today, weeks):
    """Consecutive 7-day windows, starting tomorrow."""
    for week in range(weeks):
        start = today + timedelta(days=1 + 7 * week)
        yield start, start + timedelta(days=6)


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
        for start, end in departure_windows(today, config["weeks_ahead"]):
            params = {
                "departureAirportIataCode": airport,
                "outboundDepartureDateFrom": start.isoformat(),
                "outboundDepartureDateTo": end.isoformat(),
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
                log.warning("ryanair %s %s failed: %s", airport, start, exc)
                if consecutive >= config["max_consecutive_failures"]:
                    raise SourceFailed(f"{consecutive} Ryanair requests failed in a row") from exc
            sleep(config["delay_seconds"])
    if not rows:
        raise SourceFailed("Ryanair returned no fares")
    if failed:
        log.warning("ryanair: %d requests failed, keeping the rest", failed)
    return rows
