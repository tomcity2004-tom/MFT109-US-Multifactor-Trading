"""Official monthly formation dates from the validated SPY session calendar."""

import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import session_index


def monthly_formation_dates(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last supplied SPY session of each official month, January 2016–December 2025.

    Pass the complete validated Phase 1 SPY calendar, not stock-specific dates or
    an unfinished calendar slice. Every official baseline month must be present.
    Existing session validation sorts input and rejects duplicates/invalid dates.
    No holiday calendar, execution dates, or prices are synthesized here.
    """
    calendar = session_index(sessions)
    if (calendar.day_of_week >= 5).any():
        raise ValueError("SPY session calendar cannot include weekends")
    start, end = pd.Timestamp(BASELINE.backtest_start), pd.Timestamp(BASELINE.backtest_end)
    official = calendar[(calendar >= start) & (calendar <= end)]
    expected_months = pd.period_range(start, end, freq="M")
    missing = expected_months.difference(official.to_period("M"))
    if not missing.empty:
        raise ValueError("SPY calendar must include every official baseline month; "
                         f"missing: {', '.join(map(str, missing))}")
    last_sessions = pd.Series(official, index=official.to_period("M")).groupby(level=0).max()
    return pd.DatetimeIndex(last_sessions.to_numpy(), name="formation_date")
