"""Raw liquidity from adjusted prices and Yahoo-reported volume."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import align_values, finite_result


def calculate_dollar_volume(
    adjusted_close: pd.Series, volume: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Return adjusted price times reported volume; do not rescale or fill volume."""
    price = align_values(adjusted_close, sessions)
    reported_volume = align_values(volume, sessions, volume=True)
    with np.errstate(over="ignore", invalid="ignore"):
        result = price * reported_volume
    return finite_result(result, "dollar_volume")


def calculate_adv20(
    adjusted_close: pd.Series, volume: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Mean of 20 consecutive valid dollar volumes including the current session."""
    dollar_volume = calculate_dollar_volume(adjusted_close, volume, sessions=sessions)
    window = BASELINE.liquidity_lookback_days
    result = dollar_volume.rolling(window, min_periods=window).mean()
    return finite_result(result, "adv20")


def calculate_liquidity(
    adjusted_close: pd.Series, volume: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Return ln(ADV20) only for strictly positive, complete-window ADV20."""
    adv20 = calculate_adv20(adjusted_close, volume, sessions=sessions)
    result = np.log(adv20.where(adv20.gt(0)))
    return finite_result(result, "liquidity_raw")
