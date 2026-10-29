# Phase 8 — Testing & Validation

## Objective and approved reference

Validate the complete Phase 0–7 system without redesigning the strategy, changing
production code, refreshing data or performing additional optimization. Phase 9
and Phase 10 are outside this work.

The regression reference is the **reviewed Phase 7 revised-data baseline**:

- Final strategy NAV: `6.225346615575381`.
- Final strategy value: `622534.6615575381` USD.
- Final SPY NAV: `4.002530196823173`.
- Initial capital: USD 100,000; initial NAV: 1.

These constants exist only in tests/documentation, never in production trading
logic. The earlier Phase 6 result near USD 625,050.28 describes the previous data
version and is not restored. The approved revision and its provenance are
documented in [FISV_DATA_REVISION.md](FISV_DATA_REVISION.md).

## Test scope and organization

The initial, unchanged Phase 0–7 suite ran first: **320 tests passed, zero
failures/errors, zero skips**. Earlier tests were not edited or weakened.

New Phase 8 files:

| File | Responsibility |
| --- | --- |
| `tests/phase8_support.py` | Read/check approved cache without downloader fallback; shared offline fixtures and input fingerprints |
| `tests/test_end_to_end_validation.py` | Real-data factor/scoring/ranking/accounting/benchmark/performance integration and independent scalar checks |
| `tests/test_reproducibility.py` | A second full baseline calculation, comparing intermediate and final outputs |
| `tests/test_regression_baseline.py` | Approved revised-data NAV/USD/SPY expectations and reviewed November selection |
| `tests/test_pipeline_integrity.py` | Cross-module future-data/stale-score checks, all approved sensitivity groups and file integrity |

Existing deterministic tests remain responsible for isolated edge cases already
covered in earlier phases: empty input, one eligible stock, shortages, zero
cross-sectional variance, duplicate observations, invalid dates, missing factor
inputs, missing execution/held prices, initial/cash turnover, partial/full
replacement, zero volatility, partial years and calendar boundaries. Phase 8
adds integration evidence rather than copies of those tests.

## Reproduction commands and offline policy

From the repository root, with the existing pinned environment:

```bash
MFT109_REQUIRE_APPROVED_CACHE=1 .venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B -m pip --no-cache-dir check
git diff --check
```

The cache reader checks saved request identities, universe provenance, Parquet
checksums and Phase 1 validation before calculation. It reads 500 available stock
histories and SPY while retaining all 503 fixed-universe symbols. The approved
FISV Parquet SHA-256 is pinned in the test fixture. Other cache corruption or an
unexpected absent ticker fails clearly; no refresh or alternate ticker is tried.

The test-only offline context rejects calls to `yfinance.download`, the pipeline
downloader, `urllib.request.urlopen`, socket creation helpers and socket connect.
Both baseline repetitions and sensitivity execution occur inside this context.
No generated result files are required or overwritten by the tests.

If the entire approved local cache is absent in a fresh checkout, integration
classes may explicitly skip with a message stating official validation was not
completed. Setting `MFT109_REQUIRE_APPROVED_CACHE=1` converts that absence into a
failure. **An overall Phase 8 PASS requires the real-cache checks to execute;
skipped cache validation is not evidence of baseline reproduction.**

## End-to-end validation and reproducibility

The public production functions are called in their normal order:

```text
validated cached observations
→ calculate_raw_factors
→ score_factors
→ rank_and_select
→ run_backtest
→ analyze_performance
```

A second full calculation with identical inputs checks raw factors, standardized
scores, composites, rankings, selections, formation summaries, holdings, weights,
turnover, costs, daily returns, NAV, USD value and all performance tables. This is
not a second read of saved output files. All six sensitivity baseline rows are
also compared against that separately calculated default baseline.

Each major module boundary fingerprints its inputs before and after use.
Configuration and fixed-universe inputs are checked as well. Assertions do not
replace, fill, rebase or otherwise mutate the source frames.

