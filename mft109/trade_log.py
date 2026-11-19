"""Shared trade-record schema and integrity checks, independent of engine and UI."""

import numpy as np
import pandas as pd

TRADE_COLUMNS = [
    "execution_date", "formation_date", "ticker", "side", "trade_type",
    "adjusted_execution_price", "quantity", "gross_trade_value_usd",
    "pre_trade_units", "post_trade_units", "transaction_cost_usd", "portfolio_value_usd",
]


def validate_trade_log(table: pd.DataFrame) -> None:
    """Reject malformed/corrupt observations; header-only no-trade output is valid."""
    if table.columns.tolist() != TRADE_COLUMNS:
        raise ValueError("Invalid trade log columns")
    if table.empty:
        return
    dates = pd.DatetimeIndex(table.execution_date)
    formations = pd.DatetimeIndex(table.formation_date)
    if (dates.hasnans or formations.hasnans or dates.tz is not None or formations.tz is not None
            or not dates.equals(dates.normalize()) or not formations.equals(formations.normalize())
            or not dates.is_monotonic_increasing or (formations >= dates).any()
            or table.duplicated(["execution_date", "ticker"]).any()):
        raise ValueError("Invalid trade log dates or duplicate execution/ticker")
    if table.ticker.map(lambda x: not isinstance(x, str) or not x.strip() or x != x.strip()
                        or x in ("__CASH__", "SPY")).any():
        raise ValueError("Invalid trade log ticker")
    numeric = table[TRADE_COLUMNS[5:]]
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite trade log values")
    positive = ["adjusted_execution_price", "quantity", "gross_trade_value_usd", "portfolio_value_usd"]
    if (numeric[positive].le(0).any().any()
            or numeric[["pre_trade_units", "post_trade_units", "transaction_cost_usd"]].lt(0).any().any()):
        raise ValueError("Invalid trade log price, units, notional or cost")
    delta = table.post_trade_units - table.pre_trade_units
    expected_side = np.where(delta > 0, "BUY", "SELL")
    expected_type = np.where(delta > 0, np.where(table.pre_trade_units.eq(0), "NEW_ENTRY", "INCREASE"),
                             np.where(table.post_trade_units.eq(0), "FULL_EXIT", "DECREASE"))
    if (not table.side.eq(expected_side).all() or not table.trade_type.eq(expected_type).all()
            or not np.allclose(table.quantity, abs(delta), rtol=1e-12, atol=1e-12)
            or not np.allclose(table.gross_trade_value_usd,
                               table.quantity * table.adjusted_execution_price, rtol=1e-12, atol=1e-8)):
        raise ValueError("Trade direction, type, unit change or notional mismatch")
