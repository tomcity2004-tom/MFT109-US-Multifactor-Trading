"""Fixed one-at-a-time robustness tables using the existing Phase 2–6 pipeline."""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd
import numpy as np

from mft109.analysis.performance import PerformanceAnalysis, analyze_performance
from mft109.backtesting.engine import BacktestResult, MissingHoldingPriceError, run_backtest
from mft109.factors import calculate_raw_factors
from mft109.optimization.scenarios import Scenario, approved_scenarios
from mft109.processing import score_factors
from mft109.ranking import MonthlySelection, monthly_formation_dates, rank_and_select


@dataclass(frozen=True)
class ScenarioRun:
    """Auditable selections, daily accounting and unchanged Phase 6 analysis."""

    selection: MonthlySelection
    backtest: BacktestResult
    performance: PerformanceAnalysis | None
    error: MissingHoldingPriceError | None = None


@dataclass(frozen=True)
class SensitivityResults:
    """Six CSV-compatible tables, individual runs and a common SPY metric table."""

    tables: dict[str, pd.DataFrame]
    runs: dict[str, ScenarioRun]
    spy_performance: pd.DataFrame


def run_sensitivity(
    market_data: pd.DataFrame, spy_adjusted_close: pd.Series, *,
    sessions: pd.DatetimeIndex, tickers: Sequence[str],
) -> SensitivityResults:
    """Run only the 21 approved rows; no downloads, file writes or best selection.

    Caller supplies the existing validated Phase 1 cache and fixed universe. The
    unchanged baseline is computed once and reused for each group's baseline row.
    Independent-date scoring permits caching month-end factor/score frames; full
    history is always supplied to raw-factor calculation. No financial observations
    are filled or removed from the fixed universe.
    """
    formations = monthly_formation_dates(sessions)
    raw = calculate_raw_factors(market_data, sessions=sessions, tickers=tickers)
    scored = score_factors(raw)
    selection = rank_and_select(scored, sessions=sessions)
    baseline_bt = run_backtest(selection, market_data, spy_adjusted_close, sessions=sessions)
    baseline = ScenarioRun(selection, baseline_bt, analyze_performance(baseline_bt.daily, sessions=sessions))
    base_metrics = baseline.performance.performance_summary.set_index("Metric").Strategy
    raw_cache = {(60, 20): raw.loc[raw.date.isin(formations)].copy()}
    score_cache = {(60, 20, "equal"): scored.loc[scored.date.isin(formations)].copy()}
    del raw, scored
    runs, records = {}, {}
    for scenario in approved_scenarios():
        if scenario.is_baseline:
            run = baseline
        else:
            window_key = (int(scenario.parameter("volatility_window")),
                          int(scenario.parameter("reversal_window")))
            score_key = (*window_key, str(scenario.parameter("factor_weights")))
            if window_key not in raw_cache:
                raw = calculate_raw_factors(market_data, sessions=sessions, tickers=tickers, scenario=scenario)
                raw_cache[window_key] = raw.loc[raw.date.isin(formations)].copy()
                del raw
            if score_key not in score_cache:
                score_cache[score_key] = score_factors(raw_cache[window_key], scenario=scenario)
            selection = rank_and_select(score_cache[score_key], sessions=sessions, scenario=scenario)
            try:
                bt = run_backtest(selection, market_data, spy_adjusted_close, sessions=sessions, scenario=scenario)
                run = ScenarioRun(selection, bt, analyze_performance(bt.daily, sessions=sessions))
            except MissingHoldingPriceError as error:
                # Preserve the engine's stop policy; a prefix is not official performance.
                run = ScenarioRun(selection, error.partial_result, None, error)
        runs[scenario.name] = run
        metrics = (run.performance.performance_summary.set_index("Metric").Strategy
                   if run.performance is not None else pd.Series(np.nan, index=base_metrics.index))
        final_nav = float(run.backtest.daily.strategy_nav.iloc[-1]) if run.error is None else np.nan
        final_value = float(run.backtest.daily.portfolio_value_usd.iloc[-1]) if run.error is None else np.nan
        record = {"experiment": scenario.experiment, "scenario": scenario.name,
                  "parameter_value": str(scenario.value), "is_baseline": scenario.is_baseline,
                  "status": "complete" if run.error is None else "blocked_missing_holding_price",
                  "official_period_complete": run.error is None,
                  "blocking_date": run.error.date if run.error else pd.NaT,
                  "blocking_tickers": ",".join(run.error.tickers) if run.error else "",
                  "last_valid_date": run.backtest.daily.date.iloc[-1],
                  **metrics.to_dict(), "Final NAV": final_nav,
                  "Final Portfolio Value": final_value,
                  "CAGR Difference": float(metrics["Annualized Return"] - base_metrics["Annualized Return"]),
                  "Sharpe Difference": float(metrics["Sharpe Ratio"] - base_metrics["Sharpe Ratio"]),
                  "Maximum Drawdown Difference": float(metrics["Maximum Drawdown"] - base_metrics["Maximum Drawdown"]),
                  "Final NAV Difference": float(final_nav - baseline_bt.daily.strategy_nav.iloc[-1])}
        records.setdefault(scenario.experiment, []).append(record)
    return SensitivityResults({group: pd.DataFrame(rows) for group, rows in records.items()}, runs,
                              baseline.performance.performance_summary[["Metric", "SPY"]].copy())
