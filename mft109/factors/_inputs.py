"""Shared raw-factor input checks and alignment; no downloads or imputation."""

import numpy as np
import pandas as pd


def session_index(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Validate explicit trading sessions and return them in chronological order."""
    if not isinstance(sessions, pd.DatetimeIndex):
        raise TypeError("sessions must be a DatetimeIndex of actual trading sessions")
    if sessions.empty or sessions.hasnans or sessions.has_duplicates:
        raise ValueError("sessions must be nonempty, valid, and unique")
    if sessions.tz is not None or not sessions.equals(sessions.normalize()):
        raise ValueError("sessions must be timezone-naive daily session dates")
    return sessions.sort_values().rename("date")


def align_values(
    values: pd.Series, sessions: pd.DatetimeIndex, *, volume: bool = False
) -> pd.Series:
    """Align one stock's observations without filling gaps or changing the clock.

    Nonfinite/nonpositive adjusted prices and nonfinite/negative volume are
    unavailable inputs, consistent with Phase 1 cleaning. Zero volume is valid.
    Empty numeric Series are permitted for fixed-universe stocks without history.
    """
    calendar = session_index(sessions)
    if not isinstance(values, pd.Series) or not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("factor inputs must be single-stock Series indexed by session date")
    dates = values.index
    if dates.hasnans or dates.has_duplicates:
        raise ValueError("factor input dates must be valid and unique")
    if dates.tz is not None or not dates.equals(dates.normalize()):
        raise ValueError("factor input dates must be timezone-naive daily session dates")
    if not dates.isin(calendar).all():
        raise ValueError("factor input contains dates outside the supplied trading sessions")
    if (not pd.api.types.is_numeric_dtype(values.dtype)
            or pd.api.types.is_bool_dtype(values.dtype)
            or pd.api.types.is_complex_dtype(values.dtype)):
        raise TypeError("factor inputs must contain numeric adjusted prices or volume")
    aligned = values.astype("float64").reindex(calendar)
    valid = np.isfinite(aligned) & (aligned.ge(0) if volume else aligned.gt(0))
    return aligned.where(valid)


def finite_result(values: pd.Series, name: str) -> pd.Series:
    """Keep undefined/overflowing arithmetic missing rather than publishing infinity."""
    return values.where(np.isfinite(values)).rename(name)
