# Engine-derived trade history

The trade log observes the existing backtest's pre/post-rebalance **units** at
execution. It never infers trades from Top 20 membership alone. Retained stocks
can have INCREASE / DECREASE transactions, including fee-financing reductions.
The strategy, execution timing, cash-inclusive turnover, 10 bps fee and all
validated Phase 10 financial results are unchanged.

## Generation

From the repository root, using the pinned base requirements and the approved
local market cache:

```bash
python -B -m mft109.backtesting.export
```

This explicit offline command reads/checks the fixed-universe cache metadata and
hashes (including the approved revised FISV vintage), calls the existing factor,
scoring, ranking, backtest and performance APIs, and verifies every daily
financial observation, summary metric and selected stock against the validated
tracked deployment bundle. It then reconciles stock units, cash and allocated
fees at all executions. It fails on missing/invalid caches or changed results;
there is no Yahoo download fallback, forward fill, fabricated trade or strategy
parameter override. No baseline result table or figure is overwritten.

Outputs:

- `dashboard/data/trade_log.csv`: small, tracked deployment artifact.
- `dashboard/data/trade_log_manifest.json`: checksums, price-cache provenance,
  engine/observer identity, baseline binding and reconciliation convention.
- `outputs/final_report/v1/trade_log.csv`: byte-identical report-ready copy.
- The final-report manifest gains the CSV checksum and trade provenance. The
  package now contains **27 files**, including **11 CSVs**; the original Phase
  10B 26-file financial/diagnostic package contents are otherwise preserved.

Once the official trade export exists, the normal report-packaging command
`python -B -m mft109.analysis.final_exports` also includes and validates it.
That packaging command only copies saved trades; it does not rerun the strategy.
The first trade export requires the existing validated final-report package.

Without approved price caches, restore their archived original versions before
running the command. A fresh vendor download is not guaranteed to reproduce the
approved data vintage. The app can still display tracked exports without any
price caches, local environment paths, credentials, SciPy or Matplotlib.

## Field definitions and accounting

| Field | Meaning |
| --- | --- |
| execution_date | Actual next-session adjusted-close rebalance date |
| formation_date | Prior month-end signal/ranking date |
| ticker | Fixed-universe Yahoo-compatible identifier |
| side | BUY for positive unit change; SELL for negative change |
| trade_type | NEW_ENTRY / FULL_EXIT / INCREASE / DECREASE |
| adjusted_execution_price | Adjusted close used by the engine, USD |
| quantity | Absolute change in fractional adjusted-price units |
| gross_trade_value_usd | Quantity × adjusted execution price, unsigned USD |
| pre_trade_units / post_trade_units | Actual units immediately before/after rebalance |
| transaction_cost_usd | Attribution of the **already deducted** rebalance fee |
| portfolio_value_usd | Whole portfolio closing value **after** the existing fee |

Prices/units are the academic adjusted-price accounting convention, **not actual
broker fills or necessarily contemporaneous unadjusted share counts**. No
integer-share rounding occurs. Rows are ordered by execution date and ticker.
Units differing by at most `32 * machine epsilon * max(1, abs(pre), abs(post))`
are treated as numerical noise **in the log only**; holdings are not rounded,
modified or suppressed. No transaction is recorded for unchanged holdings,
unexecutable selections or a signal outside the official execution window.
A run with no trades returns a header-only CSV.

The original portfolio cost is computed exactly once by the existing engine.
For reporting, this actual total is allocated pro rata to gross stock trade
notional, with the floating residual assigned to the largest trade. It is an
explicit accounting attribution, not a broker fee and **not** another 10 bps
charge on each row. Allocations sum to the rebalance audit fee, including initial
entry and liquidation to cash. Costs must never be subtracted again when using
this CSV. Buy/sell notional and the already charged fee reconcile to cash changes.

## Dashboard

```bash
python -m streamlit run dashboard/Home.py
```

Choose **Trade History** in the native sidebar (page file
`dashboard/pages/3_Trade_History.py`). English / 繁體中文 labels follow the existing
language selector. The page offers inclusive execution-date range, exact ticker
and BUY/SELL filters; empty ticker/side selections mean all. Counts and total
gross notional reflect the filtered observations. CSV downloads preserve the
original field names, enum identifiers and numeric precision. Display rounding
never changes stored data. Missing/corrupt artifacts show a clear warning;
empty data or no matches show an informational message and zero counts.

The independent trade manifest keeps the existing eleven dashboard artifacts
unchanged. Both new trade files must be committed for Community Cloud deployment.
The application reads them using repository-relative paths and never launches an
export, backtest or market-data request.

## Validation

```bash
python -B -m unittest discover -s tests -p test_trade_history.py -v
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -m pip check
git diff --check
```

Checks cover entry/exit, retained-name unit changes, floating noise, cash-only
periods, missing execution/holding prices, causal timing, cost attribution,
pre/post holdings, no duplicate cost charge, exact original accounting-table
identity, official baseline reproduction, checksum/corruption handling, filters,
repository-only loading, and both UI languages. No methodology change is made.
