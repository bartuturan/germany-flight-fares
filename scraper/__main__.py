"""Usage: python -m scraper run [--source NAME ...] | export --route BER-BGY [--out FILE]"""

import argparse
import csv
import logging
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from . import eurostat, google_flights, ryanair, storage

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ["eurostat", "ryanair", "google_flights"]

log = logging.getLogger("scraper")


def run_source(name, config, data_dir, today):
    if name == "eurostat":
        return storage.write_index(data_dir, eurostat.collect(config)), None
    collect = {"ryanair": ryanair.collect, "google_flights": google_flights.collect}[name]
    rows = collect(config, today)
    return storage.write_fares(data_dir, name, today, rows), len(rows)


def run(args, config):
    today = datetime.now(timezone.utc).date()
    selected = args.source or [name for name in SOURCES if config[name]["enabled"]]
    failures = []
    for name in selected:
        try:
            path, count = run_source(name, config[name], args.data_dir, today)
            log.info("%s: wrote %s%s", name, path, f" ({count} fares)" if count else "")
        except Exception as exc:  # one source failing must not stop the others
            log.error("%s failed: %s", name, exc)
            failures.append(name)
    storage.rebuild_summary(args.data_dir)
    if failures:
        log.error("failed sources: %s", ", ".join(failures))
        return 1
    return 0


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
    export_parser = commands.add_parser("export", help="write one route's fares as CSV")
    export_parser.add_argument("--route", required=True, help="for example BER-BGY")
    export_parser.add_argument("--out", type=Path, help="default: stdout")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "export":
        return export(args)
    with open(args.config, "rb") as handle:
        return run(args, tomllib.load(handle))


if __name__ == "__main__":
    sys.exit(main())
