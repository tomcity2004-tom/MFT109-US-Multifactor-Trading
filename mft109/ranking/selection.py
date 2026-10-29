"""Deterministic monthly ranking and baseline Top 20 membership; no allocation."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.optimization.scenarios import Scenario, check_scenario
from mft109.factors import RAW_FACTOR_COLUMNS
from mft109.factors._inputs import session_index
from mft109.processing import SCORE_COLUMNS
from mft109.ranking.formation import monthly_formation_dates


@dataclass(frozen=True)
class MonthlySelection:
    """Full eligible rankings and counts for every official formation date."""

    ranked: pd.DataFrame
    formation_summary: pd.DataFrame

    @property
    def selected(self) -> pd.DataFrame:
        """Return a separate table of selected stocks, without portfolio weights."""
        return self.ranked.loc[self.ranked.selected].copy()


def _validated_scores(scored_factors: pd.DataFrame) -> pd.DataFrame:
    """Copy Phase 3 identifiers/scores; do not recompute any factor or composite."""
    if not isinstance(scored_factors, pd.DataFrame):
        raise TypeError("scored_factors must be a Phase 3 output DataFrame")
    required = ["date", "ticker", "eligible", "composite_score"]
    if not scored_factors.columns.is_unique or not set(required).issubset(scored_factors.columns):
        raise ValueError("Ranking requires unique date/ticker/eligible/composite_score columns")
    if {"formation_date", "rank", "selected"}.intersection(scored_factors.columns):
        raise ValueError("Ranking expects Phase 3 scores, not already-ranked results")
    canonical = ["date", "ticker"] + RAW_FACTOR_COLUMNS + ["eligible"] + SCORE_COLUMNS + ["composite_score"]
    data = scored_factors[[column for column in canonical if column in scored_factors]].copy()
    data["date"] = pd.DatetimeIndex(data.date)
    if data.empty:
        return data
    dates = pd.DatetimeIndex(data.date)
    if dates.hasnans or dates.tz is not None or not dates.equals(dates.normalize()):
        raise ValueError("Ranking dates must be valid timezone-naive daily session dates")
    if data.ticker.map(lambda t: not isinstance(t, str) or not t.strip() or t != t.strip()).any():
        raise ValueError("Ranking rows require nonempty ticker identifiers")
    if data.ticker.eq(BASELINE.benchmark).any():
        raise ValueError("SPY is the session-calendar benchmark, not a candidate stock")
    if data.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate date/ticker observations in ranking inputs")
    if not pd.api.types.is_bool_dtype(data.eligible.dtype):
        raise TypeError("Phase 3 eligible must be a Boolean column")
    dtype = data.composite_score.dtype
    if (not pd.api.types.is_numeric_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)
            or pd.api.types.is_complex_dtype(dtype)):
        raise TypeError("Phase 3 composite_score must be real numeric data")
    return data


def rank_and_select(
    scored_factors: pd.DataFrame, *, sessions: pd.DatetimeIndex, scenario: Scenario | None = None
) -> MonthlySelection:
    """Rank exact-formation-date eligible finite scores, then mark ranks <= 20.

    Ordering is formation date, composite descending, ticker ascending for exact
    ties. Ranks are unique sequential integers within each date. There is no
    score filling, recomputation, weight assignment, or next-day execution.
    Counts explicitly document all months with fewer than 20, including zero.
    An explicit Phase 7 scenario may change N or retain quarter-end formations;
    the ranking/tie-break algorithm and default monthly Top 20 remain unchanged.
    """
    if type(BASELINE.top_n) is not int or BASELINE.top_n != 20:
        raise ValueError("Phase 4 baseline requires the configured integer top_n=20")
    check_scenario(scenario)
    top_n = scenario.top_n if scenario else BASELINE.top_n
    calendar = session_index(sessions)
    formations = monthly_formation_dates(calendar)
    if scenario is not None and scenario.quarterly:
        formations = formations[formations.month.isin([3, 6, 9, 12])]
    data = _validated_scores(scored_factors)
    # Warm-up and post-backtest observations never become official formations.
    data = data.loc[data.date.between(pd.Timestamp(BASELINE.backtest_start),
                                    pd.Timestamp(BASELINE.backtest_end))].copy()
    if not data.date.isin(calendar).all():
        raise ValueError("Official-period score dates must belong to the supplied SPY sessions")
    if data.empty:
        valid = pd.Series(False, index=data.index)
    else:
        marked_eligible = data.eligible.to_numpy(dtype=bool, na_value=False)
        finite_score = np.isfinite(data.composite_score.to_numpy(dtype="float64", na_value=np.nan))
        valid = marked_eligible & finite_score & data.date.isin(formations)
    ranked = data.loc[valid].sort_values(
        ["date", "composite_score", "ticker"], ascending=[True, False, True], kind="stable"
    ).reset_index(drop=True).rename(columns={"date": "formation_date"})
    ranked["rank"] = (ranked.groupby("formation_date", sort=False).cumcount() + 1).astype("int64")
    ranked["selected"] = ranked["rank"].le(top_n)

    # Zero counts are diagnostics only; no stock rows or scores are fabricated.
    eligible_counts = ranked.groupby("formation_date").size().reindex(formations, fill_value=0)
    selected_counts = ranked.loc[ranked.selected].groupby("formation_date").size().reindex(formations, fill_value=0)
    summary = pd.DataFrame({"formation_date": formations,
                            "eligible_count": eligible_counts.to_numpy(dtype="int64"),
                            "selected_count": selected_counts.to_numpy(dtype="int64")})
    summary["fewer_than_top_n"] = summary.eligible_count.lt(top_n)
    return MonthlySelection(ranked=ranked, formation_summary=summary)
