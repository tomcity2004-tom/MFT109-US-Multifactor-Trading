"""Official daily session grid and strictly later adjusted-close execution dates."""

import pandas as pd

from mft109.config import BASELINE, DATA_SETTINGS, BaselineSettings
from mft109.factors._inputs import session_index


def official_sessions(
    sessions: pd.DatetimeIndex, baseline: BaselineSettings = BASELINE
) -> pd.DatetimeIndex:
    """Filter a validated SPY clock to inclusive evaluation bounds, never shift start."""
    calendar = session_index(sessions)
    if (calendar.day_of_week >= 5).any():
        raise ValueError("SPY session calendar cannot include weekends")
    start, end = pd.Timestamp(baseline.backtest_start), pd.Timestamp(baseline.backtest_end)
    if start > end:
        raise ValueError("Backtest start must not follow its end")
    official = calendar[(calendar >= start) & (calendar <= end)]
    if official.empty:
        raise ValueError("No official SPY sessions are available")
    tolerance = DATA_SETTINGS.coverage_tolerance_days
    if (official[0] - start).days > tolerance or (end - official[-1]).days > tolerance:
        raise ValueError("SPY clock does not cover the requested evaluation boundaries")
    expected = pd.period_range(start, end, freq="M")
    if not expected.difference(official.to_period("M")).empty:
        raise ValueError("SPY clock is missing evaluation months")
    return official.rename("date")


def execution_schedule(
    formation_dates: pd.DatetimeIndex,
    *,
    sessions: pd.DatetimeIndex,
    baseline: BaselineSettings = BASELINE,
) -> pd.DataFrame:
    """Map each formation to the strictly next SPY session within official bounds.

    A final signal with no later official session is retained with execution_date
    NaT. No 2026 trade or invented execution date is created for a 2025 final signal.
    """
    calendar = session_index(sessions)
    official = official_sessions(calendar, baseline)
    if not isinstance(formation_dates, pd.DatetimeIndex):
        raise TypeError("formation_dates must be a DatetimeIndex")
    if formation_dates.empty:
        return pd.DataFrame({"formation_date": pd.DatetimeIndex([]),
                             "execution_date": pd.DatetimeIndex([])})
    formations = session_index(formation_dates)
    if not formations.isin(official).all():
        raise ValueError("Formation dates must be official SPY sessions")
    records = []
    for formation in formations:
        position = calendar.searchsorted(formation, side="right")
        execution = calendar[position] if position < len(calendar) else pd.NaT
        if pd.notna(execution) and execution > pd.Timestamp(baseline.backtest_end):
            execution = pd.NaT
        records.append({"formation_date": formation, "execution_date": execution})
    return pd.DataFrame(records)
