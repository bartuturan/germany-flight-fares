import tomllib
from datetime import date, timedelta
from pathlib import Path

import pytest

from scraper import quality, storage

DAY = date(2026, 11, 3)
CONFIG_PATH = Path(__file__).parent.parent / "config.toml"


@pytest.fixture
def config():
    with open(CONFIG_PATH, "rb") as handle:
        return tomllib.load(handle)


def statuses(results):
    return {row["check"]: row["status"] for row in results}


def by_check(results, name):
    return next(row for row in results if row["check"] == name)


def fare(origin, destination, departure, price=100, source="google_flights", day=DAY, **overrides):
    row = {
        "snapshot_date": day.isoformat(),
        "source": source,
        "origin": origin,
        "destination": destination,
        "departure_date": departure.isoformat(),
        "departure_time": "07:50",
        "airline": "Lufthansa",
        "flight_number": "",
        "stops": "0",
        "price": str(price),
        "currency": "EUR",
    }
    return {**row, **overrides}


def google_day(config, day=DAY, price=100, keep=None):
    rows = [
        fare(*route.split("-"), day + timedelta(days=lead), price, day=day)
        for route in config["google_flights"]["routes"]
        for lead in config["google_flights"]["lead_days"]
    ]
    return rows[:keep] if keep is not None else rows


def ryanair_day(config, day=DAY, price=40):
    return [
        fare(
            airport,
            "BGY",
            day + timedelta(days=1 + 7 * week),
            price,
            source="ryanair",
            day=day,
            airline="Ryanair",
            flight_number=f"FR{week}",
        )
        for airport in config["ryanair"]["airports"]
        for week in range(config["ryanair"]["weeks_ahead"])
    ]


def history(count, fares, median, source="google_flights", end=DAY):
    """Summary rows for the `count` days before `end`, oldest first."""
    return [
        {
            "snapshot_date": (end - timedelta(days=back)).isoformat(),
            "source": source,
            "fares": str(fares),
            "median": str(median),
        }
        for back in range(count, 0, -1)
    ]


def test_clean_day_passes(config):
    results = quality.check_fares(
        "google_flights", DAY, google_day(config), config, history(5, 80, 100)
    )
    assert set(statuses(results).values()) == {quality.PASS}


def test_clean_ryanair_day_passes(config):
    results = quality.check_fares(
        "ryanair", DAY, ryanair_day(config), config, history(5, 364, 40, source="ryanair")
    )
    assert set(statuses(results).values()) == {quality.PASS}


def test_no_fares_fails_and_stops(config):
    results = quality.check_fares("ryanair", DAY, [], config, [])
    assert statuses(results) == {"data_present": quality.FAIL}


def test_changed_columns_fail(config):
    rows = [{"origin": "BER", "price": "10"}]
    assert statuses(quality.check_fares("ryanair", DAY, rows, config, []))["columns"] == quality.FAIL


def test_losing_most_google_searches_fails_coverage(config):
    # The first deployed version kept 49 of 80 searches and still reported success.
    results = quality.check_fares("google_flights", DAY, google_day(config, keep=49), config, [])
    assert by_check(results, "coverage")["status"] == quality.FAIL
    assert "49 of 80" in by_check(results, "coverage")["detail"]


def test_small_google_gap_passes_and_names_what_is_missing(config):
    results = quality.check_fares("google_flights", DAY, google_day(config, keep=78), config, [])
    coverage = by_check(results, "coverage")
    assert coverage["status"] == quality.PASS
    assert "FRA-SIN-2027-02-01" in coverage["detail"]


