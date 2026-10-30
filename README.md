# MFT109 US Multi-Factor Trading Project

Academic U.S. equity stock-selection and backtesting project for the MFT109
Financial Algorithmic Trading course.

[PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) is the primary research and
methodology specification. [AGENTS.md](AGENTS.md) defines development rules.

Phase 1 implements data acquisition, validation, conservative cleaning, and caching.
Phase 2 adds the four raw factors; see [the raw-factor guide](docs/PHASE2_RAW_FACTORS.md).
Phase 3 adds eligibility, cross-sectional standardization, and composite scoring;
see [the scoring guide](docs/PHASE3_FACTOR_SCORING.md).
Phase 4 adds monthly ranking and Top 20 selection;
see [the ranking guide](docs/PHASE4_RANKING_SELECTION.md).
Phase 5 adds portfolio construction, adjusted-close execution, turnover-based
costs, daily accounting and SPY Buy-and-Hold;
see [the portfolio/backtest guide](docs/PHASE5_PORTFOLIO_BACKTEST.md).
Phase 6 adds performance metrics, daily drawdowns and calendar-year returns;
see [the performance guide](docs/PHASE6_PERFORMANCE_ANALYSIS.md).
Phase 7 adds predefined one-at-a-time sensitivity tables;
see [the sensitivity guide](docs/PHASE7_SENSITIVITY_ANALYSIS.md).
Phase 8 adds offline end-to-end, reproducibility and approved-baseline regression
checks; see [the validation report](docs/PHASE8_TESTING_VALIDATION.md).
The Phase 8 approved-cache validation passed all 350 tests, including 30 Phase 8 tests.
Phase 9 adds a five-page Streamlit presentation of reviewed results;
see [the dashboard guide](docs/PHASE9_STREAMLIT_DASHBOARD.md).
All 385 tests pass, including 35 dashboard/deployment tests; Phase 9 is awaiting review.
Unrestricted optimization is not implemented.
See [the data pipeline guide](docs/DATA_PIPELINE.md) for commands and data policies,
and [the validation record](docs/PHASE1_VALIDATION.md) for live results and limitations.

## Development setup

Use Python 3.12 (validated with 3.12.14). From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -c "from mft109.config import BASELINE; print(BASELINE)"
```

Phase 1 uses pinned pandas, NumPy, yfinance, and PyArrow dependencies. The root-level
package works directly from the repository root without editable installation or
PYTHONPATH changes. Tests use deterministic fixtures and require no Yahoo access.
Imports do not download data or create files. Phase 8 integration checks require
the approved local cache; use
`MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v`
for a full validation that fails instead of skipping when the cache is absent.

Run the data pipeline explicitly:

```bash
python -m mft109.data.pipeline --universe-only
python -m mft109.data.pipeline --tickers AAPL BRK-B  # live smoke test with SPY
python -m mft109.data.pipeline                       # all fixed constituents + SPY
python -m mft109.data.pipeline --refresh             # prices only, fixed snapshot retained
```

Review data-quality reports in `data/processed/`. Cached histories are ignored by
Git; the small fixed-universe CSV and provenance metadata can be versioned.

## Dashboard

From the repository root, with dependencies installed (no local market cache required):

```bash
.venv/bin/python -m streamlit run dashboard/Home.py
```

The dashboard reads the small, versionable presentation artifacts in `dashboard/data/`
without market-data downloads or new backtests. Formation-date and sensitivity controls change the displayed view only.
Missing approved artifacts produce a clear error; see the dashboard guide for
required files, offline regeneration, Community Cloud deployment and limitations.

For Streamlit Community Cloud, select `main` after the approved merge and set
Main file path to `dashboard/Home.py`. Grant Streamlit access to this private repository.
The explicit offline export command is `python -m dashboard.export_data`; it requires
the approved local research data and is never executed by the application.

## Directory guide

| Path | Purpose |
| --- | --- |
| `mft109/config.py` | Immutable approved baseline settings and repository-relative paths |
| `mft109/data/` | Acquisition, validation, cleaning, and cache management |
| `mft109/factors/` | Four independent factor modules |
| `mft109/processing/` | Cross-sectional standardization and composite scoring |
| `mft109/ranking/` | Stock ranking and Top N selection |
| `mft109/portfolio/` | Equal-weight portfolio construction |
| `mft109/backtesting/` | Engine, execution timing, turnover, and transaction costs |
| `mft109/benchmark/` | SPY Buy-and-Hold comparison |
| `mft109/analysis/` | Performance, descriptive statistics, and normality analysis |
| `mft109/optimization/` | Optimization and sensitivity analysis |
| `mft109/visualization/` | Reusable plotting independent of dashboard files |
| `data/{raw,processed,cache}/` | Local artifacts; only placeholders and fixed-universe inputs are versioned |
| `outputs/{baseline,optimization}/` | Separate generated result destinations; contents ignored |
| `tests/` | Standard-library unittest checks; quantitative tests added with implementation |
| `notebooks/` | Later exploratory and academic analysis notebooks |
| `dashboard/` | Streamlit pages and reusable presentation components |

Configuration, data, raw-factor, factor-processing, and ranking modules are
implemented along with portfolio, backtesting, benchmark and performance metrics.
Controlled sensitivity analysis and the presentation dashboard are implemented.
Descriptive data analysis remains a placeholder.
Use reusable core modules for future notebook and dashboard integration.

## Baseline and research boundaries

The configuration records the fixed current S&P 500 universe, daily Yahoo Finance
data, 2015 warm-up, 2016–2025 official backtest, four equally weighted factors,
Top 20 equal-weight portfolio, monthly formation and next-trading-day execution,
10 bps turnover-based costs, SPY benchmark, zero risk-free rate, USD 100,000
initial capital, and normalized NAV of 1.0. Current membership introduces
survivorship bias and must be disclosed. Warm-up observations are excluded from
performance statistics.

Use consistent adjusted prices with Yahoo Finance reported Volume. Do not assume
an `Adj Close` column exists. Require all four valid factors for ranking and never
fabricate missing values. Configuration dates are inclusive research boundaries;
the provider adapter adds one day to the exclusive yfinance end date.

Adjusted prices and conservative missing-data handling are explicit in the data
pipeline. Raw volatility uses sample standard deviation (`ddof=1`). Execution-price
conventions and cash-inclusive turnover are documented in the Phase 5 guide.
Performance-statistic conventions are documented in the Phase 6 guide.
The approved Phase 7 scenarios are fixed in the sensitivity guide; no unrestricted
optimization grid or automatic best-parameter selection is provided.
Resolve material methodological decisions explicitly before
implementing the affected phase. Baseline settings must not be silently changed;
optimization results remain separate.

## Next phase

Review Phase 9 before proceeding. An approved [FISV source-data revision](docs/FISV_DATA_REVISION.md)
resolves two previously blocked scenarios; all 21 revised-data runs complete.
Baseline methodology is unchanged, but revised-data results differ from the
preserved original results. Phase 10 has not begun.
