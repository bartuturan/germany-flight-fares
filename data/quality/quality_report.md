# Data quality

Latest check: 2026-11-11

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| google_flights | data_present | pass | 96 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 1.0 | >=0.95 | 96 of 96 found |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 64, max 771; allowed 10 to 10000 |
| google_flights | row_count | pass | 96 | within 20% of 82.5 | +16.4% against the trailing median |
| google_flights | median_price | pass | 115.0 | within 25% of 119 | -3.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-11 | not checked | pass | not checked |
| 2026-11-10 | pass | fail (1 warn, 3 fail) | pass |
| 2026-11-09 | pass | fail (1 warn, 4 fail) | pass |
| 2026-11-08 | pass | pass | pass |
| 2026-11-07 | pass | pass | pass |
| 2026-11-06 | pass | pass | pass |
| 2026-11-05 | pass | pass | pass |
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-03 | pass | pass | pass |
