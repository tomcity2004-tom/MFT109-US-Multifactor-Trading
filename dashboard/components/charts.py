"""Interactive charts; language changes labels and copied display fields only."""

import altair as alt
import numpy as np
import pandas as pd
from mft109.visualization.dashboard_data import SCORE_LABELS
from dashboard.components.i18n import t


def _colors(language: str) -> alt.Scale:
    return alt.Scale(domain=[t("Strategy", language), "SPY"], range=["#245EA8", "#B07A2A"])


def time_chart(daily: pd.DataFrame, *, drawdown: bool = False, language: str = "en") -> alt.Chart:
    columns = {"strategy_drawdown": t("Strategy", language), "spy_drawdown": "SPY"} if drawdown else {"strategy_nav": t("Strategy", language), "spy_nav": "SPY"}
    data = daily[["date", *columns]].rename(columns=columns)
    title = "Drawdown from running peak" if drawdown else "Multi-Factor Strategy vs SPY Buy-and-Hold"
    value_title = t("Drawdown" if drawdown else "Normalized NAV", language)
    y = alt.Y("Value:Q", title=value_title,
              axis=alt.Axis(format=".0%" if drawdown else ".1f"))
    if drawdown:
        # Display padding only: retain the original non-positive daily values.
        y.scale = alt.Scale(domain=[-0.40, 0.05], nice=False)
        y.axis = alt.Axis(format=".0%", values=[tick / 100 for tick in range(-40, 6, 5)])
    return (alt.Chart(data).transform_fold(list(columns.values()), as_=["Series", "Value"])
            .mark_line(strokeWidth=2.2).encode(
                x=alt.X("date:T", title=t("Date", language)),
                y=y,
                color=alt.Color("Series:N", scale=_colors(language), title=None),
                tooltip=[alt.Tooltip("date:T", title=t("Date", language), format="%Y-%m-%d"),
                         alt.Tooltip("Series:N", title=t("Series", language)),
                         alt.Tooltip("Value:Q", title=value_title, format=".2%" if drawdown else ".4f")])
            .properties(title=t(title, language), height=350).interactive(bind_y=False))


def annual_chart(annual: pd.DataFrame, *, language: str = "en") -> alt.Chart:
    data = annual[["Year", "Strategy", "SPY"]].rename(columns={"Strategy": t("Strategy", language)})
    return (alt.Chart(data).transform_fold([t("Strategy", language), "SPY"], as_=["Series", "Return"])
            .mark_bar().encode(x=alt.X("Year:O", title=t("Calendar year", language)), xOffset="Series:N",
                               y=alt.Y("Return:Q", title=t("Annual return", language), axis=alt.Axis(format=".0%")),
                               color=alt.Color("Series:N", scale=_colors(language), title=None),
                               tooltip=[alt.Tooltip("Year:O", title=t("Year", language)),
                                        alt.Tooltip("Series:N", title=t("Series", language)),
                                        alt.Tooltip("Return:Q", title=t("Annual return", language), format=".2%")])
            .properties(title=t("Annual returns · Strategy and SPY", language), height=330))


def factor_heatmap(selected: pd.DataFrame, *, language: str = "en") -> alt.Chart:
    labels = {k: t(v, language) for k, v in SCORE_LABELS.items()}
    data = selected[["ticker", *SCORE_LABELS]].rename(columns={"ticker": "Ticker", **labels})
    long = data.melt(id_vars="Ticker", var_name="Factor", value_name="Score")
    bound = float(np.abs(long.Score).max()) or 1.
    return (alt.Chart(long).mark_rect().encode(
        x=alt.X("Factor:N", sort=list(labels.values()), title=None),
        y=alt.Y("Ticker:N", sort=selected.ticker.tolist(), title=t("Selected stock", language)),
        color=alt.Color("Score:Q", scale=alt.Scale(domain=[-bound, bound], scheme="redblue", domainMid=0), title=t("Z-score", language)),
        tooltip=[alt.Tooltip("Ticker:N", title=t("Ticker", language)),
                 alt.Tooltip("Factor:N", title=t("Factor", language)),
                 alt.Tooltip("Score:Q", title=t("Score", language), format=".3f")])
        .properties(title=t("Standardized factor scores · higher is preferred", language), height=480))


def sensitivity_chart(table: pd.DataFrame, metric: str, *, language: str = "en") -> alt.Chart:
    metric_title = t("CAGR" if metric == "Annualized Return" else metric, language)
    return (alt.Chart(table).mark_bar().encode(
        x=alt.X("Setting:N", sort=table.Setting.tolist(), title=t("Predefined scenario", language)),
        y=alt.Y(f"{metric}:Q", title=metric_title,
                axis=alt.Axis(format=".2f" if metric == "Sharpe Ratio" else ".0%")),
        color=alt.Color("Baseline:N", scale=alt.Scale(domain=[t("Baseline", language), t("Sensitivity", language)], range=["#245EA8", "#A9BACD"]), title=None),
        tooltip=[alt.Tooltip("Setting:N", title=t("Setting", language)),
                 alt.Tooltip("Baseline:N", title=t("Baseline", language)),
                 alt.Tooltip(f"{metric}:Q", title=metric_title, format=".3f" if metric == "Sharpe Ratio" else ".2%")])
        .properties(title=t("Historical one-at-a-time sensitivity", language), height=330))
