"""Explicit offline official baseline rerun and engine-derived trade export.

python -B -m mft109.backtesting.export
Never downloads, fills gaps, rewrites market data or overwrites baseline results.
"""

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from mft109.analysis.performance import analyze_performance
from mft109.backtesting.engine import run_backtest
from mft109.backtesting.trades import reconcile_trade_log
from mft109.config import BASELINE, PROJECT_ROOT
from mft109.data.cache import request_identity, write_json
from mft109.data.universe import load_universe, universe_fingerprint
from mft109.data.validation import validate_market_data
from mft109.factors import calculate_raw_factors
from mft109.processing import score_factors
from mft109.ranking import rank_and_select
from mft109.visualization.dashboard_data import load_dashboard_bundle


APPROVED_FISV_SHA256 = '6a4c15da950254d215d8b7db0835e376fb659d67e2d869e299797d8d4f01dcf1'


def export_official_trade_log(root: Path = PROJECT_ROOT) -> Path:
    """Publish only after full daily/metric/selection reproduction and trade reconciliation."""
    root = Path(root).resolve()
    bundle = load_dashboard_bundle(root)
    universe_path = root / 'data/raw/sp500_constituents.csv'
    universe = load_universe(universe_path)
    fingerprint = universe_fingerprint(universe)
    source_hashes = {}

    def digest(path):
        value = sha256(path.read_bytes()).hexdigest()
        source_hashes[str(path.relative_to(root))] = value
        return value

    digest(universe_path)
    digest(universe_path.with_suffix('.metadata.json'))

    def read(ticker, *, benchmark=False):
        path = root / 'data/cache/market' / ('benchmark' if benchmark else 'stocks') / f'{ticker}.parquet'
        try:
            metadata = json.loads(path.with_suffix('.json').read_text())
            if metadata['request'] != request_identity(ticker, fingerprint, benchmark=benchmark):
                raise ValueError(f'Cache identity changed: {ticker}')
            checksum = digest(path)
            digest(path.with_suffix('.json'))
            if checksum != metadata['parquet_sha256']:
                raise ValueError(f'Cache checksum mismatch: {ticker}')
            if ticker == 'FISV' and checksum != APPROVED_FISV_SHA256:
                raise ValueError('Unapproved FISV data vintage')
            frame = pd.read_parquet(path)
            validate_market_data(frame, ticker, BASELINE.download_start, BASELINE.download_end,
                                 benchmark=benchmark)
            return frame
        except OSError as error:
            raise ValueError(f'Approved cache missing: {ticker}; restore approved cache, no download attempted') from error

    spy = read('SPY', benchmark=True)
    frames, missing = [], set()
    for ticker in universe.yahoo_ticker:
        if (root / 'data/cache/market/stocks' / f'{ticker}.parquet').is_file():
            frames.append(read(ticker))
        else:
            missing.add(ticker)
    if len(universe) != 503 or len(frames) != 500 or missing != {'FDXF', 'HONA', 'VYLR'}:
        raise ValueError(f'Approved fixed-universe cache coverage changed: {missing}')
    market = pd.concat(frames, ignore_index=True)
    sessions = pd.DatetimeIndex(spy.date)
    raw = calculate_raw_factors(market, sessions=sessions, tickers=universe.yahoo_ticker.tolist())
    selection = rank_and_select(score_factors(raw), sessions=sessions)
    result = run_backtest(selection, market, spy.set_index('date').adjusted_close, sessions=sessions)
    performance = analyze_performance(result.daily, sessions=sessions)
    # Require exact numeric identity across every daily observation, not only final NAV.
    for column in bundle.daily.columns:
        if column == 'date':
            if not pd.DatetimeIndex(performance.daily_performance[column]).equals(pd.DatetimeIndex(bundle.daily[column])):
                raise ValueError('STOP: official date grid changed')
        elif not performance.daily_performance[column].equals(bundle.daily[column]):
            raise ValueError(f'STOP: official daily result changed: {column}')
    assert_frame_equal(performance.performance_summary, bundle.summary, check_exact=True)
    columns = ['formation_date', 'ticker', 'rank', 'selected', 'eligible', 'composite_score',
               'momentum_score', 'low_volatility_score', 'liquidity_score', 'reversal_score']
    selected = selection.selected[columns].reset_index(drop=True)
    expected = bundle.selected[selected.columns].reset_index(drop=True)
    assert_frame_equal(selected, expected, check_exact=True, check_dtype=False)
    reconcile_trade_log(result)
    for relative, expected_hash in source_hashes.items():
        if sha256((root / relative).read_bytes()).hexdigest() != expected_hash:
            raise ValueError('Inputs changed during export; nothing published')
    directory = root / 'dashboard/data'
    data = result.trade_log.to_csv(index=False, date_format='%Y-%m-%d').encode('utf-8')
    baseline = json.loads((directory / 'manifest.json').read_text())
    manifest = {
        'schema_version': 1, 'source_data_version': bundle.version,
        'baseline_endpoints': baseline['endpoints'], 'trade_count': len(result.trade_log),
        'execution_count': int(result.rebalance_audit.status.eq('executed').sum()),
        'file': {'sha256': sha256(data).hexdigest(), 'bytes': len(data)},
        'deployment_sha256': {name: sha256((directory / name).read_bytes()).hexdigest()
                              for name in ('baseline_daily.parquet', 'baseline_selected.parquet')},
        'source_sha256': source_hashes,
        'engine_sha256': sha256((root / 'mft109/backtesting/engine.py').read_bytes()).hexdigest(),
        'trade_schema_sha256': sha256((root / 'mft109/trade_log.py').read_bytes()).hexdigest(),
        'trade_observer_sha256': sha256((root / 'mft109/backtesting/trades.py').read_bytes()).hexdigest(),
        'price_convention': 'Academic adjusted-close execution, fractional adjusted-price units; not broker fills.',
        'cost_attribution': 'Already-charged rebalance fee allocated by gross stock notional; residual on largest trade. Never charged again.',
        'portfolio_value_usd': 'Execution-day closing value after the existing rebalance fee.',
        'unit_noise_tolerance': '32 * machine epsilon * max(1, abs(pre units), abs(post units)); no holding changes.',
        'validation': 'Exact daily numeric, performance and selected-stock reproduction; unit/cash/cost reconciliation passed.',
    }
    path = directory / 'trade_log.csv'
    temporary = path.with_suffix('.csv.tmp')
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(directory / 'trade_log_manifest.json', manifest)
    # Extend final-package provenance/checksums without touching any financial table or figure.
    from mft109.analysis.final_exports import add_trade_log_to_package
    add_trade_log_to_package(root)
    return root / 'outputs/final_report/v1/trade_log.csv'


if __name__ == '__main__':
    print(export_official_trade_log())
