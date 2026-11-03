# Data quality

Latest check: 2026-11-03

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| eurostat | data_present | pass | 1306 | >0 |  |
| eurostat | series_present | pass | 6 | 6 |  |
| eurostat | row_count | skip | 1306 |  | no earlier check |
| eurostat | missing_months | pass | 0 | 0 |  |
| eurostat | invalid_values | pass | 0 | 0 |  |
| eurostat | latest_period | pass | 2 | <=2 months old | newest month is 2026-09 |
| eurostat | latest_change | pass | 0.122 | <0.4 | largest latest-month move, CP07331 I25 |
| google_flights | data_present | pass | 76 | >0 |  |
| google_flights | columns | pass |  |  |  |
| google_flights | invalid_rows | pass | 0 | 0 |  |
| google_flights | coverage | pass | 0.95 | >=0.95 | 76 of 80 found; missing FRA-BER-2027-02-01, FRA-PMI-2027-02-01, MUC-BER-2026-11-10, MUC-BER-2026-12-03 |
| google_flights | duplicates | pass | 0 | 0 |  |
| google_flights | price_range | pass | 0 | 0 | min 70, max 1623; allowed 10 to 10000 |
| google_flights | row_count | skip | 76 |  | 0 earlier snapshots, need 3 |
| google_flights | median_price | skip | 147.5 |  | 0 earlier snapshots, need 3 |
| google_flights | snapshot_gap | skip |  |  | no earlier snapshot |
| ryanair | data_present | pass | 5111 | >0 |  |
| ryanair | columns | pass |  |  |  |
| ryanair | invalid_rows | pass | 0 | 0 |  |
| ryanair | coverage | pass | 0.986 | >=0.95 | 359 of 364 found; missing BRE-21, BRE-22, BRE-23, BRE-24, BRE-25 |
| ryanair | duplicates | pass | 0 | 0 |  |
| ryanair | price_range | pass | 0 | 0 | min 14.99, max 318.99; allowed 1 to 1000 |
| ryanair | row_count | skip | 5111 |  | 0 earlier snapshots, need 3 |
| ryanair | median_price | skip | 43.75 |  | 0 earlier snapshots, need 3 |
| ryanair | snapshot_gap | skip |  |  | no earlier snapshot |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-03 | pass | pass | pass |
