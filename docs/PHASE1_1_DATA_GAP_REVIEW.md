# Phase 1.1 Data-Gap Review

Review date: 2026-10-23. Scope: read-only investigation of existing inputs and
public Yahoo metadata. No universe edits, history substitution, data refresh,
factor calculation, or methodology changes were performed.

## Recommendation

**Accept Phase 1 for progression to Phase 2 factor development**, with the gaps
below explicitly retained. This accepts the pipeline and available inputs, not a
claim that all 503 constituents have complete historical coverage. The full-run
report correctly remains `incomplete`: 500 stock histories plus SPY are available.

Keep all 503 securities in the fixed universe. At each monthly formation date,
admit a stock only if all four required factor values are valid and available.
Unavailable history must yield missing factors and ineligibility for the affected
months, never zero/mean-filled factors. No Phase 2 work is included in this review.

## Three unavailable requested-period histories

Company names and tickers below are copied from the saved universe snapshot.
Yahoo recognizes each unchanged symbol as an equity and returns recent 2026
observations. Independent chart probes for 2015–2025 again returned
`Data doesn't exist` for all three. This is not evidence of a symbol-normalization
failure, and the source's index addition dates are not being treated as IPO dates.

| Saved company name | Original source ticker | Yahoo ticker used | Yahoo `firstTradeDate` session | Normalization check |
| --- | --- | --- | --- | --- |
| FedEx Freight | FDXF | FDXF | 2026-05-27 | Correct unchanged symbol; no share-class punctuation |
| Honeywell Aerospace | HONA | HONA | 2026-06-15 | Correct unchanged symbol; no share-class punctuation |
| Vylor | VYLR | VYLR | 2026-10-01 | Correct unchanged symbol; no share-class punctuation |

The first-trade dates above describe Yahoo's coverage for those symbols; they do
not independently establish legal security inception, regular-way listing dates,
or continuity through corporate actions.

- **FDXF:** Yahoo identifies FedEx Freight Holding Company, Inc., incorporated in
  2025, with standalone symbol coverage beginning in 2026. This is consistent with
  the FedEx Freight separation/new standalone listing, rather than a missing dot
  or hyphen conversion. `FDX` has older Yahoo history, but it represents FedEx
  Corporation, the parent, not a verified historical alias for the same FDXF
  security. No same-security pre-2026 Yahoo alias was established. Retain FDXF
  with no usable requested-period history and make it ineligible throughout the
  official backtest unless valid same-security inputs become available through
  a separately reviewed correction.
- **HONA:** Yahoo identifies Honeywell Aerospace Inc. and describes it as a prior
  subsidiary of Honeywell International. Its independent symbol coverage starts
  in 2026, consistent with the aerospace separation. `HON` has older Yahoo
  history, but is the parent/remainco line, not a verified historical alias of
  standalone HONA shares; HON is also a separate fixed-universe constituent.
  No same-security pre-2026 alias was established. Keep HONA unchanged and
  ineligible for all 2016–2025 formation dates with the current inputs.
- **VYLR:** Yahoo identifies Vylor Inc., a seed/genetics business, with symbol
  coverage starting in October 2026. Yahoo search metadata associates VYLR with
  the previous name Corteva, Inc.; a separate `CTVA` query returns Corteva and a
  reciprocal Vylor previous-name reference. CTVA chart history is available from
  2019-05-24 through 2025-12-31. This identifies a **Corteva-related
  reorganization/rename candidate**, not proof that CTVA and VYLR are the same
  historical security or an interchangeable return series. Source records also
  identify Vylor as a 2026 entity. Legal/share continuity and the vendor's alias
  handling remain unverified. Do not automatically splice CTVA, earlier DuPont
  history, or another listing into VYLR. Retain VYLR and treat its factors as
  unavailable throughout 2016–2025 under the current capture.

Direct issuer-site, investor-relations, Wikipedia-page, and Yahoo article-page
requests were blocked by the network proxy. Corporate descriptions and lineage
checks therefore rely on Yahoo chart/profile/search responses and the maintained
constituent source. No claim of definitive legal continuity is made from names,
search metadata, or first-trade dates alone. This limitation does not justify a
substitution; any future proposed security-identity mapping requires evidence and
explicit review before implementation.

## Classification of the 44 warned available histories

Counts were recomputed from cached Parquet observations and SPY session dates,
not merely inferred from warning strings. The first two rows are disjoint and
sum to 44; the other rows document checked categories with zero occurrences.

| Major warning category | Stocks | Finding |
| --- | ---: | --- |
| Leading coverage gap / late usable-history start | 43 | All 48,654 absent stock/session pairs precede the stock's first available price |
| Explicit missing prices within an otherwise available history | 1 | FISV, 2025-11-12; all five price fields missing |
| Absent rows inside a stock's available date range | 0 | No internal absent-row gaps against SPY |
| Trailing coverage gaps | 0 | Available histories extend through 2025-12-31 |
| Missing Volume values in the returned data | 0 | Subject to yfinance's upstream null-to-zero limitation |

