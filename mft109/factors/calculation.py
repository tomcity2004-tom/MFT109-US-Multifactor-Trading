"""Calculate raw factors from Phase 1 observations on an explicit session grid."""

from collections.abc import Sequence

import pandas as pd

from mft109.config import BASELINE
from mft109.factors._inputs import session_index
from mft109.factors.liquidity import calculate_liquidity
from mft109.factors.low_volatility import calculate_volatility
from mft109.factors.momentum import calculate_momentum
from mft109.factors.reversal import calculate_reversal


RAW_FACTOR_COLUMNS = ["momentum", "volatility60", "liquidity_raw", "reversal20"]


def calculate_raw_factors(
    market_data: pd.DataFrame,
    *,
    sessions: pd.DatetimeIndex,
    tickers: Sequence[str],
) -> pd.DataFrame:
    """Return date/ticker plus four raw factors for every requested session/stock.

    Pass the saved universe's Yahoo symbols (or an explicit validation subset)
    and actual sessions from validated Phase 1 SPY data. Missing stock rows become
    NaN inputs on that clock, not filled observations. Entirely unavailable
    securities remain present with NaN factors. No network, file writes, stock
    selection, or cross-sectional processing is performed.
    """
    calendar = session_index(sessions)
    if isinstance(tickers, str):
        raise TypeError("tickers must be a sequence of fixed-universe Yahoo symbols")
    symbols = list(tickers)
    if not symbols or any(not isinstance(t, str) or not t.strip() or t != t.strip()
                          for t in symbols):
        raise ValueError("tickers must contain nonempty stock identifiers")
    if len(set(symbols)) != len(symbols):
        raise ValueError("tickers must be unique")
    if BASELINE.benchmark in symbols:
        raise ValueError("SPY benchmark must remain separate from stock factors")
    required = ["date", "ticker", "adjusted_close", "volume"]
    if not market_data.columns.is_unique or not set(required).issubset(market_data.columns):
        raise ValueError("market_data requires unique date/ticker/adjusted_close/volume columns")
    data = market_data[required].copy()
    if data.ticker.isna().any() or not data.ticker.isin(symbols).all():
        raise ValueError("market_data contains unidentified or unrequested tickers")
    if not data.empty:
        dates = pd.DatetimeIndex(data.date)
        if dates.hasnans or dates.tz is not None or not dates.equals(dates.normalize()):
            raise ValueError("market_data must use valid timezone-naive daily session dates")
        if not dates.isin(calendar).all():
            raise ValueError("market_data has dates outside the supplied trading sessions")
        data["date"] = dates
        if data.duplicated(["date", "ticker"]).any():
            raise ValueError("Duplicate date/ticker observations in factor inputs")
    frames = []
    for ticker in symbols:
        stock = data.loc[data.ticker.eq(ticker)].set_index("date")
        # An absent security needs only empty numeric inputs, never dummy prices.
        if stock.empty:
            price = pd.Series(index=pd.DatetimeIndex([]), dtype="float64")
            volume = price.copy()
        else:
            price, volume = stock.adjusted_close, stock.volume
        factors = pd.concat([
            calculate_momentum(price, sessions=calendar),
            calculate_volatility(price, sessions=calendar),
            calculate_liquidity(price, volume, sessions=calendar),
            calculate_reversal(price, sessions=calendar),
        ], axis=1)
        factors.insert(0, "ticker", ticker)
        frames.append(factors.reset_index())
    return (pd.concat(frames, ignore_index=True)
            .sort_values(["date", "ticker"]).reset_index(drop=True))
