# Phase 5 — Portfolio Construction & Backtesting

Implements the approved baseline in `PROJECT_REQUIREMENTS.md` using validated
Phase 4 `MonthlySelection` output. It does not recalculate factors, scores, ranks
or selection membership. No new dependencies are required.

## Modules and API

| Module | Responsibility |
| --- | --- |
| `mft109/portfolio/construction.py` | Equal-weight executable selected stocks and explicit cash target |
| `mft109/backtesting/_inputs.py` | Validate Phase 4 record consistency and adapt adjusted prices without filling |
| `mft109/backtesting/execution.py` | Official SPY sessions and strictly later execution mapping |
| `mft109/backtesting/transaction_costs.py` | Complete-portfolio turnover and locked 10 bps cost |
| `mft109/backtesting/engine.py` | Fixed units, drift, daily accounting and audit records |
| `mft109/benchmark/buy_and_hold.py` | Separate adjusted-price SPY buy-and-hold series |

```python
import pandas as pd
from mft109.backtesting.engine import run_backtest

# monthly_selection is the unchanged rank_and_select(...) result from Phase 4.
# market_data and spy_data are validated normalized Phase 1 observations.
result = run_backtest(
    monthly_selection,
    market_data,
    spy_data.set_index("date")["adjusted_close"],
    sessions=pd.DatetimeIndex(spy_data["date"]),
)
```

The core is executable without Streamlit and performs no downloads or file writes.
The optional `baseline` argument supports shorter synthetic date bounds in tests;
production uses the unchanged `BASELINE`. Economic constants are checked, not
exposed as an optimization grid. Inputs are copied/adapted without mutation.

## Timing and price convention

The official clock is the validated SPY session calendar restricted to
2016-01-01 through 2025-12-31. Warm-up observations do not become official returns.
Phase 4 supplies one formation at the final SPY session of each month. Execution
occurs at the next SPY session **strictly after** formation, at that session's
normalized **adjusted close**. This is a simplified end-of-day academic execution
convention, not an intraday execution simulation. Raw Close, Open and VWAP are
not used by this engine.

Old holdings earn the execution day's close-to-close movement. The new target
starts earning returns only after the execution close. The first formation is
2016-01-29; the first execution is 2016-02-01. All earlier official sessions remain
100% cash with return 0, NAV 1 and value USD 100,000. The strategy does not advance
its start date to the first investment.

Positions are fractional adjusted-price units. Units remain fixed between
rebalances; adjusted-price valuation consistently incorporates the data provider's
corporate-action adjustment. No separate dividend or split cash flow is added.

## Target weights, cash and missing data

Only Phase 4 selected names may receive stock weights. At execution, each selected
name requires a finite, strictly positive adjusted price on that date. Equal
weights are `1 / N` among the executable selected names: normally 20 stocks at
5% each. An unavailable entry is excluded and audited; rank 21 is never used.
There is no forward fill, backward fill, future-price execution or substitution.

Zero executable stocks targets 100% cash and emits a warning, including when
Phase 4 selected no stocks. Existing holdings with valid prices may be sold into
cash and incur turnover costs. Cash earns 0%; fully invested targets have zero
cash. The reserved cash identifier is `__CASH__`, avoiding confusion with a stock
whose ticker is CASH. Cash units are USD; its price field is deliberately NaN.

**Missing held-stock valuation:** if a currently held stock has an absent,
nonfinite or nonpositive adjusted price, the engine logs an error and raises
`MissingHoldingPriceError`. The exception contains `date`, `tickers`, and
`partial_result`, with valid daily accounting only through the preceding session
and a dated `missing_holding_price / stop_without_valuation` event. This also
applies on a rebalance date: an old position cannot be sold at an invented price.
No return or NAV is fabricated for the affected date or subsequent dates. A
partial result is not a completed baseline backtest. Missing unheld prices do not
prevent valuation; unavailable new entries follow the exclusion rule above.

## Drift, turnover and cost order

Every session follows this order:

1. Value the existing stock units at today's adjusted close and add existing cash.
2. Calculate pre-rebalance weights using this pre-cost market value. Units have
   drifted since the last rebalance; weights are not reset daily.
3. On a scheduled execution, determine valid selected names and their equal-weight
   target, including cash.
4. Compute turnover and deduct its transaction cost **once**, from pre-cost wealth.
5. Allocate the remaining post-cost wealth to target units at today's adjusted
   close. These new units apply after this close.

For the union of old and target stocks **and cash**, absent weights are zero:

```text
turnover = 0.5 * sum(abs(target_weight - pre_rebalance_weight))
cost_fraction = turnover * 0.001
cost_usd = pre_cost_wealth * cost_fraction
post_cost_wealth = pre_cost_wealth - cost_usd
```

Cash is counted once. Initial cash weight 1 changing to stock weights totaling 1
has turnover `0.5 * (1 + 1) = 1`: first cost USD 100, leaving USD 99,900 invested.
Complete stock replacement also has turnover 1; unchanged complete weights have
turnover 0. Same stock names may still require turnover because their weights
have drifted. Turnover 0.30 implies cost fraction 0.00030, not 1%.

## Returns, NAV and benchmark

```text
gross_strategy_return = pre_cost_wealth_today / previous_end_of_day_wealth - 1
strategy_return = post_cost_wealth_today / previous_end_of_day_wealth - 1
strategy_NAV = post_cost_wealth_today / 100000
portfolio_value_usd = 100000 * strategy_NAV
```