def test_losing_one_ryanair_airport_warns(config):
    rows = [row for row in ryanair_day(config) if row["origin"] != "BER"]
    results = quality.check_fares("ryanair", DAY, rows, config, [])
    assert by_check(results, "coverage")["status"] == quality.WARN


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"price": "0"}, "bad_price"),
        ({"price": "abc"}, "bad_price"),
        ({"price": "nan"}, "bad_price"),
        ({"price": "inf"}, "bad_price"),
        ({"price": ""}, "missing_price"),
        ({"currency": "USD"}, "wrong_currency"),
        ({"origin": "ber"}, "bad_airport_code"),
        ({"snapshot_date": "2026-11-02"}, "wrong_snapshot_date"),
        ({"departure_date": "soon"}, "bad_departure_date"),
        ({"departure_date": "2026-11-03"}, "unexpected_departure_or_route"),
        ({"destination": "XXX"}, "unexpected_departure_or_route"),
    ],
)
def test_bad_row_is_named_and_warned(config, overrides, reason):
    rows = google_day(config)
    rows[0] = {**rows[0], **overrides}
    results = quality.check_fares("google_flights", DAY, rows, config, history(5, 80, 100))
    invalid = by_check(results, "invalid_rows")
    assert invalid["status"] in (quality.WARN, quality.FAIL)
    assert invalid["detail"] == f"{reason}=1"


def test_day_with_no_usable_prices_is_still_recorded(tmp_path, config):
    rows = [{**row, "price": "abc"} for row in google_day(config)]
    storage.write_fares(tmp_path, "google_flights", DAY, rows)
    storage.rebuild_summary(tmp_path)
    results = quality.check_and_record(tmp_path, config, DAY, ["google_flights"])
    assert by_check(results, "invalid_rows")["status"] == quality.FAIL
    assert by_check(results, "coverage")["status"] == quality.FAIL
    assert not [row for row in results if row["check"] == "check_error"]


def test_one_bad_row_is_a_warning_and_many_are_a_failure(config):
    rows = ryanair_day(config)
    one_bad = [{**rows[0], "currency": "USD"}, *rows[1:]]
    assert by_check(
        quality.check_fares("ryanair", DAY, one_bad, config, []), "invalid_rows"
    )["status"] == quality.WARN

    all_bad = [{**row, "currency": "USD"} for row in rows]
    results = quality.check_fares("ryanair", DAY, all_bad, config, [])
    assert by_check(results, "invalid_rows")["status"] == quality.FAIL
    assert by_check(results, "coverage")["status"] == quality.FAIL


def test_ryanair_departure_past_the_last_window_is_invalid(config):
    rows = ryanair_day(config)
    rows[0] = {**rows[0], "departure_date": (DAY + timedelta(days=183)).isoformat()}
    assert "unexpected_departure_or_route" in by_check(
        quality.check_fares("ryanair", DAY, rows, config, []), "invalid_rows"
    )["detail"]


def test_duplicates_are_caught(config):
    rows = ryanair_day(config)
    results = quality.check_fares("ryanair", DAY, rows + rows[:1], config, [])
    assert by_check(results, "duplicates")["status"] == quality.WARN
    assert by_check(results, "duplicates")["value"] == 1


def test_implausible_price_is_caught(config):
    rows = ryanair_day(config)
    rows[0] = {**rows[0], "price": "5000"}
    results = quality.check_fares("ryanair", DAY, rows, config, [])
    assert by_check(results, "price_range")["status"] == quality.WARN


def test_history_checks_wait_for_enough_snapshots(config):
    results = quality.check_fares("google_flights", DAY, google_day(config), config, history(2, 80, 100))
    assert by_check(results, "row_count")["status"] == quality.SKIP
    assert by_check(results, "median_price")["status"] == quality.SKIP


@pytest.mark.parametrize(
    "median, expected",
    [(100, quality.PASS), (130, quality.WARN), (70, quality.WARN), (200, quality.FAIL), (40, quality.FAIL)],
)
def test_median_price_shift_in_either_direction(config, median, expected):
    results = quality.check_fares(
        "google_flights", DAY, google_day(config, price=median), config, history(5, 80, 100)
    )
    assert by_check(results, "median_price")["status"] == expected


