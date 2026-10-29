# Phase 4 — Ranking and Top 20 Stock Selection

Phase 4 consumes validated Phase 3 output. It determines monthly selections only;
it does not recalculate raw factors, standardize scores, allocate capital, or
execute trades. The fixed current S&P 500 universe remains unchanged.

## Official monthly formations

`monthly_formation_dates(sessions)` returns the **last valid supplied SPY session
in each calendar month** of the official 2016-01-01 through 2025-12-31 period.
Use the complete validated Phase 1 SPY calendar, including warm-up if available.
Do not derive formation dates from stock-specific scores or a generic weekday
calendar. Weekends and exchange holidays are not synthesized.

As explicitly approved in the Phase 4 request, the first official formation is
January 2016 month-end: **2016-01-29** in the existing SPY cache. There is no
December 2015 official formation. This resolves the previously documented
December 2015 momentum warm-up boundary without changing lookbacks or fabricating
an initial signal. The last official formation is **2025-12-31**. Warm-up and
post-2025 observations never become official selection dates.

Calendar validation reuses the existing session checks: unsorted dates are sorted;
duplicate, missing, timezone-aware, or intraday dates are rejected. Weekends are
also rejected. Every official month must be represented, so an absent month or
a short calendar slice cannot silently reduce the baseline schedule. Month
presence alone cannot certify that every actual SPY session was downloaded;
complete monthly coverage remains a prerequisite from Phase 1. Do not pass an
unfinished-month calendar or infer exchange holidays inside this module.

Formation answers which stocks are selected using information at that session.
The requested later convention is implementation on the next eligible trading
day, but **Phase 4 neither generates nor executes those trades**. January cash,
allocation, execution prices, and final-period execution are left to later phases.

## Ranking inputs and exact-date eligibility

`rank_and_select(scored_factors, sessions=...)` accepts existing Phase 3 data with:

```text
date, ticker, eligible, composite_score
```

Canonical raw-factor and factor-score columns are preserved when provided. No
Phase 2/3 calculations are repeated. The Phase 3 producer remains responsible
for its all-four-valid-factor eligibility rule and composite calculation.

Only rows on the **exact SPY formation session**, marked eligible by Phase 3 and
having a finite composite score, enter ranking. Missing/unknown eligibility is
not considered eligible. NaN and either infinity in the composite are excluded.
There is no preceding-session substitution, future-score lookup, interpolation,
forward/back filling, score repair, or missing-score replacement. A valid zero
or negative composite remains a valid score.

Identifiers, daily dates, unique date/ticker keys, Boolean eligibility, and real
numeric composite schemas are validated. Official-period dates must belong to
the supplied SPY clock. SPY cannot be a candidate stock. Already-ranked inputs
and malformed/ambiguous schemas raise errors. Input DataFrames and values are
not changed; unrelated extra columns are not carried into the canonical output.

## Deterministic ranking and selection

Within each formation date:

1. Sort `composite_score` **descending**.
2. Resolve **exact** score ties using canonical Yahoo `ticker` **ascending**.
3. Assign unique sequential integer `rank` values: 1, 2, 3, ... .
4. Set `selected = (rank <= BASELINE.top_n)`.

The existing configuration supplies the locked integer `top_n=20`; no alternative
Top N parameters, sensitivity analysis, or optimization framework were added.
Near-equal scores are not rounded into ties. Alphabetical tie-breaking is purely
for reproducibility, not another factor. Market cap, liquidity, volatility,
input row order, and random state do not resolve ties.

At least 20 eligible stocks produces exactly 20 selections. Fewer than 20 means
select all available eligible stocks; zero means select none. Invalid stocks,
stale scores, and fabricated rows are never added to fill the count. An absent
security is not removed from the saved fixed universe because it does not rank.

## Reusable outputs

```python
import pandas as pd
from mft109.ranking import rank_and_select

# scored and spy_data are from the existing validated Phase 1 → 2 → 3 workflow.
result = rank_and_select(scored, sessions=pd.DatetimeIndex(spy_data["date"]))
ranked = result.ranked
selected = result.selected
shortages = result.formation_summary.loc[result.formation_summary.fewer_than_top_n]
```

