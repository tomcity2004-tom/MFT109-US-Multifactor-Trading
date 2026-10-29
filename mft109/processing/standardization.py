"""Date-specific scoring eligibility and population Z-scores of Phase 2 factors."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.factors.calculation import RAW_FACTOR_COLUMNS


# Direction changes apply to scores only; raw Phase 2 columns are preserved.
FACTOR_SCORES = {
    "momentum": ("momentum_score", 1),
    "volatility60": ("low_volatility_score", -1),
    "liquidity_raw": ("liquidity_score", 1),
    "reversal20": ("reversal_score", 1),
}
SCORE_COLUMNS = [name for name, _ in FACTOR_SCORES.values()]


def _validated_raw_factors(raw_factors: pd.DataFrame) -> pd.DataFrame:
    """Copy canonical raw columns and reject ambiguous identities or schemas."""
    if not isinstance(raw_factors, pd.DataFrame):
        raise TypeError("raw_factors must be a Phase 2 output DataFrame")
    required = ["date", "ticker"] + RAW_FACTOR_COLUMNS
    if not raw_factors.columns.is_unique or not set(required).issubset(raw_factors.columns):
        raise ValueError("raw_factors requires unique date/ticker and all four raw columns")
    data = raw_factors[required].copy()
    if data.empty:
        return data
    dates = pd.DatetimeIndex(data.date)
    if dates.hasnans or dates.tz is not None or not dates.equals(dates.normalize()):
        raise ValueError("Scoring dates must be valid timezone-naive daily session dates")
    data["date"] = dates
    if data.ticker.map(lambda t: not isinstance(t, str) or not t.strip() or t != t.strip()).any():
        raise ValueError("Scoring rows require nonempty ticker identifiers")
    if data.ticker.eq(BASELINE.benchmark).any():
        raise ValueError("SPY benchmark must remain separate from stock scoring")
    if data.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate date/ticker observations in scoring inputs")
    for column in RAW_FACTOR_COLUMNS:
        dtype = data[column].dtype
        if (not pd.api.types.is_numeric_dtype(dtype)
                or pd.api.types.is_bool_dtype(dtype)
                or pd.api.types.is_complex_dtype(dtype)):
            raise TypeError(f"Raw factor {column} must be real numeric data")
    return data


def _eligible_rows(data: pd.DataFrame) -> pd.Series:
    if data.empty:
        return pd.Series(index=data.index, dtype=bool, name="eligible")
    values = data[RAW_FACTOR_COLUMNS].to_numpy(dtype="float64", na_value=np.nan)
    return pd.Series(np.isfinite(values).all(axis=1), index=data.index, name="eligible")


def scoring_eligibility(raw_factors: pd.DataFrame) -> pd.Series:
    """True only for rows with all four finite raw factors, aligned to input rows.

    Validity is evaluated independently on each date; no permanent ticker removal
    or raw-value replacement is performed. Phase 2 is responsible for raw formulas.
    """
    return _eligible_rows(_validated_raw_factors(raw_factors))


def _population_zscore(values: pd.Series) -> pd.Series:
    """Z=(X-mean(X))/std(X, ddof=0) within one eligible factor/date group."""
    values = values.astype("float64")
    if values.eq(values.iloc[0]).all():
        return pd.Series(0.0, index=values.index)
    # Positive common rescaling cancels in Z; it prevents overflow without clipping.
    scaled = values / values.abs().max()
    centered = scaled - scaled.iloc[0]
    deviation = centered.std(ddof=0)
    result = (centered - centered.mean()) / deviation
    if not np.isfinite(result).all():
        raise ArithmeticError("Cannot produce finite cross-sectional Z-scores")
    return result


def standardize_factors(raw_factors: pd.DataFrame) -> pd.DataFrame:
    """Preserve all raw rows; append eligibility and four higher-is-better scores.

    All four factors use the SAME eligible stocks on each date. Ineligible rows
    keep NaN scores. A constant cross-section, including a single eligible stock,
    receives zero. Output is sorted by date/ticker only, never by investment score.
    """
    data = _validated_raw_factors(raw_factors)
    data = data.sort_values(["date", "ticker"]).reset_index(drop=True)
    data["eligible"] = _eligible_rows(data)
    for score in SCORE_COLUMNS:
        data[score] = np.nan
    eligible = data.loc[data.eligible]
    if not eligible.empty:
        for raw, (score, direction) in FACTOR_SCORES.items():
            zscores = eligible.groupby("date", sort=False)[raw].transform(_population_zscore)
            data.loc[eligible.index, score] = direction * zscores
    return data
