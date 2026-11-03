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

## Known limits

- **Unofficial sources:** Ryanair's endpoints are undocumented and `fast-flights` scrapes Google Flights, so either can break or be blocked without notice.
- **Google consent page:** from a German-located connection, Google returned its "Before you continue" consent page instead of results. The scraper doesn't answer it and reports the source as failed, so `google_flights` may not work from an EU network without changes. It did work from a GitHub runner.
- **Gaps in Google data:** Google's page often reports an error that clears on a retry. A few searches still fail each day and the run stays green, so check the "searches gave a fare" log line or the `fares` count in the summary. In the first test, FRA-BER on 2027-02-01 and MUC-BER on 2026-12-03 failed every time with an `IndexError`, which looks like a parsing error in `fast-flights`.
- **Google prices:** fast-flights doesn't report a result's currency, so the `currency` column is what was requested. Prices are as Google shows them to the runner's location, which may differ from what a buyer in Germany sees.

## Terms of use

This project is for personal, non-commercial research, and the repo should stay private so fares aren't republished.

- **Ryanair:** its [terms of use](https://www.ryanair.com/ie/en/corporate/terms-of-use) allow private, non-commercial use only and prohibit automated extraction for commercial use. They also reserve the right to block access.
- **Google Flights:** it has no public API, and `fast-flights` is an unofficial scraper.
- **Commercial use:** this would need a licence or a paid data source. Eurostat is the source meant for open reuse.
