"""Raw 12-1 month momentum using adjusted prices and session lags."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import align_values, finite_result


def calculate_momentum(
    adjusted_close: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Return P(t-21) / P(t-252) - 1; either missing endpoint yields NaN.

    The most recent 21 sessions are skipped. Missing prices between the two
    endpoints do not invalidate this endpoint-only formula.
    """
    price = align_values(adjusted_close, sessions)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        result = (price.shift(BASELINE.momentum_skip_days)
                  / price.shift(BASELINE.momentum_lookback_days) - 1)
    return finite_result(result, "momentum")
