# Data quality

Latest check: 2026-11-18

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| eurostat | data_present | pass | 1312 | >0 |  |
| eurostat | series_present | pass | 6 | 6 |  |
| eurostat | row_count | pass | 1312 | >=1306 |  |
| eurostat | missing_months | pass | 0 | 0 |  |
| eurostat | invalid_values | pass | 0 | 0 |  |
| eurostat | latest_period | pass | 1 | <=2 months old | newest month is 2026-10 |
| eurostat | latest_change | pass | 0.133 | <0.4 | largest latest-month move, CP07332 I25 |
| google_flights | data_present | pass | 97 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 1.0 | >=0.95 | 97 of 97 found |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 67, max 1084; allowed 10 to 10000 |
| google_flights | row_count | pass | 97 | within 20% of 92 | +5.4% against the trailing median |
| google_flights | median_price | pass | 115.0 | within 25% of 119 | -3.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |
| ryanair | data_present | pass | 4432 | >0 |  |
| ryanair | columns | pass |  |  |  |
| ryanair | invalid_rows | pass | 0 | 0 |  |
| ryanair | coverage | pass | 1.0 | >=0.95 | 98 of 98 found |
| ryanair | duplicates | pass | 0 | 0 |  |
| ryanair | price_range | pass | 0 | 0 | min 14.99, max 511.94; allowed 1 to 1000 |
| ryanair | row_count | pass | 4432 | within 20% of 4223 | +4.9% against the trailing median |
| ryanair | median_price | warn | 76.99 | within 25% of 59.49 | +29.4% against the trailing median |
| ryanair | snapshot_gap | pass | 0 | 0 |  |
| wizzair | data_present | pass | 2759 | >0 |  |
| wizzair | columns | pass |  |  |  |
| wizzair | invalid_rows | pass | 0 | 0 |  |
| wizzair | coverage | pass | 1.0 | >=0.85 | 70 of 70 found |
| wizzair | duplicates | pass | 0 | 0 |  |
| wizzair | price_range | pass | 0 | 0 | min 24.99, max 449.99; allowed 5 to 1000 |
| wizzair | row_count | skip | 2759 |  | 1 earlier snapshots, need 3 |
| wizzair | median_price | skip | 79.99 |  | 1 earlier snapshots, need 3 |
| wizzair | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair | wizzair |
|---|---|---|---|---|
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
