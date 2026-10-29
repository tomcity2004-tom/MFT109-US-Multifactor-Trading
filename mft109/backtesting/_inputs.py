"""Validate Phase 4 outputs and adapt normalized adjusted prices without filling."""

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.portfolio import CASH_ASSET
from mft109.ranking import MonthlySelection


def selection_inputs(
    selection: MonthlySelection, official: pd.DatetimeIndex
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Copy validated selection records; reject inconsistent inputs, never rerank."""
    if not isinstance(selection, MonthlySelection):
        raise TypeError("Expected the validated Phase 4 MonthlySelection output")
    ranked = selection.ranked.copy(deep=True)
    summary = selection.formation_summary.copy(deep=True)
    required = {"formation_date", "ticker", "rank", "selected", "eligible", "composite_score"}
    if not required.issubset(ranked.columns) or not {
        "formation_date", "eligible_count", "selected_count", "fewer_than_top_n"
    }.issubset(summary.columns):
        raise ValueError("Missing Phase 4 selection or summary columns")
    for frame in (ranked, summary):
        dates = frame["formation_date"]
        if not pd.api.types.is_datetime64_any_dtype(dates.dtype):
            raise TypeError("Formation dates must be naive datetime values")
        if dates.dt.tz is not None or not dates.isin(official).all():
            raise ValueError("Formation dates must belong to the official SPY clock")
    if summary["formation_date"].duplicated().any():
        raise ValueError("Duplicate formation summary dates")
    # Every official calendar month must retain its Phase 4 month-end record,
    # including an empty selection and the final unexecutable formation.
    month_ends = pd.Series(official, index=official).groupby(official.to_period("M")).max()
    if set(summary.formation_date) != set(month_ends):
        raise ValueError("Phase 4 summary must cover every official month-end")
    if ranked.duplicated(["formation_date", "ticker"]).any():
        raise ValueError("Duplicate formation/ticker selection records")
    if not ranked.formation_date.isin(summary.formation_date).all():
        raise ValueError("Ranked records have no formation summary")
    for column in ("selected", "eligible"):
        if ranked[column].isna().any() or not pd.api.types.is_bool_dtype(ranked[column]):
            raise TypeError("Phase 4 eligibility and selection flags must be boolean")
    if not ranked.empty:
        if (not pd.api.types.is_integer_dtype(ranked["rank"])
                or ranked["rank"].isna().any()):
            raise ValueError("Phase 4 ranks must be integer values")
        if (not ranked.eligible.all() or not np.isfinite(ranked.composite_score).all()
                or not ranked.selected.eq(ranked["rank"] <= BASELINE.top_n).all()):
            raise ValueError("Phase 4 ranks/flags/scores are inconsistent")
        if ranked.ticker.map(lambda t: not isinstance(t, str) or not t.strip()
                             or t != t.strip() or t in (CASH_ASSET, BASELINE.benchmark)).any():
            raise ValueError("Invalid selected stock identifier")
    for row in summary.itertuples(index=False):
        group = ranked.loc[ranked.formation_date.eq(row.formation_date)]
        if (row.eligible_count != len(group) or row.selected_count != int(group.selected.sum())
                or sorted(group["rank"].tolist()) != list(range(1, len(group) + 1))
                or row.fewer_than_top_n != (row.selected_count < BASELINE.top_n)):
            raise ValueError("Phase 4 summary counts or unique sequential ranks are inconsistent")
    return (ranked.sort_values(["formation_date", "rank"]).reset_index(drop=True),
            summary.sort_values("formation_date").reset_index(drop=True))


def adjusted_price_grid(market_data: pd.DataFrame, official: pd.DatetimeIndex,
                        tickers: list[str]) -> pd.DataFrame:
    """Reindex selected stocks on SPY sessions, preserving absent prices as NaN."""
    if not isinstance(market_data, pd.DataFrame) or not {
        "date", "ticker", "adjusted_close"
    }.issubset(market_data.columns):
        raise ValueError("Normalized market data require date, ticker and adjusted_close")
    frame = market_data.loc[:, ["date", "ticker", "adjusted_close"]].copy()
    if (not pd.api.types.is_datetime64_any_dtype(frame.date)
            or frame.date.dt.tz is not None or frame.date.isna().any()
            or not frame.date.eq(frame.date.dt.normalize()).all()):
        raise ValueError("Market dates must be naive midnight datetime values")
    if frame.ticker.map(lambda t: not isinstance(t, str) or not t.strip()).any():
        raise ValueError("Market tickers must be nonempty strings")
    if frame.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate normalized market observations")
    prices = frame.adjusted_close
    if (not pd.api.types.is_numeric_dtype(prices) or pd.api.types.is_bool_dtype(prices)
            or pd.api.types.is_complex_dtype(prices)):
        raise TypeError("Adjusted prices must be real numeric values")
    grid = frame.pivot(index="date", columns="ticker", values="adjusted_close")
    return grid.reindex(index=official, columns=sorted(tickers)).astype("float64")
