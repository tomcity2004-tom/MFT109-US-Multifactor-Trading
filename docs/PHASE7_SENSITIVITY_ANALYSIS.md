# Phase 7 — Controlled Sensitivity Analysis

## Objective and boundaries

Test historical robustness using six predefined **one-at-a-time** experiments.
The original Phase 0–6 baseline remains the primary strategy regardless of any
scenario's historical return or Sharpe. There is no Cartesian product, arbitrary
parameter entry, optimizer, best-scenario selection, parameter mining, machine
learning, walk-forward optimization or Streamlit code. Phase 8 has not started.

The fixed current S&P 500 snapshot, adjusted prices and reported Volume, 2015
warm-up, 2016–2025 official period, SPY benchmark, USD 100,000 initial capital and
NAV 1 remain unchanged. Momentum, liquidity, eligibility, cross-sectional Z-score
conventions, deterministic ranking and execution/valuation accounting are shared
with the validated baseline.

## Predeclared experiments

| Dimension | Values | Baseline |
| --- | --- | --- |
| Top N | 10, 20, 30, 50 | 20 |
| Transaction cost (bps) | 0, 5, 10, 20 | 10 |
| Rebalance frequency | Monthly, Quarterly | Monthly |
| Volatility window (sessions) | 20, 60, 120 | 60 |
| Reversal window (sessions) | 5, 10, 20 | 20 |
| Factor weights | Five scenarios below | Equal |

| Weight scenario | Momentum | Low volatility | Liquidity | Reversal |
| --- | ---: | ---: | ---: | ---: |
| Equal | .25 | .25 | .25 | .25 |
| Momentum tilt | .40 | .20 | .20 | .20 |
| Low volatility tilt | .20 | .40 | .20 | .20 |
| Liquidity tilt | .20 | .20 | .40 | .20 |
| Reversal tilt | .20 | .20 | .20 | .40 |

Each weight tuple sums to 1. No arbitrary weights are normalized. The immutable
`Scenario` contains one dimension/value pair only; every other parameter comes
from its baseline. Catalogs are read-only and `BASELINE` is never patched or
mutated. There are **21 reported rows**: 4 + 4 + 2 + 3 + 3 + 5. Each table retains
its own baseline. The single unchanged baseline calculation is reused for those
six baseline rows, not redefined in each experiment.

## Shared calculation and accounting

- Top N uses the unchanged composite-descending/ticker-ascending ranking, unique
  sequential ranks and shortage behavior. Only selected executable stocks receive
  equal `1/N_executable` portfolio weights; no unselected replacement is added.
- Cost is the approved basis-point rate divided by 10,000, multiplied by actual
  cash-inclusive drifted turnover. Charge it once against pre-cost wealth.
- Monthly formations remain the last SPY session of every month. Quarterly
  formations are the last SPY sessions of March, June, September and December.
  Execution is strictly the next official SPY session at adjusted close. The
  quarterly first formation/execution is 2016-03-31 / 2016-04-01; the strategy is
  cash before then. There are 40 quarterly formations and 39 executable events.
  The final 2025-12-31 signal cannot execute in 2026.
- Volatility uses `k` consecutive daily adjusted-price returns, sample standard
  deviation (`ddof=1`) and `sqrt(252)`. A complete window requires `k+1` consecutive
  prices. Its score remains **negative** cross-sectional Z-score.
- Reversal is `-(P(t)/P(t-k)-1)` and receives a positive Z-score direction; its
  sign is not reversed twice.
- All four raw factors must be finite on the same formation date. Longer windows
  do not receive fabricated history or stale signals.

To preserve the established scoring schema, raw columns retain the names
`volatility60` and `reversal20` even for explicit research windows. The scenario
metadata identifies the actual window; those column names describe the baseline
schema, not an alternative window's formula.

The original backtest engine continues to handle fixed units, drifting weights,
cash, missing entries and missing holdings. It is not copied. Phase 6 formulas
are called unchanged: cumulative return, CAGR using 252/(observations−1), sample
annualized volatility, CAGR/volatility Sharpe at risk-free rate 0%, and maximum
drawdown. Final NAV and USD value are retained. SPY is identical across scenarios.

## Architecture and compatibility changes

`mft109/optimization/scenarios.py` defines the immutable fixed catalog.
`mft109/optimization/sensitivity.py` orchestrates the existing factor, scoring,
ranking, portfolio, backtest and performance functions.

Previous APIs locked N=20, monthly formations, 10 bps and equal factor weights.
Narrow optional `scenario` arguments now let those same algorithms consume the
approved research settings. Raw volatility/reversal accept only their approved
window values. The necessary compatibility changes are confined to:

- factor aggregation and volatility/reversal window arguments;
- scoring's predefined weight tuple;
- ranking's selection cutoff and quarter-end formation subset;
- portfolio construction's selected-name limit;
- backtest selection validation's matching cutoff/schedule;
- transaction cost's explicit rate and engine argument forwarding.

Default calls retain their validated baseline behavior. No configuration,
methodology specification, existing tests, benchmark or Phase 6 calculation file
is changed. Scenario arguments are explicit: no global monkeypatching or temporary
replacement of configuration values is used.

Only month-end raw/score frames are cached inside the orchestrator after full
history factor calculation. Same-date cross-sectional processing makes this
equivalent to retaining the complete daily scoring table; no future date is
included in an earlier score. Input order does not determine ranking results.

## Missing data and blocked scenarios

Missing inputs are never forward/backward filled, mean-filled, zero-filled,
interpolated, replaced with stale factors or substituted tickers. Invalid new
execution prices are excluded using the unchanged Phase 5 rule.

A missing **held** price still raises `MissingHoldingPriceError` in the engine.
The orchestrator catches only this explicit accounting stop to preserve its
validated prefix and audit, report the scenario as blocked, and continue the
other scenarios. A blocked prefix is **not** presented as official performance:
all full-period metrics, final NAV/value and baseline differences are NaN, and
`performance` is None. Other unexpected errors are not swallowed. A failure of
the baseline itself propagates because no valid baseline comparison is possible.

The original cached-data version revealed two blocked scenarios:

- `reversal_window:5`
- `factor_weights:reversal_tilt`

Both hold FISV on its missing adjusted-price date, **2025-11-12**, and stop with
valid daily accounting through **2025-11-11**. The original-data baseline completes.
Those original runs remain preserved as incomplete historical results.

A subsequent explicitly approved Yahoo source-data revision restores the vendor's
reported observation and three Volume revisions; see
[FISV_DATA_REVISION.md](FISV_DATA_REVISION.md). All 21 revised-data runs now complete.
The engine's missing-held-price policy remains unchanged. The revised baseline
results differ from the original-data baseline, and both versions are retained
for review rather than presented as an exact reproduction of one another.

## API, output and reproduction

```python
from mft109.optimization.sensitivity import run_sensitivity

# Phase 1 cache frames must already be validated; never use download fallbacks.
results = run_sensitivity(
    market_data, spy_adjusted_close,
    sessions=validated_spy_sessions, tickers=fixed_universe_yahoo_tickers,
)
top_n = results.tables["top_n"]
cost = results.tables["transaction_cost_bps"]
frequency = results.tables["rebalance_frequency"]
volatility = results.tables["volatility_window"]
reversal = results.tables["reversal_window"]
weights = results.tables["factor_weights"]
```

Every table includes experiment, scenario, parameter value, baseline flag, all
five metrics, final NAV/value and differences from baseline. Status, completion
flag, blocking date/tickers and last valid date distinguish complete and blocked
runs. `results.runs` retains selections, accounting/audits, performance and any
held-price error. `results.spy_performance` retains common benchmark metrics.
There is no sorting by highest performance or automatic winner.

The calculation layer performs no downloads or file writes. To export research
tables, use `table.to_csv(..., index=False)` only under ignored
`outputs/optimization/`, separately from baseline artifacts. Generated CSV/JSON
files are not committed.

```bash
.venv/bin/python -B -m unittest discover -s tests -p test_sensitivity_analysis.py
.venv/bin/python -B -m unittest discover -s tests
.venv/bin/python -B -m pip --no-cache-dir check
git diff --check
```

Tests independently verify all approved windows and weights, N cutoffs, costs,
quarterly timing, baseline reproduction, OAT isolation, missing history,
held-price stopping, failure reporting, input immutability, row-order determinism
and future-data invariance. Cached validation verifies manifest hashes and fixed
universe provenance, exactly 21 rows, six equal baseline rows, common SPY, complete
scenario fields, quarterly dates and protected data hashes. It must report
incomplete scenarios rather than label all 21 runs successful.

## Interpretation limitations

The current fixed S&P 500 universe retains survivorship bias. Historical
sensitivity evidence is not proof of future performance. Multiple scenarios
increase data-mining risk, so the experiment set was fixed in advance and varied
one dimension at a time. No scenario replaces the baseline merely because its
historical return or Sharpe is higher. Core modules return objective evidence;
they do not make investment recommendations or statistical-superiority claims.