`MonthlySelection` exposes:

- `ranked`: full ranked eligible universe, ordered by formation date and rank.
  Columns include `formation_date`, `ticker`, unchanged `composite_score`, integer
  `rank`, and Boolean `selected`, plus the Phase 3 eligibility/raw/score columns
  available in the input. `formation_date` is the exact Phase 3 date renamed.
- `selected`: a separate copy of rows whose selected flag is True.
- `formation_summary`: **all 120 official dates**, with `eligible_count`,
  `selected_count`, and `fewer_than_top_n`. This explicitly records shortages,
  including zero-stock months even when no ranked row exists for that date.

Zero diagnostic counts are not imputed scores or placeholder stock rows.
No output includes portfolio weights, trade quantities, cash allocation,
execution prices/dates, holdings, turnover, costs, NAV, benchmark returns,
performance metrics, optimization, or dashboard logic. No market data is fetched
or written by the ranking API. No dependencies or baseline settings were changed.

Changing later scores or next-month eligibility cannot change an earlier
formation's ranking. The authoritative calendar is independent of stock data.
Repeated execution and shuffled input produce identical results.

## Validation record

Validated on 2026-10-29:

- **159 passed, 0 failed/errors, 0 skipped**: all 116 existing Phase 0–3 tests and
  43 new Phase 4 tests. Coverage includes actual-session month boundaries,
  January 2016 start, holiday/weekend handling, duplicate/partial calendars,
  descending scores, exact ties, the twentieth-stock tie boundary, unique ranks,
  per-date isolation, invalid scores, shortages/zero stocks, no stale-score
  substitution, input/score preservation, deterministic shuffling, future-data
  invariance, and exclusion of Phase 5 outputs.
- Dependency check, `git diff --check`, and new-file whitespace checks pass.
- Read-only cached sample: first 40 cached tickers in saved-universe order, plus
  FISV, SNDK, Q, FDXF, HONA, and VYLR: **46 securities**, including the three
  without history. The complete fixed universe still contains 503 securities.
  This sample validates the implementation; it is not a full-universe backtest
  or a replacement research universe.
- Existing Phase 1 caches → unchanged Phase 2 functions → unchanged Phase 3
  scoring → Phase 4 produced **120 formations**, first **2016-01-29**, last
  **2025-12-31**. The sample had **38–41 eligible stocks**, **no months below
  20**, **4,768 ranked rows**, and **2,400 selected rows**.
- Independent plain-Python sorting of Phase 3 scores verified the complete order,
  sequential ranks, and Top 20 membership for **all 120 dates**. Selected sample
  checks at 2016-01-29, 2020-12-31, 2025-11-28, and 2025-12-31 had respectively
  39, 39, 40, and 40 eligible stocks; all selected exactly 20. Exact-score ties and
  shortage behavior were additionally verified with deterministic synthetic data.
- No ineligible stock entered ranking. FDXF/HONA/VYLR remained unavailable and
  were not substituted. Phase 3 composite values and inputs were checked
  unchanged. Cache checksums and universe fingerprints were validated; no market
  data was downloaded, refreshed, or modified. Shuffled scored data gave identical
  ranked results and monthly counts.

The existing Phase 1 invalid-date fixture emits a pandas parsing warning and
mocked failure tests emit expected logs; all pass. No new Phase 4 warnings or
unresolved Phase 4 methodological decisions remain. Previously documented
survivorship bias, unavailable histories, and source Volume limitations persist.

Specifications, baseline configuration, dependencies, prior-phase code/tests,
fixed-universe files, and market caches were verified unchanged by content hashes.
Portfolio, execution, costs, and backtest modules remain placeholders. Work is
left uncommitted on `phase-4-ranking-selection` for review. No push, PR, merge,
or Phase 5 implementation is included. Begin later allocation/execution work only
after review and explicit instruction.
