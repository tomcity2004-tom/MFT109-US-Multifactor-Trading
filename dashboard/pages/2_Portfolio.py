"""Historical selection controls affect display only, never strategy parameters."""

# Streamlit's console launcher may put only the script directory on sys.path.
from pathlib import Path
import sys

_REPOSITORY_ROOT = str(Path(__file__).resolve().parents[2])
if _REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT)

import pandas as pd
import streamlit as st
from mft109.visualization.dashboard_data import DashboardDataError, formation_dates
from dashboard.components.formatting import portfolio_table, number
from dashboard.components.i18n import t
from dashboard.components.layout import configure
from dashboard.components.loaders import load_or_stop, cached_portfolio


def main() -> None:
    language = configure("Portfolio")
    bundle, signature = load_or_stop(language)
    dates = formation_dates(bundle)
    chosen = st.selectbox(t("Formation date", language), dates, index=len(dates)-1, format_func=lambda d: d.strftime("%Y-%m-%d"), key="formation_date_portfolio")
    try:
        with st.spinner(t("Loading reviewed execution targets…", language)):
            view = cached_portfolio(chosen.strftime("%Y-%m-%d"), signature)
    except DashboardDataError as error:
        st.error(t("Execution targets could not be loaded.", language))
        with st.expander(t("Technical diagnostic (original message)", language)):
            st.code(str(error))
        st.stop()
    if pd.isna(view.execution_date):
        st.info(t("This final month-end is a selection signal only. No next execution occurs inside the official backtest; target weights are not assigned. Select an earlier date to inspect an executed target.", language))
    else:
        st.caption(t("Formation: {formation} · Execution: {execution} at adjusted close · Target cash: {cash}", language, formation=f"{chosen:%Y-%m-%d}", execution=f"{view.execution_date:%Y-%m-%d}", cash=number(view.cash_weight, "percent")))
    st.dataframe(portfolio_table(view.table, language), hide_index=True, width="stretch")
    st.caption(t("Targets apply at execution, then holdings drift with market prices. This table shows targets, not daily rebalanced weights.", language))


if __name__ == "__main__":
    main()
