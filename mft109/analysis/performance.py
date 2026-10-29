"""Performance analysis of existing Phase 5 outputs, without trading logic or I/O."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mft109.backtesting.execution import official_sessions
from mft109.config import BASELINE


METRICS = ["Cumulative Return", "Annualized Return", "Annualized Volatility",
           "Sharpe Ratio", "Maximum Drawdown"]


def _series(values: pd.Series, name: str, *, positive: bool = False) -> pd.Series:
    if not isinstance(values, pd.Series) or values.empty:
        raise ValueError(f"{name} must be a nonempty Series")
    dates = values.index
    if (not isinstance(dates, pd.DatetimeIndex) or dates.tz is not None
            or dates.hasnans or not dates.is_unique or not dates.equals(dates.normalize())):
        raise ValueError(f"{name} requires unique, naive daily datetime dates")
    if (not pd.api.types.is_numeric_dtype(values.dtype)
            or pd.api.types.is_bool_dtype(values.dtype)
            or pd.api.types.is_complex_dtype(values.dtype)):
        raise TypeError(f"{name} must be real numeric")
    result = values.sort_index().astype("float64").copy()
    if not np.isfinite(result.to_numpy()).all() or (positive and result.le(0).any()):
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))
    return result


def drawdown_series(nav: pd.Series) -> pd.DataFrame:
    """Return causal running peak and nonpositive drawdown for positive NAV."""
    values = _series(nav, "NAV", positive=True)
    peaks = values.cummax()
    return pd.DataFrame({"running_peak": peaks, "drawdown": values / peaks - 1})


def performance_metrics(nav: pd.Series, daily_returns: pd.Series) -> pd.Series:
    """Five metrics using n-1 genuine close-to-close returns, excluding the anchor.

    The first supplied return must be 0, marking the initial NAV anchor. CAGR
    uses 252/N; sample volatility uses those same N returns and ddof=1. Sharpe
    is CAGR/volatility at risk-free rate 0. Single-point CAGR/volatility/Sharpe
    and volatility based on fewer than two returns are undefined (NaN).
    """
    values = _series(nav, "NAV", positive=True)
    returns = _series(daily_returns, "Daily returns")
    if not values.index.equals(returns.index):
        raise ValueError("NAV and returns must have identical dates")
    if returns.iloc[0] != 0:
        raise ValueError("First return must be the zero-return initial NAV anchor")
    observed = returns.iloc[1:]
    expected = values.iloc[1:].to_numpy() / values.iloc[:-1].to_numpy() - 1
    if not np.allclose(observed, expected, rtol=1e-10, atol=1e-12):
        raise ValueError("Daily returns are inconsistent with adjacent NAV ratios")
    periods = len(observed)
    with np.errstate(over="raise", invalid="raise"):
        try:
            cumulative = float(values.iloc[-1] / values.iloc[0] - 1)
            annualized = float(np.expm1((np.log(values.iloc[-1]) - np.log(values.iloc[0]))
                                       * BASELINE.trading_days_per_year / periods)) if periods else np.nan
            volatility = np.nan
            if periods >= 2:
                volatility = (0.0 if observed.nunique() == 1 else
                              float(observed.std(ddof=1) * np.sqrt(BASELINE.trading_days_per_year)))
        except FloatingPointError as exc:
            raise ValueError("Performance arithmetic exceeded numeric range") from exc
    sharpe = annualized / volatility if np.isfinite(volatility) and volatility > 0 else np.nan
    return pd.Series([cumulative, annualized, volatility, sharpe,
                      float(drawdown_series(values).drawdown.min())], index=METRICS, dtype=float)


def annual_returns(nav: pd.Series) -> pd.DataFrame:
    """Calendar returns use the preceding year's final NAV, preserving January moves.

    The first observed year uses its initial NAV as the anchor. A year is marked
    partial when the sample does not reach within seven calendar days of both
    year boundaries, or an intervening year is absent. This flag is a boundary
    diagnostic, not proof of full session coverage; the official wrapper validates
    the complete SPY clock when sessions are supplied.
    """
    values = _series(nav, "NAV", positive=True)
    records = []
    previous_date, previous_nav = None, None
    for year, group in values.groupby(values.index.year):
        consecutive = previous_date is not None and previous_date.year == year - 1
        base_date = previous_date if consecutive else group.index[0]
        base_nav = previous_nav if consecutive else float(group.iloc[0])
        start, end = pd.Timestamp(year=year, month=1, day=1), pd.Timestamp(year=year, month=12, day=31)
        partial = ((group.index[0] - start).days > 7 or (end - group.index[-1]).days > 7
                   or (previous_date is not None and not consecutive))
        records.append({"Year": int(year), "Return": float(group.iloc[-1] / base_nav - 1),
                        "Anchor Date": base_date, "End Date": group.index[-1],
                        "Partial Year": bool(partial)})
        previous_date, previous_nav = group.index[-1], float(group.iloc[-1])
    return pd.DataFrame(records)


@dataclass(frozen=True)
class PerformanceAnalysis:
    """Reusable tables suitable for CSV export and later presentation layers."""

    performance_summary: pd.DataFrame
    annual_returns: pd.DataFrame
    daily_performance: pd.DataFrame


def analyze_performance(daily: pd.DataFrame, *, sessions: pd.DatetimeIndex | None = None) -> PerformanceAnalysis:
    """Consume Phase 5 daily output without replacing NAV, returns or capital.

    Supply the validated SPY sessions for a complete official-period analysis;
    exact official date coverage is then required. Omit sessions only for explicit
    partial-sample analysis (annual boundary flags still apply). No rows are filled.
    """
    columns = ["date", "strategy_return", "strategy_nav", "portfolio_value_usd", "spy_return", "spy_nav"]
    if not isinstance(daily, pd.DataFrame) or not set(columns).issubset(daily.columns) or daily.empty:
        raise ValueError("Nonempty Phase 5 daily output with returns, NAV and USD value is required")
    frame = daily.loc[:, columns].copy(deep=True).set_index("date").sort_index()
    strategy = performance_metrics(frame.strategy_nav, frame.strategy_return)
    benchmark = performance_metrics(frame.spy_nav, frame.spy_return)
    capital = _series(frame.portfolio_value_usd, "Portfolio value", positive=True)
    if (frame.index[0] < pd.Timestamp(BASELINE.backtest_start)
            or frame.index[-1] > pd.Timestamp(BASELINE.backtest_end)):
        raise ValueError("Performance observations must lie within official 2016–2025 bounds")
    if (frame.strategy_nav.iloc[0] != BASELINE.initial_nav
            or frame.spy_nav.iloc[0] != BASELINE.initial_nav
            or capital.iloc[0] != BASELINE.initial_capital_usd):
        raise ValueError("Phase 5 initial NAVs must be 1 and initial capital USD 100,000")
    if not np.allclose(capital, BASELINE.initial_capital_usd * frame.strategy_nav,
                       rtol=1e-12, atol=1e-8):
        raise ValueError("Portfolio value must equal 100000 times strategy NAV")
    if sessions is not None and not frame.index.equals(official_sessions(sessions)):
        raise ValueError("Daily output must cover every official SPY session exactly")
    frame["strategy_drawdown"] = drawdown_series(frame.strategy_nav).drawdown
    frame["spy_drawdown"] = drawdown_series(frame.spy_nav).drawdown
    summary = pd.DataFrame({"Metric": METRICS, "Strategy": strategy.to_numpy(), "SPY": benchmark.to_numpy()})
    years = annual_returns(frame.strategy_nav).rename(columns={"Return": "Strategy"})
    years["SPY"] = annual_returns(frame.spy_nav)["Return"].to_numpy()
    years = years[["Year", "Strategy", "SPY", "Anchor Date", "End Date", "Partial Year"]]
    return PerformanceAnalysis(summary, years, frame.reset_index())
