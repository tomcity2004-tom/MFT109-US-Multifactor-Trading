# Phase 1 data pipeline

Run commands from the repository root with the virtual environment active.
No factor calculations or performance statistics are produced.

```bash
# Fetch the current universe once, or validate the saved fixed snapshot.
python -m mft109.data.pipeline --universe-only

# Full fixed universe plus separate SPY benchmark; resume from valid caches.
python -m mft109.data.pipeline

# Limited live smoke test (always includes SPY); not a full-universe validation.
python -m mft109.data.pipeline --tickers AAPL BRK-B

# Intentionally replace successfully retrieved price caches, not the universe.
python -m mft109.data.pipeline --refresh
```

## Universe and reproducibility

The first successful run saves `data/raw/sp500_constituents.csv`, containing
`ticker`, `yahoo_ticker`, `company_name`, and `sector`. The maintained
[datasets/s-and-p-500-companies CSV](https://github.com/datasets/s-and-p-500-companies)
is a Wikipedia-derived current constituent source, not an official index feed.
The sidecar records retrieval time, source URL, count, and canonical SHA-256.
If present, its hash is checked on reload; a modified snapshot raises an error.
The source must have a plausible 450–550 securities, including share classes.

Existing valid snapshots are always reused, even with `--refresh`. An invalid
snapshot raises an error rather than triggering replacement. There is deliberately
no automatic universe-refresh switch: replacing the research universe requires
explicit review, preserving the old snapshot and documenting the change. The small
CSV and metadata are exempted from `.gitignore` for version control. The local
capture date is not a claim of historical membership or an independent audit of
source freshness. Using current constituents for 2016–2025 introduces survivorship
bias and can include companies with only partial historical data.

Original symbols are retained. Download identifiers strip surrounding whitespace,
use uppercase, and replace dots with hyphens, e.g. `BRK.B` → `BRK-B` and
`BF.B` → `BF-B`. Duplicate identifiers and conversion collisions are errors. SPY
is explicitly prohibited from the constituent snapshot.

## Prices and volume

The adapter explicitly requests `auto_adjust=True`, `back_adjust=False`,
`repair=False`, daily frequency, regular sessions, `keepna=True`, and no rounding.
With the pinned yfinance version, Open/High/Low/Close are adjusted for corporate
actions; Volume remains the Yahoo/yfinance reported volume, not rescaled by the
price adjustment ratio. `adjusted_close` explicitly aliases that adjusted Close.
No `Adj Close` column is required or guessed. A malformed/missing OHLCV response
raises an error; it is not substituted with unadjusted data.

The internal long format is:

```text
date | ticker | open | high | low | close | adjusted_close | volume
```

Each observation is uniquely identified by session date and Yahoo ticker. Daily
exchange-local session dates lose the timezone without UTC date shifting.
Both common yfinance MultiIndex column orientations are supported.

Research boundaries in configuration are inclusive. Because yfinance's end date
is exclusive, the request ends on **2026-01-01**, covering through **2025-12-31**.
The data start is 2015-01-01. The official evaluation period remains
2016-01-01 through 2025-12-31; Phase 1 does not evaluate performance.

## Validation and conservative cleaning

Structural validation rejects empty datasets, absent columns, invalid/intraday or
timezone-aware internal dates, missing/unexpected tickers, nonnumeric values,
conflicting duplicates, observations outside request bounds, and histories with no
usable adjusted price. Exact duplicate rows are collapsed and counted.

Nonfinite or nonpositive prices and nonfinite or negative volume are converted
to missing values and counted by field. Zero volume is retained. Original missing
values remain missing. There is no forward filling, zero-price imputation,
winsorization, outlier removal, synthetic price generation, or calendar reindexing.
Cleaning occurs separately from acquisition. Price anomalies outside these rules
are not automatically corrected.

A limitation of the pinned yfinance adapter is that yfinance itself converts null
source Volume to zero before returning data. We preserve its reported series;
zeros cannot reliably be classified as source nulls versus reported zero activity.
Missing-volume diagnostics therefore count missing values present in the returned
series, not all nulls in Yahoo's original response. This upstream limitation is
not hidden by claiming complete source-volume observability.

Validation reports missing prices and volumes, valid-price date range, and late
starts/early ends beyond a seven-calendar-day boundary tolerance. Stock coverage
warnings are retained, including IPOs and unavailable pre-listing history. Missing
stock rows are counted against actual SPY session dates and listed explicitly;
exchange holidays are not incorrectly counted as missing weekdays.

SPY must have usable prices across the requested date boundaries and no missing
market fields. A failed/incomplete benchmark stops the run with a nonzero exit.
This is approximate coverage validation, not an independent exchange-calendar
certification. Other stock failures are collected, the run exits nonzero, and
successful caches remain available for resuming. Stocks with partial but usable
history stay in the fixed universe and are not silently discarded. Later phases
must enforce the all-four-valid-factors eligibility rule.

## Cache contract and diagnostics

One compressed Parquet per symbol is kept under:

```text
data/cache/market/stocks/<YAHOO_TICKER>.parquet
data/cache/market/benchmark/SPY.parquet
```

Each has a JSON manifest with inclusive request bounds, symbol, role, schema
version, explicit adjustment policy, installed yfinance version, universe hash
(for stocks), retrieval timestamp, Parquet checksum, and cleaning/quality counts.
Files are reused only when the identity and checksum match and validation passes.
Corrupt/mismatched files trigger a logged download attempt. Offline failures raise
an error; stale data is not silently presented as a successful refresh. A failed
download or validation leaves a prior good cache intact. Temporary writes prevent
partial Parquet files from being published; an interrupted manifest update is
detected by checksum validation on the next run. Concurrent writes to the same
symbol are not a supported workflow; run one pipeline at a time.

No duplicate combined CSV/Parquet history is generated. Successful per-symbol
writes allow a failed run to resume without redownloading successful symbols.
yfinance's small timezone/cookie runtime cache is local, ignored, and must never
be committed or printed.

`data/processed/data_quality.json` records full-run status, mode, universe hash,
selected tickers, benchmark results, per-stock missingness and SPY session gaps,
cleaning changes, cache hits, warnings, and failures. Smoke reports are saved as
`data_quality.smoke.json` to preserve the latest full-run report. A smoke success
is not evidence of a full download. Inspect the report even when the run completes:
completion does not imply every current constituent has the full 2015–2025 history.

`DataSettings` controls operational paths, source, timeout, schema version, and
coverage tolerance; `BaselineSettings` retains approved research settings.

## Dependencies, tests, and network

Only pandas, NumPy, yfinance, and PyArrow are direct requirements. The pinned
versions were installed with normal TLS verification. Standard-library unittest
and temporary fixtures/mocks cover the pipeline without live access:

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
```

The installed yfinance 1.7.0 emits pandas 3.1 deprecation warnings. They do not
indicate failed downloads and have not been suppressed. Upgrades need adapter
revalidation and invalidate caches through the stored yfinance version.

Required source host: `raw.githubusercontent.com`. Yahoo's data/cookie flows use
`query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`,
`guce.yahoo.com`, and `consent.yahoo.com`. Proxy denial, rate limits, and
unavailable symbols are reported clearly; no fabricated fallback or alternative
market-data provider is used. Yahoo history may be revised upstream; a deliberate
refresh changes the data capture and should be documented in research records.