def test_row_count_drop_against_history(config):
    results = quality.check_fares(
        "google_flights", DAY, google_day(config, keep=38), config, history(5, 80, 100)
    )
    assert by_check(results, "row_count")["status"] == quality.FAIL


def test_baseline_uses_only_recent_snapshots(config):
    prior = history(20, 40, 100)
    prior[-14:] = history(14, 80, 100)
    results = quality.check_fares("google_flights", DAY, google_day(config), config, prior)
    assert by_check(results, "row_count")["status"] == quality.PASS


def test_missed_days_warn(config):
    prior = history(1, 80, 100, end=DAY - timedelta(days=2))
    results = quality.check_fares("google_flights", DAY, google_day(config), config, prior)
    gap = by_check(results, "snapshot_gap")
    assert (gap["status"], gap["value"]) == (quality.WARN, 2)


def index_rows(config, last="2026-09", start_year=2026):
    last_year, last_month = map(int, last.split("-"))
    rows = []
    for code in config["eurostat"]["coicop"]:
        for unit in config["eurostat"]["units"]:
            for month in range(1, last_month + 1):
                rows.append(
                    {
                        "period": f"{last_year}-{month:02d}",
                        "coicop": code,
                        "unit": unit,
                        "value": str(100 + month),
                    }
                )
    return rows


def test_clean_index_passes(config):
    results = quality.check_index(DAY, index_rows(config), config, 54)
    assert set(statuses(results).values()) == {quality.PASS}


def test_missing_index_fails(config):
    assert statuses(quality.check_index(DAY, [], config, None)) == {"data_present": quality.FAIL}


def test_missing_series_fails(config):
    rows = [row for row in index_rows(config) if row["coicop"] != "CP07332"]
    assert statuses(quality.check_index(DAY, rows, config, None))["series_present"] == quality.FAIL


def test_index_history_shrinking_fails(config):
    assert statuses(quality.check_index(DAY, index_rows(config), config, 999))["row_count"] == quality.FAIL


def test_gap_in_index_months_warns(config):
    rows = [row for row in index_rows(config) if row["period"] != "2026-05"]
    results = quality.check_index(DAY, rows, config, None)
    assert by_check(results, "missing_months")["status"] == quality.WARN
    assert by_check(results, "missing_months")["value"] == 6


@pytest.mark.parametrize(
    "last, expected",
    [("2026-10", quality.PASS), ("2026-09", quality.PASS), ("2026-08", quality.WARN), ("2026-07", quality.FAIL)],
)
def test_stale_index(config, last, expected):
    results = quality.check_index(DAY, index_rows(config, last=last), config, None)
    assert by_check(results, "latest_period")["status"] == expected


def test_index_age_across_a_year_boundary(config):
    results = quality.check_index(date(2027, 1, 20), index_rows(config, last="2026-12"), config, None)
    latest = by_check(results, "latest_period")
    assert (latest["status"], latest["value"], latest["detail"]) == (
        quality.PASS,
        1,
        "newest month is 2026-12",
    )


def test_large_index_jump_warns(config):
    rows = index_rows(config)
    rows[8] = {**rows[8], "value": "500"}
    assert statuses(quality.check_index(DAY, rows, config, None))["latest_change"] == quality.WARN


def test_invalid_index_value_fails(config):
    rows = index_rows(config)
    rows[3] = {**rows[3], "value": "-1"}
    assert statuses(quality.check_index(DAY, rows, config, None))["invalid_values"] == quality.FAIL


def write_day(tmp_path, config, day):
    storage.write_fares(tmp_path, "google_flights", day, google_day(config, day=day))
    storage.rebuild_summary(tmp_path)


