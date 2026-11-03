from argparse import Namespace
from datetime import datetime, timezone

import pytest

from scraper import __main__ as cli
from scraper import storage
from scraper.common import SourceFailed

CONFIG = {
    "eurostat": {"enabled": True},
    "ryanair": {"enabled": True},
    "google_flights": {"enabled": True},
}


def fare(day):
    return {
        "snapshot_date": day.isoformat(),
        "source": "ryanair",
        "origin": "BER",
        "destination": "BGY",
        "departure_date": "2026-12-06",
        "departure_time": "07:50",
        "airline": "Ryanair",
        "flight_number": "FR2670",
        "stops": 0,
        "price": 17.99,
        "currency": "EUR",
    }


def google_fares(config, today):
    itinerary = {
        key: value for key, value in fare(today).items() if key in storage.ITINERARY_COLUMNS
    }
    return [{**fare(today), "source": "google_flights"}], [itinerary, itinerary]


def blocked(config, today):
    raise SourceFailed("Google returned its consent page")


def stub_sources(monkeypatch, google=blocked, quality_results=()):
    calls = []

    def check_and_record(data_dir, config, day, sources, scrape_errors=None, run_at=None):
        calls.append((sources, scrape_errors))
        return list(quality_results)

    monkeypatch.setattr(cli.quality, "check_and_record", check_and_record)
    monkeypatch.setattr(
        cli.eurostat,
        "collect",
        lambda config: [{"period": "2026-09", "coicop": "CP0733", "unit": "I25", "value": 100.49}],
    )
    monkeypatch.setattr(cli.ryanair, "collect", lambda config, today: [fare(today)])
    monkeypatch.setattr(cli.google_flights, "collect", google)
    return calls


def test_one_failing_source_keeps_the_others_and_is_passed_to_the_checks(tmp_path, monkeypatch):
    calls = stub_sources(monkeypatch)
    cli.run(Namespace(source=None, data_dir=tmp_path), CONFIG)

    assert calls == [
        (
            ["eurostat", "ryanair", "google_flights"],
            {"google_flights": "Google returned its consent page"},
        )
    ]
    assert (tmp_path / "eurostat" / "germany_air_fare_index.csv").exists()
    today = datetime.now(timezone.utc).date()
    assert storage.latest_fare_path(tmp_path, "ryanair", today)
    assert not storage.latest_fare_path(tmp_path, "google_flights", today)
    assert not (tmp_path / "itineraries").exists()
    assert (tmp_path / "germany_fares_daily_summary.csv").exists()


def test_success_exits_cleanly_and_skips_disabled_sources(tmp_path, monkeypatch):
    calls = stub_sources(monkeypatch)
    config = {**CONFIG, "google_flights": {"enabled": False}}
    assert cli.run(Namespace(source=None, data_dir=tmp_path), config) == 0
    assert calls[0][0] == ["eurostat", "ryanair"]


def test_named_source_runs_and_checks_only_that_source(tmp_path, monkeypatch):
    calls = stub_sources(monkeypatch)
    assert cli.run(Namespace(source=["ryanair"], data_dir=tmp_path), CONFIG) == 0
    assert not (tmp_path / "eurostat").exists()
    assert calls[0][0] == ["ryanair"]


def test_failed_check_exits_with_an_error(tmp_path, monkeypatch):
    stub_sources(monkeypatch, quality_results=[{"status": "fail"}])
    assert cli.run(Namespace(source=["ryanair"], data_dir=tmp_path), CONFIG) == 1


def test_warning_alone_exits_cleanly(tmp_path, monkeypatch):
    stub_sources(monkeypatch, quality_results=[{"status": "warn"}, {"status": "skip"}])
    assert cli.run(Namespace(source=["ryanair"], data_dir=tmp_path), CONFIG) == 0


def test_check_command_does_not_scrape(tmp_path, monkeypatch):
    calls = stub_sources(monkeypatch, quality_results=[{"status": "fail"}])
    monkeypatch.setattr(cli.ryanair, "collect", lambda config, today: pytest.fail("scraped"))
    args = Namespace(source=["ryanair"], data_dir=tmp_path, date=None)
    assert cli.check(args, CONFIG) == 1
    assert calls[0] == (["ryanair"], None)


def test_export_writes_one_route(tmp_path, monkeypatch):
    stub_sources(monkeypatch)
    cli.run(Namespace(source=["ryanair"], data_dir=tmp_path), CONFIG)
    out = tmp_path / "route.csv"
    assert cli.export(Namespace(route="ber-bgy", data_dir=tmp_path, out=out)) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("snapshot_date,source,origin")
    assert len(lines) == 2


def test_google_writes_fares_and_itineraries_for_the_same_run(tmp_path, monkeypatch):
    stub_sources(monkeypatch, google=google_fares)
    assert cli.run(Namespace(source=["google_flights"], data_dir=tmp_path), CONFIG) == 0

    fares = next((tmp_path / "fares" / "google_flights").glob("*/*.csv.gz"))
    itineraries = next((tmp_path / "itineraries" / "google_flights").glob("*/*.csv.gz"))
    assert fares.name == itineraries.name
    assert len(list(storage.read_fare_file(itineraries))) == 2
    assert len(list(storage.read_fare_file(fares))) == 1
