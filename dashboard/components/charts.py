"""Interactive Altair charts over validated numerical output, with no model logic."""

import altair as alt
import numpy as np
import pandas as pd

from mft109.visualization.dashboard_data import SCORE_LABELS


COLORS = alt.Scale(domain=["Strategy", "SPY"], range=["#245EA8", "#B07A2A"])


def time_chart(daily: pd.DataFrame, *, drawdown: bool = False) -> alt.Chart:
    columns = {"strategy_drawdown": "Strategy", "spy_drawdown": "SPY"} if drawdown else {"strategy_nav": "Strategy", "spy_nav": "SPY"}
    data = daily[["date", *columns]].rename(columns=columns)
    title = "Drawdown from running peak" if drawdown else "Multi-Factor Strategy vs SPY Buy-and-Hold"
    return (alt.Chart(data).transform_fold(["Strategy", "SPY"], as_=["Series", "Value"])
            .mark_line(strokeWidth=2.2).encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("Value:Q", title="Drawdown" if drawdown else "Normalized NAV",
                        axis=alt.Axis(format=".0%" if drawdown else ".1f")),
                color=alt.Color("Series:N", scale=COLORS, title=None),
                tooltip=[alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"), "Series:N",
                         alt.Tooltip("Value:Q", format=".2%" if drawdown else ".4f")])
            .properties(title=title, height=350).interactive(bind_y=False))


def annual_chart(annual: pd.DataFrame) -> alt.Chart:
    return (alt.Chart(annual[["Year", "Strategy", "SPY"]])
            .transform_fold(["Strategy", "SPY"], as_=["Series", "Return"])
            .mark_bar().encode(x=alt.X("Year:O", title="Calendar year"), xOffset="Series:N",
                               y=alt.Y("Return:Q", title="Annual return", axis=alt.Axis(format=".0%")),
                               color=alt.Color("Series:N", scale=COLORS, title=None),
                               tooltip=["Year:O", "Series:N", alt.Tooltip("Return:Q", format=".2%")])
            .properties(title="Annual returns · Strategy and SPY", height=330))


def factor_heatmap(selected: pd.DataFrame) -> alt.Chart:
    data = selected[["ticker", *SCORE_LABELS]].rename(columns={"ticker": "Ticker", **SCORE_LABELS})
    long = data.melt(id_vars="Ticker", var_name="Factor", value_name="Score")
    bound = float(np.abs(long.Score).max()) or 1.
    return (alt.Chart(long).mark_rect().encode(
        x=alt.X("Factor:N", sort=list(SCORE_LABELS.values()), title=None),
        y=alt.Y("Ticker:N", sort=selected.ticker.tolist(), title="Selected stock"),
        color=alt.Color("Score:Q", scale=alt.Scale(domain=[-bound, bound], scheme="redblue", domainMid=0), title="Z-score"),
        tooltip=["Ticker:N", "Factor:N", alt.Tooltip("Score:Q", format=".3f")])
        .properties(title="Standardized factor scores · higher is preferred", height=480))


def sensitivity_chart(table: pd.DataFrame, metric: str) -> alt.Chart:
    return (alt.Chart(table).mark_bar().encode(
        x=alt.X("Setting:N", sort=table.Setting.tolist(), title="Predefined scenario"),
        y=alt.Y(f"{metric}:Q", title="CAGR" if metric == "Annualized Return" else metric,
                axis=alt.Axis(format=".2f" if metric == "Sharpe Ratio" else ".0%")),
        color=alt.Color("Baseline:N", scale=alt.Scale(domain=["Baseline", "Sensitivity"], range=["#245EA8", "#A9BACD"]), title=None),
        tooltip=["Setting:N", "Baseline:N", alt.Tooltip(f"{metric}:Q", format=".3f" if metric == "Sharpe Ratio" else ".2%")])
        .properties(title="Historical one-at-a-time sensitivity", height=330))
