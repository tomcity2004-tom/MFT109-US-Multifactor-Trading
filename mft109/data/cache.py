"""Validated per-symbol Parquet cache with request identity and content hashes."""

from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import tempfile

import pandas as pd
import yfinance as yf

from mft109.config import BASELINE, DATA_SETTINGS
from mft109.data.acquisition import download_daily
from mft109.data.cleaning import clean_market_data
from mft109.data.universe import yahoo_ticker
from mft109.data.validation import validate_market_data

LOG = logging.getLogger(__name__)


def write_json(path, value):
    """Publish a complete JSON file atomically, leaving existing data on failures."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp",
                                     delete=False, encoding="utf-8") as handle:
        temporary = Path(handle.name)
        try:
            json.dump(value, handle, indent=2, allow_nan=False)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def request_identity(ticker, universe_hash, baseline=BASELINE, settings=DATA_SETTINGS,
                     benchmark=False):
    return {"schema_version": settings.schema_version, "ticker": ticker,
            "start": baseline.download_start.isoformat(),
            "end_inclusive": baseline.download_end.isoformat(),
            "interval": "1d", "auto_adjust": True, "repair": False,
            "volume": "Yahoo Finance reported", "yfinance_version": yf.__version__,
            "universe_sha256": None if benchmark else universe_hash,
            "role": "benchmark" if benchmark else "stock"}


def load_or_download(ticker, universe_hash, *, baseline=BASELINE, settings=DATA_SETTINGS,
                     benchmark=False, refresh=False):
    """Use only a matching, checksum-verified, validated cache; else download.

    Successful symbols are retained individually for resumable full-universe runs.
    A failed refresh does not delete a previously valid cache. The benchmark has
    its own directory and is never appended to the stock candidate universe.
    """
    ticker = yahoo_ticker(ticker)
    directory = settings.market_cache / ("benchmark" if benchmark else "stocks")
    parquet = directory / f"{ticker}.parquet"
    manifest = directory / f"{ticker}.json"
    identity = request_identity(ticker, universe_hash, baseline, settings, benchmark)
    if not refresh and (parquet.exists() or manifest.exists()):
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            if metadata["request"] != identity:
                raise ValueError("request or universe fingerprint changed")
            if sha256(parquet.read_bytes()).hexdigest() != metadata["parquet_sha256"]:
                raise ValueError("Parquet checksum mismatch")
            frame = pd.read_parquet(parquet)
            quality = validate_market_data(
                frame, ticker, baseline.download_start, baseline.download_end,
                tolerance_days=settings.coverage_tolerance_days, benchmark=benchmark)
            LOG.info("Cache hit: %s", ticker)
            return frame, {**quality, "cleaning": metadata["cleaning"], "cache_hit": True}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            LOG.warning("Cache invalid for %s (%s); attempting a fresh download", ticker, exc)
    raw = download_daily(ticker, baseline, settings)
    frame, cleaning = clean_market_data(raw)
    quality = validate_market_data(
        frame, ticker, baseline.download_start, baseline.download_end,
        tolerance_days=settings.coverage_tolerance_days, benchmark=benchmark)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, suffix=".parquet", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        frame.to_parquet(temporary, index=False, compression="zstd")
        digest = sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(parquet)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(manifest, {"request": identity, "parquet_sha256": digest,
                         "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                         "cleaning": cleaning, "validation": quality})
    return frame, {**quality, "cleaning": cleaning, "cache_hit": False}
