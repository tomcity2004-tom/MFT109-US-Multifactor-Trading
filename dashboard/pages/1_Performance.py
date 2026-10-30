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
from dashboard.components.i18n import t
from dashboard.components.layout import configure
from dashboard.components.loaders import load_or_stop


def main() -> None:
    language = configure("Performance")
    bundle, _ = load_or_stop(language)
    st.altair_chart(time_chart(bundle.daily, language=language), width="stretch")
    st.altair_chart(time_chart(bundle.daily, drawdown=True, language=language), width="stretch")
    st.altair_chart(annual_chart(bundle.annual, language=language), width="stretch")
    left, right = st.columns(2)
    left.subheader(t("Strategy vs SPY", language))
    left.dataframe(comparison_table(bundle.summary, language), hide_index=True, width="stretch")
    right.subheader(t("Calendar-year returns", language))
    table = bundle.annual[["Year", "Strategy", "SPY"]].copy()
    for col in ("Strategy", "SPY"):
        table[col] = table[col].map(lambda value: number(value, "percent"))
    right.dataframe(table.rename(columns={c: t(c, language) for c in table.columns}), hide_index=True, width="stretch")
    st.caption(t("CAGR uses close-to-close periods; sample volatility uses ddof=1 and 252 sessions/year. Sharpe = CAGR / volatility at 0% risk-free rate.", language))


if __name__ == "__main__":
    main()
