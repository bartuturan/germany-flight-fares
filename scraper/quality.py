"""Check each run's data after scraping, and keep a running log of the results."""

import logging
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from . import storage
from .common import tracked_departures

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"
LOG_COLUMNS = ["date", "source", "check", "status", "value", "expected", "detail", "checked_at", "run"]
FARE_SOURCES = ["ryanair", "google_flights"]
REQUIRED_FARE_FIELDS = ["origin", "destination", "departure_date", "airline", "price", "currency"]
AIRPORT_CODE = re.compile(r"^[A-Z]{3}$")
SAMPLE_SIZE = 5

log = logging.getLogger(__name__)


def log_path(data_dir):
    return Path(data_dir) / "quality" / "quality_log.csv"


def report_path(data_dir):
    return Path(data_dir) / "quality" / "quality_report.md"


def _result(check, status, value="", expected="", detail=""):
    return {"check": check, "status": status, "value": value, "expected": expected, "detail": detail}


def _change_result(check, value, baseline, warn_at, fail_at):
    """Compare a value with its baseline by relative change, in either direction."""
    change = value / baseline - 1
    status = FAIL if abs(change) >= fail_at else WARN if abs(change) >= warn_at else PASS
    return _result(
        check,
        status,
        value,
        f"within {warn_at:.0%} of {baseline:g}",
        f"{change:+.1%} against the trailing median",
    )


def _bad_rows_result(check, bad, total, fail_share, detail=""):
    """Any bad row is a warning, and more than a small share of them is a failure."""
    status = PASS if not bad else FAIL if bad / total > fail_share else WARN
    return _result(check, status, bad, "0", detail)


def _sample(values):
    values = sorted(values, key=str)
    text = ", ".join("-".join(str(part) for part in value) for value in values[:SAMPLE_SIZE])
    return f"{text}, +{len(values) - SAMPLE_SIZE} more" if len(values) > SAMPLE_SIZE else text


def _expected_keys(source, source_config, day):
    """What a complete run contains: each airport and week, or each tracked departure.

    Ryanair is counted by week because small airports have no flights on many days.
    """
    if source == "ryanair":
        return {
            (airport, week)
            for airport in source_config["airports"]
            for week in range(_ryanair_week(source_config["days_ahead"]) + 1)
        }
    return {
        (*route.split("-"), departure.isoformat())
        for route in source_config["routes"]
        for departure in tracked_departures(
            route, day, source_config["min_lead_days"], source_config["max_lead_days"]
        )
    }


def _ryanair_week(days_ahead):
    return (days_ahead - 1) // 7


def _row_key(source, row, day, source_config):
    if source == "ryanair":
        days_ahead = (date.fromisoformat(row["departure_date"]) - day).days
        if not 1 <= days_ahead <= source_config["days_ahead"]:
            return None
        return (row["origin"], _ryanair_week(days_ahead))
    return (row["origin"], row["destination"], row["departure_date"])


def _row_problem(source, row, day, source_config, expected):
    for field in REQUIRED_FARE_FIELDS:
        if not row[field]:
            return f"missing_{field}"
    if row["snapshot_date"] != day.isoformat():
        return "wrong_snapshot_date"
    if not AIRPORT_CODE.match(row["origin"]) or not AIRPORT_CODE.match(row["destination"]):
        return "bad_airport_code"
    if storage.parse_price(row["price"]) is None:
        return "bad_price"
    if row["currency"] != source_config["currency"]:
        return "wrong_currency"
    try:
        date.fromisoformat(row["departure_date"])
    except ValueError:
        return "bad_departure_date"
    return None if _row_key(source, row, day, source_config) in expected else "unexpected_departure_or_route"


def _history_results(rows, limits, prior):
    """Compare today with recent snapshots of the same source, once there are enough."""
    recent = prior[-limits["history_days"] :]
    summary = storage.summarize(rows)
    median = summary["median"] if summary else ""
    if len(recent) < limits["min_history"]:
        detail = f"{len(recent)} earlier snapshots, need {limits['min_history']}"
        return [
            _result("row_count", SKIP, len(rows), detail=detail),
            _result("median_price", SKIP, median, detail=detail),
        ]
    results = [
        _change_result(
            "row_count",
            len(rows),
            statistics.median(int(row["fares"]) for row in recent),
            limits["row_count_warn_change"],
            limits["row_count_fail_change"],
        )
    ]
    if summary:
        results.append(
            _change_result(
                "median_price",
                median,
                statistics.median(float(row["median"]) for row in recent),
                limits["median_price_warn_change"],
                limits["median_price_fail_change"],
            )
        )
    return results


def _gap_result(prior, day):
    if not prior:
        return _result("snapshot_gap", SKIP, detail="no earlier snapshot")
    previous = date.fromisoformat(prior[-1]["snapshot_date"])
    missed = (day - previous).days - 1
    detail = f"last snapshot {previous}" if missed else ""
    return _result("snapshot_gap", WARN if missed else PASS, missed, "0", detail)


