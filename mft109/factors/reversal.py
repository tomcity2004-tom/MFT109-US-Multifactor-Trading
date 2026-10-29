"""Raw negative 20-session adjusted-price return."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import align_values, finite_result


def calculate_reversal(
    adjusted_close: pd.Series, *, sessions: pd.DatetimeIndex, window: int | None = None
) -> pd.Series:
    """Return -(P(t)/P(t-k)-1); default k=20, approved research k=5/10/20.

    A missing endpoint yields NaN; output keeps its baseline schema name.
    """
    price = align_values(adjusted_close, sessions)
    window = BASELINE.reversal_lookback_days if window is None else window
    if type(window) is not int or window not in (5, 10, 20):
        raise ValueError("Approved reversal windows are 5, 10 and 20 sessions")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        result = -(price / price.shift(window) - 1)
    return finite_result(result, "reversal20")
