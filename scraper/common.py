"""Shared HTTP helper and error type."""

import time

import requests

USER_AGENT = "germany-flight-fares/0.1 (personal research)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class SourceFailed(Exception):
    """A source could not produce a usable result for this run."""


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
