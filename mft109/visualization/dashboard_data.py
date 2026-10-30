"""Read-only, repository-relative presentation artifacts; no cache or pipeline access."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd
from mft109.config import PROJECT_ROOT


SCORE_LABELS = {"momentum_score": "Momentum", "low_volatility_score": "Low Volatility",
                "liquidity_score": "Liquidity", "reversal_score": "Reversal"}
GROUP_LABELS = {"top_n": "Top N", "transaction_cost_bps": "Transaction cost",
                "rebalance_frequency": "Rebalance frequency", "volatility_window": "Volatility window",
                "reversal_window": "Reversal window", "factor_weights": "Factor weights"}
METRIC_COLUMNS = ["Cumulative Return", "Annualized Return", "Annualized Volatility",
                  "Sharpe Ratio", "Maximum Drawdown", "Final NAV", "Final Portfolio Value"]


class DashboardDataError(ValueError):
    """Missing or inconsistent reviewed artifacts; never fall back to made-up data."""


@dataclass(frozen=True)
class DashboardBundle:
    daily: pd.DataFrame
    summary: pd.DataFrame
    annual: pd.DataFrame
    selected: pd.DataFrame
    sensitivity: dict[str, pd.DataFrame]
    sessions: pd.DatetimeIndex
    version: str


@dataclass(frozen=True)
class PortfolioView:
    table: pd.DataFrame
    formation_date: pd.Timestamp
    execution_date: pd.Timestamp
    cash_weight: float | None


ARTIFACT_NAMES = ("baseline_daily.parquet", "baseline_performance.csv", "baseline_annual_returns.csv",
                  "baseline_selected.parquet", *[f"phase7_{group}.csv" for group in GROUP_LABELS])


def output_directory(root: Path = PROJECT_ROOT) -> Path:
    return root / "dashboard/data"


def bundle_signature(root: Path = PROJECT_ROOT) -> tuple:
    directory = output_directory(root)
    try:
        return tuple((name, (directory / name).stat().st_mtime_ns, (directory / name).stat().st_size)
                     for name in ("manifest.json", *ARTIFACT_NAMES))
    except OSError as error:
        raise DashboardDataError(f"Required deployment artifact is missing: {error.filename}") from error


def _require(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    if frame.empty or not set(columns).issubset(frame.columns):
        raise DashboardDataError(f"Missing/empty deployment fields: {label}.")


def load_dashboard_bundle(root: Path = PROJECT_ROOT) -> DashboardBundle:
    """Read exported results only. Checks detect corruption; never recalculate strategy results."""
    directory = output_directory(root)
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["schema_version"] != 1 or set(manifest["files"]) != set(ARTIFACT_NAMES):
            raise DashboardDataError("Invalid deployment manifest schema/files.")
        for name in ARTIFACT_NAMES:
            data = (directory / name).read_bytes()
            entry = manifest["files"][name]
            if sha256(data).hexdigest() != entry["sha256"] or len(data) != entry["bytes"]:
                raise DashboardDataError(f"Deployment checksum mismatch: {name}.")
        daily = pd.read_parquet(directory / "baseline_daily.parquet")
        _require(daily, ["date", "strategy_return", "strategy_nav", "portfolio_value_usd", "spy_return",
                         "spy_nav", "strategy_drawdown", "spy_drawdown"], "daily")
        sessions = pd.DatetimeIndex(daily.date)
        if (sessions.has_duplicates or sessions.hasnans or not sessions.is_monotonic_increasing
                or not np.isfinite(daily.drop(columns="date")).all().all()):
            raise DashboardDataError("Invalid deployment daily observations.")
        for key, expected in manifest["endpoints"].items():
            if daily.iloc[-1][key] != expected:
                raise DashboardDataError("Deployment endpoints do not match manifest.")
        summary = pd.read_csv(directory / "baseline_performance.csv")
        annual = pd.read_csv(directory / "baseline_annual_returns.csv", parse_dates=["Anchor Date", "End Date"])
        annual[["Anchor Date", "End Date"]] = annual[["Anchor Date", "End Date"]].astype("datetime64[ms]")
        _require(summary, ["Metric", "Strategy", "SPY"], "metrics")
        _require(annual, ["Year", "Strategy", "SPY"], "annual returns")
        if (summary.Metric.tolist() != METRIC_COLUMNS[:5] or annual.Year.tolist() != list(range(2016, 2026))
                or not np.isfinite(summary[["Strategy", "SPY"]]).all().all()
                or not np.isfinite(annual[["Strategy", "SPY"]]).all().all()):
            raise DashboardDataError("Invalid deployment performance tables.")
        selected = pd.read_parquet(directory / "baseline_selected.parquet")
        _require(selected, ["formation_date", "ticker", "rank", "composite_score", *SCORE_LABELS,
                            "execution_date", "target_weight", "cash_weight", "eligible", "selected"], "portfolio")
        if (selected.duplicated(["formation_date", "ticker"]).any()
                or not selected.eligible.eq(True).all() or not selected.selected.eq(True).all()
                or not np.isfinite(selected[["composite_score", *SCORE_LABELS]]).all().all()):
            raise DashboardDataError("Invalid deployment portfolio scores.")
        for date, rows in selected.groupby("formation_date", sort=False):
            if (rows["rank"].tolist() != list(range(1, 21))
                    or not rows.execution_date.nunique(dropna=False) == 1):
                raise DashboardDataError("Invalid deployment portfolio snapshot.")
            execution = rows.execution_date.iloc[0]
            if pd.isna(execution):
                if not rows[["target_weight", "cash_weight"]].isna().all().all():
                    raise DashboardDataError("Unexecuted snapshot must retain undefined weights.")
            elif (execution <= date or execution not in sessions
                  or not np.isfinite(rows[["target_weight", "cash_weight"]]).all().all()):
                raise DashboardDataError("Invalid exported execution timing/weights.")
        sensitivity = {}
        for group in GROUP_LABELS:
            table = pd.read_csv(directory / f"phase7_{group}.csv", dtype={"parameter_value": str})
            _require(table, ["parameter_value", "is_baseline", "status", *METRIC_COLUMNS], "sensitivity")
            if (table.is_baseline.sum() != 1 or not table.status.eq("complete").all()
                    or not np.isfinite(table[METRIC_COLUMNS]).all().all()):
                raise DashboardDataError("Invalid deployment sensitivity results.")
            baseline = table.loc[table.is_baseline].iloc[0]
            if not np.array_equal(baseline[METRIC_COLUMNS[:5]].to_numpy(dtype=float), summary.Strategy.to_numpy()):
                raise DashboardDataError("Deployment sensitivity baseline does not match metrics.")
            sensitivity[group] = table
        return DashboardBundle(daily, summary, annual, selected, sensitivity, sessions, manifest["source_version"])
    except DashboardDataError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise DashboardDataError(f"Cannot load deployment artifacts/manifest: {error}") from error


def formation_dates(bundle: DashboardBundle) -> list[pd.Timestamp]:
    return sorted(bundle.selected.formation_date.unique().tolist())


def portfolio_view(bundle: DashboardBundle, formation: pd.Timestamp, root: Path = PROJECT_ROOT) -> PortfolioView:
    """Read validated exported execution targets, with no raw-price/cache access."""
    date = pd.Timestamp(formation)
    if date not in formation_dates(bundle):
        raise DashboardDataError("Choose a reviewed portfolio formation date.")
    table = bundle.selected.loc[bundle.selected.formation_date.eq(date)].copy()
    execution = table.execution_date.iloc[0]
    cash = table.cash_weight.iloc[0]
    return PortfolioView(table, date, execution, None if pd.isna(cash) else float(cash))
