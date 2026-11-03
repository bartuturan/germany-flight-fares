"""Write the daily fare files, the Eurostat index and the summary."""

import csv
import gzip
import io
import math
import os
import statistics
from pathlib import Path

FARE_COLUMNS = [
    "snapshot_date",
    "source",
    "origin",
    "destination",
    "departure_date",
    "departure_time",
    "airline",
    "flight_number",
    "stops",
    "price",
    "currency",
    "snapshot_at",
]
# Files written before snapshots had a time.
LEGACY_FARE_COLUMNS = FARE_COLUMNS[:-1]
ITINERARY_COLUMNS = [
    "snapshot_date",
    "snapshot_at",
    "source",
    "origin",
    "destination",
    "departure_date",
    "departure_time",
    "airline",
    "stops",
    "price",
    "currency",
]
INDEX_COLUMNS = ["period", "coicop", "unit", "value"]
SUMMARY_COLUMNS = ["snapshot_date", "source", "fares", "min", "p25", "median", "p75"]


def _replace_atomically(path, data):
    """Write through a temp name so an interrupted run never leaves a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(data)
    os.replace(partial, path)


def _csv_text(rows, columns):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_csv(path, rows, columns):
    _replace_atomically(Path(path), _csv_text(rows, columns).encode("utf-8"))
    return path


def read_csv(path):
    """Rows of a plain CSV file, or nothing if the file doesn't exist yet."""
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def index_path(data_dir):
    return Path(data_dir) / "eurostat" / "germany_air_fare_index.csv"


def summary_path(data_dir):
    return Path(data_dir) / "germany_fares_daily_summary.csv"


def run_label(run_at):
    """Identifies one run. It's safe in a file name and sorts in time order."""
    return run_at.strftime("%Y-%m-%dT%H%MZ")


def _run_path(data_dir, folder, source, run_at):
    return Path(data_dir) / folder / source / f"{run_at.year:04d}" / f"{run_label(run_at)}.csv.gz"


def fare_path(data_dir, source, run_at):
    return _run_path(data_dir, "fares", source, run_at)


def itinerary_path(data_dir, source, run_at):
    return _run_path(data_dir, "itineraries", source, run_at)


def _write_run(path, rows, columns, run_at):
    """Every row gets the time the run started, so all of a run's rows share one snapshot."""
    stamp = run_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamped = [{**row, "snapshot_at": stamp} for row in rows]
    # mtime=0 keeps identical content byte-identical, so re-runs don't create noise in git.
    _replace_atomically(path, gzip.compress(_csv_text(stamped, columns).encode("utf-8"), mtime=0))
    return path


def write_fares(data_dir, source, run_at, rows):
    return _write_run(fare_path(data_dir, source, run_at), rows, FARE_COLUMNS, run_at)


def write_itineraries(data_dir, source, run_at, rows):
    return _write_run(itinerary_path(data_dir, source, run_at), rows, ITINERARY_COLUMNS, run_at)


def write_index(data_dir, rows):
    return write_csv(index_path(data_dir), rows, INDEX_COLUMNS)


def fare_files(data_dir):
    return sorted((Path(data_dir) / "fares").glob("*/*/*.csv.gz"))


def latest_fare_path(data_dir, source, day):
    """That source's last run on a date, or None. Legacy files are named by date alone."""
    folder = Path(data_dir) / "fares" / source / f"{day.year:04d}"
    paths = sorted(folder.glob(f"{day.isoformat()}*.csv.gz"))
    return paths[-1] if paths else None


def path_label(path):
    return Path(path).name.removesuffix(".csv.gz")


def read_fare_file(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def parse_price(text):
    """The price as a number, or None if it isn't a usable one."""
    try:
        price = float(text)
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 0 else None


def summarize(rows):
    """Fare count and price spread for one source on one snapshot date, ignoring unusable prices."""
    prices = [price for price in map(parse_price, (row["price"] for row in rows)) if price is not None]
    if not prices:
        return None
    if len(prices) == 1:
        p25 = median = p75 = prices[0]
    else:
        p25, median, p75 = statistics.quantiles(prices, n=4, method="inclusive")
    return {
        "snapshot_date": rows[0]["snapshot_date"],
        "source": rows[0]["source"],
        "fares": len(prices),
        "min": min(prices),
        "p25": round(p25, 2),
        "median": round(median, 2),
        "p75": round(p75, 2),
    }


def rebuild_summary(data_dir):
    """One row per day and source, from that day's last run, so days stay comparable."""
    last_runs = {(path.parent.parent.name, path.name[:10]): path for path in fare_files(data_dir)}
    summaries = []
    for path in last_runs.values():
        summary = summarize(list(read_fare_file(path)))
        if summary:
            summaries.append(summary)
    summaries.sort(key=lambda row: (row["snapshot_date"], row["source"]))
    return write_csv(summary_path(data_dir), summaries, SUMMARY_COLUMNS)


def route_rows(data_dir, origin, destination):
    rows = []
    for path in fare_files(data_dir):
        rows += [
            row
            for row in read_fare_file(path)
            if row["origin"] == origin and row["destination"] == destination
        ]
    return sorted(
        rows,
        key=lambda row: (
            row["snapshot_date"],
            row.get("snapshot_at", ""),
            row["departure_date"],
            row["source"],
        ),
    )
