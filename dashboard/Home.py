"""Project overview; display validated results without implementing model logic."""

# Streamlit's console launcher may put only the script directory on sys.path.
from pathlib import Path
import sys

_REPOSITORY_ROOT = str(Path(__file__).resolve().parents[1])
if _REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT)

import streamlit as st
from mft109.config import BASELINE
from dashboard.components.charts import time_chart
from dashboard.components.layout import configure, limitations
from dashboard.components.loaders import load_or_stop
from dashboard.components.metrics import kpi_cards
from dashboard.components.formatting import number


def main() -> None:
    configure("MFT109 — U.S. Multi-Factor Trading Strategy")
    st.markdown("Four complementary factors combine momentum, low volatility, liquidity and short-term reversal into monthly stock selections.")
    bundle, _ = load_or_stop()
    st.caption("Reviewed revised-data results · full official backtest · no live market-data requests")
    kpi_cards(bundle)
    st.altair_chart(time_chart(bundle.daily), width="stretch")
    st.subheader("Approved baseline")
    left, right = st.columns(2)
    left.markdown(f"**Market:** U.S. Equities  \n**Universe:** Fixed current S&P 500 snapshot  \n**Portfolio:** Top {BASELINE.top_n}, equal weight  \n**Rebalance:** Monthly")
    right.markdown(f"**Costs:** {BASELINE.transaction_cost_rate * 10000:g} bps × turnover  \n**Benchmark:** SPY Buy-and-Hold  \n**Backtest:** 2016–2025  \n**Initial capital:** {number(BASELINE.initial_capital_usd, 'currency')}")
    limitations()


if __name__ == "__main__":
    main()
