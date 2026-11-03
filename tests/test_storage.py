from datetime import date

from scraper import storage

DAY = date(2026, 11, 3)


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


def test_fares_round_trip_to_a_dated_path(tmp_path):
    path = storage.write_fares(tmp_path, "ryanair", DAY, [fare(17.99)])
    assert path == tmp_path / "fares" / "ryanair" / "2026" / "2026-11-03.csv.gz"
    rows = list(storage.read_fare_file(path))
    assert rows[0]["destination"] == "BGY"
    assert rows[0]["price"] == "17.99"


def test_same_day_rerun_overwrites_with_identical_bytes(tmp_path):
    first = storage.write_fares(tmp_path, "ryanair", DAY, [fare(10), fare(20)]).read_bytes()
    second_path = storage.write_fares(tmp_path, "ryanair", DAY, [fare(10), fare(20)])
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


def test_summary_has_one_row_per_day_and_source(tmp_path):
    storage.write_fares(tmp_path, "ryanair", DAY, [fare(10), fare(30)])
    storage.write_fares(tmp_path, "google_flights", DAY, [fare(99, source="google_flights")])
    later = date(2026, 11, 4)
    storage.write_fares(tmp_path, "ryanair", later, [fare(50, day=later)])

    lines = storage.rebuild_summary(tmp_path).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "snapshot_date,source,fares,min,p25,median,p75"
    assert [line.split(",")[:3] for line in lines[1:]] == [
        ["2026-11-03", "google_flights", "1"],
        ["2026-11-03", "ryanair", "2"],
        ["2026-11-04", "ryanair", "1"],
    ]


def test_route_rows_filters_and_sorts(tmp_path):
    later = date(2026, 11, 4)
    storage.write_fares(tmp_path, "ryanair", later, [fare(50, day=later)])
    storage.write_fares(
        tmp_path,
        "ryanair",
        DAY,
        [fare(20, departure="2026-12-13"), fare(10), fare(5, destination="AGP")],
    )
    rows = storage.route_rows(tmp_path, "BER", "BGY")
    assert [(r["snapshot_date"], r["departure_date"]) for r in rows] == [
        ("2026-11-03", "2026-12-06"),
        ("2026-11-03", "2026-12-13"),
        ("2026-11-04", "2026-12-06"),
    ]
