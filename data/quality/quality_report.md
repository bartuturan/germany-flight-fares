# Data quality

Latest check: 2026-11-12

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| eurostat | data_present | pass | 1306 | >0 |  |
| eurostat | series_present | pass | 6 | 6 |  |
| eurostat | row_count | pass | 1306 | >=1306 |  |
| eurostat | missing_months | pass | 0 | 0 |  |
| eurostat | invalid_values | pass | 0 | 0 |  |
| eurostat | latest_period | pass | 2 | <=2 months old | newest month is 2026-09 |
| eurostat | latest_change | pass | 0.122 | <0.4 | largest latest-month move, CP07331 I25 |
| google_flights | data_present | pass | 96 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 1.0 | >=0.95 | 96 of 96 found |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 64, max 771; allowed 10 to 10000 |
| google_flights | row_count | pass | 96 | within 20% of 83 | +15.7% against the trailing median |
| google_flights | median_price | pass | 119.5 | within 25% of 119 | +0.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |
| ryanair | data_present | pass | 4251 | >0 |  |
| ryanair | columns | pass |  |  |  |
| ryanair | invalid_rows | pass | 0 | 0 |  |
| ryanair | coverage | pass | 1.0 | >=0.95 | 98 of 98 found |
| ryanair | duplicates | pass | 0 | 0 |  |
| ryanair | price_range | pass | 0 | 0 | min 14.99, max 486.99; allowed 1 to 1000 |
| ryanair | row_count | pass | 4251 | within 20% of 4214 | +0.9% against the trailing median |
| ryanair | median_price | pass | 65.99 | within 25% of 53.99 | +22.2% against the trailing median |
| ryanair | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
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
