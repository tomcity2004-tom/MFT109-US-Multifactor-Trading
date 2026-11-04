# Reproducibility and Deployment

## Environment

Use Python 3.12 and the pinned dependency files. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-analysis.txt
python -m pip check
```

`requirements-analysis.txt` includes the unchanged base requirements plus SciPy
and Matplotlib. For dashboard-only deployment, `requirements.txt` is sufficient;
the application does not import the offline statistical/export modules.

## A. Full quantitative reproduction

Exact research reproduction requires the **approved local/ignored historical
cache**, not a fresh Yahoo download. Restore the archived normalized stock/SPY
Parquet files, matching metadata, fixed universe and provenance. The approved
FISV Parquet SHA-256 is
`6a4c15da950254d215d8b7db0835e376fb659d67e2d869e299797d8d4f01dcf1`.
The reviewed fixture expects 500 stock caches plus SPY, retaining all 503 universe
symbols, with FDXF/HONA/VYLR unavailable.

Run the strict complete validation:

```bash
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
```

This reruns public factor, scoring, ranking, backtest, benchmark and performance
APIs on approved cached inputs; repeats the baseline; and validates the fixed
sensitivity catalog. No downloader fallback or output overwrite is allowed by
the Phase 8 integration fixture. Missing approved cache is a failure in this
mode. A run with skipped cache checks is not a full quantitative reproduction.

To inspect one validated fresh calculation in memory using the existing test
fixture (POSIX shell):

```bash
PYTHONPATH=tests MFT109_REQUIRE_APPROVED_CACHE=1 python -B -c 'from phase8_support import baseline_run; r=baseline_run(); print(r.performance.performance_summary.to_string(index=False)); print(r.backtest.daily.tail(1).to_string(index=False))'
```

This calls production algorithms through the offline validation harness; it is
not a second trading implementation. Operational production APIs are documented
in the Phase 2–7 guides. The original pipeline command `python -m
mft109.data.pipeline` is for acquisition and may contact Yahoo; it is **not** the
command for proving reproduction of the frozen approved data vintage.

Expected official endpoints:

- Strategy NAV `6.225346615575381`.
- Strategy value `622534.6615575381` USD.
- SPY NAV `4.002530196823173`.
- Strategy maximum drawdown `-0.35452504758611847`.

See [Phase 8](PHASE8_TESTING_VALIDATION.md), [FISV revision](FISV_DATA_REVISION.md)
and [methodology](FINAL_METHODOLOGY.md). The older data version remains historical
evidence, never the current regression target. Historical Yahoo revisions mean
live re-downloads may produce a different dataset.

## B. Report materials without the market cache

The tracked `dashboard/data/` bundle already contains validated returns, NAV,
drawdowns, metrics, annual returns, targets, scores and sensitivity results. It
is sufficient to reproduce the statistical diagnostics and report package:

```bash
python -B -m mft109.analysis.data_analysis
python -B -m mft109.analysis.final_exports
```

The first command explicitly regenerates Phase 10A diagnostics from the validated
tracked returns into ignored `outputs/final_analysis/`. The second verifies and
**copies** those approved outputs; it does not silently rerun statistics,
backtests or sensitivity analysis. Its destination is
`outputs/final_report/v1/`, intentionally eligible for version control.

The final exporter fails on missing/corrupt inputs and refuses protected output
locations or unrelated existing destination files. It verifies source/code/output
hashes and rechecks inputs after writing. With identical inputs/code/software,
exports are byte-identical. A changing generation timestamp is deliberately
omitted; the fixed Phase 10A checkpoint and code/source hashes supply provenance.

On restricted hosts, plotting may need writable temporary cache paths:

```bash
MPLCONFIGDIR=/tmp/mft109-matplotlib-cache XDG_CACHE_HOME=/tmp/mft109-phase10-cache \
  python -B -m mft109.analysis.final_exports
```

Inspect [the export index](FINAL_EXPORT_INDEX.md), `manifest.json`, and source
hashes before using figures or copying tables into a report. Phase 10A CSVs and
figures are copied byte-for-byte, including underflow p-value notes and the
2,513-return sample convention. Do not substitute local old-vintage outputs.

## C. Dashboard deployment

```bash
python -m pip install -r requirements.txt
python -m streamlit run dashboard/Home.py
```

The official entry point remains **dashboard/Home.py**. The five pages support
English and 繁體中文 through the sidebar; language persists across navigation.
Filename-based native navigation labels and original technical diagnostics remain
English where documented. No local market cache, API key, live Yahoo request,
normality calculation or full backtest is needed at startup.

For Streamlit Community Cloud: authorize the private repository
`tomcity2004-tom/MFT109-US-Multifactor-Trading`, select `main` after the approved
merge, Python 3.12 and Main file path `dashboard/Home.py`. Keep root
`requirements.txt` and all eleven `dashboard/data/` artifacts available. Secrets
must never be added to the repository. Platform authorization is distinct from
application credentials; no application credentials are required.

Regenerating deployment artifacts with `python -m dashboard.export_data` is a
separate explicit maintenance operation requiring approved local research
caches/results. It is not needed for ordinary launch or final-package export.
Do not regenerate them merely to package the report.

## Final checks

```bash
python -B -m unittest discover -s tests -p test_data_analysis.py -v
python -B -m unittest discover -s tests -p test_final_exports.py -v
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -B -m pip check
git diff --check
```

The final-export integration tests require approved Phase 10A outputs; explicitly
run the diagnostic command above if this ignored folder is absent in a clean
checkout. Presentation-only launch and inspection of the tracked final package
remain independent of all ignored research files. Final course-report/PPT
writing is deliberately separate from these commands.
