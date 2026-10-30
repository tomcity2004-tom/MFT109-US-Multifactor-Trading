"""Consistent project framing and visible academic limitations."""

import streamlit as st
from mft109.config import BASELINE


def configure(title: str) -> None:
    st.set_page_config(page_title="MFT109 Multi-Factor Trading", layout="wide")
    st.sidebar.title("MFT109")
    st.sidebar.caption("Financial Algorithmic Trading")
    st.sidebar.markdown("**U.S. multi-factor stock selection**\n\n2016–2025 · SPY benchmark\n\n4 factors · Top 20 · Monthly")
    st.sidebar.divider()
    st.sidebar.caption("Fixed current S&P 500 snapshot. Survivorship bias applies. Academic research; not investment advice.")
    st.title(title)
    st.caption("S&P 500 Multi-Factor Stock Selection Backtest · 2016–2025")


def limitations() -> None:
    st.subheader("Methodology and limitations")
    st.markdown(
        "- A fixed snapshot of **current S&P 500 constituents** is used throughout history, introducing **survivorship bias**.\n"
        "- Yahoo Finance historical data may be revised; this dashboard uses the reviewed data version.\n"
        "- Next-session adjusted-close execution is a simplified academic convention.\n"
        f"- Transaction costs are {BASELINE.transaction_cost_rate * 10000:g} bps × actual cash-inclusive turnover.\n"
        "- Historical results and sensitivity comparisons are not evidence of future superiority.\n"
        "- This academic backtest is **not investment advice**.")
