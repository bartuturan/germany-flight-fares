"""Write the daily fare files, the Eurostat index and the summary."""

import csv
import gzip
import io
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


def fare_path(data_dir, source, snapshot_date):
    return (
        Path(data_dir)
        / "fares"
        / source
        / f"{snapshot_date.year:04d}"
        / f"{snapshot_date.isoformat()}.csv.gz"
    )


def write_fares(data_dir, source, snapshot_date, rows):
    path = fare_path(data_dir, source, snapshot_date)
    # mtime=0 keeps identical content byte-identical, so re-runs don't create noise in git.
    data = gzip.compress(_csv_text(rows, FARE_COLUMNS).encode("utf-8"), mtime=0)
    _replace_atomically(path, data)
    return path


def write_index(data_dir, rows):
    path = Path(data_dir) / "eurostat" / "germany_air_fare_index.csv"
    _replace_atomically(path, _csv_text(rows, INDEX_COLUMNS).encode("utf-8"))
    return path


def fare_files(data_dir):
    return sorted((Path(data_dir) / "fares").glob("*/*/*.csv.gz"))


def read_fare_file(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def summarize(rows):
    """Fare count and price spread for one source on one snapshot date."""
    prices = [float(row["price"]) for row in rows]
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
    summaries = []
    for path in fare_files(data_dir):
        rows = list(read_fare_file(path))
        if rows:
            summaries.append(summarize(rows))
    summaries.sort(key=lambda row: (row["snapshot_date"], row["source"]))
    path = Path(data_dir) / "germany_fares_daily_summary.csv"
    _replace_atomically(path, _csv_text(summaries, SUMMARY_COLUMNS).encode("utf-8"))
    return path


def route_rows(data_dir, origin, destination):
    rows = []
    for path in fare_files(data_dir):
        rows += [
            row
            for row in read_fare_file(path)
            if row["origin"] == origin and row["destination"] == destination
        ]
    return sorted(rows, key=lambda row: (row["snapshot_date"], row["departure_date"], row["source"]))
