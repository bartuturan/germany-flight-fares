"""Usage: python -m scraper run [--source NAME ...] | check [--date YYYY-MM-DD] | export --route BER-BGY"""

import argparse
import csv
import logging
import sys
import tomllib
from datetime import date, datetime, timezone
from pathlib import Path

from . import eurostat, google_flights, quality, ryanair, storage, wizzair
from .common import SourceFailed

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ["eurostat", "ryanair", "wizzair", "google_flights"]
# Sources that write one fare file per run and return a plain list of fare rows.
FARE_COLLECTORS = {"ryanair": ryanair, "wizzair": wizzair}

log = logging.getLogger("scraper")


def write_google(data_dir, run_at, rows, itineraries):
    storage.write_itineraries(data_dir, "google_flights", run_at, itineraries)
    return storage.write_fares(data_dir, "google_flights", run_at, rows)


def run_source(name, config, data_dir, run_at):
    if name == "eurostat":
        return storage.write_index(data_dir, eurostat.collect(config)), None
    today = run_at.date()
    if name == "google_flights":
        try:
            rows, itineraries = google_flights.collect(config, today)
        except SourceFailed as exc:
            if exc.partial:
                rows, itineraries = exc.partial
                path = write_google(data_dir, run_at, rows, itineraries)
                log.warning("google_flights: stopped early, kept %d fares in %s", len(rows), path)
            raise
        return write_google(data_dir, run_at, rows, itineraries), len(rows)
    rows = FARE_COLLECTORS[name].collect(config, today)
    return storage.write_fares(data_dir, name, run_at, rows), len(rows)


def run(args, config):
    run_at = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    selected = args.source or enabled_sources(config)
    failures = {}
    for name in selected:
        try:
            path, count = run_source(name, config[name], args.data_dir, run_at)
            log.info("%s: wrote %s%s", name, path, f" ({count} fares)" if count else "")
        except Exception as exc:  # one source failing must not stop the others
            log.error("%s failed: %s", name, exc)
            failures[name] = str(exc)
    storage.rebuild_summary(args.data_dir)
    if failures:
        log.error("failed sources: %s", ", ".join(failures))
    results = quality.check_and_record(args.data_dir, config, run_at.date(), selected, failures, run_at)
    return exit_code(results)


def enabled_sources(config):
    return [name for name in SOURCES if config[name]["enabled"]]


def exit_code(results):
    """Only failures end the run with an error. Warnings stay in the log and report."""
    failed = [row for row in results if row["status"] == quality.FAIL]
    log.info("quality: %d checks, %d failed", len(results), len(failed))
    return 1 if failed else 0


def check(args, config):
    day = args.date or datetime.now(timezone.utc).date()
    storage.rebuild_summary(args.data_dir)
    results = quality.check_and_record(args.data_dir, config, day, args.source or enabled_sources(config))
    return exit_code(results)


def export(args):
    origin, destination = args.route.upper().split("-")
    rows = storage.route_rows(args.data_dir, origin, destination)
    handle = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=storage.FARE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.out:
            handle.close()
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m scraper", description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.toml")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="collect today's data")
    run_parser.add_argument("--source", nargs="+", choices=SOURCES, help="default: all enabled")
    check_parser = commands.add_parser("check", help="re-run the quality checks without scraping")
    check_parser.add_argument("--source", nargs="+", choices=SOURCES, help="default: all enabled")
    check_parser.add_argument("--date", type=date.fromisoformat, help="default: today (UTC)")
    export_parser = commands.add_parser("export", help="write one route's fares as CSV")
    export_parser.add_argument("--route", required=True, help="for example BER-BGY")
    export_parser.add_argument("--out", type=Path, help="default: stdout")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "export":
        return export(args)
    with open(args.config, "rb") as handle:
        config = tomllib.load(handle)
    return check(args, config) if args.command == "check" else run(args, config)


if __name__ == "__main__":
    sys.exit(main())
