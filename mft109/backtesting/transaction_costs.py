"""Weight turnover including cash and the locked 10 bps cost convention."""

import math

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.optimization.scenarios import Scenario, check_scenario
from mft109.portfolio import CASH_ASSET


def portfolio_turnover(pre_weights: pd.Series, target_weights: pd.Series) -> float:
    """Half the L1 weight change over the union of assets, with cash included.

    Weights on each side must form a complete long-only portfolio summing to 1.
    Absent assets have zero weight. Cash-to-fully-invested turnover is 1.0,
    including the cash leg once; a complete stock replacement is also 1.0.
    """
    for weights in (pre_weights, target_weights):
        if not isinstance(weights, pd.Series) or not weights.index.is_unique or weights.empty:
            raise ValueError("Portfolio weights require a nonempty unique-index Series")
        if (not pd.api.types.is_numeric_dtype(weights.dtype)
                or pd.api.types.is_bool_dtype(weights.dtype)
                or pd.api.types.is_complex_dtype(weights.dtype)):
            raise TypeError("Portfolio weights must be real numeric values")
        values = weights.to_numpy(dtype="float64", na_value=np.nan)
        if (not np.isfinite(values).all() or (values < 0).any()
                or not math.isclose(float(values.sum()), 1.0, rel_tol=0, abs_tol=1e-12)):
            raise ValueError("Finite nonnegative complete portfolio weights must sum to 1")
    assets = pre_weights.index.union(target_weights.index).union(pd.Index([CASH_ASSET]))
    difference = target_weights.reindex(assets, fill_value=0) - pre_weights.reindex(assets, fill_value=0)
    return 0.5 * float(difference.abs().sum())


def transaction_cost_fraction(turnover: float, *, scenario: Scenario | None = None) -> float:
    """Return turnover * 0.001; the engine charges this once on pre-cost wealth."""
    if not math.isfinite(turnover) or not 0 <= turnover <= 1 + 1e-12:
        raise ValueError("Long-only portfolio turnover must be finite and between 0 and 1")
    if BASELINE.transaction_cost_rate != 0.001:
        raise ValueError("Locked baseline transaction-cost rate must remain 0.001")
    check_scenario(scenario)
    return turnover * (scenario.cost_rate if scenario else BASELINE.transaction_cost_rate)
