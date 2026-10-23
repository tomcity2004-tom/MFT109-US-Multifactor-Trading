"""Obtain a current constituent list once and preserve its fixed local snapshot."""

from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
import logging
from pathlib import Path
import re
from urllib.request import Request, urlopen

import pandas as pd

from mft109.config import BASELINE, DATA_SETTINGS

LOG = logging.getLogger(__name__)
UNIVERSE_COLUMNS = ["ticker", "yahoo_ticker", "company_name", "sector"]


def yahoo_ticker(ticker):
    """Preserve the original separately; Yahoo uses hyphens for share classes."""
    value = str(ticker).strip().upper().replace(".", "-")
    if not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", value):
        raise ValueError(f"Unsupported stock ticker: {ticker!r}")
    return value


def validate_universe(frame):
    """Reject empty, ambiguous, duplicate, or benchmark-contaminated snapshots."""
    if frame.empty or not set(UNIVERSE_COLUMNS).issubset(frame.columns):
        raise ValueError("Universe must be nonempty with " + ", ".join(UNIVERSE_COLUMNS))
    result = frame[UNIVERSE_COLUMNS].copy()
    for column in UNIVERSE_COLUMNS:
        if result[column].isna().any() or result[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Universe contains missing {column}")
        result[column] = result[column].astype(str).str.strip()
    if result.ticker.duplicated().any() or result.yahoo_ticker.duplicated().any():
        raise ValueError("Universe contains duplicate original or Yahoo tickers")
    expected = result.ticker.map(yahoo_ticker)
    if not expected.equals(result.yahoo_ticker):
        raise ValueError("Universe Yahoo tickers do not match original tickers")
    if BASELINE.benchmark in set(result.yahoo_ticker):
        raise ValueError("SPY benchmark must not be a universe constituent")
    return result.sort_values("ticker").reset_index(drop=True)


def load_universe(path):
    """An invalid existing snapshot is an error, never permission to replace it."""
    path = Path(path)
    result = validate_universe(pd.read_csv(path, dtype=str, keep_default_na=False))
    metadata_path = path.with_suffix(".metadata.json")
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("universe_sha256") != universe_fingerprint(result):
            raise ValueError("Fixed universe snapshot differs from its saved provenance hash")
    return result


def universe_fingerprint(frame):
    canonical = validate_universe(frame).to_csv(index=False).encode("utf-8")
    return sha256(canonical).hexdigest()


def get_universe(settings=DATA_SETTINGS):
    """Reuse an existing snapshot; fetch the maintained DataHub CSV only once.

    Source is the datasets/s-and-p-500-companies project (Wikipedia-derived),
    not an official historical index-membership feed. No historical membership
    reconstruction or automatic refresh is performed.
    """
    path = Path(settings.universe_snapshot)
    if path.exists():
        LOG.info("Using fixed universe snapshot %s", path)
        return load_universe(path)
    request = Request(settings.universe_source, headers={"User-Agent": "MFT109 research/1.0"})
    try:
        with urlopen(request, timeout=settings.request_timeout_seconds) as response:
            source = pd.read_csv(StringIO(response.read().decode("utf-8-sig")), dtype=str)
    except Exception as exc:
        raise RuntimeError(f"Cannot retrieve current S&P 500 universe: {exc}") from exc
    # Accommodate the source's legacy and current descriptive column names.
    source = source.rename(columns={"Symbol": "ticker", "Name": "company_name",
                                    "Security": "company_name", "Sector": "sector",
                                    "GICS Sector": "sector"})
    if not {"ticker", "company_name", "sector"}.issubset(source.columns):
        raise ValueError("Constituent source schema changed; inspect it before proceeding")
    source["yahoo_ticker"] = source.ticker.map(yahoo_ticker)
    result = validate_universe(source)
    if not 450 <= len(result) <= 550:
        raise ValueError(f"Implausible S&P 500 source size: {len(result)} securities")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects an existing fixed snapshot, including concurrent runs.
    try:
        with path.open("x", encoding="utf-8", newline="") as handle:
            result.to_csv(handle, index=False)
    except FileExistsError:
        return load_universe(path)
    metadata = {"source": settings.universe_source,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "securities": len(result), "universe_sha256": universe_fingerprint(result),
                "limitation": "Current membership fixed for all history; survivorship bias."}
    with path.with_suffix(".metadata.json").open("x", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    LOG.info("Saved fixed universe: %d securities", len(result))
    return result
