# Phase 10A — Descriptive Statistics, Distribution and Normality Analysis

## Purpose and boundary

Complete the descriptive and diagnostic return-analysis requirement using the
existing validated Strategy/SPY daily results. This is not a new backtest,
strategy change, optimization, final report, slide deck or Phase 10B package.
No factor, signal, portfolio, cost, benchmark or performance calculation changes.

## Source and provenance

Numerical input: **dashboard/data/baseline_daily.parquet** from the reviewed
`fisv_revision_20261029T170124Z` baseline. The existing read-only presentation
loader also verifies the manifest and all ten data files as one coherent
bundle (eleven files including the manifest). All input hashes are recorded in
`analysis_metadata.json`, alongside the analysis-code hash, package versions,
source version, unchanged financial endpoints and output hashes.

No Yahoo request, ignored market cache or strategy execution is needed. The
obsolete baseline near USD 625,050 is not used. Official endpoints remain:

- Strategy NAV: `6.225346615575381`
- Strategy value: `622534.6615575381` USD
- SPY NAV: `4.002530196823173`
- Strategy maximum drawdown: `-0.35452504758611847`

## Sample and missing observations

| Item | Value |
| --- | --- |
| Official research boundaries | 2016-01-01 through 2025-12-31 |
| Source rows / first / last date | 2,514 / 2016-01-04 / 2025-12-31 |
| Initial accounting anchor excluded | 2016-01-04, paired synthetic zero returns |
| Actual statistical first / last date | 2016-01-05 / 2025-12-31 |
| Strategy observations | 2,513 |
| SPY observations | 2,513 |
| Aligned observations | 2,513 |
| Missing paired rows removed in this source | 0 |

The initial zero row anchors normalized NAV and is not a measured close-to-close
return. Excluding it follows the existing Phase 6 volatility/return-period
convention; the source file and its NAV accounting remain unchanged. All later
zero returns, including genuine pre-investment cash days, are retained. The
analysis does not condition on being invested or delete legitimate extremes.

Alignment uses date keys and paired complete observations. The reusable helper
records any pairwise-missing exclusions without filling; infinities and invalid
or duplicate dates fail explicitly. In the approved source both series are
already complete. The existing artifact loader rejects corrupted/nonfinite
validated results rather than silently substituting data.

## Statistical conventions

The CSV table uses **daily decimal simple returns**, so 0.01 means 1%. Count,
skewness and kurtosis are not percentages. The narrative and figure axes show
return values as percentages; nothing is annualized in this diagnostic table.

- Count, arithmetic mean, median, minimum and maximum.
- Sample standard deviation: `ddof=1`.
- 25th and 75th percentiles: linear interpolation.
- Skewness: SciPy `skew(..., bias=False)`, adjusted Fisher–Pearson sample estimate.
- Excess kurtosis: SciPy `kurtosis(..., fisher=True, bias=False)`. Normal-reference
  excess kurtosis is 0, not 3.
- Constant samples have undefined skewness, kurtosis and normality tests, reported
  as missing/undefined rather than fabricated zero statistics or normality claims.

Jarque–Bera is the sole normality test; alpha is **0.05**. Its standard statistic
uses biased central moments internally, as `scipy.stats.jarque_bera` specifies:

`JB = n * (g1**2 / 6 + g2**2 / 24)`

Here `g1` is moment skewness and `g2` is moment Fisher excess kurtosis, not the
bias-corrected estimates in the descriptive table. The asymptotic reference is
chi-square with two degrees of freedom. H0 is the normal skewness/kurtosis
restriction. Reject H0 only when `p < 0.05`; otherwise **do not reject**, which
is not proof of normality.

Very large statistics cause double-precision p-values to underflow to `0.0`.
The CSV explicitly flags this and records `Log p-value = -JB/2`, using the exact
chi-square(2) survival identity. A stored zero does not mean exact probability
zero. No optional extra tests were added.

## Results

Return-valued entries below are percentages of daily returns; CSV values remain
decimals. Skewness and excess kurtosis are dimensionless.

| Statistic | Strategy | SPY |
| --- | ---: | ---: |
| Count | 2,513 | 2,513 |
| Mean | 0.083366% | 0.061655% |
| Median | 0.118532% | 0.073115% |
| Sample SD | 1.452504% | 1.134352% |
| Minimum | -12.362296% | -10.942366% |
| 25th percentile | -0.521491% | -0.357581% |
| 75th percentile | 0.803003% | 0.594312% |
| Maximum | 13.205530% | 10.501940% |
| Skewness | -0.226640 | -0.320631 |
| Excess kurtosis | 10.151643 | 14.732943 |
| Jarque–Bera | 10,764.357409 | 22,673.307197 |
| Log p-value | -5,382.178704 | -11,336.653598 |
| p-value | 0.0 (underflow) | 0.0 (underflow) |
| Conclusion at 5% | Reject H0 | Reject H0 |

