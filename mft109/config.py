"""Approved baseline settings from PROJECT_REQUIREMENTS.md; no strategy logic.

Dates are inclusive research boundaries, not provider API end-date arguments.
Configuration import performs no downloads, creates no files, and starts no services.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
BASELINE_OUTPUT_DIR = OUTPUT_DIR / "baseline"
OPTIMIZATION_OUTPUT_DIR = OUTPUT_DIR / "optimization"


@dataclass(frozen=True)
class BaselineSettings:
    """Immutable baseline defaults; changes to methodology require approval."""

    universe: str = "current S&P 500 constituents, fixed throughout backtest"
    data_source: str = "Yahoo Finance / yfinance"
    data_frequency: str = "daily"
    download_start: date = date(2015, 1, 1)
    download_end: date = date(2025, 12, 31)
    backtest_start: date = date(2016, 1, 1)
    backtest_end: date = date(2025, 12, 31)
    benchmark: str = "SPY"
    price_basis: str = "adjusted"
    volume_basis: str = "Yahoo Finance reported Volume"
    momentum_lookback_days: int = 252
    momentum_skip_days: int = 21
    volatility_lookback_days: int = 60
    liquidity_lookback_days: int = 20
    reversal_lookback_days: int = 20
    trading_days_per_year: int = 252
    momentum_weight: float = 0.25
    low_volatility_weight: float = 0.25
    liquidity_weight: float = 0.25
    reversal_weight: float = 0.25
    standardization: str = "cross-sectional Z-score"
    require_all_four_factors: bool = True
    top_n: int = 20
    portfolio_weighting: str = "equal weight"
    rebalance_frequency: str = "monthly"
    signal_timing: str = "month-end information"
    execution_timing: str = "next eligible trading day"
    transaction_cost_rate: float = 0.001
    risk_free_rate: float = 0.0
    initial_capital_usd: float = 100_000.0
    initial_nav: float = 1.0
    sharpe_definition: str = "Annualized Return / Annualized Volatility"


BASELINE = BaselineSettings()


@dataclass(frozen=True)
class DataSettings:
    """Operational data-pipeline settings; research defaults remain in BASELINE."""

    universe_source: str = (
        "https://raw.githubusercontent.com/datasets/"
        "s-and-p-500-companies/main/data/constituents.csv"
    )
    universe_snapshot: Path = RAW_DATA_DIR / "sp500_constituents.csv"
    market_cache: Path = CACHE_DIR / "market"
    validation_report: Path = PROCESSED_DATA_DIR / "data_quality.json"
    request_timeout_seconds: int = 30
    coverage_tolerance_days: int = 7
    schema_version: int = 1


DATA_SETTINGS = DataSettings()
