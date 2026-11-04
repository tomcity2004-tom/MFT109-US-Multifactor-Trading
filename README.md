# MFT109 US Multi-Factor Trading Project

Academic Python project for the **MFT109 Financial Algorithmic Trading** course:
U.S. equity multi-factor stock selection, backtesting and comparison with SPY
Buy-and-Hold. Validated Phase 0–10A research is consolidated into a versioned
Phase 10B report-material package, awaiting review. The final course report and
PowerPoint are separate deliverables and have not been generated.

## Strategy and validated results

A fixed current S&P 500 constituent snapshot is ranked monthly using four
equally weighted standardized factors: **12–1 month momentum, 60-day low
volatility, 20-day dollar-volume liquidity, and 20-day short-term reversal**.
The Top 20 form an equal-weight portfolio, implemented at the next eligible
session's adjusted close. Costs are 10 bps times actual cash-inclusive turnover.

Official backtest: **2016–2025**, with 2015 warm-up; initial capital USD 100,000;
benchmark **SPY Buy-and-Hold**; risk-free rate 0%.

| Validated metric | Strategy | SPY |
| --- | ---: | ---: |
| Final NAV | 6.225346615575381 | 4.002530196823173 |
| Cumulative return | 522.534662% | 300.253020% |
| CAGR | 20.126153% | 14.921489% |
| Annualized volatility | 23.057786% | 18.007274% |
| Sharpe (CAGR/volatility) | 0.872857 | 0.828637 |
| Maximum drawdown | -35.452505% | -33.717264% |

Final strategy value: **USD 622,534.6615575381**. This is the current approved
revised-data baseline. Strategy's higher historical return accompanies greater
volatility and maximum drawdown; future superiority is not established.

## Documentation and official materials

- [Locked methodology](docs/FINAL_METHODOLOGY.md)
- [Validated results](docs/FINAL_RESULTS.md)
- [Limitations](docs/LIMITATIONS.md)
- [Reproducibility and deployment](docs/REPRODUCIBILITY.md)
- [Final export index](docs/FINAL_EXPORT_INDEX.md) and [package manifest](outputs/final_report/v1/manifest.json)
- [Assignment mapping](docs/ASSIGNMENT_MAPPING.md)
- [Phase 10A statistics](docs/PHASE10A_DATA_ANALYSIS.md) and [Phase 10B record](docs/PHASE10B_FINAL_EXPORTS.md)

[PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) defines the research
specification; [AGENTS.md](AGENTS.md) defines development rules. Historical phase
guides remain under `docs/`, including [data processing](docs/DATA_PIPELINE.md),
[Phase 8 validation](docs/PHASE8_TESTING_VALIDATION.md),
[FISV revision provenance](docs/FISV_DATA_REVISION.md), and
[dashboard](docs/PHASE9_STREAMLIT_DASHBOARD.md)/[bilingual usage](docs/PHASE9_1_BILINGUAL_DASHBOARD.md).
Their historical work-status statements are preserved; the consolidated final
documents describe the current research state.

## Setup and commands

Use Python 3.12. For research diagnostics, static exports and all tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-analysis.txt
python -m pip check
```

To explicitly regenerate diagnostic and final-package outputs from tracked
validated artifacts (no market-data download or new backtest):

```bash
python -B -m mft109.analysis.data_analysis
python -B -m mft109.analysis.final_exports
```

Phase 10A generates ignored diagnostic files. Phase 10B verifies/copies those
outputs and creates the versionable `outputs/final_report/v1/` package. It never
silently chooses older results or reruns research. Do not edit exported financial
values manually. The package includes 2016–2025 annual tables, daily NAV/drawdowns,
portfolio targets, all six sensitivity groups, statistical tables and static
figures. See the index for units and provenance.

## Streamlit dashboard

Five pages: Home, Performance, Portfolio, Factors and Sensitivity. The sidebar
**Language / 語言** selector supports **English / 繁體中文**, preserving language
across navigation. Financial results are identical in both languages.

```bash
python -m pip install -r requirements.txt
python -m streamlit run dashboard/Home.py
```

Official entry point: **dashboard/Home.py**. It reads eleven tracked deployment
artifacts and requires no local market cache, secrets or live Yahoo requests.
For Community Cloud, authorize the private GitHub repository, select `main`
after merge, Python 3.12 and the same Main file path. Analysis dependencies are
not needed for dashboard-only deployment. See reproducibility guidance for the
separate full quantitative workflow.

## Testing

After the explicit diagnostic regeneration command, run:

```bash
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -B -m pip check
git diff --check
```

Full integration validation requires the approved ignored stock/SPY cache and
runs offline. The strict flag fails when that cache is absent; skipped cache
checks do not establish a reproduced baseline. Presentation and report-package
inspection remain possible from GitHub alone. Final-export tests require the
approved Phase 10A outputs; regenerate them explicitly if absent in a clean clone.
No test or export command should refresh Yahoo data to force a result match.

## Repository structure

| Path | Purpose |
| --- | --- |
| `mft109/config.py` | Locked baseline configuration |
| `mft109/data/` | Acquisition, validation, cleaning and cache handling |
| `mft109/factors/`, `processing/`, `ranking/` | Raw factors, Z-scores/composite and deterministic Top N selection |
| `mft109/portfolio/`, `backtesting/`, `benchmark/` | Targets, execution, drift, costs, NAV and SPY |
| `mft109/analysis/` | Validated performance, return diagnostics and explicit final exports |
| `mft109/optimization/` | Fixed one-at-a-time sensitivity; no unrestricted optimizer |
| `dashboard/` | Bilingual presentation, tracked deployment data and offline maintenance export |
| `outputs/final_report/v1/` | Versioned, report-ready source materials and manifest |
| `outputs/final_analysis/` | Ignored reproducible Phase 10A diagnostics |
| `data/`, other `outputs/` | Fixed universe plus ignored caches/historical generated research data |
| `docs/`, `tests/`, `notebooks/` | Methodology/evidence, automated validation and optional exploration |

## Academic disclaimer

Using current constituents across history introduces **survivorship bias**.
Yahoo data can be revised; execution and costs are simplified, while taxes and
market impact are not modeled. Historical
sensitivity and normality diagnostics are not evidence of future profitability.
This is academic research, **not investment advice**. No final report, PPT or
submission archive is created by the packaging workflow.
