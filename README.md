# Germany flight fares

Builds a time series of flight prices for Germany, for free, on a daily GitHub Actions schedule.

No free source offers past fares per route, so this combines two kinds of data:

- **Official history:** a monthly price index going back to 1996. It shows how prices moved, not what a ticket cost.
- **Actual fares:** daily snapshots in euros. These start on the first run, so the history grows from there.

## Data

| File | Contents |
|---|---|
| `data/eurostat/germany_air_fare_index.csv` | `period, coicop, unit, value`, rewritten on each run |
| `data/fares/<source>/<year>/<date>.csv.gz` | One file of fare snapshots per source per day |
| `data/germany_fares_daily_summary.csv` | Fare count, min, p25, median and p75 per day and source |
| `data/quality/quality_report.md` | Latest quality results and a day-by-day history, rebuilt on each run |
| `data/quality/quality_log.csv` | Every quality check result for every day, kept permanently |

**Eurostat index:** HICP dataset `prc_hicp_minr` for Germany. `CP0733` is all passenger air transport (from 1996-01), `CP07331` is domestic and `CP07332` is international (both from 2014-12). `I25` means 2025 = 100 and `I15` means 2015 = 100.

**Fare columns:** `snapshot_date, source, origin, destination, departure_date, departure_time, airline, flight_number, stops, price, currency`. Fields a source doesn't provide are empty.

### What the fares mean

- **Direction:** one-way departures from Germany only.
- **Price:** the lowest base fare for one adult, so bags and seat fees aren't included.
- **`ryanair`:** the cheapest fare to each destination in each of the next 26 weekly departure windows, from all 14 German airports Ryanair serves. It doesn't cover FRA or MUC, and it only covers one low-cost airline.
- **`google_flights`:** the cheapest economy itinerary on all airlines, for the routes in `config.toml`, departing 7, 30, 60 and 90 days ahead. Prices are whole euros.

The sources aren't directly comparable, and the summary mixes whatever routes were available that day. For analysis, use one route at a time:

```bash
python -m scraper export --route BER-BGY --out ber-bgy.csv
```

The same departure appears in many snapshots, so you can follow its price as the date gets closer.

## Running it

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m scraper run
.venv/Scripts/python.exe -m scraper run --source eurostat ryanair
```

On Linux or macOS, use `.venv/bin/python`. Airports, routes, lead times, delays and on/off switches are in `config.toml`.

## Schedule and failures

`.github/workflows/scrape.yml` runs daily at about 05:17 UTC, though GitHub may start it late. You can also start it by hand from the Actions tab.

Each source runs independently. A source that is blocked, returns nothing or fails repeatedly writes no file that day, and missed days can't be recovered afterwards. The workflow still commits what succeeded, then marks the run as failed so GitHub notifies you.

Requests are retried on HTTP 429, HTTP 5xx and connection errors. The summary is rebuilt from all the daily files on each run.

## Data quality

Quality checks run automatically after each scrape. Start with `data/quality/quality_report.md`, which also appears on each workflow run's summary page.

| Check | Sources | What it looks for |
|---|---|---|
| `scrape` | all | The source failed during this run, with the reason. Only recorded on a failure |
| `check_error` | all | A check crashed, for example on a damaged file. Only recorded on a failure |
| `data_present` | all | Today's data exists and isn't empty |
| `columns` | fares | The file has the expected columns |
| `invalid_rows` | fares | Missing fields, bad prices, dates or airport codes, the wrong currency, or departures outside what was requested |
| `coverage` | fares | Share of airport and week combinations (Ryanair) or route and lead time searches (Google) with a fare, naming what's missing |
| `duplicates` | fares | The same flight listed twice |
| `price_range` | fares | Prices outside the plausible range in `config.toml` |
| `row_count` | all | Fares: fare count compared with the median of the last 14 snapshots. Eurostat: fewer rows than the last check |
| `median_price` | fares | Median price compared with the median of the last 14 snapshots |
| `snapshot_gap` | fares | Days missed since the previous snapshot |
| `series_present`, `missing_months`, `invalid_values` | Eurostat | All series exist, with no gaps and no non-positive values |
| `latest_period` | Eurostat | How old the newest month is |
| `latest_change` | Eurostat | An unusually large move in the latest month |

Each result is one of:

- **`pass`:** nothing wrong.
- **`warn`:** recorded in the log and report, and the run stays green.
- **`fail`:** recorded, and the run is marked as failed so GitHub notifies you. The data is still committed, so review it before relying on that day.
- **`skip`:** not enough history yet. `row_count` and `median_price` need 3 earlier snapshots.

Thresholds are in `config.toml` under `[quality]`, and they're based on a single day of data so far, so they may need adjusting. Re-running a source on the same day replaces that source's log entries for the day.

To re-run the checks without scraping:

```bash
.venv/Scripts/python.exe -m scraper check
.venv/Scripts/python.exe -m scraper check --date 2026-11-03 --source ryanair
```

If the scheduled workflow never starts, no check runs and no notification is sent. `snapshot_gap` only reports the missed days on the next run that does start.

## Known limits

- **Unofficial sources:** Ryanair's endpoints are undocumented and `fast-flights` scrapes Google Flights, so either can break or be blocked without notice.
- **Google consent page:** from a German-located connection, Google returned its "Before you continue" consent page instead of results. The scraper doesn't answer it and reports the source as failed, so `google_flights` may not work from an EU network without changes. It did work from a GitHub runner.
- **Gaps in Google data:** Google's page often reports an error that clears on a retry. A few searches can still fail, and the `coverage` check names them. In the first test, FRA-BER on 2027-02-01 and MUC-BER on 2026-12-03 failed every time with an `IndexError`, which looks like a parsing error in `fast-flights`.
- **Google prices:** fast-flights doesn't report a result's currency, so the `currency` column is what was requested. Prices are as Google shows them to the runner's location, which may differ from what a buyer in Germany sees.

## Terms of use

This project is for personal, non-commercial research, and the repo should stay private so fares aren't republished.

- **Ryanair:** its [terms of use](https://www.ryanair.com/ie/en/corporate/terms-of-use) allow private, non-commercial use only and prohibit automated extraction for commercial use. They also reserve the right to block access.
- **Google Flights:** it has no public API, and `fast-flights` is an unofficial scraper.
- **Commercial use:** this would need a licence or a paid data source. Eurostat is the source meant for open reuse.
