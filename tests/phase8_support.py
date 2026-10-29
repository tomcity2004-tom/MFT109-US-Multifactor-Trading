"""Offline integration fixtures for the approved cache; never refresh or write data."""

from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from mft109.analysis.performance import PerformanceAnalysis, analyze_performance
from mft109.backtesting.engine import BacktestResult, run_backtest
from mft109.config import BASELINE, DATA_SETTINGS, PROJECT_ROOT
from mft109.data.cache import request_identity
from mft109.data.universe import load_universe, universe_fingerprint
from mft109.data.validation import validate_market_data
from mft109.factors import calculate_raw_factors
from mft109.optimization.sensitivity import SensitivityResults, run_sensitivity
from mft109.processing import score_factors
from mft109.ranking import MonthlySelection, rank_and_select


APPROVED_FINAL_NAV = 6.225346615575381
APPROVED_FINAL_USD = 622534.6615575381
APPROVED_SPY_NAV = 4.002530196823173
APPROVED_FISV_HASH = "6a4c15da950254d215d8b7db0835e376fb659d67e2d869e299797d8d4f01dcf1"
UNAVAILABLE = {"FDXF", "HONA", "VYLR"}


@contextmanager
def offline():
    """Fail on attempted provider/network access, including downloader fallback."""
    with ExitStack() as stack:
        mocks = [stack.enter_context(patch(name, side_effect=AssertionError("Phase 8 forbids downloads/network")))
                 for name in ("yfinance.download", "mft109.data.cache.download_daily",
                              "urllib.request.urlopen", "socket.create_connection", "socket.socket.connect")]
        yield mocks
        assert all(mock.call_count == 0 for mock in mocks), "Network access was attempted"


