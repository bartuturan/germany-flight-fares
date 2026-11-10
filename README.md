# Germany flight fares

Builds a time series of flight prices for Germany, for free, on a daily GitHub Actions schedule.

No free source offers past fares per route, so this combines two kinds of data:

- **Official history:** a monthly price index going back to 1996. It shows how prices moved, not what a ticket cost.
- **Actual fares:** repeated snapshots in euros, which follow the same departures as they get closer. These start on the first run, so the history grows from there.

## Data

| File | Contents |
|---|---|
| `data/eurostat/germany_air_fare_index.csv` | `period, coicop, unit, value`, rewritten on each run |
| `data/fares/<source>/<year>/<run>.csv.gz` | One file of fares per source per run, such as `2026-11-04T0517Z` |
| `data/itineraries/google_flights/<year>/<run>.csv.gz` | Every itinerary each Google Flights search returned, in the same runs |
| `data/germany_fares_daily_summary.csv` | Fare count, min, p25, median and p75 per day and source, from each day's last run |
| `data/quality/quality_report.md` | Quality results of each source's latest run and a day-by-day history, rebuilt on each run |
| `data/quality/quality_log.csv` | Every quality check result for every run, kept permanently |

**Eurostat index:** HICP dataset `prc_hicp_minr` for Germany. `CP0733` is all passenger air transport (from 1996-01), `CP07331` is domestic and `CP07332` is international (both from 2014-12). `I25` means 2025 = 100 and `I15` means 2015 = 100.

**Fare columns:** `snapshot_date, source, origin, destination, departure_date, departure_time, airline, flight_number, stops, price, currency, snapshot_at`. `snapshot_at` is the UTC time the run started. It's empty in the first files, from 2026-11-03, which are named by date alone. Fields a source doesn't provide are empty.

**Itinerary columns:** `snapshot_date, snapshot_at, source, origin, destination, departure_date, departure_time, airline, stops, price, currency`. Use these to compare airlines or filter by stops, because the fare files hold only the cheapest itinerary.

### What the fares mean

- **Direction:** one-way departures from Germany only.
- **Price:** the lowest base fare for one adult, so bags and seat fees aren't included.
- **`ryanair`:** the cheapest fare to each destination on each of the next 45 days, from all 14 German airports Ryanair serves. A route and day with no fare has no flight on sale. It doesn't cover FRA or MUC, and it only covers one low-cost airline. The first file, from 2026-11-03, holds the cheapest fare per week instead.
- **`wizzair`:** the cheapest fare on each route and departure day for the next 45 days, from the 10 German airports Wizz Air serves, to every destination on its route map. It's off by default (`enabled = false` in `config.toml`). The answer gives each day's cheapest price and its flight times, but not which flight has the price, so `departure_time` and `flight_number` are empty. Days Wizz Air marks `checkPrice` (price 0, "check the price") are left out, because they have no usable fare. That means the series skips some days, which may be days with high or unavailable fares, so don't read a missing day as no flight. Each run logs how many there were.
- **`google_flights`:** the cheapest economy itinerary on all airlines, for the routes in `config.toml`. Each route tracks one departure a week, from 60 days ahead until it leaves. The weekday moves on by one each week and differs between routes. Prices are whole euros, and the cheapest itinerary can be on any airline, including low-cost ones, with any number of stops.

The sources aren't directly comparable, and the summary mixes whatever routes were available that day. For analysis, use one route at a time:

```bash
python -m scraper export --route BER-BGY --out ber-bgy.csv
```

The same departure appears in many snapshots, so you can follow its price as the date gets closer. Ryanair and Wizz Air give one price per day for each route, and Google Flights gives three per day for each tracked departure.

