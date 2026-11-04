# Final Locked Methodology

This consolidates [PROJECT_REQUIREMENTS.md](../PROJECT_REQUIREMENTS.md) and the
validated implementation. It introduces no new assumptions. The official result
set is the approved revised Yahoo dataset, identified in the final package
manifest and [FISV provenance](FISV_DATA_REVISION.md).

## Market, universe and data

- U.S. equities; fixed snapshot of **503 current S&P 500 constituent securities**
  used throughout history. Historical membership is not reconstructed. This
  introduces survivorship bias; unavailable constituents remain in the universe.
- Yahoo Finance through pinned yfinance. Daily OHLCV; calendar download boundaries
  2015-01-01–2025-12-31 inclusive. The provider adapter accounts for its exclusive
  API end boundary. Calendar 2015 is warm-up, not reported strategy performance.
- Official backtest: 2016-01-01–2025-12-31. Actual official SPY sessions:
  2016-01-04–2025-12-31, 2,514 observations.
- A consistent adjusted-price series is used for factors, returns, execution and
  valuation. The installed yfinance behavior is handled explicitly; `Adj Close`
  is not assumed to exist. Liquidity uses Yahoo-reported Volume.
- Cache identities/checksums, fixed-universe provenance and available date coverage
  are validated. Cached valid histories are reused. No ticker splicing or vendor
  substitution is used to fill FDXF/HONA/VYLR. See [data gaps](PHASE1_1_DATA_GAP_REVIEW.md).

## Four factors

Let P be adjusted price, V reported Volume, and t an actual trading-session
position. All required input observations must exist.

| Factor | Exact raw definition | Final standardized score | Weight |
| --- | --- | --- | ---: |
| 12–1 month momentum | `P(i,t-21)/P(i,t-252)-1` | `M=Z(Momentum)` | 25% |
| 60-day low volatility | `r(i,t)=P(i,t)/P(i,t-1)-1`; `Std(r(i,t-59:t),ddof=1)*sqrt(252)` | `LV=-Z(Volatility)` | 25% |
| 20-day liquidity | `DV=P*V`; `ADV20=mean(DV(i,t-19:t))`; `LiquidityRaw=ln(ADV20)` | `L=Z(LiquidityRaw)` | 25% |
| 20-day short-term reversal | `-(P(i,t)/P(i,t-20)-1)` | `R=Z(Reversal)` | 25% |

Momentum skips the most recent 21 sessions. Volatility needs 60 consecutive
returns (61 valid prices); liquidity needs 20 consecutive valid price/volume
pairs and positive ADV20. Reversal's negative-return definition is not negated
again in scoring. Missing input windows produce NaN, never fabricated factors.

At each formation, only stocks with all four finite raw factors are eligible.
Use the same eligible cross-section for every factor:

`Z(X) = (X - cross-sectional mean) / cross-sectional SD(ddof=0)`

Exactly constant valid factors receive neutral zero scores; this is not missing
factor imputation. Ineligible rows keep NaN. No winsorization, forward/back fill,
mean fill, interpolation, stale-score substitution or partial reweighting occurs.

`CompositeScore = 0.25*M + 0.25*LV + 0.25*L + 0.25*R`

Higher is preferred for all final scores. Rank by composite descending, then
ticker ascending; ranks are sequential and unique. Select Top 20 eligible stocks.

## Portfolio, execution and costs

Formation uses information available at the final SPY session of each month.
Execution is strictly the next eligible official SPY session, at its adjusted
close. Old holdings earn that day's close-to-close movement; newly allocated
holdings earn returns only after the execution close. No future information is
used to form the signal.

Normal targets are 20 stocks at 5% each. Only selected executable stocks may
receive weights, equally allocated across those with valid positive entry prices;
rank 21 is not substituted. No executable names means cash. Missing held-stock
valuation stops the run explicitly; it is not forward-filled or fabricated.
Positions use fractional adjusted-price units, fixed between rebalances, allowing
natural weight drift. Cash earns 0%; no separate dividend cash flow is double-counted.

There are 120 formations and 119 executions. First formation/execution:
2016-01-29 / 2016-02-01. Earlier official dates remain cash, NAV 1, USD 100,000.
The 2025-12-31 formation is an unexecuted signal inside the official period;
no 2026 trade or target is invented.

Over the union of stocks **and cash**, using execution-date pre-cost drifted
weights:

```text
turnover = 0.5 * sum(abs(target_weight - pre_rebalance_weight))
cost_fraction = turnover * 0.001
cost_usd = pre_cost_wealth * cost_fraction
post_cost_wealth = pre_cost_wealth * (1 - cost_fraction)
```

The 10 bps baseline cost is charged once. Initial cash-to-stock turnover is 1.
[Phase 5](PHASE5_PORTFOLIO_BACKTEST.md) records the validated accounting order.

## Benchmark and metrics

SPY Buy-and-Hold uses adjusted prices and the same official session period,
anchored at its first official close. It is a separate benchmark, not a strategy
constituent, and is not charged strategy turnover costs.

Initial strategy capital is USD 100,000; initial strategy/SPY NAV is 1. With K
closes there are N=K−1 actual close-to-close returns. The first synthetic zero
anchor is excluded from return statistics, while all subsequent genuine zeros
are retained. Here K=2,514 and N=2,513.

| Metric | Convention |
| --- | --- |
| Cumulative return | `final_NAV/initial_NAV - 1` |
| Annualized return / CAGR | `(final_NAV/initial_NAV)^(252/N)-1` |
| Annualized volatility | `Std(actual_daily_returns,ddof=1)*sqrt(252)` |
| Sharpe | `CAGR/annualized_volatility`, risk-free rate 0% |
| Drawdown | `NAV/running_max_NAV - 1` |
| Maximum drawdown | Minimum daily drawdown |

The CAGR-based Sharpe is the approved simplified convention, not an arithmetic
mean-excess-return Sharpe. Annual returns use actual year-end NAV versus preceding
year-end NAV, with the first official NAV as the 2016 anchor. Warm-up observations
are never included. Return, weight and drawdown CSV values are decimal fractions;
Sharpe is dimensionless. Strategy USD value equals initial capital times NAV.

## Sensitivity and descriptive analysis

Six predefined one-at-a-time groups: Top N {10,20,30,50}; cost {0,5,10,20} bps;
frequency {monthly,quarterly}; volatility window {20,60,120}; reversal window
{5,10,20}; weights {equal, each single-factor 40% tilt with others 20%}.

There are 21 reported rows including six identical baseline rows: 16 unique
configurations. Other dimensions stay at baseline. There is no Cartesian grid,
automatic best-parameter selection or baseline replacement. See
[Phase 7](PHASE7_SENSITIVITY_ANALYSIS.md).

[Phase 10A](PHASE10A_DATA_ANALYSIS.md) separately diagnoses the 2,513 aligned
Strategy/SPY actual daily returns from 2016-01-05–2025-12-31. It uses sample SD,
bias-corrected skewness and Fisher excess kurtosis, and standard Jarque–Bera at
alpha 0.05. No returns are winsorized or filled. These diagnostic outputs do not
change trading methodology or validated financial results.
