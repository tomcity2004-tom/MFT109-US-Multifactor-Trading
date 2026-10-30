"""Streamlit cache wrappers; no downloads, writes or backtest execution."""

import pandas as pd
import streamlit as st
from dashboard.components.i18n import t

from mft109.visualization.dashboard_data import (
    DashboardBundle, DashboardDataError, PortfolioView, bundle_signature,
    load_dashboard_bundle, portfolio_view,
)


@st.cache_data(show_spinner=False, max_entries=2)
def cached_bundle(signature: tuple) -> DashboardBundle:
    return load_dashboard_bundle()


@st.cache_data(show_spinner=False, max_entries=24)
def cached_portfolio(formation: str, signature: tuple) -> PortfolioView:
    return portfolio_view(cached_bundle(signature), pd.Timestamp(formation))


def load_or_stop(language: str = "en") -> tuple[DashboardBundle, tuple]:
    try:
        signature = bundle_signature()
        with st.spinner(t("Loading reviewed project results…", language)):
            return cached_bundle(signature), signature
    except DashboardDataError as error:
        st.error(t("Reviewed project data could not be loaded. No results have been substituted.", language))
        st.warning(t("Required deployment data are missing or inconsistent.", language))
        with st.expander(t("Technical diagnostic (original message)", language)):
            st.code(str(error))
        st.caption(t("Restore the approved tracked dashboard/data deployment artifacts. See docs/PHASE9_STREAMLIT_DASHBOARD.md.", language))
        st.stop()