On non-rebalance days pre- and post-cost wealth are equal. Daily net return
therefore compounds the actual held stocks, cash and event costs. NAV never
resets at a rebalance. Ordinary floating-point reconciliation tolerance applies.

SPY buys and holds from the **first official session's adjusted close**. Its first
return is explicitly 0 and NAV is 1. Later returns use adjacent official adjusted
prices; NAV is current adjusted price divided by the first official adjusted
price. Warm-up returns and future returns are excluded. The benchmark receives
no monthly strategy transaction costs. Missing official SPY prices are an error.

The 2025-12-31 formation is retained in the audit with execution date NaT and
status `not_executed_within_backtest`. Executable count is unknown (NA), rather
than zero; no 2026 price, trade or return is included. Existing holdings are valued
through 2025-12-31 without a mandatory terminal liquidation or extra terminal fee.

## Outputs and safeguards

`BacktestResult` contains five DataFrames:

- `daily`: official date, gross/net strategy return, NAV, USD value, cash weight,
  cost fraction/USD, SPY return and SPY NAV.
- `holdings`: date, ticker, fixed units, adjusted price, USD market value and
  end-of-day weight, including cash.
- `rebalance_audit`: formation/execution dates, status, eligible/selected/executable
  counts, turnover, costs, pre/post wealth, target cash weight and flags.
- `rebalance_weights`: selected/executable flags and pre-rebalance/target weights
  over the union of old holdings, selected names and cash.
- `missing_price_events`: date, applicable formation, ticker, event and action.

Prices are read for the current session only. Selection membership is consumed
only on its mapped execution date. Future inputs cannot change earlier economic
outputs; deterministic sorting makes shuffled input rows produce identical
results. Phase 4 ranks, flags and summary consistency are checked without
recomputing any ranking or score. Every monthly summary, including empty and
final unexecuted signals, must be present. There is no alternative selection rule.

## Validation record

Run from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
git diff --check
```

Phase 5 tests in `tests/test_portfolio_backtest.py` exercise scalar weights,
cash-inclusive turnover, costs, execution timing, held-unit drift, valuation
reconciliation, benchmark prices, missing entry/holding observations, input
immutability, row-order determinism, future-data invariance and phase boundaries.
The complete suite passed **229 tests: 70 new Phase 5 tests and all 159 existing
Phase 0–4 tests**, with zero failures/errors and zero skips. Dependency checking
reported no broken requirements; `git diff --check` passed, and new files were
also checked for trailing whitespace.

The existing full cached universe was checked using saved manifest checksums,
the fixed-universe fingerprint and Phase 1 validation before running the unchanged
Phase 2 → Phase 3 → Phase 4 pipeline and this engine. There were 503 fixed names,
500 saved stock histories and three unavailable histories (FDXF, HONA, VYLR),
which stayed in the universe and naturally remained ineligible. No data downloads
or market-data writes occurred. All 1,041 protected prior-phase/data file hashes
matched their pre-implementation values.

| Cached-run accounting check | Result |
| --- | ---: |
| Official sessions | 2,514 |
| First formation / execution | 2016-01-29 / 2016-02-01 |
| Last formation / executed rebalance | 2025-12-31 / 2025-12-01 |
| Executed rebalances / final unexecuted signal | 119 / 1 |
| Formation months with 20 selected / fewer than 20 | 120 / 0 |
| Executed rebalances with fewer than 20 / zero executable | 0 / 0 |
| Minimum / maximum executable stocks | 20 / 20 |
| Minimum / maximum / mean executed turnover | 0.324150640 / 1.000000000 / 0.653702034 |
| Sum of event cost fractions | 0.0777905421 |
| Sum of nominal USD fees charged | 21,969.932697 |
| Initial / final strategy NAV | 1.000000000 / 6.250502799 |
| Initial / final portfolio USD | 100,000.000000 / 625,050.279934 |
| Initial / final SPY NAV | 1.000000000 / 4.002530197 |
| Missing execution/holding-price events | 0 |

The sum of event cost fractions is an arithmetic sum of event rates, **not**
cumulative wealth drag or a performance metric. The final unexecuted signal is
excluded from executable-count, turnover and cost-rate averages.

Independent scalar checks reconstructed old units at current prices, drifted
weights, executable targets, cash-inclusive turnover and fees on 2016-02-01,
2016-03-01, 2019-06-03, 2022-10-03 and 2025-12-01. Ordinary-day checks on
2016-01-05, 2016-02-17, 2016-05-26, 2023-12-13 and 2025-12-11 verified unchanged
units, zero fees and returns from held units and current prices. Daily holdings
and NAV reconciliation also passed.

FISV's missing 2025-11-12 adjusted price remains NaN. FISV was not held that day,
so this observed data gap did not trigger the held-price stop policy. Synthetic
tests exercise that stop policy, missing-entry exclusions and all-cash outcomes.
The prior-phase invalid-date test emits an expected pandas date-parsing warning.

## Limitations and Phase 6 boundary

This academic convention assumes fractional units, adjusted-close execution and
no additional slippage/market-impact model. Current fixed S&P 500 membership
retains survivorship bias. A missing held price deliberately prevents a complete
run; resolving such a data problem may require a separately approved data or
methodology decision, not an automatic imputation.

These are accounting validation results, not final performance conclusions.
Annualized return, annualized volatility, Sharpe ratio, maximum drawdown,
attribution, optimization, sensitivity analysis and dashboard functionality are
not implemented. Phase 6 has not started. Next action is review and approval of
Phase 5; do not proceed automatically.
