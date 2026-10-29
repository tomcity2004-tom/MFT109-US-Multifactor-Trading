"""Raw negative 20-session adjusted-price return."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import align_values, finite_result


def calculate_reversal(
    adjusted_close: pd.Series, *, sessions: pd.DatetimeIndex
) -> pd.Series:
    """Return -(P(t)/P(t-20)-1); a missing endpoint yields NaN."""
    price = align_values(adjusted_close, sessions)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        result = -(price / price.shift(BASELINE.reversal_lookback_days) - 1)
    return finite_result(result, "reversal20")
