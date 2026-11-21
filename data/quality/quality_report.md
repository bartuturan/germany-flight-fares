# Data quality

Latest check: 2026-11-21

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| google_flights | data_present | pass | 91 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 0.968 | >=0.95 | 91 of 94 found; missing FRA-CDG-2026-12-17, MUC-ATH-2026-12-08, MUC-IST-2027-01-02 |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 67, max 1084; allowed 10 to 10000 |
| google_flights | row_count | pass | 91 | within 20% of 94.5 | -3.7% against the trailing median |
| google_flights | median_price | pass | 115.0 | within 25% of 119 | -3.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair | wizzair |
|---|---|---|---|---|
| 2026-11-21 | not checked | pass | not checked | not checked |
| 2026-11-20 | pass | fail (0 warn, 2 fail) | pass | pass |
| 2026-11-19 | pass | fail (1 warn, 2 fail) | pass | pass |
| 2026-11-18 | pass | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-17 | pass | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-16 | pass | pass | warn (1 warn, 0 fail) | not checked |
| 2026-11-15 | pass | pass | warn (1 warn, 0 fail) | not checked |
| 2026-11-14 | pass | pass | warn (1 warn, 0 fail) | not checked |
| 2026-11-13 | pass | pass | warn (1 warn, 0 fail) | not checked |
| 2026-11-12 | pass | pass | pass | not checked |
| 2026-11-11 | pass | pass | pass | not checked |
| 2026-11-10 | pass | fail (1 warn, 3 fail) | pass | not checked |
| 2026-11-09 | pass | fail (1 warn, 4 fail) | pass | not checked |
| 2026-11-08 | pass | pass | pass | not checked |
| 2026-11-07 | pass | pass | pass | not checked |
| 2026-11-06 | pass | pass | pass | not checked |
| 2026-11-05 | pass | pass | pass | not checked |
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass | not checked |
| 2026-11-03 | pass | pass | pass | not checked |
