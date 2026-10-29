"""Daily adjusted returns and raw 60-return sample historical volatility."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import align_values, finite_result


def calculate_daily_returns(
    adjusted_close: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Return P(t)/P(t-1)-1 without implicit pct_change filling or gap skipping."""
    price = align_values(adjusted_close, sessions)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        result = price / price.shift(1) - 1
    return finite_result(result, "daily_return")


def calculate_volatility(
    adjusted_close: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Sample std (ddof=1) of 60 consecutive valid returns, times sqrt(252).

    A full window needs 61 consecutive valid prices. Output is raw nonnegative
    volatility, without the later low-volatility direction transform or Z-score.
    """
    returns = calculate_daily_returns(adjusted_close, sessions=sessions)
    window = BASELINE.volatility_lookback_days
    result = returns.rolling(window, min_periods=window).std(ddof=1)
    result = result * np.sqrt(BASELINE.trading_days_per_year)
    return finite_result(result, "volatility60")