Both samples have negative skewness and strongly positive excess kurtosis,
consistent with asymmetry and greater tail influence than the normal reference.
The strategy has a higher sample mean daily return and higher daily volatility;
SPY has greater standardized excess kurtosis. The Q-Q plots show marked tail
departures from their fitted normal reference lines. These describe this sample,
not causes, forecast superiority or a reason to change the baseline.

## Static figures and output files

All outputs are in **outputs/final_analysis/**. This narrowly scoped generated
folder is ignored, consistent with existing research-output conventions. No
historical Phase 0–9.1 output is overwritten.

- `descriptive_statistics.csv`
- `normality_tests.csv`
- `strategy_return_distribution.png`
- `spy_return_distribution.png`
- `strategy_qq_plot.png`
- `spy_qq_plot.png`
- `analysis_summary.md`: concise generated interpretation, not the final report.
- `analysis_metadata.json`: sample, conventions, provenance, software and hashes.

Histograms use common Freedman–Diaconis bins over both complete samples and
probability-density normalization. A fitted normal PDF uses each sample's mean
and sample SD in the same decimal-return units. Axes display returns as
percentages while density is explicitly per decimal-return unit. No clipping,
aggregation, winsorization or outlier deletion is performed.

Q-Q plots use SciPy normal theoretical order-statistic quantiles and a fitted
least-squares line. Every sorted observation is retained. Figures are independent
of Streamlit, exported at 300 dpi and 2250 × 1440 pixels. Legends, units and full
observed ranges are visible; the four static figures are intended for later
report insertion. Extreme observations can compress the histogram center; they
are preserved and this visualization limitation is explicit.

## Reproduction and tests

From the repository root with Python 3.12:

```bash
python -m pip install -r requirements-analysis.txt
python -B -m mft109.analysis.data_analysis
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -B -m pip check
git diff --check
```

`requirements-analysis.txt` adds pinned SciPy 1.18.1 and Matplotlib 3.11.2 to the
unchanged base requirements. Streamlit startup does not import this module and
its deployment dependencies remain unchanged. No editable install is needed.

On a restricted host with read-only home/config directories, writable temporary
cache locations may be specified for plotting, without changing numerical data:

```bash
MPLCONFIGDIR=/tmp/mft109-matplotlib-cache XDG_CACHE_HOME=/tmp/mft109-phase10a-cache \
  python -B -m mft109.analysis.data_analysis
```

`tests/test_data_analysis.py` adds 24 checks covering source identity/corruption,
anchor and paired alignment, counts, invalid inputs, independent scalar moment
formulas, percentile conventions, Jarque–Bera and p-values, alpha boundaries,
constant samples, underflow, histogram/PDF units, full Q-Q points, CSV schema,
PNG dimensions, protected destinations and source immutability. Full-cache
validation still requires the approved local research cache; these diagnostics
and their export alone need only the tracked deployment artifacts.

## Interpretation limits

Jarque–Bera is asymptotic. These 2,513-return samples exceed the usual large-sample
rule of thumb, but financial-return serial dependence and volatility clustering
still limit textbook p-value calibration. Large samples can reject small
violations. Marginal normality testing does not test independence, establish
causality, determine whether a strategy is good or bad, or invalidate the backtest.
The fixed current S&P 500 snapshot still introduces survivorship bias. No
strategy parameter is changed in response to the diagnostics.

Final validation:

| Check | Result |
| --- | --- |
| New Phase 10A tests | 24 passed; 0 failures/errors; 0 skipped |
| Complete repository suite | 428 passed; 0 failures/errors; 0 skipped |
| Existing tests | All 404 passed |
| Source, code and output checksums | PASS |
| Repeat export | All eight files byte-identical |
| Figure dimensions and visual inspection | Four 2250 × 1440 PNGs; PASS |
| Dependency / whitespace checks | PASS / PASS |
| Protected existing files | 1,164 unchanged |
| Validated NAV, USD value and maximum drawdown | Unchanged |

The only modified pre-existing files are the authorized analysis placeholder and
its scoped generated-output ignore rule. Base requirements, README, performance
logic, dashboard code/data, cache and historical outputs remain unchanged.
Expected prior invalid-date/mocked-data and Streamlit test-harness diagnostics
remain distinct from failures; no new statistical test or application failures
remain. Phase 10B, the final course report, PPT, comprehensive packaging and
submission exports have not started. Work remains uncommitted for review.

**PHASE 10A READY FOR REVIEW: YES**
