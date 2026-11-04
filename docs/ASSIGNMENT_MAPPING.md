# Assignment Requirement Mapping

This maps validated source material to the four requested academic sections.
It is an evidence map for later writing, not the final report or slides.

| Section | Evidence | Report-ready material |
| --- | --- | --- |
| 1. Strategy Design | PROJECT_REQUIREMENTS.md; FINAL_METHODOLOGY.md; Phase 2–5 guides; config and independently tested formulas/scoring/ranking/accounting | methodology_parameters.csv; factor_definitions.csv; portfolio_snapshots.csv |
| 2. Data Source and Processing | DATA_PIPELINE.md; Phase 1/1.1 reviews; FISV revision; Phase 8 checks; Phase 10A diagnostics; LIMITATIONS.md | data_quality_context.csv; descriptive_statistics.csv; normality_tests.csv; two histograms and two Q-Q plots; sample/provenance metadata |
| 3. Backtest and Performance Analysis | Phase 5/6/8 records; FINAL_RESULTS.md; validated official 2016–2025 Strategy/SPY results | performance_summary.csv; annual_returns.csv; baseline_daily.csv; NAV, drawdown and annual-return figures |
| 4. Optimization / Sensitivity Analysis | Phase 7's fixed one-at-a-time catalog; revised-data completed scenarios; final results/limitations discussion | sensitivity_summary.csv; six sensitivity figures showing CAGR, Sharpe and drawdown |

Paths above are relative to `outputs/final_report/v1/` (figures under `figures/`)
unless a document is named. The package manifest and FINAL_EXPORT_INDEX.md give
precise paths and checksums. Data processing includes the approved Phase 10A
2,513-return descriptive/distribution/normality sample, not a fresh market-data
audit. Its first accounting anchor is excluded consistently with Phase 6.

The “Optimization” section is fulfilled by the explicitly approved sensitivity
scope: one dimension at a time, fixed baseline, no parameter mining, Cartesian
search or automatic best-setting adoption. Do not claim a general optimizer or
out-of-sample validation was implemented.

Later report writing should explain the fixed current-universe survivorship
bias, Yahoo revision provenance, simplified execution/costs, distribution
findings and risk trade-offs, not just the headline return. Historical phase
records may describe then-current work states; final consolidated documents
identify the official present state without rewriting that history.

The approximately eight-page course report, PPT, citations/layout requirements
and actual submission packaging remain separate deliverables. No new financial
experiment is required to write from this material; course-specific formatting
and any hosted-app URL can be added when preparing those deliverables.
