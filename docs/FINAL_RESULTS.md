# Final Validated Results

Official source: [final package v1](../outputs/final_report/v1/manifest.json),
using revised-data vintage `fisv_revision_20261029T170124Z`. This is historical
in-sample evidence for the locked baseline, not a claim of causal or universal
superiority. [Methodology](FINAL_METHODOLOGY.md) and [limitations](LIMITATIONS.md)
are part of interpreting these results.

## Baseline and Strategy vs SPY

Fixed current S&P 500 snapshot; four 25% factor scores; monthly Top 20 equal-weight
portfolio; next-session adjusted-close execution; 10 bps turnover costs; USD
100,000 initial capital; 0% risk-free rate. Official evaluation: 2016–2025.

| Metric | Strategy | SPY Buy-and-Hold |
| --- | ---: | ---: |
| Final NAV | 6.225346615575381 | 4.002530196823173 |
| Cumulative return | 522.534662% | 300.253020% |
| CAGR | 20.126153% | 14.921489% |
| Annualized volatility | 23.057786% | 18.007274% |
| Sharpe, CAGR/volatility | 0.872857 | 0.828637 |
| Maximum drawdown | -35.452505% | -33.717264% |
| Final strategy portfolio value | USD 622,534.6615575381 | Not supplied as a USD portfolio |

Strategy's historical CAGR and simplified Sharpe are higher, but annualized
volatility and maximum drawdown are also higher. Higher terminal wealth is not
proof of lower risk or future outperformance. SPY's exported USD cell is blank;
no new benchmark dollar-account assumption is introduced.

There are 2,514 official daily NAV observations and 2,513 actual return periods.
The strategy remains cash until its first execution on 2016-02-01. All subsequent
cash-day zero returns remain included in performance and descriptive statistics.

## Annual returns and drawdowns

| Year | Strategy | SPY |
| --- | ---: | ---: |
| 2016 | 17.662258% | 13.585736% |
| 2017 | 35.730965% | 21.705423% |
| 2018 | 1.367210% | -4.569020% |
| 2019 | 27.249688% | 31.223860% |
| 2020 | 41.503183% | 18.331619% |
| 2021 | 16.682544% | 28.728756% |
| 2022 | -6.550883% | -18.175363% |
| 2023 | 35.425748% | 26.175801% |
| 2024 | 27.714023% | 24.886476% |
| 2025 | 13.241620% | 17.719051% |

Strategy's annual return exceeds SPY in seven of ten years; SPY leads in 2019,
2021 and 2025. Strategy's highest calendar-year return is 2020, and its only
negative calendar year is 2022. These observations summarize the supplied period,
not a forecast or explanation of the causes.

Both series reach their sample maximum drawdown on 2020-03-23. Strategy's decline
from its own running peak is approximately 35.45%, compared with SPY's 33.72%.
The exported daily series preserve all observations; no annual aggregation is
used in NAV or drawdown figures. Static report figures do not alter the approved
Streamlit chart settings.

## Phase 10A distributions and normality

The statistical sample excludes only the synthetic 2016-01-04 zero anchor,
following Phase 6. Both series have 2,513 aligned actual returns, 2016-01-05 through
2025-12-31, with no missing-pair exclusions. All legitimate extremes and later
zeros are retained.

| Daily-return statistic | Strategy | SPY |
| --- | ---: | ---: |
| Mean | 0.083366% | 0.061655% |
| Median | 0.118532% | 0.073115% |
| Sample SD | 1.452504% | 1.134352% |
| Minimum | -12.362296% | -10.942366% |
| Maximum | 13.205530% | 10.501940% |
| Skewness | -0.226640 | -0.320631 |
| Fisher excess kurtosis | 10.151643 | 14.732943 |
| Jarque–Bera | 10,764.357409 | 22,673.307197 |
| Natural log p-value | -5,382.178704 | -11,336.653598 |
| Conclusion at alpha 0.05 | Reject H0 | Reject H0 |

Stored p-values are 0.0 due to floating-point underflow, not exact zero
probability. Finite log p-values are preserved. Descriptive shape estimates use
bias correction; standard Jarque–Bera uses moment estimators internally.

Negative skewness, substantial positive excess kurtosis and Q-Q tail departures
support non-normal marginal-return behavior in this sample. Strategy has higher
mean and daily SD; SPY has greater excess kurtosis. Financial dependence and
volatility clustering limit textbook p-value calibration. Rejecting normality
does not invalidate the backtest, establish causality or determine strategy
quality. See [Phase 10A](PHASE10A_DATA_ANALYSIS.md) for conventions and complete
quartiles; its approved CSVs and four figures are copied byte-for-byte.

## One-at-a-time sensitivity

All 21 reported rows complete the official period. Six are repeated baseline
rows; the package preserves catalog order and does not rank scenarios as winners.

| Dimension | Tested settings | Historical CAGR range |
| --- | --- | ---: |
| Top N | 10,20,30,50 | 17.9130%–26.8482% |
| Cost | 0,5,10,20 bps | 19.1912%–21.0678% |
| Frequency | Monthly, quarterly | 20.1262%–20.7925% |
| Volatility window | 20,60,120 sessions | 19.3168%–21.6152% |
| Reversal window | 5,10,20 sessions | 20.1262%–25.8816% |
| Factor weights | Equal and four 40% tilts | 17.5676%–25.9455% |

Top 10 has higher observed CAGR (26.8482%) but higher volatility (27.1166%) and
worse maximum drawdown (-39.0956%) than Top 20. Quarterly rebalancing has CAGR
20.7925% and maximum drawdown -35.6035%; this is not an isolated execution-only
comparison because its first investment is later. Five-session reversal has
CAGR 25.8816%, Sharpe 1.1376 and drawdown -34.4434%, but remains an in-sample
sensitivity result, not a new baseline.

At 0 versus 20 bps the observed CAGR is 21.0678% versus 19.1912%, illustrating
cost sensitivity under the existing turnover model. Reversal-weight tilt has
maximum drawdown -44.5668%; low-volatility tilt has lower annualized volatility
18.0508% but lower CAGR 17.5676%. These trade-offs should be shown rather than
selecting the highest historical return.

**The official baseline remains Top 20, monthly, 10 bps, volatility 60, reversal
20, and four equal 25% factor weights.** No out-of-sample selection experiment,
new optimizer or parameter change is inferred from these comparisons.
