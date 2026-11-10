# Data quality

Latest check: 2026-11-10

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| eurostat | data_present | pass | 1306 | >0 |  |
| eurostat | series_present | pass | 6 | 6 |  |
| eurostat | row_count | pass | 1306 | >=1306 |  |
| eurostat | missing_months | pass | 0 | 0 |  |
| eurostat | invalid_values | pass | 0 | 0 |  |
| eurostat | latest_period | pass | 2 | <=2 months old | newest month is 2026-09 |
| eurostat | latest_change | pass | 0.122 | <0.4 | largest latest-month move, CP07331 I25 |
| google_flights | data_present | pass | 61 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | fail | 0.693 | >=0.95 | 61 of 88 found; missing FRA-BER-2026-11-18, FRA-BER-2026-12-12, FRA-BER-2026-12-13, FRA-BKK-2026-12-05, FRA-BKK-2026-12-22, +22 more |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 75, max 753; allowed 10 to 10000 |
| google_flights | row_count | warn | 61 | within 20% of 82 | -25.6% against the trailing median |
| google_flights | median_price | pass | 115.0 | within 25% of 119 | -3.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |
| ryanair | data_present | pass | 4136 | >0 |  |
| ryanair | columns | pass |  |  |  |
| ryanair | invalid_rows | pass | 0 | 0 |  |
| ryanair | coverage | pass | 0.98 | >=0.95 | 96 of 98 found; missing FDH-6, PAD-6 |
| ryanair | duplicates | pass | 0 | 0 |  |
| ryanair | price_range | pass | 0 | 0 | min 14.99, max 479.02; allowed 1 to 1000 |
| ryanair | row_count | pass | 4136 | within 20% of 4214 | -1.9% against the trailing median |
| ryanair | median_price | pass | 57.99 | within 25% of 52.7 | +10.0% against the trailing median |
| ryanair | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-10 | pass | fail (1 warn, 3 fail) | pass |
| 2026-11-09 | pass | fail (1 warn, 4 fail) | pass |
| 2026-11-08 | pass | pass | pass |
| 2026-11-07 | pass | pass | pass |
| 2026-11-06 | pass | pass | pass |
| 2026-11-05 | pass | pass | pass |
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-03 | pass | pass | pass |
