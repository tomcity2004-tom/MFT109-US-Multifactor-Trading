# Phase 2 — Raw Factor Calculation

This phase implements reusable raw factors only. It does not implement Z-scores,
cross-sectional direction transforms, factor weights/composite scores, ranking,
selection, portfolios, backtesting, costs, performance, optimization, or Streamlit.
PROJECT_REQUIREMENTS.md remains the primary specification. The Phase 2 request
explicitly fixes volatility `ddof=1`, complete rolling windows, and inclusion of
the current session in ADV20; no other research assumptions were changed.

## Formulas and boundaries

Here P is Phase 1's normalized adjusted_close and V is its Yahoo-reported Volume.
Offsets count actual trading sessions, not calendar days or available-row counts.

| Output | Formula | First possible valid value with complete inputs |
| --- | --- | --- |
| `momentum` | P(t-21) / P(t-252) - 1 | Session index 252: 253 price-grid positions |
| `volatility60` | sample std of r(t-59), ..., r(t), times sqrt(252), where r(t)=P(t)/P(t-1)-1 | Session index 60: 61 consecutive valid prices |
| `liquidity_raw` | ln(mean of P(s)*V(s) for s=t-19, ..., t) | Session index 19: 20 consecutive valid price/volume pairs |
| `reversal20` | -(P(t)/P(t-20)-1) | Session index 20: 21 price-grid positions |

Volatility uses `ddof=1` and stays raw/nonnegative. There is no multiplication by
-1 or Z-score. Reversal's negative sign is part of its specified raw formula.
Liquidity uses the natural logarithm and requires strictly positive ADV20.
Daily dollar volume, ADV20, and daily returns are independently reusable helpers.

## API and integration

The four existing modules contain the individual calculations; `_inputs.py`
centralizes checks and calendar alignment. Each individual function accepts a
single-stock, date-indexed pandas Series and an explicit `sessions` DatetimeIndex.
Liquidity additionally accepts date-indexed volume. All functions return sorted,
date-indexed Series and leave their inputs unchanged. No dependencies were added.

For multiple stocks, use normalized Phase 1 data and the saved universe:

```python
import pandas as pd
from mft109.factors import calculate_raw_factors

# market_data, spy_data, and universe come from the existing Phase 1 workflow.
# Use all fixed-universe Yahoo symbols in research; subsets are for validation.
raw = calculate_raw_factors(
    market_data,
    sessions=pd.DatetimeIndex(spy_data["date"]),
    tickers=universe["yahoo_ticker"].tolist(),
)
```

Required input columns are `date`, `ticker`, `adjusted_close`, and `volume`.
Unadjusted Close and optional Adj Close fields are not used. Output columns are
`date`, `ticker`, `momentum`, `volatility60`, `liquidity_raw`, and `reversal20`,
sorted by date/ticker. No factor eligibility filter or stock ranking is applied.

The caller must provide the complete, validated session clock from Phase 1 SPY
history, including warm-up, rather than derive dates from a sparse stock. The API
validates the clock's shape, but cannot independently certify that a caller has
supplied every exchange session. It does not synthesize weekdays/holidays.
Unsorted input is sorted; invalid/duplicate dates, duplicate date/ticker rows,
unrequested tickers, SPY in the stock list, or dates outside the calendar raise
clear errors. Structural/nonnumeric input errors are not silently coerced.

The calculator performs no downloads, cache writes, universe changes, or provider
fallback. Use the existing Phase 1 cache validation/loading workflow; there is no
second market-data pipeline. The explicit ticker list preserves unavailable
securities: passing FDXF, HONA, and VYLR yields all-NaN factor series for them when
their histories are absent. It never substitutes FDX, HON, CTVA, or other symbols.

## Missing data and time integrity

- Absent stock dates are aligned to the supplied clock as NaN inputs. Prices,
  volume, and factor values are never forward/back-filled or replaced with zero
  or cross-sectional means. Original market data and caches are not changed.
- Nonfinite/nonpositive prices and nonfinite/negative volume are unavailable
  inputs, matching Phase 1 cleaning. Zero reported volume is allowed; a complete
  all-zero ADV20 yields NaN liquidity because its logarithm is undefined.
- Rolling calculations require all 60 returns or all 20 dollar-volume inputs.
  Missing values are not skipped in a smaller sample. One missing price breaks
  two adjacent daily returns; volatility recovers only after both leave the
  60-return window. No return is computed across a missing session.
- Momentum and reversal use only their specified endpoints. Missing prices
  elsewhere do not invalidate those endpoint-only formulas. Missing either
  required endpoint yields NaN; momentum does not require the current price.
- Overflowing/nonfinite arithmetic yields NaN. No winsorization, outlier clipping,
  price repair, or factor direction processing is performed.
- Each stock is calculated independently with trailing windows and positive
  shifts. Altering future prices/volume or appending future sessions cannot
  change earlier outputs. No future data is used to fill warm-up periods.

Yahoo/yfinance's existing source-null Volume-to-zero limitation remains unchanged.
Later monthly ranking must still require all four valid factor values; this phase
returns each raw factor independently, without implementing that ranking phase.

## Validation record

Validated on 2026-10-29 with the existing Python environment and dependencies:

- Complete suite: **76 passed, 0 failed, 0 skipped** (37 existing + 39 new tests).
- Tests cover independent formulas, exact/off-by-one boundaries, `ddof=1`,
  annualization, gap propagation/recovery, invalid values, ticker isolation,
  chronological ordering, adjusted-price selection, no filling, preservation of
  unavailable stocks, input immutability, and future-data invariance.
- `python -m pip check`: no broken requirements. `git diff --check` and new-file
  whitespace checks passed. No formatter is configured or newly introduced.
- A read-only sample used cached AAPL, FISV, SNDK, Q, and three absent securities
  on 2,766 validated SPY sessions: **19,362 output rows**. Cache checksums and
  universe fingerprints were verified before calculation. No downloads or market
  data writes were performed. An AAPL observation on 2016-03-14 matched all four
  independently computed scalar formulas, using Python `statistics.stdev` for
  volatility.
- AAPL warm-up NaN counts: momentum 252, volatility 60, liquidity 19, reversal 20.
  First valid dates: 2016-01-04, 2015-03-31, 2015-01-30, and 2015-02-02 respectively.
- FISV's 2025-11-12 price row remains missing. November/December 2025 month-end
  volatility is NaN; November liquidity is NaN and December liquidity is valid.
- SNDK/Q momentum stays NaN throughout this capture; FDXF/HONA/VYLR retain all
  four NaN outputs throughout. These are expected data limitations, not failed
  calculations. No first-month signal or initial portfolio was invented to
  bypass the previously documented December 2015 momentum warm-up boundary.
- Existing Phase 1 invalid-date test emits a pandas date-parsing warning. It is
  unchanged and the test passes. No new factor warnings or unresolved
  methodological decisions were identified for this phase.

Specifications, baseline configuration, dependency declarations, fixed universe,
Phase 1 modules, and market-data files were verified unchanged by content hashes.
Phase 3 and all later components remain placeholders. No commits, pushes, merges,
or pull requests are part of this implementation task. Stop for review before
starting Phase 3.
