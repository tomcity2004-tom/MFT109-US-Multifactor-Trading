"""Read-only presentation adapters for reviewed outputs; no trading methodology."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from mft109.analysis.performance import analyze_performance
from mft109.backtesting.execution import execution_schedule
from mft109.config import BASELINE, PROJECT_ROOT
from mft109.data.universe import load_universe
from mft109.data.validation import validate_market_data
from mft109.optimization.scenarios import BASE_VALUES, VALUES
from mft109.portfolio import CASH_ASSET, equal_weight_target
from mft109.ranking import monthly_formation_dates


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


def output_directory(root: Path = PROJECT_ROOT) -> Path:
    """Identify the reviewed output vintage from active FISV provenance, not a glob."""
    try:
        meta = json.loads((root / "data/cache/market/stocks/FISV.json").read_text())
        version = Path(meta["data_revision"]["archive_directory"]).name
        if not version or not version.replace("T", "").replace("Z", "").isdigit():
            raise ValueError("Invalid data revision identifier")
        return root / "outputs/optimization" / f"fisv_revision_{version}"
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DashboardDataError("Approved data-version metadata is unavailable or invalid (FISV.json).") from error


def bundle_signature(root: Path = PROJECT_ROOT) -> tuple:
    """Read-only mtime/size signature used to invalidate presentation caches."""
    directory = output_directory(root)
    files = [directory / name for name in ("validation.json", "baseline_daily.parquet", "baseline_performance.csv",
                                           "baseline_annual_returns.csv", "baseline_selected.csv")]
    files += [directory / f"phase7_{group}.csv" for group in VALUES]
    files += [root / "data/cache/market/stocks/FISV.json", root / "data/cache/market/stocks/FISV.parquet",
              root / "data/cache/market/benchmark/SPY.parquet", root / "data/cache/market/benchmark/SPY.json",
              root / "data/raw/sp500_constituents.csv", root / "data/raw/sp500_constituents.metadata.json"]
    # Target displays also depend on the existing stock caches; stat, never download.
    files += list((root / "data/cache/market/stocks").glob("*.parquet"))
    files += list((root / "data/cache/market/stocks").glob("*.json"))
    try:
        return tuple((str(p.relative_to(root)), p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(set(files)))
    except OSError as error:
        raise DashboardDataError(f"Required reviewed data/output is missing: {error.filename}") from error


def _cache_frame(ticker: str, root: Path, *, benchmark: bool = False) -> pd.DataFrame:
    path = root / "data/cache/market" / ("benchmark" if benchmark else "stocks") / f"{ticker}.parquet"
    meta = json.loads(path.with_suffix(".json").read_text())
    if (sha256(path.read_bytes()).hexdigest() != meta["parquet_sha256"]
            or meta["request"]["ticker"] != ticker or meta["request"]["auto_adjust"] is not True):
        raise DashboardDataError(f"Cache identity/checksum mismatch for {ticker}.")
    frame = pd.read_parquet(path)
    validate_market_data(frame, ticker, BASELINE.download_start, BASELINE.download_end, benchmark=benchmark)
    return frame


def _numeric_match(actual: pd.DataFrame, saved: pd.DataFrame, key: str, columns: list[str]) -> None:
    a, b = actual.set_index(key).sort_index(), saved.set_index(key).sort_index()
    if not a.index.equals(b.index) or not np.allclose(a[columns], b[columns], rtol=1e-10, atol=1e-12):
        raise DashboardDataError(f"Saved {key} table does not match validated daily results.")


def load_dashboard_bundle(root: Path = PROJECT_ROOT) -> DashboardBundle:
    """Load reviewed artifacts; reuse Phase 6 validation, without rerunning backtests."""
    try:
        directory = output_directory(root)
        audit = json.loads((directory / "validation.json").read_text())
        if audit["rows"] != 21 or audit["completed_rows"] != 21 or audit["blocked_rows"] != 0:
            raise DashboardDataError("The reviewed scenario run is incomplete.")
        fisv_meta = json.loads((root / "data/cache/market/stocks/FISV.json").read_text())
        if fisv_meta["parquet_sha256"] != fisv_meta["data_revision"]["replacement_parquet_sha256"]:
            raise DashboardDataError("FISV data revision identity is inconsistent.")
        _cache_frame("FISV", root)
        spy = _cache_frame("SPY", root, benchmark=True)
        sessions = pd.DatetimeIndex(spy.date)
        daily = pd.read_parquet(directory / "baseline_daily.parquet")
        analysis = analyze_performance(daily, sessions=sessions)
        saved_summary = pd.read_csv(directory / "baseline_performance.csv")
        saved_annual = pd.read_csv(directory / "baseline_annual_returns.csv")
        _numeric_match(analysis.performance_summary, saved_summary, "Metric", ["Strategy", "SPY"])
        _numeric_match(analysis.annual_returns, saved_annual, "Year", ["Strategy", "SPY"])
        final = daily.iloc[-1]
        for actual, expected in ((final.strategy_nav, audit["new_final_strategy_nav"]),
                                 (final.portfolio_value_usd, audit["new_final_strategy_usd"]),
                                 (final.spy_nav, audit["final_spy_nav"])):
            if not np.isclose(actual, expected, rtol=1e-12, atol=1e-10):
                raise DashboardDataError("Daily results disagree with the reviewed data-version audit.")
        selected = pd.read_csv(directory / "baseline_selected.csv", parse_dates=["formation_date"])
        required = ["formation_date", "ticker", "rank", "selected", "eligible", "composite_score", *SCORE_LABELS]
        if (not set(required).issubset(selected.columns) or selected.empty
                or selected.duplicated(["formation_date", "ticker"]).any()
                or selected.duplicated(["formation_date", "rank"]).any()
                or not selected.selected.eq(True).all() or not selected.eligible.eq(True).all()
                or not np.isfinite(selected[["composite_score", *SCORE_LABELS]]).all().all()):
            raise DashboardDataError("Invalid reviewed selection table.")
        if set(selected.formation_date) != set(monthly_formation_dates(sessions)):
            raise DashboardDataError("Selection table does not cover the reviewed formation calendar.")
        universe = load_universe(root / "data/raw/sp500_constituents.csv")
        if not selected.ticker.isin(universe.yahoo_ticker).all():
            raise DashboardDataError("Selection table contains a stock outside the fixed universe.")
        for _, group in selected.groupby("formation_date"):
            order = group.sort_values(["composite_score", "ticker"], ascending=[False, True])
            if len(group) != BASELINE.top_n or order["rank"].tolist() != list(range(1, BASELINE.top_n + 1)):
                raise DashboardDataError("Reviewed Top 20 ranks/order are inconsistent.")
        sensitivity = {}
        for group, values in VALUES.items():
            table = pd.read_csv(directory / f"phase7_{group}.csv", dtype={"parameter_value": str})
            required_sensitivity = {"parameter_value", "experiment", "is_baseline", "official_period_complete", "status", *METRIC_COLUMNS}
            if (not required_sensitivity.issubset(table.columns)
                    or table.parameter_value.tolist() != list(map(str, values)) or not table.experiment.eq(group).all()
                    or table.is_baseline.sum() != 1
                    or not table.is_baseline.eq(table.parameter_value.eq(str(BASE_VALUES[group]))).all()
                    or not table.official_period_complete.eq(True).all()
                    or not table.status.eq("complete").all()
                    or not np.isfinite(table[METRIC_COLUMNS]).all().all()):
                raise DashboardDataError(f"Invalid or incomplete {GROUP_LABELS[group]} sensitivity results.")
            baseline = table.loc[table.is_baseline].iloc[0]
            if not np.allclose(baseline[METRIC_COLUMNS[:5]].to_numpy(dtype=float),
                               analysis.performance_summary.Strategy, rtol=1e-10, atol=1e-12):
                raise DashboardDataError("Sensitivity baseline uses a different data version.")
            if (not np.allclose(table["Cumulative Return"], table["Final NAV"] - 1, rtol=1e-10, atol=1e-12)
                    or not np.allclose(table["Final Portfolio Value"], BASELINE.initial_capital_usd * table["Final NAV"], rtol=1e-12, atol=1e-8)
                    or not np.isclose(baseline["Final NAV"], final.strategy_nav, rtol=1e-12)
                    or not np.isclose(baseline["Final Portfolio Value"], final.portfolio_value_usd, rtol=1e-12)):
                raise DashboardDataError("Sensitivity NAV/value fields are inconsistent.")
            sensitivity[group] = table.copy()
        return DashboardBundle(analysis.daily_performance, analysis.performance_summary, analysis.annual_returns,
                               selected.sort_values(["formation_date", "rank"]).reset_index(drop=True),
                               sensitivity, sessions, directory.name)
    except DashboardDataError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise DashboardDataError(f"Cannot load reviewed dashboard data: {error}") from error


def formation_dates(bundle: DashboardBundle) -> list[pd.Timestamp]:
    return sorted(bundle.selected.formation_date.unique().tolist())


def portfolio_view(bundle: DashboardBundle, formation: pd.Timestamp, root: Path = PROJECT_ROOT) -> PortfolioView:
    """Use the validated execution mapper and target helper; never invent a final trade."""
    date = pd.Timestamp(formation)
    if date not in formation_dates(bundle):
        raise DashboardDataError("Choose a reviewed portfolio formation date.")
    table = bundle.selected.loc[bundle.selected.formation_date.eq(date)].copy()
    execution = execution_schedule(pd.DatetimeIndex([date]), sessions=bundle.sessions).execution_date.iloc[0]
    table["target_weight"] = np.nan
    if pd.isna(execution):
        return PortfolioView(table, date, pd.NaT, None)
    try:
        prices = {}
        for ticker in table.ticker:
            frame = _cache_frame(ticker, root).set_index("date")
            prices[ticker] = frame.adjusted_close.get(execution, np.nan)
        target = equal_weight_target(table.ticker.tolist(), pd.Series(prices, dtype=float))
        table["target_weight"] = table.ticker.map(lambda t: float(target.weights.get(t, 0)))
        return PortfolioView(table, date, execution, float(target.weights[CASH_ASSET]))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DashboardDataError(f"Cannot verify execution targets: {error}") from error


def export_dashboard_data(root: Path = PROJECT_ROOT) -> Path:
    """Explicit offline export of reviewed presentation results, never run by the app."""
    from dataclasses import asdict
    import subprocess

    bundle = load_dashboard_bundle(root)
    signature = bundle_signature(root)
    targets = []
    for date in formation_dates(bundle):
        view = portfolio_view(bundle, date, root)
        table = view.table[["formation_date", "ticker", "rank", "selected", "eligible",
                            "composite_score", *SCORE_LABELS, "target_weight"]].copy()
        table["execution_date"] = view.execution_date
        table["cash_weight"] = view.cash_weight
        targets.append(table)
    destination = root / "dashboard/data"
    destination.mkdir(parents=True, exist_ok=True)
    bundle.daily.to_parquet(destination / "baseline_daily.parquet", index=False)
    bundle.summary.to_csv(destination / "baseline_performance.csv", index=False)
    bundle.annual.to_csv(destination / "baseline_annual_returns.csv", index=False)
    pd.concat(targets, ignore_index=True).to_parquet(destination / "baseline_selected.parquet", index=False)
    for group, table in bundle.sensitivity.items():
        table.to_csv(destination / f"phase7_{group}.csv", index=False)
    names = ["baseline_daily.parquet", "baseline_performance.csv", "baseline_annual_returns.csv",
             "baseline_selected.parquet", *[f"phase7_{g}.csv" for g in GROUP_LABELS]]
    sources = {name: sha256((root / name).read_bytes()).hexdigest() for name, _, _ in signature}
    if signature != bundle_signature(root):
        raise DashboardDataError("Reviewed sources changed during export; do not use this export.")
    manifest = {
        "schema_version": 1,
        "source_version": bundle.version,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "provenance": "Derived presentation outputs from reviewed Phase 0–8 results; no new backtest or downloads.",
        "baseline_settings": {k: str(v) if hasattr(v, "isoformat") else v for k, v in asdict(BASELINE).items()},
        "files": {n: {"sha256": sha256((destination / n).read_bytes()).hexdigest(),
                       "bytes": (destination / n).stat().st_size} for n in names},
        "source_sha256": sources,
        "endpoints": {k: float(bundle.daily.iloc[-1][k]) for k in
                      ("strategy_nav", "portfolio_value_usd", "spy_nav")},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return destination


if __name__ == "__main__":
    print(export_dashboard_data())
