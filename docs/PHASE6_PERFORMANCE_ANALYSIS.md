# Phase 6 — Performance Analysis

This layer analyzes validated Phase 5 output for the Multi-Factor Strategy and
SPY Buy-and-Hold. The official evaluation period remains 2016-01-01 through
2025-12-31. It does not recompute signals, selections, weights, costs or NAV.
The implementation is in `mft109/analysis/performance.py`; it performs no I/O
and introduces no dependencies.

## Formulas and return-period convention

The first observed NAV is an initial-value anchor, not an earned return period.
Phase 5 supplies a zero return on that first observation. With `K` observed
official closes there are `N = K - 1` close-to-close return periods. The cached
official sample has 2,514 closes and **2,513 return periods**. Both CAGR and
volatility exclude only the initial anchor. All subsequent zero-return cash days
are retained; the sample is not shortened to the first stock purchase.

| Metric | Formula |
| --- | --- |
| Cumulative Return | `final_NAV / initial_NAV - 1` |
| Annualized Return | `(final_NAV / initial_NAV) ** (252 / N) - 1` |
| Annualized Volatility | `std(close_to_close_returns, ddof=1) * sqrt(252)` |
| Sharpe Ratio | `annualized_return / annualized_volatility` |
| Running peak | Cumulative maximum of NAV, including the initial anchor |
| Daily drawdown | `NAV / running_peak - 1` |
| Maximum Drawdown | Minimum daily drawdown; zero or negative |

Annualized return uses a logarithmic equivalent of CAGR for numeric stability.
It is not arithmetic mean return times 252. The approved simplified Sharpe uses
CAGR, with **risk-free rate 0%**, and no Treasury series. Zero volatility gives
undefined Sharpe (NaN). These are the project's conventions, not a claim that
CAGR-based Sharpe equals a mean-excess-return Sharpe.

## Input and output

```python
from mft109.analysis.performance import analyze_performance

# result is the unchanged BacktestResult from Phase 5; sessions are validated SPY dates.
analysis = analyze_performance(result.daily, sessions=sessions)
summary = analysis.performance_summary
annual = analysis.annual_returns
daily = analysis.daily_performance
```

`PerformanceAnalysis` exposes three reusable DataFrames:

- `performance_summary`: `Metric`, `Strategy`, `SPY`, with the five required metrics.
- `annual_returns`: `Year`, `Strategy`, `SPY`, `Anchor Date`, `End Date`, `Partial Year`.
- `daily_performance`: unchanged `date`, `strategy_return`, `strategy_nav`,
  `portfolio_value_usd`, `spy_return`, `spy_nav`, plus `strategy_drawdown` and
  `spy_drawdown`.

Returns and drawdowns are decimal fractions. Sharpe is dimensionless. Computation
contains no subjective interpretation. Tables can later be exported with pandas
`to_csv(..., index=False)` to ignored `outputs/baseline/` paths or consumed by a
presentation layer. Generated result artifacts are not tracked.

Both initial NAVs must remain exactly 1 and initial strategy capital USD 100,000.
Portfolio value must equal `100000 * strategy_NAV` within relative tolerance
`1e-12` and absolute tolerance `1e-8` USD. Source returns, NAVs and USD values are
preserved; the layer does not rebase or reset them at year boundaries.

## Annual returns

For each year after the first, divide that year's final observed NAV by the
preceding calendar year's final observed NAV, then subtract 1. This includes the
first January session's return. The first year uses its first official NAV anchor;
the SPY first anchor is the 2016-01-04 adjusted close, as already defined in Phase 5.
The last observed session is used, even when December 31 is a weekend or holiday.
There is no annual Sharpe or annual drawdown calculation.

For partial samples, a year is flagged partial if its first or last observation
falls more than seven calendar days from the corresponding year boundary. If a
calendar year is absent, the next observed year is flagged partial and uses its
own first NAV as anchor instead of labeling a multi-year return as an annual
return. Absent years receive no fabricated rows. This flag diagnoses boundary
coverage; it does not certify every internal session. Passing the official SPY
clock to `analyze_performance` validates exact full-session coverage, including
all ten official years. Omit the clock only for intentional partial-sample work.

## Validation and edge cases

- Empty data raise a clear error.
- A single observation gives cumulative return 0 and maximum drawdown 0;
  annualized return, volatility and Sharpe are NaN. One return period permits
  CAGR but not sample volatility or Sharpe.
- Missing, nonfinite or nonpositive NAV, missing/nonfinite returns, invalid capital,
  duplicate dates, timezone-aware dates and intraday dates are rejected.
- Unsorted observations are copied and sorted chronologically. Source inputs
  are never mutated, filled, interpolated or silently dropped.
- Return and NAV dates must match exactly. The initial return must be zero;
  later returns must match adjacent NAV ratios within `rtol=1e-10, atol=1e-12`.
- Official wrapper observations outside 2016–2025 are rejected. Supplied SPY
  sessions must match the complete official output dates exactly.
- Low-level `performance_metrics`, `drawdown_series` and `annual_returns` can
  analyze explicit finite samples independently. A newly anchored subperiod must
  explicitly supply its zero-return starting anchor; no anchor is invented.

Daily running peaks and drawdowns are causal. Changing future observations cannot
change earlier daily drawdowns or a calculation explicitly restricted to an
earlier completed sample. Full-sample metrics intentionally describe the full
supplied sample and should not be treated as historical signals.

## Reproducibility and validation

Run the complete deterministic suite and repository checks:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B -m pip --no-cache-dir check
git diff --check
```

For the official validation, load the unchanged fixed universe; verify saved
market-cache manifest checksums and universe fingerprints; run Phase 1 validation
on the cached frames; then call the existing functions in order:

```python
raw = calculate_raw_factors(market_data, sessions=sessions, tickers=fixed_tickers)
scored = score_factors(raw)
selection = rank_and_select(scored, sessions=sessions)
result = run_backtest(selection, market_data, spy_adjusted_close, sessions=sessions)
analysis = analyze_performance(result.daily, sessions=sessions)
```

The 503-security universe, 500 saved stock histories and unavailable names
FDXF/HONA/VYLR are preserved. Cache-only validation must not use downloader
fallbacks. Both final NAVs and the USD value match the previously validated Phase 5
run exactly. Independent scalar CAGR, sample standard deviation, drawdown and all
annual-return calculations match the analysis tables. Phase 5 inputs and protected
prior-phase/data file hashes are unchanged. No data downloads or cache writes occur.

`tests/test_performance_analysis.py` covers formulas, anchor counting, constant and
single-point samples, drawdowns, calendar-year linking, partial-year flags,
validation errors, input immutability and future-data invariance. Existing tests
also continue to validate the unchanged Phase 0–5 system.

## Boundaries

Fixed-current-universe survivorship bias and the academic execution conventions
documented in Phase 5 still apply. Empirical results do not change these assumptions.
No optimization, sensitivity analysis, parameter experiments, alternative weights,
alternative costs, alternative lookbacks or Streamlit functionality is implemented.
Phase 7 has not started. Stop for Phase 6 review before proceeding.
