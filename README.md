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
Performance analytics, optimization and dashboard logic are not implemented.
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
Imports do not download data or create files. Run the data pipeline explicitly:

```bash
python -m mft109.data.pipeline --universe-only
python -m mft109.data.pipeline --tickers AAPL BRK-B  # live smoke test with SPY
python -m mft109.data.pipeline                       # all fixed constituents + SPY
python -m mft109.data.pipeline --refresh             # prices only, fixed snapshot retained
```

Review data-quality reports in `data/processed/`. Cached histories are ignored by
Git; the small fixed-universe CSV and provenance metadata can be versioned.

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
| `dashboard/` | Reserved for Phase 9 Streamlit presentation; no dashboard implemented |

Configuration, data, raw-factor, factor-processing, and ranking modules are
implemented along with portfolio, backtesting and benchmark modules. Performance
analysis and later components remain docstring-only placeholders.
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
Later statistical conventions and the optimization grid remain unresolved.
Resolve material methodological decisions explicitly before
implementing the affected phase. Baseline settings must not be silently changed;
optimization results remain separate.

## Next phase

Review and validate Phase 5 before proceeding. Phase 6 will add performance
analytics only after explicit approval; no Phase 6 implementation has begun.
