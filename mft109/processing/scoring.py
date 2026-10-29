"""Locked equal-weight composite scoring; no ranking or portfolio selection."""

import math

import pandas as pd

from mft109.config import BASELINE
from mft109.optimization.scenarios import Scenario, check_scenario
from mft109.processing.standardization import standardize_factors


def baseline_factor_weights() -> dict[str, float]:
    """Read and validate existing configuration; no custom/dynamic weights."""
    weights = {
        "momentum_score": BASELINE.momentum_weight,
        "low_volatility_score": BASELINE.low_volatility_weight,
        "liquidity_score": BASELINE.liquidity_weight,
        "reversal_score": BASELINE.reversal_weight,
    }
    if (any(not math.isfinite(w) for w in weights.values())
            or sum(weights.values()) != 1.0
            or any(w != 0.25 for w in weights.values())):
        raise ValueError("Baseline requires four fixed 0.25 weights summing exactly to 1.0")
    return weights


def score_factors(raw_factors: pd.DataFrame, *, scenario: Scenario | None = None) -> pd.DataFrame:
    """Append same-date standardized scores and their fixed 25% composite.

    Returns canonical raw columns, eligible, four score columns, composite_score.
    Every input date/ticker row is retained. Ineligible rows receive NaN scores,
    not neutral zeros or redistributed weights. There is no rank or selection.
    Phase 7 may explicitly supply one predefined factor-weight tilt. No custom
    weights are accepted, and the default remains the validated equal composite.
    """
    weights = baseline_factor_weights()
    check_scenario(scenario)
    if scenario is not None:
        weights = dict(zip(weights, scenario.weights, strict=True))
    result = standardize_factors(raw_factors)
    # Explicit addition propagates NaN; a skip-NaN row sum could fabricate zeros.
    result["composite_score"] = (
        weights["momentum_score"] * result.momentum_score
        + weights["low_volatility_score"] * result.low_volatility_score
        + weights["liquidity_score"] * result.liquidity_score
        + weights["reversal_score"] * result.reversal_score
    )
    return result
