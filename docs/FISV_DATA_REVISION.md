# User-approved FISV source-data revision

## Approval and scope

The user explicitly approved the complete Yahoo Finance revision: restore the
reported 2025-11-12 OHLCV observation and accept Yahoo's Volume revisions on
2025-10-16, 2025-10-22 and 2025-11-19. This is a source-data version update, not
price imputation, a ticker substitution, or a strategy-methodology change.

Only the official FISV Parquet cache and its metadata were replaced. The fixed
universe, all other stock/SPY caches, configuration and calculation code were
unchanged by this update. The existing yfinance 1.7.0 adapter, normalization,
cleaning and validation functions were used with their existing settings:
daily data, 2015-01-01 through 2025-12-31 inclusive, auto_adjust=True,
back_adjust=False, repair=False and reported Volume.

## Traceability and recovery

The archive is under ignored cache storage:

`data/cache/market/revisions/FISV/20261029T170124Z/`

The directory timestamp is UTC (2026-10-30 01:01:24 Hong Kong time). It contains:

- Byte-preserved `original_FISV.parquet` and `original_FISV.json`.
- The original Phase 7 output files in `previous_phase7_outputs/`.
- `before_hashes.json` covering pre-update project/data/result files.
- Candidate normalized Parquet, cleaning/validation results and exact cell changes.
- Full `query1_response.json` and `query2_response.json` source responses.
- `revision_audit.json` with approval scope, URLs, UTC retrieval times, response
  hashes, old/new Parquet hashes and the nine changed cells.

The active FISV metadata retains the original request identity and adds a
`data_revision` record. Its new hash, retrieval time and validation report match
the replacement cache. The existing cache loader confirmed a validated cache hit
with downloader fallback explicitly disabled.

| Version | Parquet SHA-256 |
| --- | --- |
| Previous | `8a6c9bbcd35cee33f708b312ccb102a122ceabc98b140f95b9986ac450842166` |
| Revised | `6a4c15da950254d215d8b7db0835e376fb659d67e2d869e299797d8d4f01dcf1` |

To restore the previous data version, verify the archived original against its
saved metadata hash, then restore **both** original files as a pair. Old and new
results must not be mixed or relabeled as the same data version. Cache/runtime
files and source receipts remain ignored and must not be committed.

## Observed changes

All 2,766 session dates and all other numerical observations are unchanged.
There are exactly nine changed cells:

| Date | Field | Previous | Revised |
| --- | --- | ---: | ---: |
| 2025-11-12 | Open | NaN | 64.19999694824219 |
| 2025-11-12 | High | NaN | 64.87000274658203 |
| 2025-11-12 | Low | NaN | 63.11000061035156 |
| 2025-11-12 | Close | NaN | 64.37999725341797 |
| 2025-11-12 | Adjusted Close | NaN | 64.37999725341797 |
| 2025-11-12 | Volume | 0 | 6,244,700 |
| 2025-10-16 | Volume | 5,394,700 | 5,384,800 |
| 2025-10-22 | Volume | 3,953,600 | 3,952,900 |
| 2025-11-19 | Volume | 5,086,100 | 5,077,000 |

Both Yahoo chart endpoints confirmed the restored prices and all four Volume
observations. Source URLs, including query parameters, are retained in the audit:

- https://query1.finance.yahoo.com/v8/finance/chart/FISV?period1=1420070400&period2=1767225600&interval=1d&events=div%2Csplits
- https://query2.finance.yahoo.com/v8/finance/chart/FISV?period1=1420070400&period2=1767225600&interval=1d&events=div%2Csplits

No cause such as a listing/ticker transition has been established for the original
gap. Current availability under the same FISV symbol is verified; a causal claim
about why the vendor previously omitted the row is unnecessary and unproven.

## Revalidation and baseline version comparison

The complete existing test suite passed: **320 passed, zero failures/errors,
zero skips**. Dependency and whitespace checks passed. All six Phase 7 groups
produced the intended 21 rows and all 21 now complete through 2025-12-31, with
2,514 official sessions and zero missing-price events. The 5-day reversal and
reversal-weight tilt no longer stop on FISV's missing observation.

Revised generated outputs are separate from the original outputs:

`outputs/optimization/fisv_revision_20261029T170124Z/`

The directory contains six scenario tables, old/new scenario comparisons, new
baseline daily/annual/summary outputs, resolved-scenario daily evidence and a
`validation.json`. Original Phase 5/6 reports and original Phase 7 tables remain
historical evidence of the previous data version; they were not overwritten.

The baseline **methodology** remains identical, but its **empirical results**
change under the approved revised dataset:

| Baseline output | Previous data | Revised data |
| --- | ---: | ---: |
| Cumulative return | 525.0502799344% | 522.5346615575% |
| CAGR | 20.1747420844% | 20.1261530065% |
| Annualized volatility | 23.0537061774% | 23.0577861766% |
| Sharpe ratio | 0.8751192511 | 0.8728571274 |
| Maximum drawdown | -35.4525047586% | -35.4525047586% |
| Final strategy NAV | 6.250502799343636 | 6.225346615575381 |
| Final strategy USD | 625,050.2799343636 | 622,534.6615575381 |
| Final SPY NAV | 4.002530196823173 | 4.002530196823173 |

All six baseline rows reproduce the same revised-data baseline. This does not
mean they exactly reproduce the old-data baseline; that distinction is recorded
explicitly in `validation.json`. Yahoo data are revisable historical data, not
a point-in-time archive. New results require review with their data provenance;
no parameter was changed to improve or preserve reported performance.

An additional archived-data replay exactly reproduced the approved Phase 6
metrics and final NAV using the previous FISV cache with the current unchanged
calculation code. Comparing baseline selections identifies one changed formation:
on **2025-11-28**, **PANW replaces V** in Top 20. The first changed daily return
is **2025-12-01**, consistent with next-session execution. The final USD difference
is **-2,515.6183768254705**. The separate generated
`baseline_vintage_attribution.json` and old-vintage baseline daily series retain
this evidence.

No commit, push, pull request, or Phase 8 work accompanies this update.
