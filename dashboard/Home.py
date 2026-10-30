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
from dashboard.components.i18n import t
from dashboard.components.layout import configure, limitations
from dashboard.components.loaders import load_or_stop
from dashboard.components.metrics import kpi_cards
from dashboard.components.formatting import number


def main() -> None:
    language = configure("MFT109 — U.S. Multi-Factor Trading Strategy")
    st.markdown(t("Four complementary factors combine momentum, low volatility, liquidity and short-term reversal into monthly stock selections.", language))
    bundle, _ = load_or_stop(language)
    st.caption(t("Reviewed revised-data results · full official backtest · no live market-data requests", language))
    kpi_cards(bundle, language)
    st.altair_chart(time_chart(bundle.daily, language=language), width="stretch")
    st.subheader(t("Approved baseline", language))
    left, right = st.columns(2)
    left.markdown(t("**Market:** U.S. Equities  \n**Universe:** Fixed current S&P 500 snapshot  \n**Portfolio:** Top {top_n}, equal weight  \n**Rebalance:** Monthly", language, top_n=BASELINE.top_n))
    right.markdown(t("**Costs:** {bps} bps × turnover  \n**Benchmark:** SPY Buy-and-Hold  \n**Backtest:** 2016–2025  \n**Initial capital:** {capital}", language, bps=f"{BASELINE.transaction_cost_rate * 10000:g}", capital=number(BASELINE.initial_capital_usd, 'currency')))
    limitations(language)


if __name__ == "__main__":
    main()
