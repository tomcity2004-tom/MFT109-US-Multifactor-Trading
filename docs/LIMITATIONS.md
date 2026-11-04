# Limitations and Academic Interpretation

1. **Survivorship bias and universe timing.** A fixed snapshot of current S&P 500
   constituents is applied to all 2016–2025 dates. Historical index membership is
   not reconstructed. This is not a point-in-time investable index sample.
2. **Incomplete security histories.** All 503 snapshot securities remain in the
   universe, but only 500 stock histories were available in reviewed validation.
   FDXF/HONA/VYLR have no requested-period history; shorter histories can prevent
   complete factors. Monthly eligibility excludes incomplete signals rather than
   fabricating values or substituting parent/previous tickers.
3. **Yahoo revision and provider risk.** Historical prices/Volume may change.
   The official baseline is the approved revised dataset recorded in the package
   manifest and [FISV audit](FISV_DATA_REVISION.md). A fresh download is not proof
   of reproducing that exact version. yfinance's upstream null-Volume-to-zero
   behavior also limits what returned completeness can establish.
4. **Historical versus current quality evidence.** The older local
   `data/processed/data_quality.json` and Phase 1.1 FISV missing-price finding
   predate the approved revision. They must not be presented as a fresh audit or
   an unresolved current gap. The approved revision restores the observation and
   accepts three other Volume revisions; source receipts and hashes are archived.
   Phase 8 validates the revised baseline. No new vendor-quality audit is claimed
   by the final package; the historical record is preserved.
5. **Simplified execution.** Next-session adjusted-close fills, fractional units,
   price-consistent valuation and zero cash interest are academic conventions.
   They do not model intraday fills, bid/ask dynamics, execution delay, brokerage
   constraints or actual corporate-action settlement. Missing held prices stop
   the engine rather than being marked at an invented value.
6. **Simplified transaction costs.** The baseline deducts 10 bps times actual
   cash-inclusive turnover. It does not separately estimate spreads, commissions
   by security, liquidity-dependent fees or financing costs.
7. **No market-impact or capacity model.** Real implementation costs may depend
   on trade size, participation and liquidity. The test does not establish
   institutional capacity or executable scale.
8. **No tax model.** Realized gains, dividend taxes, withholding, tax lots and
   investor-specific taxation are not modeled.
9. **Metric conventions.** Sharpe is CAGR divided by sample annualized volatility
   at 0% risk-free rate. It differs from an arithmetic mean-excess-return Sharpe.
   Benchmark NAV is supplied; the final export does not invent a separate SPY USD
   account. Warm-up dates and the synthetic initial anchor are not earned returns.
10. **Distribution and dependence.** Phase 10A rejects marginal normality for both
    series using Jarque–Bera at 5%, with negative skewness and positive excess
    kurtosis. Underflow p-values are numerical zeros, not exact probabilities;
    finite log p-values are included. Serial dependence/volatility clustering and
    large-sample power limit interpretation. Normality alone does not determine
    strategy quality or invalidate accounting/backtest results.
11. **In-sample sensitivity.** Six predeclared one-at-a-time groups are robustness
    checks, not a parameter search or new baseline selection. Multiple historical
    comparisons can encourage data mining; no out-of-sample superiority is
    established. The Top 20 equal-factor baseline remains unchanged.
12. **Historical evidence only.** Higher sample return or Sharpe does not imply
    universal superiority, causality or future outperformance. Strategy has
    greater volatility and maximum drawdown than SPY in the approved baseline.
    This is academic research, **not investment advice**.

The final package is source material for a later report and presentation. It is
not the approximately eight-page final report, a PPT or a submission archive.
