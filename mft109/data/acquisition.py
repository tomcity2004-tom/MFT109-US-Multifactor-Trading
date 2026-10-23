"""Explicit yfinance adapter for adjusted daily OHLC and reported Volume."""

from datetime import timedelta
import logging

import pandas as pd
import yfinance as yf

from mft109.config import BASELINE, DATA_SETTINGS
from mft109.data.validation import COLUMNS, DataValidationError
from mft109.data.universe import yahoo_ticker

LOG = logging.getLogger(__name__)


def normalize_download(raw, ticker):
    """Normalize a single-symbol auto_adjust=True response, including MultiIndex.

    All OHLC prices are adjusted by yfinance; `adjusted_close` explicitly aliases
    adjusted `Close`. We never infer adjustment from an optional Adj Close column.
    """
    if raw is None or raw.empty:
        raise DataValidationError(f"Yahoo Finance returned no data for {ticker}")
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        ticker_levels = [i for i in range(frame.columns.nlevels)
                         if ticker in frame.columns.get_level_values(i)]
        if len(ticker_levels) != 1:
            raise DataValidationError(f"Cannot identify {ticker} in Yahoo column layout")
        frame = frame.xs(ticker, axis=1, level=ticker_levels[0])
    fields = ["Open", "High", "Low", "Close", "Volume"]
    if not set(fields).issubset(frame.columns) or frame.columns.duplicated().any():
        raise DataValidationError(f"Unexpected Yahoo OHLCV columns for {ticker}")
    frame = frame[fields].rename(columns=str.lower)
    dates = pd.to_datetime(frame.index, errors="coerce")
    # Daily index denotes exchange-local session dates: remove TZ without UTC shifting.
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    frame.insert(0, "date", dates)
    frame.insert(1, "ticker", ticker)
    frame["adjusted_close"] = frame["close"]
    return frame[COLUMNS].reset_index(drop=True)


def download_daily(ticker, baseline=BASELINE, settings=DATA_SETTINGS):
    ticker = yahoo_ticker(ticker)
    LOG.info("Downloading %s: %s through %s", ticker, baseline.download_start, baseline.download_end)
    # Keep yfinance's small runtime timezone/cookie cache in the ignored project cache.
    runtime_cache = settings.market_cache / "yfinance_runtime"
    runtime_cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(runtime_cache))
    try:
        raw = yf.download(
            ticker, start=baseline.download_start.isoformat(),
            end=(baseline.download_end + timedelta(days=1)).isoformat(),
            interval="1d", auto_adjust=True, back_adjust=False, repair=False,
            actions=False, keepna=True, rounding=False, prepost=False,
            threads=False, progress=False, timeout=settings.request_timeout_seconds,
            group_by="column", multi_level_index=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Yahoo Finance download failed for {ticker}: {exc}") from exc
    return normalize_download(raw, ticker)
