# Phase 3 — Factor Standardization and Composite Scoring

Phase 3 consumes the existing Phase 2 raw outputs. It does not recalculate raw
factors, change the fixed universe, or implement investment ranking/selection.
PROJECT_REQUIREMENTS.md and the explicit Phase 3 request define the methodology.

## Eligibility and output model

`scoring_eligibility(raw_factors)` returns a Boolean mask: a date/ticker row is
eligible only when **all four** canonical raw factors are finite. NaN, missing,
positive infinity, or negative infinity in any factor makes that row ineligible
for every score. Zero raw volatility is valid. Phase 2 remains responsible for
the raw formulas and required lookback completeness.

All four factor statistics use the same eligible stocks on the same date. A
stock missing liquidity cannot influence momentum or volatility statistics on
that date. Eligibility is recalculated independently each date, so a stock can
become eligible again. It is never permanently removed from the fixed universe.

The API uses output option **B** from the Phase 3 request: preserve every supplied
raw row, append `eligible`, and leave all five scores NaN on ineligible rows.
If a date has zero eligible stocks, its raw rows remain unscored; it has no scored
stock rows and no fabricated placeholder scores. FDXF/HONA/VYLR consequently
remain represented with NaN scores when their Phase 2 inputs are unavailable.

Required input columns:

```text
date, ticker, momentum, volatility60, liquidity_raw, reversal20
```

The result preserves those six canonical columns and adds:

```text
eligible, momentum_score, low_volatility_score, liquidity_score,
reversal_score, composite_score
```

Extra input columns are not carried into the canonical scoring output. The input
DataFrame is not modified. Duplicate date/ticker observations, unidentified
tickers, SPY benchmark rows, malformed dates, missing/duplicate columns, and
nonnumeric factor schemas raise errors rather than silently changing the sample.
Output is sorted by date/ticker for deterministic presentation, never by score.
Scoring applies to dates supplied by the caller; no monthly formation schedule
or rebalance execution is implemented here.

## Cross-sectional Z-scores and directions

For eligible stocks on date t, use:

```text
Z(i,t) = (X(i,t) - Mean_t(X)) / Std_t(X, ddof=0)
```

This is a population cross-sectional standard deviation, **ddof=0**. Phase 2
historical volatility still uses **ddof=1** on trailing daily returns. No Phase 2
formula or convention was changed. No statistics are calculated through time
within a stock, across dates, or using future eligibility.

| Raw Phase 2 column | Phase 3 column | Direction |
| --- | --- | --- |
| `momentum` | `momentum_score` | Z(momentum) |
| `volatility60` | `low_volatility_score` | -Z(volatility60) |
| `liquidity_raw` | `liquidity_score` | Z(liquidity_raw) |
| `reversal20` | `reversal_score` | Z(reversal20) |

These are the snake_case equivalents of MomentumScore, LowVolatilityScore,
LiquidityScore, and ReversalScore. Higher scores are better for all four factors.
Volatility's sign is reversed exactly once, only in its standardized score.
Reversal is not negated again because Phase 2 already defines its preferred sign.

When a factor is identical across eligible stocks, every eligible stock receives
0.0 for that factor. This is a neutral score for an observed constant factor,
not missing-data imputation. Other factors still contribute normally. One
eligible stock gets four zero scores and a zero composite. Ineligible peers keep
NaN, including on constant-factor and single-stock dates.

The Z-score helper uses common positive rescaling and centering to avoid
overflow/underflow when finite raw inputs are extreme. Both operations cancel
algebraically in Z; they do not clip inputs, change the eligible universe, or
introduce a near-zero-variance cutoff. Tiny nonzero dispersion is standardized;
only exactly constant groups receive neutral zeros. Unrepresentable results
raise a clear error rather than publishing infinity or fabricating a score.

## Locked equal-weight composite

`baseline_factor_weights()` reads the existing `BaselineSettings` fields. Each
weight must be finite and exactly 0.25, and the four weights must sum exactly
to 1.0. No alternate/custom weights or optimization framework were added.

```text
composite_score = 0.25 * momentum_score
                + 0.25 * low_volatility_score
                + 0.25 * liquidity_score
                + 0.25 * reversal_score
```

Explicit addition propagates missing scores; weights are never redistributed
or dynamically renormalized. There is no skip-NaN sum that turns missing factors
into zero or partial composites.

## Reusable API and scope

```python
from mft109.processing import score_factors

# raw_factors is the existing calculate_raw_factors(...) Phase 2 result.
scored = score_factors(raw_factors)
```

`standardize_factors(...)` exposes eligibility and the four direction-adjusted
scores without the composite. `score_factors(...)` additionally applies the
locked weights. No network requests, file writes, raw-factor calculations,
additional dependencies, or changes to baseline configuration are required.

No winsorization, score clipping, interpolation, forward/back filling, or
cross-sectional-mean imputation is performed. Only same-date eligible raw
information is used. Changing future rows, eligibility, or factor values does not
alter earlier scores. The input data and Phase 2 raw outputs remain unchanged.

There are **no rank numbers, score-sorted investment lists, Top 20 selections,
portfolio allocations, turnover, costs, benchmark comparisons, backtesting,
performance metrics, optimization, or dashboard logic**. Phase 4 was not started.

## Validation record

Validated on 2026-10-29:

- Complete suite: **116 passed, 0 failed/errors, 0 skipped**. All existing 76
  Phase 0/1/2 tests pass; 40 new Phase 3 tests cover eligibility, same-date
  population statistics, directions, zero variance, one/zero eligible stocks,
  composites, fixed weights, outliers, numerical extremes, missingness,
  nonmutation, chronology, and future-data invariance.
- `git diff --check`, new-file whitespace checks, and dependency checks passed.
  No formatter or new dependency was introduced.
- Cached sample: AAPL, MSFT, BRK-B, FISV, SNDK, Q, FDXF, HONA, and VYLR on
  2,766 SPY sessions, using existing Phase 1 caches and Phase 2 functions.
  It produced 24,894 raw-preserving rows: **10,022 eligible/scored** and
  **14,872 ineligible/unscored**, with scored stocks on 2,514 dates.
- All five score columns are present. Eligible scores are finite; ineligible
  scores are all NaN. No rank/selection columns exist. SNDK/Q and the three
  unavailable symbols remain unscored; FISV is unscored at November/December
  2025 month-end because its existing price gap invalidates required raw inputs.
- Cross-sectional means of all four scores have maximum absolute deviation
  **2.78e-16** from zero. Population score standard deviations match 1 for
  nonconstant groups (0 for constant groups). Independent scalar formulas were
  checked on 2016-01-29, 2020-12-31, 2025-11-28, and 2025-12-31. Lower raw
  volatility receives the higher low-volatility score.
- Cache checksums and saved-universe fingerprints were verified. No market data
  was downloaded or modified, and raw-factor outputs were checked unchanged.
- Protected-file hashes confirm unchanged specifications, baseline configuration,
  dependencies, Phase 1/2 modules/tests, fixed universe, and data files.

The existing Phase 1 invalid-date fixture emits a pandas date-parsing warning;
its test passes. Mocked cache/download-failure tests also emit expected logs.
No new scoring warnings or unresolved Phase 3 methodology issues were found.
Existing survivorship bias, unavailable histories, initial warm-up boundary,
and yfinance source-null Volume handling remain as documented in earlier phases.

Changes are left uncommitted on `phase-3-factor-scoring` for review. No push,
pull request, merge, or Phase 4 work is included. The recommended next phase,
only after approval and explicit instruction, is Phase 4 stock ranking and
portfolio construction.