Floating-point checks generally use relative tolerance `1e-12`; scalar factor
checks allow `1e-10`, and direct population-Z checks allow absolute `1e-10` for
ordinary centering differences. Approved endpoint tests allow absolute NAV error
`1e-11` and USD error `1e-6`. Dates, tickers, flags and selections must agree
exactly. No result is rounded before calculation to force a passing comparison.

## Factors, standardization and eligibility

Independent real-price checks cover AAPL, BRK-B and FISV at multiple historical
positions, including the final available observation:

- Momentum: `P(t-21)/P(t-252)-1` using trading-session positions.
- Volatility: exactly 60 consecutive simple returns; `statistics.stdev` with
  `ddof=1`, then `sqrt(252)`.
- Liquidity: natural logarithm of the 20-session mean of adjusted price times
  Yahoo-reported Volume.
- Reversal: `-(P(t)/P(t-20)-1)`.

For every official formation, independently calculated population mean/std
verify Z-scores over the common all-four-valid eligible set. Directions remain
`+Momentum`, `-Volatility`, `+Liquidity`, `+Reversal`; the baseline composite is
the sum of four 25% contributions. Missing-factor rows retain NaN scores and
composites, without partial reweighting, winsorization or fabricated values.

Known eligibility cases:

| Symbol | Expected approved-data behavior |
| --- | --- |
| FDXF, HONA, VYLR | Retained in the fixed universe with all-NaN factors; never ranked/held |
| SNDK, Q | Cached histories are too short for baseline momentum in this sample; remain ineligible |
| FISV | Approved source revision restores 2025-11-12; eligible at November/December 2025 formations |

A removed stock session remains a missing observation on the SPY clock, never a
compressed lag. A test removes an otherwise valid month-end observation and
checks that the prior day's valid score is not substituted into that formation.

## Ranking, portfolio and execution validation

Plain-Python ordering independently verifies every monthly ranking: composite
descending, ticker ascending, unique sequential ranks, first 20 eligible names.
Month-ends are the last actual SPY sessions. There are 120 formations and 119
executed rebalances; the first formation/execution is 2016-01-29 / 2016-02-01.
The final 2025-12-31 signal has no official execution.

Targets contain the selected executable names at 5% in the normal 20-name case.
Daily holdings are unique, nonnegative and reconcile to weights summing to 1 and
the recorded portfolio value. SPY is not a strategy constituent. Existing tests
cover entry-price exclusions without Rank 21 replacement and held-price errors
without invented valuation or liquidation.

The cross-module leakage test changes only future adjusted-price observations
in copied input frames. Earlier raw factors, standardized factors, composites,
rankings, selections, execution records, holdings, weights, turnover, costs,
returns and NAV must remain unchanged. This extends isolated prior-phase leakage
tests across the complete calculation chain.

## Turnover, transaction costs and NAV

All 119 baseline rebalances are independently reconstructed from the preceding
session's fixed units, valued at the execution session's adjusted close. Pre-cost
wealth gives drifted pre-rebalance weights. Over the stock/cash union:

```text
turnover = 0.5 * sum(abs(target_weight - pre_rebalance_weight))
cost_fraction = turnover * 0.001
cost_usd = pre_cost_wealth * cost_fraction
post_cost_wealth = pre_cost_wealth * (1 - cost_fraction)
```

Initial cash-to-stock turnover is 1 and costs USD 100. Daily accounting also
checks `net_return = (1 + gross_return) * (1 - cost_fraction) - 1`, with no fees
on non-rebalance sessions. This detects double charging or an incorrect order.
Weights drift between rebalances; tests do not assume daily equal-weight resets.

All 19 official January 2016 sessions before first execution retain return 0,
NAV 1 and USD 100,000. Net returns compound to NAV without monthly/yearly resets;
portfolio value equals initial capital times NAV within floating-point tolerance.

## SPY, performance metrics and annual returns

SPY uses the separate adjusted-price buy-and-hold path anchored at its first
official close. Direct adjusted-price ratios independently verify daily returns
and NAV; no strategy cost is charged to SPY.