def protected_hashes() -> dict[str, str]:
    """Market/universe/archive/output and production Python bytes, including ignored files."""
    paths = set()
    for root in (PROJECT_ROOT / "data", PROJECT_ROOT / "outputs"):
        paths.update(p for p in root.rglob("*") if p.is_file())
    paths.update((PROJECT_ROOT / "mft109").rglob("*.py"))
    paths.update(PROJECT_ROOT / p for p in ("AGENTS.md", "PROJECT_REQUIREMENTS.md", "requirements.txt"))
    return {str(p.relative_to(PROJECT_ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def frame_fingerprint(frame: pd.DataFrame | pd.Series) -> str:
    """Detect row/index/value/schema mutation without serializing result files."""
    schema = str(frame.dtypes) + str(getattr(frame, "columns", frame.name if isinstance(frame, pd.Series) else ""))
    return sha256(schema.encode() + pd.util.hash_pandas_object(frame, index=True).values.tobytes()).hexdigest()


@dataclass(frozen=True)
class CacheFixture:
    universe: pd.DataFrame
    market: pd.DataFrame
    spy: pd.DataFrame
    sessions: pd.DatetimeIndex
    hashes: dict[str, str]


@lru_cache(maxsize=1)
def approved_cache() -> CacheFixture:
    """Read/check manifests directly; absence may skip, corruption never does."""
    benchmark = DATA_SETTINGS.market_cache / "benchmark" / "SPY.parquet"
    if not benchmark.exists():
        message = "Approved local cache unavailable; no download attempted; official validation NOT completed"
        if os.environ.get("MFT109_REQUIRE_APPROVED_CACHE") == "1":
            raise AssertionError(message)
        raise unittest.SkipTest(message)
    hashes = protected_hashes()
    with offline():
        universe = load_universe(DATA_SETTINGS.universe_snapshot)
        fingerprint = universe_fingerprint(universe)

        def read(ticker: str, *, benchmark: bool = False) -> pd.DataFrame:
            path = DATA_SETTINGS.market_cache / ("benchmark" if benchmark else "stocks") / f"{ticker}.parquet"
            metadata = json.loads(path.with_suffix(".json").read_text())
            assert metadata["request"] == request_identity(ticker, fingerprint, benchmark=benchmark), ticker
            assert sha256(path.read_bytes()).hexdigest() == metadata["parquet_sha256"], ticker
            if ticker == "FISV":
                assert metadata["parquet_sha256"] == APPROVED_FISV_HASH, "Unapproved FISV data version"
            frame = pd.read_parquet(path)
            validate_market_data(frame, ticker, BASELINE.download_start, BASELINE.download_end,
                                 benchmark=benchmark)
            return frame

        spy = read("SPY", benchmark=True)
        frames, missing = [], set()
        for ticker in universe.yahoo_ticker:
            path = DATA_SETTINGS.market_cache / "stocks" / f"{ticker}.parquet"
            if path.exists():
                frame = read(ticker)
                validate_market_data(frame, ticker, BASELINE.download_start, BASELINE.download_end,
                                     reference_dates=spy.date)
                frames.append(frame)
            else:
                missing.add(ticker)
        assert missing == UNAVAILABLE, f"Unexpected unavailable caches: {missing}"
        assert len(universe) == 503 and len(frames) == 500
        market = pd.concat(frames, ignore_index=True)
    return CacheFixture(universe, market, spy, pd.DatetimeIndex(spy.date), hashes)


@dataclass(frozen=True)
class PipelineRun:
    raw: pd.DataFrame
    scored: pd.DataFrame
    selection: MonthlySelection
    backtest: BacktestResult
    performance: PerformanceAnalysis


def pipeline(market: pd.DataFrame, sessions: pd.DatetimeIndex,
             tickers: list[str], spy: pd.Series) -> PipelineRun:
    """Exercise public APIs and check every major input boundary for mutation."""
    configuration = asdict(BASELINE)
    market_hash, spy_hash = frame_fingerprint(market), frame_fingerprint(spy)
    with offline():
        raw = calculate_raw_factors(market, sessions=sessions, tickers=tickers)
        assert frame_fingerprint(market) == market_hash
        raw_hash = frame_fingerprint(raw)
        scored = score_factors(raw)
        assert frame_fingerprint(raw) == raw_hash
        scored_hash = frame_fingerprint(scored)
        selection = rank_and_select(scored, sessions=sessions)
        assert frame_fingerprint(scored) == scored_hash
        rank_hash, summary_hash = frame_fingerprint(selection.ranked), frame_fingerprint(selection.formation_summary)
        backtest = run_backtest(selection, market, spy, sessions=sessions)
        assert frame_fingerprint(selection.ranked) == rank_hash
        assert frame_fingerprint(selection.formation_summary) == summary_hash
        daily_hash = frame_fingerprint(backtest.daily)
        performance = analyze_performance(backtest.daily, sessions=sessions)
        assert frame_fingerprint(backtest.daily) == daily_hash
    assert frame_fingerprint(market) == market_hash and frame_fingerprint(spy) == spy_hash
    assert asdict(BASELINE) == configuration
    return PipelineRun(raw, scored, selection, backtest, performance)


@lru_cache(maxsize=2)
def baseline_run(repeat: bool = False) -> PipelineRun:
    """repeat=True performs another full calculation with identical input values."""
    fixture = approved_cache()
    result = pipeline(fixture.market, fixture.sessions, fixture.universe.yahoo_ticker.tolist(),
                      fixture.spy.set_index("date").adjusted_close)
    final = result.backtest.daily.iloc[-1]
    import math
    assert math.isclose(final.strategy_nav, APPROVED_FINAL_NAV, rel_tol=1e-12, abs_tol=1e-12), "STOP: baseline NAV discrepancy"
    assert math.isclose(final.portfolio_value_usd, APPROVED_FINAL_USD, rel_tol=1e-12, abs_tol=1e-7), "STOP: baseline USD discrepancy"
    assert math.isclose(final.spy_nav, APPROVED_SPY_NAV, rel_tol=1e-12, abs_tol=1e-12), "STOP: SPY discrepancy"
    return result


@lru_cache(maxsize=1)
def sensitivity_run() -> SensitivityResults:
    fixture = approved_cache()
    before = frame_fingerprint(fixture.market), frame_fingerprint(fixture.universe), asdict(BASELINE)
    with offline():
        result = run_sensitivity(fixture.market, fixture.spy.set_index("date").adjusted_close,
                                 sessions=fixture.sessions, tickers=fixture.universe.yahoo_ticker.tolist())
    assert before == (frame_fingerprint(fixture.market), frame_fingerprint(fixture.universe), asdict(BASELINE))
    return result
