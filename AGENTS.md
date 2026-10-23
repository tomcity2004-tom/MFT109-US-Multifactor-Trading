# AGENTS.md

## 1. Project Context

This repository contains an academic quantitative trading project
for the MFT109 Financial Algorithmic Trading course.

The project implements a U.S. equity multi-factor stock selection
and backtesting system.

PROJECT_REQUIREMENTS.md defines the official research methodology.

All implementation work must remain consistent with
PROJECT_REQUIREMENTS.md.

---

## 2. Primary Rule

Before making any significant code change:

1. Read PROJECT_REQUIREMENTS.md.
2. Inspect the existing repository structure.
3. Understand the existing implementation.
4. Preserve previously validated functionality.
5. Do not modify research assumptions without explicit approval.

If there is a conflict between implementation convenience and
PROJECT_REQUIREMENTS.md, follow PROJECT_REQUIREMENTS.md.

---

## 3. Methodology Must Not Be Changed

Do not independently change:

- Investment universe
- Data source
- Factor definitions
- Factor formulas
- Factor lookback periods
- Factor directions
- Factor weights
- Top N selection rule
- Portfolio weighting method
- Rebalancing frequency
- Transaction-cost assumption
- Benchmark
- Backtest period

Any proposed methodological change must first be clearly identified
and must not be implemented without explicit approval.

---

## 4. Development Approach

Develop the project incrementally.

Do not attempt to build the entire trading system in one task.

Use the following development phases:

Phase 0:
Repository structure and configuration

Phase 1:
Data acquisition, validation, cleaning and caching

Phase 2:
Factor calculation

Phase 3:
Factor standardization and composite scoring

Phase 4:
Stock ranking and portfolio construction

Phase 5:
Backtesting, monthly rebalancing, transaction costs and benchmark

Phase 6:
Performance analysis

Phase 7:
Optimization and sensitivity analysis

Phase 8:
Testing and validation

Phase 9:
Streamlit dashboard

Phase 10:
Final documentation and result export

Complete and validate each major phase before proceeding to the next.

---

## 5. Python Architecture

Use modular Python code.

Do not place the entire system in one Python file.

The architecture should clearly separate:

- configuration
- data acquisition
- data cleaning
- factor calculations
- factor processing
- stock ranking
- portfolio construction
- backtesting
- transaction costs
- benchmark
- performance analysis
- optimization
- visualization

Prefer reusable functions and modules.

Avoid unnecessary abstraction and unnecessary complexity.

---

## 6. Data Rules

Use Yahoo Finance / yfinance as specified in
PROJECT_REQUIREMENTS.md.

Do not repeatedly download the same historical data if valid cached
data already exists.

Downloaded data should be validated before use.

Data-processing decisions must be explicit and reproducible.

Do not silently fill, remove or modify missing observations without
a documented rule.

Do not silently replace unavailable data with fabricated values.

---

## 7. Look-Ahead Bias

Avoid look-ahead bias throughout the project.

Portfolio decisions may only use information available at the
portfolio formation date.

Monthly factor calculation and ranking use information available
at month-end.

The resulting portfolio should be implemented from the next
eligible trading day.

Never use future prices, returns or future information when
constructing historical signals.

---

## 8. Factor Implementation

Factor formulas must exactly follow PROJECT_REQUIREMENTS.md.

The baseline factors are:

1. 12-1 Month Momentum
2. 60-Day Low Volatility
3. 20-Day Average Dollar Volume Liquidity
4. 20-Day Short-Term Reversal

Do not replace these factors with technical indicators or other
factor definitions.

All factor calculations should be testable independently.

---

## 9. Backtesting

The backtest engine must clearly separate:

- signal calculation
- portfolio formation
- execution timing
- holding-period returns
- portfolio turnover
- transaction costs
- benchmark returns

Transaction costs must be based on portfolio turnover.

Warm-up data must not be included in official performance
statistics.

Baseline results must be preserved separately from optimization
results.

---

## 10. Testing

Add tests for critical quantitative calculations.

Important tests should eventually include:

- factor formula correctness
- Z-score calculation
- factor direction
- composite score
- Top 20 selection
- equal weighting
- rebalance timing
- portfolio turnover
- transaction-cost calculation
- performance metrics
- prevention of obvious look-ahead errors

Run relevant tests after implementing or modifying a major module.

Do not claim that a phase is complete if relevant tests are failing.

---

## 11. Error Handling

Use clear error messages.

Do not silently ignore major data or calculation errors.

When external data retrieval fails, report the problem clearly.

Where appropriate, log important pipeline steps.

---

## 12. Reproducibility

The project should be reproducible from the repository.

Use configuration values rather than scattering important parameters
throughout the code.

Save useful intermediate outputs where appropriate.

Use deterministic processing wherever possible.

Document important assumptions.

---

## 13. Streamlit

Streamlit is a presentation layer only.

Do not put the primary quantitative methodology inside Streamlit
page files.

Streamlit should call reusable core modules or read validated
outputs.

The quantitative system must remain executable without Streamlit.

---

## 14. Git and Repository Hygiene

Do not commit unnecessary large raw market-data files.

Use .gitignore for cache files, temporary files, virtual
environments and other generated artifacts where appropriate.

Do not commit API keys, passwords, tokens or secrets.

Keep generated results organized.

Do not delete existing user files without a clear reason.

---

## 15. Communication Before Major Changes

Before implementing a new major development phase:

1. Inspect the relevant existing files.
2. State what will be implemented.
3. Identify files expected to be created or modified.
4. Identify important assumptions or unresolved decisions.

If an unresolved methodological decision would materially affect
the implementation, stop and ask for clarification rather than
inventing a research assumption.

---

## 16. Communication After Each Phase

After completing a development phase, provide:

1. Summary of work completed.
2. Files created.
3. Files modified.
4. Tests performed.
5. Test results.
6. Important assumptions.
7. Known limitations or issues.
8. Recommended next phase.

Do not automatically begin the next major phase unless explicitly
requested.

---

## 17. Simplicity Principle

This is an academic course project.

Prefer solutions that are:

- correct
- reproducible
- explainable
- testable
- maintainable

over solutions that are unnecessarily sophisticated.

The objective is not to build a production institutional trading
platform.

The implementation should remain understandable enough to explain
in the final report and oral presentation.
