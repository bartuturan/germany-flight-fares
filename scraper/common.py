"""Shared HTTP helper and error type."""

import time
import zlib
from datetime import timedelta

import requests

USER_AGENT = "germany-flight-fares/0.1 (personal research)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class SourceFailed(Exception):
    """A source could not produce a usable result for this run.

    `partial` holds what it did collect before stopping, if anything, so it can still be saved.
    """

    def __init__(self, message, partial=None):
        super().__init__(message)
        self.partial = partial


def tracked_departures(route, today, min_lead, max_lead):
    """The departures to search for a route today: one in each 7-day block of the calendar.

    The choice depends only on the route and the date, so a departure stays tracked on every
    run until it leaves. The weekday moves on by one each week, and differs between routes.
    """
    route_offset = zlib.crc32(route.encode())
    departures = []
    for lead in range(min_lead, max_lead + 1):
        day = today + timedelta(days=lead)
        ordinal = day.toordinal()
        if ordinal % 7 == (ordinal // 7 + route_offset) % 7:
            departures.append(day)
    return departures


def get_json(url, params=None, attempts=3, backoff_seconds=5.0, timeout=60, sleep=time.sleep):
    """GET JSON, retrying rate limits, server errors and connection problems."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
            )
            if response.status_code not in RETRY_STATUS:
                response.raise_for_status()
                return response.json()
            error = requests.HTTPError(f"HTTP {response.status_code} from {url}")
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = exc
        if attempt < attempts:
            sleep(backoff_seconds * 2 ** (attempt - 1))
    raise error
