"""Equal-weight targets from Phase 4 selected names and current execution prices."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from mft109.config import BASELINE
from mft109.optimization.scenarios import Scenario, check_scenario


CASH_ASSET = "__CASH__"


@dataclass(frozen=True)
class TargetPortfolio:
    """Complete target weights, including cash, and excluded selected symbols."""

    weights: pd.Series
    excluded_tickers: tuple[str, ...]


def equal_weight_target(
    selected_tickers: Sequence[str], execution_prices: pd.Series, *, scenario: Scenario | None = None
) -> TargetPortfolio:
    """Equal-weight only selected stocks with finite positive prices at execution.

    No unselected stock is a replacement. Zero executable stocks targets cash.
    Missing current holdings must be handled by valuation before calling this.
    """
    check_scenario(scenario)
    top_n = scenario.top_n if scenario else BASELINE.top_n
    if isinstance(selected_tickers, str):
        raise TypeError("selected_tickers must be a sequence, not one string")
    tickers = list(selected_tickers)
    if (len(set(tickers)) != len(tickers) or len(tickers) > top_n
            or any(not isinstance(t, str) or not t.strip() or t != t.strip()
                   or t in (CASH_ASSET, BASELINE.benchmark) for t in tickers)):
        raise ValueError(f"Expected unique selected stock identifiers, at most {top_n}")
    if not isinstance(execution_prices, pd.Series) or not execution_prices.index.is_unique:
        raise ValueError("Execution prices must be a Series with unique stock identifiers")
    executable, excluded = [], []
    for ticker in sorted(tickers):
        price = execution_prices.get(ticker, np.nan)
        if pd.notna(price) and np.isfinite(price) and price > 0:
            executable.append(ticker)
        else:
            excluded.append(ticker)
    weights = {ticker: 1.0 / len(executable) for ticker in executable}
    weights[CASH_ASSET] = 0.0 if executable else 1.0
    return TargetPortfolio(pd.Series(weights, dtype="float64", name="target_weight"),
                           tuple(excluded))