The 43 leading-gap symbols are: ABNB, APP, BE, CARR, CEG, COIN, CRWD, CVNA, DASH,
DDOG, DELL, DOW, EXE, FOX, FOXA, FTV, GDDY, GEHC, GEV, HOOD, HPE, HWM, INVH, IR,
KHC, KVUE, LITE, MRNA, OTIS, P, PLTR, PYPL, Q, RDDT, SNDK, SOLV, TWLO, UBER,
VICI, VLTO, VRT, VST, XYZ.

These are coverage classifications, not assertions that every company IPOed on
its first Yahoo date. IPOs, spin-offs, relistings, reorganizations, and limited
vendor history can all produce leading gaps.

**Factor implications, without calculating factors:**

- A leading gap prevents any factor whose required price, return, or volume
  inputs are unavailable. A first quoted price alone is insufficient: momentum
  requires the 252-session lagged price and 21-session skipped endpoint;
  volatility requires 60 valid daily returns; liquidity requires its 20-day
  price/volume inputs; reversal requires its 20-session price comparison.
- Do not compress the trading calendar by dropping gaps, silently skip missing
  inputs in rolling calculations, or use future data to fill early history.
  Eligibility begins only at a formation date with all required inputs valid.
- SNDK has only 222 observations and Q only 46 through 2025-12-31. Neither has
  a 252-session lagged price during its available backtest history; neither can
  receive all four valid baseline factors in the official period from this
  capture. The three entirely unavailable symbols are likewise ineligible.
- Initial warm-up boundary: SPY has 252 observations in calendar 2015. At the
  2015-12-31 formation date a 252-session lag requires an earlier observation
  than this capture provides. This can prevent an initial January 2016 portfolio
  signal even for otherwise complete histories. Preserve missingness; do not
  silently extend dates, shorten momentum, or invent an initial portfolio.
  Record this for the later backtest-startup decision. It does not block correct
  factor implementation or change the official evaluation dates.

## FISV observation verification

The existing FISV Parquet file still contains exactly one row dated 2025-11-12.
`open`, `high`, `low`, `close`, and `adjusted_close` are all missing; Volume is
the returned 0. Adjacent adjusted closes are 64.26 on November 11 and 64.53 on
November 13. The missing row equals neither neighbor and was not interpolated,
forward-filled, or replaced with zero prices. Its Parquet content hash was
unchanged by this review.

The gap falls within the price inputs needed for the 60-return volatility window
at both 2025-11-28 and 2025-12-31 month-end. It also falls within the 20-session
liquidity inputs at November month-end, but not December month-end. Consequently,
FISV cannot enter either month's ranking when those required factor inputs remain
missing, even if another factor's endpoints happen to be valid. No numerical
factor values were computed to reach this input-availability conclusion.

The Volume value cannot prove there were no source-volume nulls: the pinned
yfinance version converts them to zero. This existing limitation is retained
explicitly; zero reported volume is not automatically changed or imputed.

## Evidence and verification

- Local evidence: `data/raw/sp500_constituents.csv`, its provenance sidecar,
  `data/processed/data_quality.json`, per-stock Parquet files/manifests, and SPY.
- [Maintained constituent source](https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv)
  corroborates index additions in 2026; the saved snapshot was not refreshed.
- Yahoo recent chart metadata:
  [FDXF](https://query1.finance.yahoo.com/v8/finance/chart/FDXF?range=1mo&interval=1d),
  [HONA](https://query1.finance.yahoo.com/v8/finance/chart/HONA?range=1mo&interval=1d),
  [VYLR](https://query1.finance.yahoo.com/v8/finance/chart/VYLR?range=1mo&interval=1d).
- Yahoo name/alias evidence:
  [VYLR search](https://query1.finance.yahoo.com/v1/finance/search?q=Vylor),
  [CTVA search](https://query1.finance.yahoo.com/v1/finance/search?q=CTVA),
  and [CTVA requested-period chart](https://query1.finance.yahoo.com/v8/finance/chart/CTVA?period1=1420070400&period2=1767225600&interval=1d).
- Read-only assertions checked all warning classifications, the FISV row, cache
  checksums, and protected-file hashes. No application code changed, so no new
  unit tests were added. Existing 37 passing Phase 0/1 tests are recorded in
  `PHASE1_VALIDATION.md`; that result is not described as a new test-suite run.

Only this report was created. Universe membership, snapshot/provenance files,
market caches, quality reports, baseline configuration, PROJECT_REQUIREMENTS.md,
AGENTS.md, and all factor placeholders were preserved byte-for-byte.
