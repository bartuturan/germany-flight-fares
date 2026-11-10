"""Throwaway check: does Wizz Air answer requests from this machine (for example a GitHub runner)?

Makes real requests to the homepage, the route map and the timetable, classifies every answer and
prints a Markdown report. It writes nothing to data/ and imports nothing from scraper/, because it
has to see every raw status and body, where scraper.common.get_json retries and raises.

    python tools/wizzair_probe.py --scale sample --out probe.json
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta

import requests

HONEST_UA = "germany-flight-fares/0.1 (personal research)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
HOME_URL = "https://www.wizzair.com/en-gb"
API_URL_PATTERN = re.compile(r'apiUrl:"(https://be\.wizzair\.com/[\d.]+/Api)"')
BLOCK_TEXT = ("access denied", "captcha", "request blocked", "bot detection")
SHOWN_HEADERS = ("server", "x-cache", "via", "retry-after")
BLOCKED_STATUS = {403, 405, 429}
MAX_BLOCKED_SHARE = 0.2

OK, INVALID, BLOCKED, ERROR = "ok", "invalid", "blocked", "error"


def extract_api_url(html):
    """The versioned API base the site's own pages use, or None if the homepage didn't have it."""
    match = API_URL_PATTERN.search(html or "")
    return match.group(1) if match else None


def date_windows(today, days_ahead=45, split_after=23):
    """Two windows covering tomorrow..days_ahead. The timetable rejects windows over 38 days."""
    first = (today + timedelta(days=1), today + timedelta(days=split_after))
    second = (today + timedelta(days=split_after + 1), today + timedelta(days=days_ahead))
    return [first, second]


def classify(status, body, expect_key):
    """ok | invalid (our request was wrong) | blocked | error, from one raw response."""
    text = (body or "")[:2000].lower()
    if any(marker in text for marker in BLOCK_TEXT):
        return BLOCKED
    if status in BLOCKED_STATUS:
        return BLOCKED
    if status is None or status >= 500:
        return ERROR
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        # A 200 or 400 that isn't JSON is a web page where the API should be.
        return BLOCKED
    if status == 200:
        return OK if isinstance(payload, dict) and expect_key in payload else INVALID
    if status == 400 and isinstance(payload, dict) and "validationCodes" in payload:
        return INVALID
    return ERROR


def german_routes(map_payload):
    """(origin, destination) for every connection from a German station, in the map's order."""
    routes = []
    for city in map_payload.get("cities", []):
        if city.get("countryCode") != "DE":
            continue
        for connection in city.get("connections", []):
            routes.append((city["iata"], connection["iata"]))
    return routes


def spread_sample(routes, count=10):
    """One route per origin first, so the sample covers every German station."""
    by_origin = {}
    for origin, destination in routes:
        by_origin.setdefault(origin, []).append((origin, destination))
    picked = []
    depth = 0
    while len(picked) < count and any(len(v) > depth for v in by_origin.values()):
        for options in by_origin.values():
            if len(options) > depth and len(picked) < count:
                picked.append(options[depth])
        depth += 1
    return picked


def send(method, url, user_agent, expect_key, step, label, **kwargs):
    """One request, never raising: the result row says what happened."""
    headers = {"User-Agent": user_agent}
    if "json" in kwargs:
        headers["Content-Type"] = "application/json"
    started = time.monotonic()
    row = {"step": step, "label": label, "ua": "honest" if user_agent == HONEST_UA else "browser"}
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    except requests.RequestException as exc:
        row.update(result=ERROR, status=None, ms=int((time.monotonic() - started) * 1000))
        row["note"] = f"{type(exc).__name__}: {exc}"[:200]
        return row, None
    body = response.text
    row.update(
        result=classify(response.status_code, body, expect_key),
        status=response.status_code,
        ms=int((time.monotonic() - started) * 1000),
        size=len(body),
        headers={k: response.headers[k] for k in response.headers if k.lower() in SHOWN_HEADERS},
        cookies=sorted(response.cookies.keys()),
    )
    if row["result"] != OK:
        row["note"] = body[:200]
    return row, body


def timetable_body(origin, destination, start, end):
    return {
        "flightList": [
            {
                "departureStation": origin,
                "arrivalStation": destination,
                "from": start.isoformat(),
                "to": end.isoformat(),
            }
        ],
        "priceType": "regular",
        "adultCount": 1,
        "childCount": 0,
        "infantCount": 0,
    }


