"""Repository-only, read-only trade artifact validation and display filtering."""

from hashlib import sha256
import io
import json
from pathlib import Path

import pandas as pd

from mft109.config import PROJECT_ROOT
from mft109.visualization.dashboard_data import DashboardDataError


from mft109.trade_log import TRADE_COLUMNS, validate_trade_log


def trade_signature(root: Path = PROJECT_ROOT) -> tuple:
    try:
        return tuple((name, (root / 'dashboard/data' / name).stat().st_mtime_ns,
                      (root / 'dashboard/data' / name).stat().st_size)
                     for name in ('trade_log.csv', 'trade_log_manifest.json', 'manifest.json',
                                  'baseline_daily.parquet', 'baseline_selected.parquet'))
    except OSError as error:
        raise DashboardDataError("Trade history is unavailable; export approved cached data offline.") from error


def load_trade_history(root: Path = PROJECT_ROOT) -> pd.DataFrame:
    """Verify separate trade provenance without refreshing the legacy dashboard bundle."""
    directory = root / 'dashboard/data'
    try:
        manifest = json.loads((directory / 'trade_log_manifest.json').read_text())
        baseline = json.loads((directory / 'manifest.json').read_text())
        data = (directory / 'trade_log.csv').read_bytes()
        if (manifest['schema_version'] != 1 or manifest['source_data_version'] != baseline['source_version']
                or manifest['baseline_endpoints'] != baseline['endpoints']
                or manifest['file']['sha256'] != sha256(data).hexdigest()
                or manifest['file']['bytes'] != len(data)):
            raise ValueError("Trade log checksum, version or baseline mismatch")
        for name in ('baseline_daily.parquet', 'baseline_selected.parquet'):
            digest = sha256((directory / name).read_bytes()).hexdigest()
            if digest != manifest['deployment_sha256'][name] or digest != baseline['files'][name]['sha256']:
                raise ValueError("Trade log refers to a different deployment baseline")
        table = pd.read_csv(io.BytesIO(data), parse_dates=['execution_date', 'formation_date'],
                            dtype={'ticker': str, 'side': str, 'trade_type': str},
                            converters={name: float for name in TRADE_COLUMNS[5:]})
        validate_trade_log(table)
        if len(table) != manifest['trade_count']:
            raise ValueError("Trade count mismatch")
        return table
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DashboardDataError(f"Trade history unavailable or invalid: {error}") from error


def filter_trades(table: pd.DataFrame, *, start=None, end=None, tickers=(), sides=()) -> pd.DataFrame:
    """Inclusive dates and exact identifiers; never transform financial values."""
    mask = pd.Series(True, index=table.index)
    if start is not None:
        mask &= table.execution_date.ge(pd.Timestamp(start))
    if end is not None:
        mask &= table.execution_date.le(pd.Timestamp(end))
    if tickers:
        mask &= table.ticker.isin(tickers)
    if sides:
        mask &= table.side.isin(sides)
    return table.loc[mask].copy()
