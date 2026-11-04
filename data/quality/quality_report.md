# Data quality

Latest check: 2026-11-04

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| eurostat | data_present | pass | 1306 | >0 |  |
| eurostat | series_present | pass | 6 | 6 |  |
| eurostat | row_count | pass | 1306 | >=1306 |  |
| eurostat | missing_months | pass | 0 | 0 |  |
| eurostat | invalid_values | pass | 0 | 0 |  |
| eurostat | latest_period | pass | 2 | <=2 months old | newest month is 2026-09 |
| eurostat | latest_change | pass | 0.122 | <0.4 | largest latest-month move, CP07331 I25 |
| google_flights | data_present | pass | 73 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | warn | 0.869 | >=0.95 | 73 of 84 found; missing FRA-BER-2026-12-04, FRA-CDG-2026-11-06, FRA-CDG-2027-01-03, FRA-LHR-2026-12-22, FRA-PMI-2026-11-05, +6 more |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 79, max 827; allowed 10 to 10000 |
| google_flights | row_count | skip | 73 |  | 1 earlier snapshots, need 3 |
| google_flights | median_price | skip | 114.0 |  | 1 earlier snapshots, need 3 |
| google_flights | snapshot_gap | pass | 0 | 0 |  |
| ryanair | data_present | pass | 4164 | >0 |  |
| ryanair | columns | pass |  |  |  |
| ryanair | invalid_rows | pass | 0 | 0 |  |
| ryanair | coverage | pass | 1.0 | >=0.95 | 98 of 98 found |
| ryanair | duplicates | pass | 0 | 0 |  |
| ryanair | price_range | pass | 0 | 0 | min 14.99, max 501.3; allowed 1 to 1000 |
| ryanair | row_count | skip | 4164 |  | 1 earlier snapshots, need 3 |
| ryanair | median_price | skip | 46.03 |  | 1 earlier snapshots, need 3 |
| ryanair | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-03 | pass | pass | pass |
