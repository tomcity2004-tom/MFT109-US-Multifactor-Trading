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
from dashboard.components.i18n import t
from dashboard.components.layout import configure, translated_choice
from dashboard.components.loaders import load_or_stop


def main() -> None:
    language = configure("Sensitivity Analysis")
    st.write(t("Each predefined experiment changes one dimension while keeping all other assumptions at baseline. These are historical robustness checks, not a search for the best strategy.", language))
    st.info(t("Baseline: Top 20 · 10 bps · Monthly · Volatility 60 · Reversal 20 · Four factor weights of 25% each.", language))
    bundle, _ = load_or_stop(language)
    group = translated_choice("Experiment", GROUP_LABELS, "sensitivity_group", language)
    metric = translated_choice("Displayed metric", {"Annualized Return": "CAGR", "Sharpe Ratio": "Sharpe Ratio", "Maximum Drawdown": "Maximum Drawdown"}, "sensitivity_metric", language)
    table = sensitivity_view(bundle.sensitivity[group], group, language)
    st.altair_chart(sensitivity_chart(table, metric, language=language), width="stretch")
    st.dataframe(sensitivity_table(table, language), hide_index=True, width="stretch")
    if group == "factor_weights":
        st.caption(t("Tilts use 40% for the named factor and 20% for each other factor. Equal weight uses 25% each.", language))
    st.caption(t("Baseline is highlighted by configuration, not by highest observed performance. Display controls do not run new backtests or modify parameters.", language))


if __name__ == "__main__":
    main()
