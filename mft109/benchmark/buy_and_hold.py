"""Adjusted-price SPY buy-and-hold returns/NAV, without strategy costs or metrics."""

import numpy as np
import pandas as pd

from mft109.backtesting.execution import official_sessions
from mft109.config import BASELINE, BaselineSettings
from mft109.factors._inputs import align_values


def build_spy_benchmark(
    adjusted_close: pd.Series,
    *,
    sessions: pd.DatetimeIndex,
    baseline: BaselineSettings = BASELINE,
) -> pd.DataFrame:
    """Buy at the first official adjusted close: first return 0, NAV starts at 1.

    Warm-up and future returns are excluded. Subsequent returns are adjacent
    official-session adjusted-close ratios. Missing official prices are an error.
    """
    official = official_sessions(sessions, baseline)
    price = align_values(adjusted_close, sessions).reindex(official)
    if price.isna().any():
        raise ValueError("SPY benchmark requires a valid positive adjusted price on every official session")
    returns = price / price.shift(1) - 1
    returns.iloc[0] = 0.0
    nav = price / price.iloc[0]
    if not np.isfinite(returns).all() or not np.isfinite(nav).all():
        raise ValueError("SPY arithmetic produced nonfinite returns or NAV")
    return pd.DataFrame({"date": official, "spy_return": returns.to_numpy(),
                         "spy_nav": nav.to_numpy()})