def test_log_keeps_earlier_days_and_replaces_a_rerun(tmp_path, config):
    later = DAY + timedelta(days=1)
    write_day(tmp_path, config, DAY)
    quality.check_and_record(tmp_path, config, DAY, ["google_flights"])
    first_day_rows = storage.read_csv(quality.log_path(tmp_path))

    write_day(tmp_path, config, later)
    quality.check_and_record(tmp_path, config, later, ["google_flights"])
    quality.check_and_record(tmp_path, config, later, ["google_flights"])

    rows = storage.read_csv(quality.log_path(tmp_path))
    assert [r for r in rows if r["date"] == DAY.isoformat()] == first_day_rows
    checks = [r["check"] for r in rows if r["date"] == later.isoformat()]
    assert len(checks) == len(set(checks))


def test_rerun_of_one_source_leaves_the_others_in_the_log(tmp_path, config):
    write_day(tmp_path, config, DAY)
    storage.write_fares(tmp_path, "ryanair", DAY, ryanair_day(config))
    quality.check_and_record(tmp_path, config, DAY, ["google_flights", "ryanair"])
    quality.check_and_record(tmp_path, config, DAY, ["google_flights"])
    assert {r["source"] for r in storage.read_csv(quality.log_path(tmp_path))} == {
        "google_flights",
        "ryanair",
    }


def test_scrape_error_is_recorded_with_its_reason(tmp_path, config):
    results = quality.check_and_record(
        tmp_path, config, DAY, ["google_flights"], {"google_flights": "Google returned its consent page"}
    )
    assert by_check(results, "scrape")["status"] == quality.FAIL
    assert "consent" in by_check(results, "scrape")["detail"]
    assert by_check(results, "data_present")["status"] == quality.FAIL


def test_second_day_compares_with_the_first(tmp_path, config):
    write_day(tmp_path, config, DAY)
    quality.check_and_record(tmp_path, config, DAY, ["google_flights"])
    later = DAY + timedelta(days=3)
    write_day(tmp_path, config, later)
    results = quality.check_and_record(tmp_path, config, later, ["google_flights"])
    assert by_check(results, "snapshot_gap")["value"] == 2


def test_index_row_count_compares_with_the_last_logged_count(tmp_path, config):
    storage.write_index(tmp_path, index_rows(config))
    quality.check_and_record(tmp_path, config, DAY, ["eurostat"])
    storage.write_index(tmp_path, index_rows(config)[1:])
    results = quality.check_and_record(tmp_path, config, DAY + timedelta(days=1), ["eurostat"])
    assert by_check(results, "row_count")["status"] == quality.FAIL


def test_damaged_file_is_recorded_and_other_sources_still_run(tmp_path, config):
    path = storage.fare_path(tmp_path, "ryanair", DAY)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not gzip")
    storage.write_fares(tmp_path, "google_flights", DAY, google_day(config))
    results = quality.check_and_record(tmp_path, config, DAY, ["ryanair", "google_flights"])
    assert {r["source"]: r["status"] for r in results if r["check"] == "check_error"} == {
        "ryanair": quality.FAIL
    }
    assert any(r["source"] == "google_flights" and r["check"] == "coverage" for r in results)


def test_report_shows_latest_detail_and_daily_history(tmp_path, config):
    write_day(tmp_path, config, DAY)
    quality.check_and_record(tmp_path, config, DAY, ["google_flights"])
    later = DAY + timedelta(days=1)
    storage.write_fares(tmp_path, "google_flights", later, google_day(config, day=later, keep=49))
    quality.check_and_record(tmp_path, config, later, ["google_flights"])

    report = quality.report_path(tmp_path).read_text(encoding="utf-8")
    assert "Latest check: 2026-11-04" in report
    assert "49 of 80 found" in report
    assert "| 2026-11-04 | fail (0 warn, 1 fail) |" in report
    assert "| 2026-11-03 | pass |" in report


def test_report_goes_to_the_github_step_summary(tmp_path, config, monkeypatch):
    summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    write_day(tmp_path, config, DAY)
    quality.check_and_record(tmp_path, config, DAY, ["google_flights"])
    assert "# Data quality" in summary.read_text(encoding="utf-8")
