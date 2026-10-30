"""Academic factor definitions and standardized-score visualization."""

# Streamlit's console launcher may put only the script directory on sys.path.
from pathlib import Path
import sys

_REPOSITORY_ROOT = str(Path(__file__).resolve().parents[2])
if _REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT)

import streamlit as st
from mft109.visualization.dashboard_data import formation_dates
from dashboard.components.charts import factor_heatmap
from dashboard.components.layout import configure
from dashboard.components.loaders import load_or_stop


def main() -> None:
    configure("Factors")
    st.caption("P is the consistent adjusted-price series; lags count trading sessions.")
    left, right = st.columns(2)
    with left:
        st.subheader("12–1 Month Momentum")
        st.latex(r"Momentum_t = P_{t-21}/P_{t-252}-1")
        st.write("Higher is preferred. Skip the most recent 21 sessions.")
        st.subheader("20-Day Liquidity")
        st.latex(r"DV_t=P_t V_t,\quad ADV20_t=mean(DV_{t-19:t})")
        st.latex(r"LiquidityRaw_t=\ln(ADV20_t)")
        st.write("Higher is preferred. Volume is Yahoo-reported Volume.")
    with right:
        st.subheader("60-Day Historical Volatility")
        st.latex(r"r_t=P_t/P_{t-1}-1,\quad Vol60_t=Std(r_{t-59:t},ddof=1)\sqrt{252}")
        st.write("Require all 60 consecutive returns. Lower raw volatility is preferred; its score is −Z(Vol60).")
        st.subheader("20-Day Short-Term Reversal")
        st.latex(r"Reversal20_t=-(P_t/P_{t-20}-1)")
        st.write("Recent underperformers receive higher reversal scores.")
    st.subheader("Cross-sectional composite")
    st.latex(r"M=Z(Momentum),\quad LV=-Z(Vol60),\quad L=Z(LiquidityRaw),\quad R=Z(Reversal20)")
    st.latex(r"CompositeScore=0.25M+0.25LV+0.25L+0.25R")
    st.write("Standardize across eligible stocks at each formation. All four factors must be valid. Higher CompositeScore means a more desirable stock; missing factors are not filled or partially reweighted.")
    bundle, _ = load_or_stop()
    dates = formation_dates(bundle)
    chosen = st.selectbox("Formation date", dates, index=len(dates)-1, format_func=lambda d: d.strftime("%Y-%m-%d"))
    selected = bundle.selected.loc[bundle.selected.formation_date.eq(chosen)]
    st.altair_chart(factor_heatmap(selected), width="stretch")


if __name__ == "__main__":
    main()
