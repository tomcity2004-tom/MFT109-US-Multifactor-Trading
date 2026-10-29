"""End-of-day adjusted-price accounting for validated monthly Phase 4 selections."""

from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd

from mft109.backtesting._inputs import adjusted_price_grid, selection_inputs
from mft109.backtesting.execution import execution_schedule, official_sessions
from mft109.backtesting.transaction_costs import portfolio_turnover, transaction_cost_fraction
from mft109.benchmark import build_spy_benchmark
from mft109.config import BASELINE, BaselineSettings
from mft109.optimization.scenarios import Scenario, check_scenario
from mft109.portfolio import CASH_ASSET, equal_weight_target
from mft109.ranking import MonthlySelection


LOGGER = logging.getLogger(__name__)
DAILY_COLUMNS = ["date", "gross_strategy_return", "strategy_return", "strategy_nav",
                 "portfolio_value_usd", "cash_weight", "transaction_cost_fraction",
                 "transaction_cost_usd", "spy_return", "spy_nav"]
HOLDING_COLUMNS = ["date", "ticker", "units", "adjusted_close", "market_value_usd", "weight"]
AUDIT_COLUMNS = ["formation_date", "execution_date", "status", "eligible_count",
                 "selected_count", "executable_count", "turnover", "transaction_cost_fraction",
                 "transaction_cost_usd", "pre_value_usd", "post_value_usd",
                 "target_cash_weight", "flags"]
WEIGHT_COLUMNS = ["formation_date", "execution_date", "ticker", "selected", "executable",
                  "pre_rebalance_weight", "target_weight"]
EVENT_COLUMNS = ["date", "formation_date", "ticker", "event", "action"]


@dataclass(frozen=True)
class BacktestResult:
    """Daily accounting, end-of-day holdings, rebalance audit and missing-price flags."""

    daily: pd.DataFrame
    holdings: pd.DataFrame
    rebalance_audit: pd.DataFrame
    rebalance_weights: pd.DataFrame
    missing_price_events: pd.DataFrame


class MissingHoldingPriceError(ValueError):
    """A held stock cannot be valued: stop with validated prefix and dated audit."""

    def __init__(self, date: pd.Timestamp, tickers: tuple[str, ...], partial_result: BacktestResult):
        self.date, self.tickers, self.partial_result = date, tickers, partial_result
        super().__init__(f"Missing/invalid held adjusted price on {date.date()}: {', '.join(tickers)}; "
                         "backtest stopped without fabricating valuation or returns")