For both Strategy and SPY, scalar checks independently verify cumulative return,
CAGR using 2,513 close-to-close periods, sample annualized volatility, the approved
0%-risk-free CAGR/volatility Sharpe and minimum running-peak drawdown. Annual
returns for 2016–2025 use actual year-end observations and the preceding year's
final NAV, with the first year's initial NAV as anchor. All 20 annual values
are recomputed; December 31 is not assumed to be a trading day.

## Sensitivity framework

The approved six groups remain 4 Top-N, 4 cost, 2 frequency, 3 volatility-window,
3 reversal-window and 5 weight rows: exactly 21. Each changes one methodological
dimension only and retains one explicit baseline row per table. There is no
Cartesian product, additional experiment or automatic best-parameter selection.

All runs must reach the final official date, retain common SPY and contain finite
required metrics. The two formerly blocked FISV scenarios explicitly verify a
positive held position valued at the approved reported price on 2025-11-12.
Quarterly validation retains 40 formations and 39 executions, beginning 2016-04-01.

## File integrity and limitations

Tests hash all cached/approved data, universe, archives, existing output files,
production Python, configuration and primary specifications before/after use.
The task's separate initial file snapshot additionally protects all existing
tests and documentation, except the authorized README status update. No prior
test or production module is edited during Phase 8.

The project uses a **fixed current S&P 500 constituent snapshot throughout the
historical backtest and therefore contains survivorship bias**. Historical
membership is not reconstructed. Yahoo historical data are revisable, so the
approved FISV revision and dataset identity matter for reproducibility. This is
not a point-in-time fundamentals feed or proof against every possible research
bias. Adjusted-close execution, fractional units, zero cash interest and the
existing cost model remain simplified academic conventions. Tests establish
specified behavior, not future profitability or production execution realism.

## Validation status

| Run/check | Result |
| --- | --- |
| Initial existing Phase 0–7 suite | 320 passed; 0 failures/errors; 0 skips |
| New Phase 8 tests | 30 passed; 0 failures/errors; 0 skips |
| Final complete suite | 350 passed; 0 failures/errors; 0 skips |
| Complete baseline, repeated baseline and intermediate-output reproduction | PASS |
| Cross-module future-price and stale-score tests | PASS |
| All 119 turnover/cost reconstructions and daily NAV accounting | PASS |
| All 120 formation rankings and cross-sectional calculations | PASS |
| Independent Strategy/SPY metrics and all 20 annual returns | PASS |
| All six sensitivity groups / intended rows / complete runs | 6 / 21 / 21 |
| Dependency and whitespace checks | PASS |
| Protected preexisting file hashes | 1,128 unchanged; README alone intentionally updated |
| Test-local cache/output/production/specification hash set | 1,106 unchanged |
| Actual data downloads, cache writes or prior-output writes | 0 |

The fresh approved-cache run produced:

| Metric | Strategy | SPY |
| --- | ---: | ---: |
| Cumulative return | 522.5346615575% | 300.2530196823% |
| CAGR | 20.1261530065% | 14.9214886227% |
| Annualized volatility | 23.0577861766% | 18.0072742667% |
| Sharpe ratio | 0.8728571274 | 0.8286367166 |
| Maximum drawdown | -35.4525047586% | -33.7172637860% |
| Final NAV | 6.225346615575381 | 4.002530196823173 |
| Final strategy value, USD | 622,534.6615575381 | — |

The full annual-return table for 2016–2025 was reproduced from actual NAV, with
the revised-data 2025 strategy return approximately 13.2416%. No annual value is
hard-coded into calculation logic. The original-data annual/performance reports
remain historical artifacts, not the regression target for this validation.

The existing invalid-date fixture emits an expected pandas parsing warning, and
mocked data-failure tests emit expected diagnostics. These do not represent live
downloads or a failure of the approved cache. No new methodological blocker was
found. This validation is specification/accounting evidence, not proof of future
profitability or absence of all possible biases.

Work remains uncommitted for review on `phase-8-testing-validation`. No push,
pull request, Phase 9 implementation or Phase 10 work is included.

**PHASE 8 VALIDATION: PASS**
