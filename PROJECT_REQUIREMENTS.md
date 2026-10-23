# MFT109 US Multi-Factor Trading Project

## 1. Project Objective

This project is developed for the MFT109 Financial Algorithmic Trading course.

The objective is to build a Python-based multi-factor stock selection and backtesting system for the U.S. equity market.

The strategy will use a fixed universe of current S&P 500 constituent stocks and compare the strategy performance against SPY Buy-and-Hold.

The system should eventually support:
- Market data acquisition
- Data cleaning
- Descriptive statistics
- Normality analysis
- Factor calculation
- Cross-sectional factor standardization
- Composite factor scoring
- Stock ranking
- Portfolio construction
- Backtesting
- Transaction costs
- Benchmark comparison
- Performance evaluation
- Parameter optimization
- Sensitivity analysis
- Streamlit visualization

---

## 2. Market and Investment Universe

Market:
U.S. Equity Market

Investment Universe:
Current S&P 500 constituent stocks.

The current S&P 500 constituents will be used as a fixed investment universe throughout the entire backtest.

Historical index membership will NOT be reconstructed.

This simplified methodology may introduce survivorship bias and this limitation must be disclosed in the final report.

---

## 3. Data Source

Primary data source:
Yahoo Finance using the Python yfinance library.

Required stock data:
Daily OHLCV data.

Required fields should include:
- Open
- High
- Low
- Close / adjusted price as appropriate
- Volume

Benchmark:
SPY

Data frequency:
Daily.

Approximate data download period:
2015-01-01 to 2025-12-31.

Official backtest period:
2016-01-01 to 2025-12-31.

The additional historical data before the official backtest period is used as warm-up data for factor calculations.

---

## 4. Factor 1 — Momentum

Factor name:
12-1 Month Momentum

Formula:

Momentum(i,t) = P(i,t-21) / P(i,t-252) - 1

Parameters:
- Lookback period = 252 trading days
- Skip the most recent 21 trading days

Interpretation:
Higher Momentum is better.

Final standardized score:

M(i,t) = Z(Momentum(i,t))

---

## 5. Factor 2 — Low Volatility

Calculate daily stock returns first.

Formula:

r(i,t) = P(i,t) / P(i,t-1) - 1

60-Day Historical Volatility:

Volatility(i,t) =
Std(r(i,t-59:t)) × sqrt(252)

Parameter:
60 trading days.

Interpretation:
Lower volatility is better.

Because all final factor scores must follow the rule that higher scores are better:

LV(i,t) = -Z(Volatility(i,t))

---

## 6. Factor 3 — Liquidity

Use 20-Day Average Dollar Volume.

Daily Dollar Volume:

DV(i,t) = P(i,t) × Volume(i,t)

20-Day Average Dollar Volume:

ADV20(i,t) =
mean(DV over the previous 20 trading days)

Apply natural logarithm:

LiquidityRaw(i,t) = ln(ADV20(i,t))

Final score:

L(i,t) = Z(LiquidityRaw(i,t))

Interpretation:
Higher liquidity is better.

---

## 7. Factor 4 — Short-Term Reversal

Use negative 20-day stock return.

Formula:

Reversal(i,t) =
-(P(i,t) / P(i,t-20) - 1)

Parameter:
20 trading days.

Interpretation:
Stocks with poorer recent 20-day performance receive higher reversal scores.

Final score:

R(i,t) = Z(Reversal(i,t))

Higher is better.

---

## 8. Factor Standardization

At every portfolio formation date, factors must be standardized cross-sectionally across eligible stocks.

Use Z-score standardization.

All factor directions must be transformed so that:

Higher score = better stock ranking.

The four final standardized factors are:

M  = Momentum Score
LV = Low Volatility Score
L  = Liquidity Score
R  = Short-Term Reversal Score

---

## 9. Composite Multi-Factor Score

Use equal factor weights.

CompositeScore(i,t) =

0.25 × M(i,t)
+ 0.25 × LV(i,t)
+ 0.25 × L(i,t)
+ 0.25 × R(i,t)

Baseline factor weights:

Momentum = 25%
Low Volatility = 25%
Liquidity = 25%
Short-Term Reversal = 25%

Stocks should be ranked from highest Composite Score to lowest.

---

## 10. Stock Selection

Baseline strategy:

