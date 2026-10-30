"""Validated NAV, drawdown, annual returns and metric comparison."""

# Streamlit's console launcher may put only the script directory on sys.path.
from pathlib import Path
import sys

_REPOSITORY_ROOT = str(Path(__file__).resolve().parents[2])
if _REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT)

import streamlit as st
from dashboard.components.charts import time_chart, annual_chart
from dashboard.components.formatting import comparison_table, number
from dashboard.components.layout import configure
from dashboard.components.loaders import load_or_stop


def main() -> None:
    configure("Performance")
    bundle, _ = load_or_stop()
    st.altair_chart(time_chart(bundle.daily), width="stretch")
    st.altair_chart(time_chart(bundle.daily, drawdown=True), width="stretch")
    st.altair_chart(annual_chart(bundle.annual), width="stretch")
    left, right = st.columns(2)
    left.subheader("Strategy vs SPY")
    left.dataframe(comparison_table(bundle.summary), hide_index=True, width="stretch")
    right.subheader("Calendar-year returns")
    table = bundle.annual[["Year", "Strategy", "SPY"]].copy()
    for col in ("Strategy", "SPY"):
        table[col] = table[col].map(lambda value: number(value, "percent"))
    right.dataframe(table, hide_index=True, width="stretch")
    st.caption("CAGR uses close-to-close periods; sample volatility uses ddof=1 and 252 sessions/year. Sharpe = CAGR / volatility at 0% risk-free rate.")


if __name__ == "__main__":
    main()
