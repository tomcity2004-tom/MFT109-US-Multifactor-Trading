# Phase 9 — Streamlit Dashboard

## Scope

Five presentation pages expose the validated Phase 0–8 results. The limited
Phase 9 deployment fix removes local cache/output dependencies; it does not
change methodology, run a new backtest, or begin Phase 10. No protected core
module, prior-phase test, universe, market cache or reviewed result is changed.

## Launch and Streamlit Community Cloud

Use Python 3.12, install the root requirements, and run from the repository root:

```bash
python -m pip install -r requirements.txt
streamlit run dashboard/Home.py
```

The official Main file path is **dashboard/Home.py**. For Community Cloud:

1. After review and eventual merge, connect the private GitHub repository
   `tomcity2004-tom/MFT109-US-Multifactor-Trading`.
2. Authorize Streamlit to access the private repository.
3. Choose branch `main`, Main file path `dashboard/Home.py`, and Python 3.12.
4. Deploy with root `requirements.txt`. No Yahoo credentials or Streamlit secrets
   are required by this application. Platform GitHub authorization is separate.

No actual cloud deployment, commit, push or pull request is part of this fix.
Streamlit and Altair are pinned; the prior quantitative dependency pins remain
unchanged. `.streamlit/config.toml` supplies the light theme and disables usage
statistics. The core quantitative project remains executable without Streamlit.

## Deployment artifacts

