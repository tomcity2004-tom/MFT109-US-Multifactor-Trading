"""Metric cards from the validated performance table."""

import streamlit as st
from dashboard.components.formatting import number
from dashboard.components.i18n import t


def kpi_cards(bundle, language: str = "en") -> None:
    metrics = bundle.summary.set_index("Metric")
    final = bundle.daily.iloc[-1]
    rows = [
        [("Final portfolio value", final.portfolio_value_usd, "currency"),
         ("Strategy final NAV", final.strategy_nav, "nav"),
         ("SPY final NAV", final.spy_nav, "nav"),
         ("Cumulative return", metrics.at["Cumulative Return", "Strategy"], "percent")],
        [("CAGR", metrics.at["Annualized Return", "Strategy"], "percent"),
         ("Annualized volatility", metrics.at["Annualized Volatility", "Strategy"], "percent"),
         ("Sharpe ratio · RF 0%", metrics.at["Sharpe Ratio", "Strategy"], "number"),
         ("Maximum drawdown", metrics.at["Maximum Drawdown", "Strategy"], "percent")],
    ]
    for row in rows:
        for column, (label, value, kind) in zip(st.columns(4), row, strict=True):
            column.metric(t(label, language), number(value, kind), border=True)