def check_fares(source, day, rows, config, prior):
    """Check one run's fares. `prior` is that source's earlier summary rows, oldest first."""
    if not rows:
        return [_result("data_present", FAIL, 0, ">0", "no fares for this date")]
    results = [_result("data_present", PASS, len(rows), ">0")]

    if list(rows[0]) not in (storage.FARE_COLUMNS, storage.LEGACY_FARE_COLUMNS):
        return [*results, _result("columns", FAIL, detail=f"found {list(rows[0])}")]
    results.append(_result("columns", PASS))

    limits = config["quality"]
    source_limits = limits[source]
    source_config = config[source]
    expected = _expected_keys(source, source_config, day)
    fail_share = limits["bad_rows_fail_share"]

    problems = Counter()
    valid = []
    for row in rows:
        problem = _row_problem(source, row, day, source_config, expected)
        if problem:
            problems[problem] += 1
        else:
            valid.append(row)
    detail = ", ".join(f"{name}={count}" for name, count in sorted(problems.items()))
    results.append(_bad_rows_result("invalid_rows", len(rows) - len(valid), len(rows), fail_share, detail))

    found = {_row_key(source, row, day, source_config) for row in valid}
    coverage = len(found & expected) / len(expected)
    status = (
        FAIL
        if coverage < source_limits["coverage_fail_below"]
        else WARN
        if coverage < source_limits["coverage_warn_below"]
        else PASS
    )
    missing = expected - found
    results.append(
        _result(
            "coverage",
            status,
            round(coverage, 3),
            f">={source_limits['coverage_warn_below']}",
            f"{len(expected) - len(missing)} of {len(expected)} found"
            + (f"; missing {_sample(missing)}" if missing else ""),
        )
    )

    identities = Counter(
        (r["origin"], r["destination"], r["departure_date"], r["departure_time"], r["flight_number"])
        for r in rows
    )
    duplicates = sum(count - 1 for count in identities.values())
    results.append(_bad_rows_result("duplicates", duplicates, len(rows), fail_share))

    if valid:
        low, high = source_limits["price_min"], source_limits["price_max"]
        prices = [storage.parse_price(row["price"]) for row in valid]
        outliers = [price for price in prices if not low <= price <= high]
        detail = f"min {min(prices):g}, max {max(prices):g}; allowed {low:g} to {high:g}"
        results.append(_bad_rows_result("price_range", len(outliers), len(valid), fail_share, detail))

    results += _history_results(rows, limits, prior)
    results.append(_gap_result(prior, day))
    return results


def _month_number(period):
    year, month = period.split("-")
    return int(year) * 12 + int(month)


def check_index(day, rows, config, prior_row_count):
    """Check the Eurostat index. `prior_row_count` comes from the last logged check, if any."""
    if not rows:
        return [_result("data_present", FAIL, 0, ">0", "index file is missing or empty")]
    results = [_result("data_present", PASS, len(rows), ">0")]
    limits = config["quality"]["eurostat"]

    series = defaultdict(list)
    for row in rows:
        series[row["coicop"], row["unit"]].append(row)

    wanted = {(code, unit) for code in config["eurostat"]["coicop"] for unit in config["eurostat"]["units"]}
    absent = wanted - set(series)
    results.append(
        _result(
            "series_present",
            FAIL if absent else PASS,
            len(wanted) - len(absent),
            str(len(wanted)),
            f"missing {_sample(absent)}" if absent else "",
        )
    )

    if prior_row_count is None:
        results.append(_result("row_count", SKIP, len(rows), detail="no earlier check"))
    else:
        results.append(
            _result(
                "row_count",
                FAIL if len(rows) < prior_row_count else PASS,
                len(rows),
                f">={prior_row_count}",
                "history shrank since the last check" if len(rows) < prior_row_count else "",
            )
        )

    gaps = 0
    invalid = 0
    jumps = []
    for key, points in series.items():
        points = sorted(points, key=lambda point: point["period"])
        months = [_month_number(point["period"]) for point in points]
        gaps += months[-1] - months[0] + 1 - len(months)
        values = [float(point["value"]) for point in points]
        invalid += sum(value <= 0 for value in values)
        if len(values) > 1 and values[-2] > 0:
            jumps.append((abs(values[-1] / values[-2] - 1), key))

    results.append(_result("missing_months", WARN if gaps else PASS, gaps, "0"))
    results.append(_result("invalid_values", FAIL if invalid else PASS, invalid, "0"))

    newest = max(row["period"] for row in rows)
    age = _month_number(day.strftime("%Y-%m")) - _month_number(newest)
    allowed = limits["max_age_months_warn"]
    status = FAIL if age > allowed + 1 else WARN if age > allowed else PASS
    results.append(
        _result("latest_period", status, age, f"<={allowed} months old", f"newest month is {newest}")
    )

    if jumps:
        largest, key = max(jumps)
        results.append(
            _result(
                "latest_change",
                WARN if largest >= limits["monthly_change_warn"] else PASS,
                round(largest, 3),
                f"<{limits['monthly_change_warn']}",
                f"largest latest-month move, {key[0]} {key[1]}",
            )
        )
    return results


