from datetime import date, datetime, timezone

from scraper import storage

DAY = date(2026, 11, 3)


def at(day, hour=5, minute=17):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


def fare(price, origin="BER", destination="BGY", departure="2026-12-06", day=DAY, source="ryanair"):
    return {
        "snapshot_date": day.isoformat(),
        "source": source,
        "origin": origin,
        "destination": destination,
        "departure_date": departure,
        "departure_time": "07:50",
        "airline": "Ryanair",
        "flight_number": "FR2670",
        "stops": 0,
        "price": price,
        "currency": "EUR",
    }


def test_fares_round_trip_to_a_path_named_by_run(tmp_path):
    path = storage.write_fares(tmp_path, "ryanair", at(DAY), [fare(17.99)])
    assert path == tmp_path / "fares" / "ryanair" / "2026" / "2026-11-03T0517Z.csv.gz"
    rows = list(storage.read_fare_file(path))
    assert rows[0]["destination"] == "BGY"
    assert rows[0]["price"] == "17.99"
    assert rows[0]["snapshot_at"] == "2026-11-03T05:17:00Z"
    assert list(rows[0]) == storage.FARE_COLUMNS


def test_later_run_on_the_same_day_keeps_the_earlier_one(tmp_path):
    morning = storage.write_fares(tmp_path, "ryanair", at(DAY), [fare(10)])
    evening = storage.write_fares(tmp_path, "ryanair", at(DAY, 21), [fare(99)])
    assert morning != evening
    assert next(storage.read_fare_file(morning))["price"] == "10"
    assert storage.latest_fare_path(tmp_path, "ryanair", DAY) == evening
    assert storage.latest_fare_path(tmp_path, "ryanair", date(2026, 11, 4)) is None
    assert storage.latest_fare_path(tmp_path, "google_flights", DAY) is None


def test_itineraries_are_stored_apart_from_fares(tmp_path):
    row = {key: fare(10)[key] for key in storage.ITINERARY_COLUMNS if key != "snapshot_at"}
    path = storage.write_itineraries(tmp_path, "google_flights", at(DAY), [row])
    assert path == tmp_path / "itineraries" / "google_flights" / "2026" / "2026-11-03T0517Z.csv.gz"
    assert storage.fare_files(tmp_path) == []
    assert next(storage.read_fare_file(path))["snapshot_at"] == "2026-11-03T05:17:00Z"


def test_summary_uses_the_last_run_of_each_day(tmp_path):
    storage.write_fares(tmp_path, "google_flights", at(DAY), [fare(10), fare(20), fare(30)])
    storage.write_fares(tmp_path, "google_flights", at(DAY, 21), [fare(90)])
    lines = storage.rebuild_summary(tmp_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("2026-11-03,ryanair,1,90.0,")


def test_a_file_from_before_runs_had_times_still_counts(tmp_path):
    legacy = tmp_path / "fares" / "ryanair" / "2026" / "2026-11-03.csv.gz"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(storage.write_fares(tmp_path, "ryanair", at(DAY), [fare(10)]).read_bytes())
    assert storage.path_label(legacy) == "2026-11-03"
    assert storage.latest_fare_path(tmp_path, "ryanair", DAY).name == "2026-11-03T0517Z.csv.gz"
    storage.fare_path(tmp_path, "ryanair", at(DAY)).unlink()
    assert storage.latest_fare_path(tmp_path, "ryanair", DAY) == legacy


def test_same_minute_rerun_overwrites_with_identical_bytes(tmp_path):
    first = storage.write_fares(tmp_path, "ryanair", at(DAY), [fare(10), fare(20)]).read_bytes()
    second_path = storage.write_fares(tmp_path, "ryanair", at(DAY), [fare(10), fare(20)])
    assert second_path.read_bytes() == first
    assert len(storage.fare_files(tmp_path)) == 1
    assert not list(tmp_path.rglob("*.partial"))


def test_summary_quartiles():
    summary = storage.summarize([{**fare(p), "price": str(p)} for p in (10, 20, 30, 40, 50)])
    assert summary == {
        "snapshot_date": "2026-11-03",
        "source": "ryanair",
        "fares": 5,
        "min": 10.0,
        "p25": 20.0,
        "median": 30.0,
        "p75": 40.0,
    }


def test_summary_of_a_single_fare():
    summary = storage.summarize([{**fare(10), "price": "10"}])
    assert (summary["fares"], summary["p25"], summary["median"], summary["p75"]) == (1, 10, 10, 10)


def test_summary_survives_unusable_prices(tmp_path):
    good_and_bad = [fare(10), fare("abc"), fare(""), fare("nan"), fare(-5), fare(30)]
    storage.write_fares(tmp_path, "ryanair", at(DAY), good_and_bad)
    lines = storage.rebuild_summary(tmp_path).read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith("2026-11-03,ryanair,2,10.0,")


def test_summary_skips_a_day_with_no_usable_prices(tmp_path):
    storage.write_fares(tmp_path, "ryanair", at(DAY), [fare("abc")])
    lines = storage.rebuild_summary(tmp_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_summary_has_one_row_per_day_and_source(tmp_path):
    storage.write_fares(tmp_path, "ryanair", at(DAY), [fare(10), fare(30)])
    storage.write_fares(tmp_path, "google_flights", at(DAY), [fare(99, source="google_flights")])
    later = date(2026, 11, 4)
    storage.write_fares(tmp_path, "ryanair", at(later), [fare(50, day=later)])
    storage.write_fares(tmp_path, "ryanair", at(later, 21), [fare(50, day=later)])

    lines = storage.rebuild_summary(tmp_path).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "snapshot_date,source,fares,min,p25,median,p75"
    assert [line.split(",")[:3] for line in lines[1:]] == [
        ["2026-11-03", "google_flights", "1"],
        ["2026-11-03", "ryanair", "2"],
        ["2026-11-04", "ryanair", "1"],
    ]


def test_route_rows_filters_and_sorts(tmp_path):
    later = date(2026, 11, 4)
    storage.write_fares(tmp_path, "ryanair", at(later), [fare(50, day=later)])
    storage.write_fares(
        tmp_path,
        "ryanair",
        at(DAY),
        [fare(20, departure="2026-12-13"), fare(10), fare(5, destination="AGP")],
    )
    rows = storage.route_rows(tmp_path, "BER", "BGY")
    assert [(r["snapshot_date"], r["departure_date"]) for r in rows] == [
        ("2026-11-03", "2026-12-06"),
        ("2026-11-03", "2026-12-13"),
        ("2026-11-04", "2026-12-06"),
    ]


def test_route_rows_keep_each_run_in_time_order(tmp_path):
    storage.write_fares(tmp_path, "google_flights", at(DAY, 21), [fare(30)])
    storage.write_fares(tmp_path, "google_flights", at(DAY, 5), [fare(10)])
    storage.write_fares(tmp_path, "google_flights", at(DAY, 13), [fare(20)])
    rows = storage.route_rows(tmp_path, "BER", "BGY")
    assert [row["price"] for row in rows] == ["10", "20", "30"]