Select the Top 20 stocks according to Composite Score at each portfolio formation date.

Top N baseline:

N = 20

---

## 11. Portfolio Construction

Use an Equal Weight portfolio.

For the baseline Top 20 portfolio:

Weight per stock = 1 / 20 = 5%

No factor-weighted or market-cap-weighted portfolio is required for the baseline strategy.

---

## 12. Rebalancing

Portfolio rebalancing frequency:

Monthly.

Factor calculation and stock ranking should be performed using information available at the end of the month.

The new portfolio should be implemented on the next trading day.

The implementation must avoid look-ahead bias.

Information that was not available at the portfolio formation time must never be used to make that portfolio decision.

---

## 13. Transaction Costs

Baseline transaction cost:

10 basis points = 0.10%

Transaction costs must be based on actual portfolio turnover.

TransactionCost(t) =
Turnover(t) × 0.10%

Transaction costs must be deducted from strategy returns.

---

## 14. Benchmark

Benchmark:

SPY Buy-and-Hold.

The multi-factor strategy must be compared against SPY over the same official backtest period.

---

## 15. Official Backtest Period

Official strategy performance evaluation period:

2016-01-01 to 2025-12-31.

Data before 2016 may only be used as warm-up data for factor calculations.

Warm-up data must not be included in official strategy performance statistics.

---

## 16. Required Performance Metrics

At minimum calculate:

- Cumulative Return
- Annualized Return
- Annualized Volatility
- Sharpe Ratio
- Maximum Drawdown

The system should also produce a strategy equity / NAV curve and compare it against SPY Buy-and-Hold.

Additional useful performance statistics may be added later, but they must not replace the required metrics.

---

## 17. Data Analysis Requirements

The project should support:

- Data cleaning
- Missing-value analysis
- Descriptive statistics
- Return distribution analysis
- Normality analysis

These outputs will be used in the final academic report.

---

## 18. Optimization and Sensitivity Analysis

The architecture must support later parameter optimization and sensitivity analysis.

The exact optimization parameter grid will be finalized separately.

The baseline strategy defined in this document must remain unchanged unless explicitly approved.

Optimization results must be kept separate from baseline backtest results.

---

## 19. Streamlit Dashboard

A Streamlit dashboard will be developed only after the core quantitative trading system is complete and validated.

Streamlit is the presentation layer.

It must NOT contain the primary quantitative logic.

The dashboard should call reusable modules or read validated output files generated by the core Python system.

The core project must remain executable without Streamlit.

---

## 20. Research and Implementation Principles

The implementation must prioritize:

1. Reproducibility
2. Clear and modular Python code
3. Avoidance of look-ahead bias
4. Explicit treatment of missing data
5. Clear separation of data, factors, strategy, backtest and analysis
6. Reproducible intermediate results
7. Appropriate testing of critical calculations
8. Academic explainability
9. Consistency between code and research methodology
10. Simplicity over unnecessary complexity

Do not silently change the research methodology.

Any major methodological change must be explicitly approved before implementation.

---

## 21. Finalized Baseline Implementation Settings

### Price Data

Use adjusted price data for return-based calculations and factor
calculations.

The implementation must account for the behavior of the installed
yfinance version and must not assume that an "Adj Close" column
always exists.

Use a consistent adjusted price series for:

- Momentum
- Low Volatility
- Liquidity price component
- Short-Term Reversal
- Portfolio return calculations where appropriate

Use Yahoo Finance reported Volume data for the volume component of
the Liquidity factor.

### Missing Factor Data

A stock is eligible for cross-sectional ranking at a portfolio
formation date only when all four required factor values are valid
and available:

- Momentum
- Low Volatility
- Liquidity
- Short-Term Reversal

If any required factor is missing, the stock must be excluded from
that month's ranking.

Do not replace a missing factor with zero, a cross-sectional mean,
or another fabricated value.

### Sharpe Ratio

For the baseline analysis, use:

Risk-Free Rate = 0%

Baseline Sharpe Ratio:

Sharpe Ratio =
Annualized Return / Annualized Volatility

The zero risk-free-rate assumption must be documented in the final
analysis.

### Initial Portfolio Value

Initial Portfolio Capital:

USD 100,000

Also maintain a normalized NAV series beginning at:

NAV = 1.0

Portfolio value and normalized NAV represent the same underlying
strategy return series and are different presentation formats.
