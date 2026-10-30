"""Display-only labels and number formatting; source values are never changed."""

import math
import pandas as pd
from dashboard.components.i18n import t

from mft109.visualization.dashboard_data import METRIC_COLUMNS, SCORE_LABELS


def number(value: float, kind: str = "number") -> str:
    if pd.isna(value) or not math.isfinite(float(value)):
        return "—"
    if kind == "percent":
        return f"{value:.2%}"
    if kind == "currency":
        return f"${value:,.2f}"
    if kind == "nav":
        return f"{value:.4f}"
    return f"{value:.3f}"


def comparison_table(summary: pd.DataFrame, language: str = "en") -> pd.DataFrame:
    result = summary.copy(deep=True)
    result[["Strategy", "SPY"]] = result[["Strategy", "SPY"]].astype(object)
    for i, row in result.iterrows():
        kind = "number" if row.Metric == "Sharpe Ratio" else "percent"
        for column in ("Strategy", "SPY"):
            result.at[i, column] = number(row[column], kind)
    result["Metric"] = result["Metric"].map(lambda key: t("CAGR" if key == "Annualized Return" else key, language))
    return result.rename(columns={c: t(c, language) for c in result.columns})


def portfolio_table(table: pd.DataFrame, language: str = "en") -> pd.DataFrame:
    columns = {"rank": "Rank", "ticker": "Ticker", "composite_score": "CompositeScore",
               "target_weight": "Target weight", **{k: f"{v} Score" for k, v in SCORE_LABELS.items()}}
    result = table[list(columns)].copy().rename(columns=columns)
    for col in ("CompositeScore", *(f"{v} Score" for v in SCORE_LABELS.values())):
        result[col] = result[col].map(number)
    result["Target weight"] = result["Target weight"].map(lambda x: number(x, "percent"))
    return result.rename(columns={c: t(c, language) for c in result.columns})


def sensitivity_view(table: pd.DataFrame, group: str, language: str = "en") -> pd.DataFrame:
    result = table.copy(deep=True)
    def label(value: str) -> str:
        if group == "transaction_cost_bps":
            return t("{value} bps", language, value=value)
        if group in ("volatility_window", "reversal_window"):
            return t("{value} sessions", language, value=value)
        if group == "factor_weights":
            return t("Equal weight" if value == "equal" else value.replace("_", " ").title(), language)
        return t(str(value).title(), language) if group == "rebalance_frequency" else str(value)
    result["Setting"] = result.parameter_value.map(label)
    result["Baseline"] = result.is_baseline.map({True: t("Baseline", language), False: t("Sensitivity", language)})
    return result


def sensitivity_table(table: pd.DataFrame, language: str = "en") -> pd.DataFrame:
    result = table[["Setting", "Baseline", *METRIC_COLUMNS]].copy()
    for col in METRIC_COLUMNS:
        kind = "currency" if col == "Final Portfolio Value" else "nav" if col == "Final NAV" else "number" if col == "Sharpe Ratio" else "percent"
        result[col] = result[col].map(lambda x: number(x, kind))
    return result.rename(columns={c: t("CAGR" if c == "Annualized Return" else c, language) for c in result.columns})
