# Data quality

Latest check: 2026-11-21

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| eurostat | data_present | pass | 1312 | >0 |  |
| eurostat | series_present | pass | 6 | 6 |  |
| eurostat | row_count | pass | 1312 | >=1312 |  |
| eurostat | missing_months | pass | 0 | 0 |  |
| eurostat | invalid_values | pass | 0 | 0 |  |
| eurostat | latest_period | pass | 1 | <=2 months old | newest month is 2026-10 |
| eurostat | latest_change | pass | 0.133 | <0.4 | largest latest-month move, CP07332 I25 |
| google_flights | data_present | pass | 94 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 1.0 | >=0.95 | 94 of 94 found |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 59, max 900; allowed 10 to 10000 |
| google_flights | row_count | pass | 94 | within 20% of 94.5 | -0.5% against the trailing median |
| google_flights | median_price | pass | 115.0 | within 25% of 119 | -3.4% against the trailing median |
| google_flights | snapshot_gap | pass | 0 | 0 |  |
| ryanair | data_present | pass | 4430 | >0 |  |
| ryanair | columns | pass |  |  |  |
| ryanair | invalid_rows | pass | 0 | 0 |  |
| ryanair | coverage | pass | 0.99 | >=0.95 | 97 of 98 found; missing SCN-6 |
| ryanair | duplicates | pass | 0 | 0 |  |
| ryanair | price_range | pass | 0 | 0 | min 14.99, max 522.58; allowed 1 to 1000 |
| ryanair | row_count | pass | 4430 | within 20% of 4269 | +3.8% against the trailing median |
| ryanair | median_price | pass | 74.99 | within 25% of 71.615 | +4.7% against the trailing median |
| ryanair | snapshot_gap | pass | 0 | 0 |  |
| wizzair | data_present | pass | 2736 | >0 |  |
| wizzair | columns | pass |  |  |  |
| wizzair | invalid_rows | pass | 0 | 0 |  |
| wizzair | coverage | pass | 0.986 | >=0.85 | 69 of 70 found; missing FDH-3 |
| wizzair | duplicates | pass | 0 | 0 |  |
| wizzair | price_range | pass | 0 | 0 | min 23.99, max 449.99; allowed 5 to 1000 |
| wizzair | row_count | pass | 2736 | within 20% of 2758 | -0.8% against the trailing median |
| wizzair | median_price | pass | 79.99 | within 25% of 79.99 | +0.0% against the trailing median |
| wizzair | snapshot_gap | pass | 0 | 0 |  |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair | wizzair |
|---|---|---|---|---|
| 2026-11-21 | pass | warn (1 warn, 0 fail) | pass | pass |
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