## Running it

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m scraper run
.venv/Scripts/python.exe -m scraper run --source eurostat ryanair
```

On Linux or macOS, use `.venv/bin/python`. Airports, routes, how far ahead to search, delays and on/off switches are in `config.toml`.

## Schedule and failures

`.github/workflows/scrape.yml` runs every source at about 05:17 UTC, and Google Flights again at about 13:17 and 21:17 UTC, so short-lived price moves can be measured. GitHub may start any of these late, which is why each row records its time. You can also start it by hand from the Actions tab.

These runs use GitHub Actions minutes, roughly 1,450 a month by estimate. Wizz Air, once enabled, adds about 10 minutes a day, so roughly 300 more a month. Check that against your plan's allowance for private repos. To use fewer, remove a schedule or some routes.

Each source runs independently. A source that is blocked at the start or returns nothing writes no file for that run, and missed runs can't be recovered afterwards. Google Flights keeps what it collected if it is blocked part-way or runs out of time (`time_budget_minutes`), and the run is still marked as failed. The workflow always commits what succeeded, then fails the run so GitHub notifies you.

Runs never overlap: one that starts while another is running waits, then starts from the latest commit so their data doesn't conflict. If a run still can't push its data after 3 tries, the data is kept as the `data-not-pushed` artifact on that run for 14 days, because the runner is discarded afterwards.

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
| `coverage` | fares | Share of airport and week combinations (Ryanair, Wizz Air) or tracked departures (Google) with a fare, naming what's missing |
| `duplicates` | fares | The same flight listed twice |
| `price_range` | fares | Prices outside the plausible range in `config.toml` |
| `row_count` | all | Fares: fare count compared with the median of the last 14 days. Eurostat: fewer rows than the last check |
| `median_price` | fares | Median price compared with the median of the last 14 days |
| `snapshot_gap` | fares | Days missed since the previous snapshot |
| `series_present`, `missing_months`, `invalid_values` | Eurostat | All series exist, with no gaps and no non-positive values |
| `latest_period` | Eurostat | How old the newest month is |
| `latest_change` | Eurostat | An unusually large move in the latest month |

Each result is one of:

- **`pass`:** nothing wrong.
- **`warn`:** recorded in the log and report, and the run stays green.
- **`fail`:** recorded, and the run is marked as failed so GitHub notifies you. The data is still committed, so review it before relying on that day.
- **`skip`:** not enough history yet. `row_count` and `median_price` need 3 earlier snapshots.

Thresholds are in `config.toml` under `[quality]`, and they're based on a single day of data so far, so they may need adjusting. Ryanair's coverage thresholds predate one-day searches. Each run gets its own log entries, and the day-by-day history shows the worst result across that day's runs.

To re-run the checks without scraping:

```bash
.venv/Scripts/python.exe -m scraper check
.venv/Scripts/python.exe -m scraper check --date 2026-11-03 --source ryanair
```

This re-checks the last run of that day.

If the scheduled workflow never starts, no check runs and no notification is sent. `snapshot_gap` only reports the missed days on the next run that does start.

## Known limits

- **Unofficial sources:** Ryanair's endpoints are undocumented and `fast-flights` scrapes Google Flights, so either can break or be blocked without notice.
- **Wizz Air's API:** it's the one Wizz Air's website calls, not a public one. Its address contains a version that changes every few weeks, so each run reads the current one from the homepage and falls back to `fallback_api_version` in `config.toml` if that fails. The homepage answers a plain scraper user agent with a "Human Verification" page, so that one request uses a browser user agent. The API itself answers either. A probe on GitHub runners (`.github/workflows/wizzair-probe.yml`, run by hand) made 888 timetable requests from three runners at one time of day and got no blocks, and only 3 server errors.
- **Wizz Air errors and duplicates:** server errors (HTTP 503) come in short bursts, about 4% of requests in a test run. Requests that fail are tried again once after a pause. The route map also lists city-group codes beside real airports (`ROM` beside `FCO`, `MIL` beside `MXP`), and asking for the group returns the airport's flights again, so rows are de-duplicated by route and day.
- **Google consent page:** from a German-located connection, Google returned its "Before you continue" consent page instead of results. The scraper doesn't answer it and reports the source as failed, so `google_flights` may not work from an EU network without changes. It did work from a GitHub runner.
- **Google errors:** some Google searches come back as an internal error (code 13 in its response), and the rate changes a lot from hour to hour: from none in a run to around half of requests. A test of 120 requests on a GitHub runner found that reusing one browser session, as the scraper now does, errored on 6 of 40 requests, against 39 of 80 with a new session for each search. Pauses and other browser profiles made no difference, and an immediate retry usually fails too. Searches that fail are tried again in up to 3 passes, a minute and a half apart. Any that still fail are left out, and the `coverage` check names them. Each run logs how many requests errored, so you can see whether the rate is changing.
- **Google response format:** `fast-flights` only makes the request. Its parser misses the "best flights" section and fails on itineraries with no price, so `scraper/google_flights.py` parses the response itself. That code relies on the positions of fields in an undocumented response, so a change at Google can break it, which the `coverage` check would show.
- **Google prices:** fast-flights doesn't report a result's currency, so the `currency` column is what was requested. Prices are as Google shows them to the runner's location, which may differ from what a buyer in Germany sees.

## Terms of use

This project is for personal, non-commercial research, and the repo should stay private so fares aren't republished.

- **Ryanair:** its [terms of use](https://www.ryanair.com/ie/en/corporate/terms-of-use) allow private, non-commercial use only and prohibit automated extraction for commercial use. They also reserve the right to block access.
- **Wizz Air:** it has no public API, and this uses the undocumented one its website calls. I haven't read its terms of use, so check them before enabling the source.
- **Google Flights:** it has no public API, and `fast-flights` is an unofficial scraper.
- **Commercial use:** this would need a licence or a paid data source. Eurostat is the source meant for open reuse.
