# Data quality

Latest check: 2026-11-14

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| google_flights | data_present | pass | 92 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 1.0 | >=0.95 | 92 of 92 found |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 60, max 772; allowed 10 to 10000 |
| google_flights | row_count | pass | 92 | within 20% of 84 | +9.5% against the trailing median |
| google_flights | median_price | pass | 119.5 | within 25% of 119 | +0.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-14 | not checked | pass | not checked |
| 2026-11-13 | pass | pass | warn (1 warn, 0 fail) |
| 2026-11-12 | pass | pass | pass |
| 2026-11-11 | pass | pass | pass |
| 2026-11-10 | pass | fail (1 warn, 3 fail) | pass |
| 2026-11-09 | pass | fail (1 warn, 4 fail) | pass |
| 2026-11-08 | pass | pass | pass |
| 2026-11-07 | pass | pass | pass |
| 2026-11-06 | pass | pass | pass |
| 2026-11-05 | pass | pass | pass |
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-03 | pass | pass | pass |
