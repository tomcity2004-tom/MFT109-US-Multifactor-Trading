# Official Final Export Index — v1

Package: [outputs/final_report/v1](../outputs/final_report/v1/).
Machine-readable inventory: [manifest.json](../outputs/final_report/v1/manifest.json).
Source vintage: `fisv_revision_20261029T170124Z`.
Approved Phase 10A checkpoint: `fcb2633b5dd5271774a281d271f87474cb3febe2`.

These are versionable report source materials, not the final approximately
8-page report, a PPT or a submission archive. The exporter copies/plots existing
validated outputs only. The manifest records source/specification/code hashes,
software, all output checksums/sizes, sample conventions and baseline endpoints.
It excludes its own hash to avoid self-reference. No generation timestamp is
injected, allowing deterministic regeneration after a commit without changing
provenance to the latest Git HEAD.

## CSVs

| File | Contents |
| --- | --- |
| [performance_summary.csv](../outputs/final_report/v1/performance_summary.csv) | Strategy/SPY final NAV, cumulative return, CAGR, volatility, Sharpe, drawdown and strategy USD value |
| [annual_returns.csv](../outputs/final_report/v1/annual_returns.csv) | All ten calendar years, Strategy/SPY returns |
| [descriptive_statistics.csv](../outputs/final_report/v1/descriptive_statistics.csv) | Byte-identical approved Phase 10A statistics |
| [normality_tests.csv](../outputs/final_report/v1/normality_tests.csv) | Byte-identical Jarque–Bera tests, log p-values and underflow notes |
| [sensitivity_summary.csv](../outputs/final_report/v1/sensitivity_summary.csv) | All 21 catalog rows; six intentional repeated baseline rows; original metrics/differences |
| [methodology_parameters.csv](../outputs/final_report/v1/methodology_parameters.csv) | All immutable BASELINE fields plus documented operational conventions |
| [factor_definitions.csv](../outputs/final_report/v1/factor_definitions.csv) | Four exact formulas, windows, directions, Z-score conventions and weights |
| [baseline_daily.csv](../outputs/final_report/v1/baseline_daily.csv) | All 2,514 daily returns, NAVs, USD values and drawdowns; initial anchor retained |
| [portfolio_snapshots.csv](../outputs/final_report/v1/portfolio_snapshots.csv) | 2,400 selected rows: ranks, scores, execution dates and target/cash weights |
| [data_quality_context.csv](../outputs/final_report/v1/data_quality_context.csv) | Dated evidence labels and provenance context, not a new quality audit |

CSV returns, drawdowns, weights and probabilities use decimal units; 0.01 = 1%.
Sharpe, skewness and kurtosis are dimensionless. Only strategy USD portfolio
value is supplied; SPY's corresponding cell is blank. The unexecuted final
2025-12-31 portfolio signal retains undefined target weights; these snapshots
are execution targets, not complete daily holdings or daily equal-weight resets.

## Figures

All figures are standalone PNGs at 300 dpi. The nine new figures use only
validated daily, annual and sensitivity observations. Four Phase 10A figures
are copied exactly; no raw prices or Volume histories are included.

- [NAV comparison](../outputs/final_report/v1/figures/nav_comparison.png)
- [Drawdown comparison](../outputs/final_report/v1/figures/drawdown_comparison.png)
- [Annual returns](../outputs/final_report/v1/figures/annual_returns_comparison.png)
- [Top-N sensitivity](../outputs/final_report/v1/figures/sensitivity_top_n.png)
- [Transaction-cost sensitivity](../outputs/final_report/v1/figures/sensitivity_transaction_cost_bps.png)
- [Rebalance-frequency sensitivity](../outputs/final_report/v1/figures/sensitivity_rebalance_frequency.png)
- [Volatility-window sensitivity](../outputs/final_report/v1/figures/sensitivity_volatility_window.png)
- [Reversal-window sensitivity](../outputs/final_report/v1/figures/sensitivity_reversal_window.png)
- [Factor-weight sensitivity](../outputs/final_report/v1/figures/sensitivity_factor_weights.png)
- [Strategy distribution](../outputs/final_report/v1/figures/strategy_return_distribution.png)
- [SPY distribution](../outputs/final_report/v1/figures/spy_return_distribution.png)
- [Strategy Q-Q](../outputs/final_report/v1/figures/strategy_qq_plot.png)
- [SPY Q-Q](../outputs/final_report/v1/figures/spy_qq_plot.png)

Each sensitivity figure presents CAGR, Sharpe and maximum drawdown in catalog
order, with the configured baseline highlighted. No winning-parameter selection
is performed. Data are not clipped or altered to improve appearance.

## Supporting provenance and documents

[phase10a_metadata.json](../outputs/final_report/v1/phase10a_metadata.json) and
[phase10a_interpretation.md](../outputs/final_report/v1/phase10a_interpretation.md)
are unchanged source copies. Their internal filenames refer to the original
Phase 10A output directory; use this package's manifest for final-package paths.
Original Phase 10A outputs remain ignored; this deliberate reviewed final copy
is versionable. Raw caches and previous historical outputs remain ignored.

- [Final methodology](FINAL_METHODOLOGY.md)
- [Final results](FINAL_RESULTS.md)
- [Limitations](LIMITATIONS.md)
- [Reproducibility](REPRODUCIBILITY.md)
- [Assignment mapping](ASSIGNMENT_MAPPING.md)
- [Phase 10B validation record](PHASE10B_FINAL_EXPORTS.md)

See reproducibility instructions for explicit regeneration. Missing approved
sources cause failure; the utility never silently replaces them with older
results or new research. Version v1 designates the reviewed data/methodology
bundle, not a promise that future vendor re-downloads are identical.
