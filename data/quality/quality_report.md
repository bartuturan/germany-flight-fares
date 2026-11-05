# Data quality

Latest check: 2026-11-05

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| google_flights | data_present | pass | 82 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 1.0 | >=0.95 | 82 of 82 found |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 75, max 827; allowed 10 to 10000 |
| google_flights | row_count | skip | 82 |  | 2 earlier snapshots, need 3 |
| google_flights | median_price | skip | 114.5 |  | 2 earlier snapshots, need 3 |
| google_flights | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-05 | not checked | pass | not checked |
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-03 | pass | pass | pass |