def run_backtest(
    selection: MonthlySelection,
    market_data: pd.DataFrame,
    spy_adjusted_close: pd.Series,
    *,
    sessions: pd.DatetimeIndex,
    baseline: BaselineSettings = BASELINE,
    scenario: Scenario | None = None,
) -> BacktestResult:
    """Value old units, calculate drift/turnover, charge cost, then allocate new units.

    Trades execute at the next session's adjusted close. New holdings earn returns
    only after that close. Missing held prices stop the run; no fill or assumed
    liquidation is allowed. Inputs are not mutated and this function performs no I/O.
    The optional date bounds support deterministic small fixtures; economic baseline
    constants remain locked at $100,000, NAV 1 and 10 bps.
    Explicit approved Phase 7 scenarios vary N, schedule or cost via the shared
    accounting functions; default calls retain every Phase 5 convention.
    """
    if (baseline.initial_capital_usd != 100000 or baseline.initial_nav != 1
            or baseline.transaction_cost_rate != 0.001 or baseline.top_n != 20
            or baseline.benchmark != "SPY"):
        raise ValueError("Phase 5 economic baseline settings must remain unchanged")
    check_scenario(scenario)
    official = official_sessions(sessions, baseline)
    ranked, summary = selection_inputs(selection, official, scenario=scenario)
    selected = ranked.loc[ranked.selected]
    grid = adjusted_price_grid(market_data, official, sorted(selected.ticker.unique()))
    benchmark = build_spy_benchmark(spy_adjusted_close, sessions=sessions,
                                    baseline=baseline).set_index("date")
    schedule = execution_schedule(pd.DatetimeIndex(summary.formation_date), sessions=sessions,
                                  baseline=baseline).merge(summary, on="formation_date", validate="1:1")
    executable_schedule = schedule.loc[schedule.execution_date.notna()]
    if executable_schedule.execution_date.duplicated().any():
        raise ValueError("Multiple formations map to the same execution session")
    events_by_date = {row.execution_date: row for row in executable_schedule.itertuples(index=False)}
    names_by_date = {date: group.ticker.tolist() for date, group in selected.groupby("formation_date")}
    daily, holdings, audits, weights, events = [], [], [], [], []

    def result() -> BacktestResult:
        return BacktestResult(pd.DataFrame(daily, columns=DAILY_COLUMNS),
                              pd.DataFrame(holdings, columns=HOLDING_COLUMNS),
                              pd.DataFrame(audits, columns=AUDIT_COLUMNS),
                              pd.DataFrame(weights, columns=WEIGHT_COLUMNS),
                              pd.DataFrame(events, columns=EVENT_COLUMNS))

    cash = previous_value = float(baseline.initial_capital_usd)
    units: dict[str, float] = {}
    for date in official:
        prices = grid.loc[date]
        rebalance = events_by_date.get(date)
        formation = rebalance.formation_date if rebalance is not None else pd.NaT
        invalid = tuple(ticker for ticker in sorted(units)
                        if not np.isfinite(prices[ticker]) or prices[ticker] <= 0)
        if invalid:
            for ticker in invalid:
                events.append(dict(date=date, formation_date=formation, ticker=ticker,
                                   event="missing_holding_price", action="stop_without_valuation"))
            LOGGER.error("Cannot value held stocks on %s: %s", date.date(), invalid)
            raise MissingHoldingPriceError(date, invalid, result())
        market_values = {ticker: units[ticker] * float(prices[ticker]) for ticker in sorted(units)}
        pre_value = cash + sum(market_values.values())
        if not np.isfinite(pre_value) or pre_value <= 0:
            raise ValueError(f"Nonfinite/nonpositive portfolio valuation on {date.date()}")
        pre_weights = pd.Series({**{t: v / pre_value for t, v in market_values.items()},
                                 CASH_ASSET: cash / pre_value}, dtype="float64")
        cost_fraction = cost_usd = 0.0
        post_value = pre_value
        if rebalance is not None:
            names = names_by_date.get(formation, [])
            target = equal_weight_target(names, prices, scenario=scenario)
            executable = [t for t in target.weights.index if t != CASH_ASSET]
            flags = []
            for ticker in target.excluded_tickers:
                events.append(dict(date=date, formation_date=formation, ticker=ticker,
                                   event="missing_execution_price", action="exclude_without_replacement"))
            if target.excluded_tickers:
                flags.append("missing_execution_price:" + ",".join(target.excluded_tickers))
            if not executable:
                flags.append("zero_executable_stocks")
            if flags:
                LOGGER.warning("Rebalance %s: %s", date.date(), ";".join(flags))
            turnover = portfolio_turnover(pre_weights, target.weights)
            cost_fraction = transaction_cost_fraction(turnover, scenario=scenario)
            cost_usd = pre_value * cost_fraction
            post_value = pre_value - cost_usd
            units = {ticker: post_value * float(target.weights[ticker]) / float(prices[ticker])
                     for ticker in executable}
            cash = post_value * float(target.weights[CASH_ASSET])
            for ticker in sorted(set(pre_weights.index) | set(target.weights.index) | set(names)):
                weights.append(dict(formation_date=formation, execution_date=date, ticker=ticker,
                                    selected=ticker in names, executable=ticker in executable,
                                    pre_rebalance_weight=float(pre_weights.get(ticker, 0)),
                                    target_weight=float(target.weights.get(ticker, 0))))
            audits.append(dict(formation_date=formation, execution_date=date, status="executed",
                               eligible_count=rebalance.eligible_count, selected_count=rebalance.selected_count,
                               executable_count=len(executable), turnover=turnover,
                               transaction_cost_fraction=cost_fraction, transaction_cost_usd=cost_usd,
                               pre_value_usd=pre_value, post_value_usd=post_value,
                               target_cash_weight=float(target.weights[CASH_ASSET]), flags=";".join(flags)))
        daily.append(dict(date=date, gross_strategy_return=pre_value / previous_value - 1,
                          strategy_return=post_value / previous_value - 1,
                          strategy_nav=post_value / baseline.initial_capital_usd,
                          portfolio_value_usd=post_value, cash_weight=cash / post_value,
                          transaction_cost_fraction=cost_fraction, transaction_cost_usd=cost_usd,
                          spy_return=benchmark.at[date, "spy_return"], spy_nav=benchmark.at[date, "spy_nav"]))
        for ticker in sorted(units):
            value = units[ticker] * float(prices[ticker])
            holdings.append(dict(date=date, ticker=ticker, units=units[ticker],
                                 adjusted_close=float(prices[ticker]), market_value_usd=value,
                                 weight=value / post_value))
        holdings.append(dict(date=date, ticker=CASH_ASSET, units=cash, adjusted_close=np.nan,
                             market_value_usd=cash, weight=cash / post_value))
        previous_value = post_value
    for row in schedule.loc[schedule.execution_date.isna()].itertuples(index=False):
        audits.append(dict(formation_date=row.formation_date, execution_date=pd.NaT,
                           status="not_executed_within_backtest", eligible_count=row.eligible_count,
                           selected_count=row.selected_count, executable_count=pd.NA, turnover=0.0,
                           transaction_cost_fraction=0.0, transaction_cost_usd=0.0,
                           pre_value_usd=np.nan, post_value_usd=np.nan, target_cash_weight=np.nan,
                           flags="no_official_execution_session"))
    return result()