All runtime financial data are in **dashboard/data/**, eligible for Git tracking.
The adapter resolves the directory relative to `mft109/config.py`'s repository
root, independent of the caller's working directory. It does not read ignored
`data/cache/`, `outputs/`, runtime files, credentials or files outside the repo.

| Artifact | Content |
| --- | --- |
| `baseline_daily.parquet` | 2,514 official daily observations: strategy/SPY returns and NAV, strategy USD value and both drawdowns |
| `baseline_performance.csv` | Five required Strategy/SPY performance metrics |
| `baseline_annual_returns.csv` | 2016–2025 annual returns and original anchor/end dates |
| `baseline_selected.parquet` | 2,400 selected rows over 120 formations: ranks, composites, standardized scores, execution dates, target and cash weights |
| `phase7_top_n.csv` | Four predefined Top N comparisons |
| `phase7_transaction_cost_bps.csv` | Four predefined cost comparisons |
| `phase7_rebalance_frequency.csv` | Monthly and quarterly comparisons |
| `phase7_volatility_window.csv` | Three volatility-window comparisons |
| `phase7_reversal_window.csv` | Three reversal-window comparisons |
| `phase7_factor_weights.csv` | Equal weights and four factor tilts |
| `manifest.json` | Schema, baseline settings, data vintage, source commit, source SHA-256 provenance, exported-file checksums/sizes and endpoints |

The eleven files total approximately 439 KB (429 KiB). They are derived
presentation outputs, not the complete Yahoo cache. No raw OHLCV prices or volumes
are exported. Original caches and research outputs remain ignored. No broad
`.gitignore` exception is needed because `dashboard/data/` is not ignored.

## Provenance and explicit regeneration

The offline utility is run manually by a maintainer with the approved local
cache and reviewed results:

```bash
python -B -m dashboard.export_data
```

`dashboard/export_data.py` retains the reviewed Phase 9 source-output validation:
active FISV revision identity, normalized-cache checksums, complete scenario
catalog and baseline flags, original selection order, universe membership, and
saved metrics checked using existing Phase 6 analysis. It loads the reviewed
`outputs/optimization/fisv_revision_20261029T170124Z/` results. It calls the
unchanged Phase 5 execution/target helpers with approved adjusted prices to
export all historical execution targets. It never reruns the backtest or
sensitivity engine, downloads data, or writes into the original cache/results.

The manifest records SHA-256 hashes of source inputs and each exported artifact.
There is no timestamp injected during export; identical sources/code produce
identical content. Sources are checked for changes during export. Missing or
inconsistent approved sources raise a clear error; no fallback financial values
are invented. Regenerated artifacts must be reviewed and versioned together.

The current data version includes the explicitly approved FISV Yahoo revision;
see [FISV_DATA_REVISION.md](FISV_DATA_REVISION.md). Never replace the final
validated baseline with older Phase 6 outputs merely because results differ.

## Runtime architecture

- `dashboard/Home.py` and four scripts under `dashboard/pages/`: standard
  Streamlit multipage navigation.
- `dashboard/components/`: framing, formatting, chart specs and memory caches.
- `mft109/visualization/dashboard_data.py`: reads only the eleven deployment
  artifacts. It checks checksums, schema, finite values, exported execution
  timing, required metrics and baseline consistency. It imports no backtest,
  analysis, factor, ranking or export modules and performs no strategy calculation.
- `dashboard/export_data.py`: offline export only; never imported by app startup.
- `tests/test_dashboard.py`: presentation, artifact and page-execution tests.

`st.cache_data` stores read-only presentation bundles and chosen snapshots in
memory. Mtime/size signatures cover only deployment artifacts. On a cache miss,
manifest checksums are verified. These detect accidental corruption; they are
not signed proof of financial correctness. Independent Phase 0–8 regression
checks and source-to-export tests establish the approved result provenance.
Missing or corrupt artifacts produce an explicit error and no fabricated KPIs.
No downloads or pipeline execution occur at startup or on widget changes.

## Five pages and preserved semantics

| Page | Content |
| --- | --- |
| Overview | Eight KPI cards, approved baseline settings, comparative NAV and limitations |
| Performance | Strategy/SPY NAV, drawdowns, annual bars, metrics and annual tables |
| Portfolio | Formation selector, Top 20 ranks, composite/factor scores and exported execution targets |
| Factors | Exact approved formulas, score directions and factor-score heatmap |
| Sensitivity | Six fixed experiment groups, baseline-highlighted charts and all 21 original rows |

The final 2025-12-31 formation has no execution inside the official period.
Its target/cash weights stay undefined and are displayed as `—`; no 2026 trade
is invented. Earlier snapshots read the exported targets from the same unchanged
core helpers. For 2025-11-28, execution is 2025-12-01, with PANW included and V
excluded. Targets are not daily rebalanced holdings; natural drift remains part
of the original backtest, never recalculated by the UI.

Charts use Altair, with dates, legends, percentages/currency labels and tooltips.
Navigation and selectors change presentation only. No optimizer, unrestricted
parameter grid, automatic winning-scenario choice or new scenario is introduced.

Visible limitations retain survivorship bias from the fixed current S&P 500
universe, vendor data revisions, adjusted-close academic execution, 10 bps
turnover costs, historical sensitivity limitations and non-advisory research use.

## Validation

```bash
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -B -m pip check
git diff --check
```

There are 35 dashboard tests (26 prior presentation checks updated to the artifact
contract and nine deployment checks). Deployment tests cover artifact presence,
ignore status, cache-free loading, working-directory independence, exact approved
endpoints, source hashes, corruption failure, no quantitative runtime imports,
console-launcher imports without the repository on `sys.path`,
and equality of all numeric tables and all 120 execution snapshots to reviewed
sources. Prior Phase 0–8 tests remain unchanged.

The repository-only simulation excludes all ignored local data, copies the
tracked project plus proposed Phase 9 files into a temporary clean directory,
installs requirements into a fresh Python 3.12 virtual environment, imports the
app, executes all five pages with Streamlit AppTest, exercises portfolio and
sensitivity controls, and starts `streamlit run dashboard/Home.py` headlessly.
This simulates the proposed commit contents, not a GitHub branch already pushed.
No graphical browser or actual Streamlit Community Cloud deployment is performed.

Approved endpoints, unchanged:

- Strategy final NAV: `6.225346615575381`
- Strategy final USD value: `622534.6615575381`
- SPY final NAV: `4.002530196823173`

CAGR, volatility, zero-risk-free Sharpe, maximum drawdown, annual returns and all
sensitivity metrics are exported unchanged, not approximated by the UI.

Final validation:

| Check | Result |
| --- | --- |
| Complete approved-cache suite | 385 passed, 0 failures/errors, 0 skipped |
| Prior Phase 0–8 tests | All 350 passed |
| Dashboard / deployment tests | All 35 passed |
| Exact source-to-export tables and 120 target snapshots | PASS |
| Deterministic repeat export | All 11 files byte-identical |
| Fresh Python 3.12 dependency installation and pip check | PASS |
| Cache-free repository-only simulation | All five pages and display controls passed |
| Console-style imports without root on initial sys.path | All five pages passed |
| Headless app shell / health | HTTP 200 / HTTP 200 |
| Protected existing files | 1,133 unchanged |
| git diff --check | PASS |

Expected warnings are Streamlit bare-mode/test-harness notices and the existing
Phase 1 invalid-date fixture warning/mocked retrieval diagnostics. There were no
remaining application exceptions. No actual graphical-browser or Community Cloud
session was tested; private-repository platform authorization is still required.

Work remains uncommitted for review. Phase 10 has not started.

**PHASE 9 DEPLOYMENT FIX: PASS**
