from argparse import Namespace
from datetime import datetime, timezone

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


def blocked(config, today):
    raise SourceFailed("Google returned its consent page")


def stub_sources(monkeypatch, google=blocked):
    monkeypatch.setattr(
        cli.eurostat,
        "collect",
        lambda config: [{"period": "2026-09", "coicop": "CP0733", "unit": "I25", "value": 100.49}],
    )
    monkeypatch.setattr(cli.ryanair, "collect", lambda config, today: [fare(today)])
    monkeypatch.setattr(cli.google_flights, "collect", google)


def test_one_failing_source_keeps_the_others_and_exits_with_an_error(tmp_path, monkeypatch):
    stub_sources(monkeypatch)
    code = cli.run(Namespace(source=None, data_dir=tmp_path), CONFIG)

    assert code == 1
    assert (tmp_path / "eurostat" / "germany_air_fare_index.csv").exists()
    today = datetime.now(timezone.utc).date()
    assert storage.fare_path(tmp_path, "ryanair", today).exists()
    assert not storage.fare_path(tmp_path, "google_flights", today).exists()
    assert (tmp_path / "germany_fares_daily_summary.csv").exists()


def test_success_exits_cleanly_and_skips_disabled_sources(tmp_path, monkeypatch):
    stub_sources(monkeypatch)
    config = {**CONFIG, "google_flights": {"enabled": False}}
    assert cli.run(Namespace(source=None, data_dir=tmp_path), config) == 0


def test_named_source_runs_only_that_source(tmp_path, monkeypatch):
    stub_sources(monkeypatch)
    assert cli.run(Namespace(source=["ryanair"], data_dir=tmp_path), CONFIG) == 0
    assert not (tmp_path / "eurostat").exists()


def test_export_writes_one_route(tmp_path, monkeypatch):
    stub_sources(monkeypatch)
    cli.run(Namespace(source=["ryanair"], data_dir=tmp_path), CONFIG)
    out = tmp_path / "route.csv"
    assert cli.export(Namespace(route="ber-bgy", data_dir=tmp_path, out=out)) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("snapshot_date,source,origin")
    assert len(lines) == 2
