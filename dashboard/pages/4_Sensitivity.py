"""Fixed historical sensitivity comparisons, without automatic winner selection."""

# Streamlit's console launcher may put only the script directory on sys.path.
from pathlib import Path
import sys

_REPOSITORY_ROOT = str(Path(__file__).resolve().parents[2])
if _REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT)

import streamlit as st
from mft109.visualization.dashboard_data import GROUP_LABELS
from dashboard.components.charts import sensitivity_chart
from dashboard.components.formatting import sensitivity_view, sensitivity_table
from dashboard.components.layout import configure
from dashboard.components.loaders import load_or_stop


def main() -> None:
    configure("Sensitivity Analysis")
    st.write("Each predefined experiment changes one dimension while keeping all other assumptions at baseline. These are historical robustness checks, not a search for the best strategy.")
    st.info("Baseline: Top 20 · 10 bps · Monthly · Volatility 60 · Reversal 20 · Four factor weights of 25% each.")
    bundle, _ = load_or_stop()
    group_label = st.selectbox("Experiment", list(GROUP_LABELS.values()))
    group = next(key for key, label in GROUP_LABELS.items() if label == group_label)
    metric_label = st.selectbox("Displayed metric", ["CAGR", "Sharpe Ratio", "Maximum Drawdown"])
    metric = "Annualized Return" if metric_label == "CAGR" else metric_label
    table = sensitivity_view(bundle.sensitivity[group], group)
    st.altair_chart(sensitivity_chart(table, metric), width="stretch")
    st.dataframe(sensitivity_table(table), hide_index=True, width="stretch")
    if group == "factor_weights":
        st.caption("Tilts use 40% for the named factor and 20% for each other factor. Equal weight uses 25% each.")
    st.caption("Baseline is highlighted by configuration, not by highest observed performance. Display controls do not run new backtests or modify parameters.")


if __name__ == "__main__":
    main()
