# Phase 1 validation record

Validation date: 2026-10-23. This records current-machine evidence, not future
Yahoo availability or publication of an environment snapshot.

## Implementation and deterministic tests

- Python 3.12.14; pandas 3.1.0; NumPy 2.5.4; yfinance 1.7.0; PyArrow 26.0.0.
- `python -m unittest discover -s tests -v`: **37 passed**, no failures or skips.
  This includes all four existing Phase 0 tests and 33 Phase 1 tests.
- Coverage includes share-class conversion, source capture and provenance,
  snapshot reuse and tamper detection, adjusted-price layouts, inclusive date
  conversion, missing observations, invalid values, duplicate handling, cache
  identity/checksums/refresh, benchmark separation, reporting, and pipeline failure
  propagation. Tests use temporary data and mocks, not live Yahoo access.
- `python -m pip check`: no broken requirements.
- `git diff --check` and new-source whitespace checks passed.
- SHA-256 checks confirmed AGENTS.md and PROJECT_REQUIREMENTS.md unchanged.
- All 20 later-phase Python files remain docstring-only placeholders.

## Live universe and history

The current-source capture saved **503 securities** in
`data/raw/sp500_constituents.csv`, with source and retrieval metadata. The original
and Yahoo tickers are preserved; SPY is not a candidate stock. The local snapshot
is fixed and survives normal and explicit price-refresh runs.

The live AAPL / BRK-B / SPY smoke test succeeded. A cache-only CLI rerun loaded all
three without downloading. An explicit live smoke refresh also succeeded without
changing the fixed universe.

A full fixed-universe download attempted all 503 symbols and separately loaded
SPY. It saved **500 stock histories** containing **1,334,346 observations**, and
**2,766 SPY observations**. Combined observed coverage is **2015-01-02 through
2025-12-31**; individual stock histories can begin later.

The full run correctly exited **1** and reported `status: incomplete`, because
three symbols had no Yahoo history in the requested 2015–2025 window:

| Symbol | Current source company | Current source index addition date |
| --- | --- | --- |
| FDXF | FedEx Freight | 2026-06-01 |
| HONA | Honeywell Aerospace | 2026-06-29 |
| VYLR | Vylor | 2026-10-01 |

These source addition dates were inspected during diagnosis; they do not prove
first listing dates. Yahoo specifically returned no requested-period data for
these symbols. No predecessor-symbol reconstruction, fabricated history, universe
removal, or alternate data source was used. They remain fixed-universe members
and explicit failures. This prevents a claim of complete historical coverage of
all 503 current constituents. Repeating a download does not create unavailable
history.

## Data quality and limitations

- **44** available stock histories have coverage or missing-data warnings.
- **48,654 stock/session pairs** have no returned stock row compared with the
  SPY session calendar, including unavailable pre-listing histories. They remain
  absent, with dates listed per ticker in the report.
- **One** returned stock row has missing price fields: FISV on 2025-11-12.
  Open, High, Low, Close, and adjusted_close remain missing; Volume was returned
  as 0. No forward filling or fabricated prices were applied.
- Zero missing Volume values remain in the returned available histories. This is
  not evidence of no source nulls: yfinance converts source null Volume to zero.
- No invalid numerical values required masking and no exact duplicate rows
  required removal in this live capture. Those cleaning paths are tested offline.
- SPY has no missing returned market fields and spans the requested boundaries.
- Late starts include ABNB (2020-12-10), GEV (2024-03-27), and Q (2025-10-27).
  Later factor eligibility must use only available history.
- yfinance emits pandas 3.1 deprecation warnings; they were not suppressed and
  did not prevent the successful downloads.

The complete machine-readable diagnostics are in
`data/processed/data_quality.json`. Smoke diagnostics use
`data/processed/data_quality.smoke.json` and do not overwrite that full report.
The report distinguishes failed symbols, missing fields, absent rows, and cache
hits. Generated histories and reports are intentionally ignored by Git.

All **500 stock caches plus SPY** were subsequently loaded and validated with the
downloader patched to raise on any network attempt. All 501 loads succeeded as
cache hits. This verifies usable cached data, not recovery of the three absent
histories. Integrity and validation are checked on every cache load.

## Environment network configuration

Yahoo initially returned a proxy 403. A network draft was saved adding
`query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`,
`guce.yahoo.com`, and `consent.yahoo.com`, preserving existing presets. Later live
requests succeeded in the running environment. Draft saving alone is not a claim
of runtime application or publication. Review/save the draft and publish through
environment settings to retain the configuration for future tasks.

## Scope and next phase

Phase 1 code is implemented and tested; the full live historical dataset remains
incomplete for the three symbols above. No factors or official performance metrics
were calculated. No research methodology was changed.

Recommended next phase, only on explicit request: Phase 2 factor calculation.
Respect the documented incomplete histories and all-four-valid-factors eligibility;
do not fill gaps or reinterpret unavailable symbols as predecessor companies.