def _prior_summaries(data_dir, source, day):
    rows = storage.read_csv(storage.summary_path(data_dir))
    earlier = [r for r in rows if r["source"] == source and r["snapshot_date"] < day.isoformat()]
    return sorted(earlier, key=lambda row: row["snapshot_date"])


def _prior_index_count(log_rows, day):
    counts = [
        row
        for row in log_rows
        if row["source"] == "eurostat" and row["check"] == "row_count" and row["date"] < day.isoformat()
    ]
    return int(max(counts, key=lambda row: row["date"])["value"]) if counts else None


def _fares_to_check(data_dir, source, day, run_at):
    """This run's file, which a failed scrape won't have, or the day's last run if none is given."""
    if run_at:
        return storage.fare_path(data_dir, source, run_at)
    return storage.latest_fare_path(data_dir, source, day)


def _check_source(data_dir, config, day, source, log_rows, run_at):
    if source == "eurostat":
        rows = storage.read_csv(storage.index_path(data_dir))
        return check_index(day, rows, config, _prior_index_count(log_rows, day))
    path = _fares_to_check(data_dir, source, day, run_at)
    rows = list(storage.read_fare_file(path)) if path and path.exists() else []
    return check_fares(source, day, rows, config, _prior_summaries(data_dir, source, day))


def _run_of(data_dir, source, day, run_at):
    if run_at:
        return storage.run_label(run_at)
    path = None if source == "eurostat" else storage.latest_fare_path(data_dir, source, day)
    return storage.path_label(path) if path else day.isoformat()


def _logged_run(row):
    """Entries logged before runs were tracked count as one run for their date."""
    return row.get("run") or row["date"]


def _worst(statuses):
    for status in (FAIL, WARN, PASS):
        if status in statuses:
            return status
    return SKIP


def render_report(log_rows, report_days):
    """Results of each source's latest run, then a day-by-day history covering every run."""
    if not log_rows:
        return "# Data quality\n\nNo checks have run yet.\n"
    sources = sorted({row["source"] for row in log_rows})
    by_day = defaultdict(lambda: defaultdict(list))
    for row in log_rows:
        by_day[row["date"]][row["source"]].append(row)
    days = sorted(by_day, reverse=True)

    lines = ["# Data quality", "", f"Latest check: {days[0]}", ""]
    latest = by_day[days[0]]
    lines += ["| Source | Check | Status | Value | Expected | Detail |", "|---|---|---|---|---|---|"]
    for source in sources:
        rows = latest.get(source, [])
        last_run = max((_logged_run(row) for row in rows), default=None)
        for row in rows:
            if _logged_run(row) != last_run:
                continue
            cells = [source, row["check"], row["status"], row["value"], row["expected"], row["detail"]]
            lines.append("| " + " | ".join(str(c).replace("|", "/") for c in cells) + " |")

    lines += ["", f"## Last {report_days} days", "", "Each cell is the worst result that day, with warning and failure counts.", ""]
    lines += ["| Date | " + " | ".join(sources) + " |", "|---|" + "---|" * len(sources)]
    for day in days[:report_days]:
        cells = []
        for source in sources:
            statuses = [row["status"] for row in by_day[day].get(source, [])]
            if not statuses:
                cells.append("not checked")
                continue
            cell = _worst(statuses)
            if cell in (WARN, FAIL):
                cell += f" ({statuses.count(WARN)} warn, {statuses.count(FAIL)} fail)"
            cells.append(cell)
        lines.append(f"| {day} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def check_and_record(data_dir, config, day, sources, scrape_errors=None, run_at=None):
    """Check one run per source, replace that run's log entries, rebuild the report.

    Without `run_at`, this re-checks the last run of the day.
    """
    scrape_errors = scrape_errors or {}
    log_rows = storage.read_csv(log_path(data_dir))
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    new_rows = []
    for source in sources:
        results = []
        if source in scrape_errors:
            results.append(_result("scrape", FAIL, detail=scrape_errors[source]))
        try:
            results += _check_source(data_dir, config, day, source, log_rows, run_at)
        except Exception as exc:  # a damaged file should be recorded, not stop the other checks
            results.append(_result("check_error", FAIL, detail=repr(exc)))
        new_rows += [
            {
                "date": day.isoformat(),
                "source": source,
                **result,
                "checked_at": checked_at,
                "run": _run_of(data_dir, source, day, run_at),
            }
            for result in results
        ]

    replaced = {(row["source"], _logged_run(row)) for row in new_rows}
    kept = [row for row in log_rows if (row["source"], _logged_run(row)) not in replaced]
    all_rows = sorted(kept + new_rows, key=lambda row: (row["date"], row["source"], _logged_run(row)))
    storage.write_csv(log_path(data_dir), all_rows, LOG_COLUMNS)

    report = render_report(all_rows, config["quality"]["report_days"])
    report_file = report_path(data_dir)
    report_file.write_text(report, encoding="utf-8", newline="\n")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write(report)

    for row in new_rows:
        if row["status"] in (WARN, FAIL):
            level = logging.ERROR if row["status"] == FAIL else logging.WARNING
            log.log(level, "quality %s %s: %s %s", row["source"], row["check"], row["value"], row["detail"])
    return new_rows