def run_probe(scale, delay, today, sleep=time.sleep):
    rows = []

    def record(row, body):
        rows.append(row)
        sleep(delay)
        return body

    api_url = None
    for agent in (HONEST_UA, BROWSER_UA):
        row, body = send("GET", HOME_URL, agent, "", "homepage", "en-gb")
        found = extract_api_url(body) if row["result"] != ERROR else None
        row["api_url_found"] = bool(found)
        # The homepage is HTML, so "ok" here means it came back with the API address in it.
        row["result"] = OK if found else (row["result"] if row["result"] != OK else BLOCKED)
        record(row, body)
        api_url = api_url or found
    if not api_url:
        return rows, None

    map_payload = None
    for agent in (HONEST_UA, BROWSER_UA):
        row, body = send(
            "GET", f"{api_url}/asset/map", agent, "cities", "route_map", "asset/map",
            params={"languageCode": "en-gb"},
        )
        record(row, body)
        if row["result"] == OK and map_payload is None:
            map_payload = json.loads(body)
    if map_payload is None:
        return rows, api_url

    routes = german_routes(map_payload)
    if scale == "sample":
        routes = spread_sample(routes)
    windows = date_windows(today)
    for origin, destination in routes:
        for start, end in windows:
            row, body = send(
                "POST", f"{api_url}/search/timetable", HONEST_UA, "outboundFlights", "timetable",
                f"{origin}-{destination} {start}..{end}",
                json=timetable_body(origin, destination, start, end),
            )
            record(row, body)

    # If the plain UA was blocked, say whether a browser UA gets through.
    if any(r["step"] == "timetable" and r["result"] == BLOCKED for r in rows):
        for origin, destination in routes[:3]:
            start, end = windows[0]
            row, body = send(
                "POST", f"{api_url}/search/timetable", BROWSER_UA, "outboundFlights",
                "timetable", f"{origin}-{destination} {start}..{end}",
                json=timetable_body(origin, destination, start, end),
            )
            record(row, body)
    return rows, api_url


def blocked_share(rows):
    """Share of honest-UA timetable calls that were blocked."""
    calls = [r for r in rows if r["step"] == "timetable" and r["ua"] == "honest"]
    return sum(r["result"] == BLOCKED for r in calls) / len(calls) if calls else 1.0


def markdown_report(rows, api_url, scale):
    lines = [f"## Wizz Air probe ({scale})", "", f"API: `{api_url or 'not found'}`", ""]
    counts = Counter((r["step"], r["ua"], r["result"]) for r in rows)
    lines += ["| step | user agent | result | calls |", "|---|---|---|---|"]
    for (step, agent, result), n in sorted(counts.items()):
        lines.append(f"| {step} | {agent} | {result} | {n} |")
    timetable = [r["ms"] for r in rows if r["step"] == "timetable" and "ms" in r]
    if timetable:
        lines += ["", f"Timetable: median {sorted(timetable)[len(timetable) // 2]} ms, "
                      f"blocked share {blocked_share(rows):.0%} (limit {MAX_BLOCKED_SHARE:.0%})"]
    first_bad = next((r for r in rows if r["result"] in (BLOCKED, ERROR)), None)
    if first_bad:
        lines += ["", "First blocked or failed call:", "", "```",
                  f"{first_bad['step']} {first_bad['label']} [{first_bad['ua']}] "
                  f"HTTP {first_bad['status']} {first_bad.get('headers', '')}",
                  (first_bad.get("note") or "")[:200], "```"]
    seen = sorted({c for r in rows for c in r.get("cookies", [])})
    if seen:
        lines += ["", f"Cookies set (names only): {', '.join(seen)}"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scale", choices=["sample", "full"], default="sample")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between requests")
    parser.add_argument("--out", help="write every result as JSON")
    args = parser.parse_args()

    rows, api_url = run_probe(args.scale, args.delay, date.today())
    report = markdown_report(rows, api_url, args.scale)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"api_url": api_url, "rows": rows}, handle, indent=1)
    failed = api_url is None or blocked_share(rows) > MAX_BLOCKED_SHARE
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
