# Data quality

Latest check: 2026-11-10

| Source | Check | Status | Value | Expected | Detail |
|---|---|---|---|---|---|
| google_flights | scrape | fail |  |  | 5 Google searches failed in a row |
| google_flights | data_present | fail | 0 | >0 | no fares for this date |

## Last 30 days

Each cell is the worst result that day, with warning and failure counts.

| Date | eurostat | google_flights | ryanair |
|---|---|---|---|
| 2026-11-10 | not checked | fail (0 warn, 2 fail) | not checked |
| 2026-11-09 | pass | fail (1 warn, 4 fail) | pass |
| 2026-11-08 | pass | pass | pass |
| 2026-11-07 | pass | pass | pass |
| 2026-11-06 | pass | pass | pass |
| 2026-11-05 | pass | pass | pass |
| 2026-11-04 | pass | warn (1 warn, 0 fail) | pass |
| 2026-11-03 | pass | pass | pass |
