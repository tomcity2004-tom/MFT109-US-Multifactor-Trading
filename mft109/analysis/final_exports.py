"""Versioned report materials copied/plotted from validated results; no new research.

Run explicitly with python -m mft109.analysis.final_exports. Does not execute
factors, backtests, sensitivity runs or normality analysis.
"""

from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import textwrap

import numpy as np
import pandas as pd

from mft109.config import BASELINE, PROJECT_ROOT
from mft109.visualization.dashboard_data import ARTIFACT_NAMES, GROUP_LABELS, load_dashboard_bundle

EXPORT_VERSION = "v1"
PHASE10A_CHECKPOINT = "fcb2633b5dd5271774a281d271f87474cb3febe2"
DOCUMENTS = (
    "docs/FINAL_RESULTS.md", "docs/FINAL_METHODOLOGY.md", "docs/LIMITATIONS.md",
    "docs/REPRODUCIBILITY.md", "docs/FINAL_EXPORT_INDEX.md", "docs/ASSIGNMENT_MAPPING.md",
    "docs/PHASE10B_FINAL_EXPORTS.md",
)
ANALYSIS_FILES = (
    "descriptive_statistics.csv", "normality_tests.csv", "strategy_return_distribution.png",
    "spy_return_distribution.png", "strategy_qq_plot.png", "spy_qq_plot.png",
    "analysis_summary.md", "analysis_metadata.json",
)
CSV_FILES = (
    "performance_summary.csv", "annual_returns.csv", "descriptive_statistics.csv", "normality_tests.csv",
    "sensitivity_summary.csv", "methodology_parameters.csv", "factor_definitions.csv",
    "baseline_daily.csv", "portfolio_snapshots.csv", "data_quality_context.csv",
)
FIGURE_FILES = (
    "nav_comparison.png", "drawdown_comparison.png", "annual_returns_comparison.png",
    *[f"sensitivity_{group}.png" for group in GROUP_LABELS],
    *[name for name in ANALYSIS_FILES if name.endswith(".png")],
)
PACKAGE_FILES = (*CSV_FILES, *[f"figures/{name}" for name in FIGURE_FILES],
                 "phase10a_metadata.json", "phase10a_interpretation.md", "manifest.json")


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def methodology_parameters(root: Path = PROJECT_ROOT) -> pd.DataFrame:
    """Describe immutable configuration; no portfolio or metric calculations."""
    rows = [{"Parameter": name, "Value": str(value), "Convention": "mft109.config.BASELINE"}
            for name, value in asdict(BASELINE).items()]
    extras = {
        "market": "U.S. Equity Market",
        "warm_up_period": f"{BASELINE.download_start} through {pd.Timestamp(BASELINE.backtest_start).date() - pd.Timedelta(days=1)}",
        "universe_snapshot_rows": str(len(pd.read_csv(root / 'data/raw/sp500_constituents.csv'))),
        "cross_sectional_zscore_ddof": "0",
        "historical_volatility_ddof": "1",
        "turnover_definition": "0.5 * sum(abs(target_weight - drifted_pre_rebalance_weight)); include cash",
        "execution_valuation_price": "Next eligible SPY session adjusted close; new holdings earn after that close",
        "missing_factor_rule": "All four finite factors required; no imputation or partial reweighting",
        "ranking_tie_break": "CompositeScore descending, ticker ascending; unique sequential ranks",
        "forward_fill": "Never",
    }
    rows += [{"Parameter": name, "Value": value, "Convention": "Locked methodology; see FINAL_METHODOLOGY.md"}
             for name, value in extras.items()]
    return pd.DataFrame(rows)


def factor_definitions() -> pd.DataFrame:
    definitions = [
        ("12-1 Month Momentum", "P(i,t-21) / P(i,t-252) - 1", BASELINE.momentum_lookback_days,
         BASELINE.momentum_skip_days, "Higher", "M(i,t) = Z(Momentum(i,t))", BASELINE.momentum_weight),
        ("60-Day Low Volatility", "r(i,t) = P(i,t)/P(i,t-1)-1; Volatility(i,t) = Std(r(i,t-59:t), ddof=1) * sqrt(252)",
         BASELINE.volatility_lookback_days, 0, "Lower", "LV(i,t) = -Z(Volatility(i,t))", BASELINE.low_volatility_weight),
        ("20-Day Liquidity", "DV(i,t) = P(i,t)*Volume(i,t); ADV20(i,t) = mean(DV(i,t-19:t)); LiquidityRaw(i,t) = ln(ADV20(i,t))",
         BASELINE.liquidity_lookback_days, 0, "Higher", "L(i,t) = Z(LiquidityRaw(i,t))", BASELINE.liquidity_weight),
        ("20-Day Short-Term Reversal", "Reversal(i,t) = -(P(i,t)/P(i,t-20)-1)",
         BASELINE.reversal_lookback_days, 0, "Higher (raw return is already negated)", "R(i,t) = Z(Reversal(i,t))", BASELINE.reversal_weight),
    ]
    frame = pd.DataFrame(definitions, columns=["Factor", "Raw Definition", "Lookback Sessions", "Skip Sessions",
                                               "Preferred Raw Direction", "Standardized Score", "Composite Weight"])
    frame["Price / Volume Convention"] = "P = adjusted price; Volume = Yahoo-reported Volume"
    frame["Z-score Convention"] = "Same-date common eligible universe; population SD ddof=0; higher final score is better"
    return frame


def data_quality_context() -> pd.DataFrame:
    """Label reviewed evidence and historical diagnostics, not a fabricated new audit."""
    return pd.DataFrame([
        ("Fixed universe", "503 securities; fixed current snapshot, not historical membership", "Current approved methodology", "data/raw/sp500_constituents.csv; docs/PHASE8_TESTING_VALIDATION.md"),
        ("Available histories", "500 stock histories plus SPY in reviewed cache validation", "Reviewed Phase 8 evidence; not a fresh vendor audit", "docs/PHASE8_TESTING_VALIDATION.md"),
        ("Unavailable symbols", "FDXF, HONA, VYLR retained; no requested-period history or substitutions", "Reviewed missing-data treatment", "docs/PHASE1_1_DATA_GAP_REVIEW.md; docs/PHASE8_TESTING_VALIDATION.md"),
        ("Leading coverage gaps", "43 leading-gap histories in the Phase 1.1 review; eligibility depends on complete factor windows", "Historical classification", "docs/PHASE1_1_DATA_GAP_REVIEW.md"),
        ("FISV gap", "2025-11-12 observation restored by approved Yahoo revision; three other Volume observations revised", "Current revised-data provenance", "docs/FISV_DATA_REVISION.md"),
        ("Older quality report", "data/processed/data_quality.json predates the FISV revision; its missing-price warning is historical", "Historical local report; not current revised-cache evidence", "docs/PHASE1_1_DATA_GAP_REVIEW.md; docs/FISV_DATA_REVISION.md"),
        ("Return analysis", "2514 source rows; exclude initial accounting anchor; 2513 paired actual returns with zero missing-pair exclusions", "Approved Phase 10A sample", "docs/PHASE10A_DATA_ANALYSIS.md"),
        ("Volume limitation", "yfinance may normalize upstream null Volume to zero; returned completeness is not proof of original source completeness", "Provider limitation retained", "docs/PHASE2_RAW_FACTORS.md"),
    ], columns=["Topic", "Evidence / treatment", "Evidence status", "Source"])


def _figure(rows: int = 1, *, height: float = 4.8):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(7.5, height), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(rows, 1, squeeze=False)[:, 0]
    return figure, axes


def comparison_figure(daily: pd.DataFrame, *, drawdown: bool = False):
    import matplotlib.dates as dates
    from matplotlib.ticker import PercentFormatter, MultipleLocator
    figure, axes = _figure()
    axis = axes[0]
    for label, prefix, color in (("Strategy", "strategy", "#245EA8"), ("SPY", "spy", "#B07A2A")):
        axis.plot(daily.date, daily[f"{prefix}_{'drawdown' if drawdown else 'nav'}"], label=label, color=color, linewidth=1.2)
    axis.set(title="Strategy vs SPY — drawdown from historical peak" if drawdown else "Strategy vs SPY — normalized NAV",
             xlabel="Date", ylabel="Drawdown" if drawdown else "Normalized NAV")
    axis.xaxis.set_major_locator(dates.YearLocator())
    axis.xaxis.set_major_formatter(dates.DateFormatter("%Y"))
    axis.set_xlim(pd.Timestamp(year=daily.date.min().year, month=1, day=1), daily.date.max())
    if drawdown:
        axis.set_ylim(-.40, .05)
        axis.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
        axis.yaxis.set_major_locator(MultipleLocator(.05))
    else:
        axis.set_ylim(bottom=0)
    axis.legend()
    axis.grid(alpha=.2)
    return figure


def annual_figure(annual: pd.DataFrame):
    from matplotlib.ticker import PercentFormatter
    figure, axes = _figure()
    axis = axes[0]
    x = np.arange(len(annual))
    axis.bar(x-.19, annual.Strategy, .38, label="Strategy", color="#245EA8")
    axis.bar(x+.19, annual.SPY, .38, label="SPY", color="#B07A2A")
    axis.set_xticks(x, annual.Year.astype(str))
    axis.set(title="Calendar-year returns — Strategy vs SPY", xlabel="Year", ylabel="Annual return")
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    axis.axhline(0, color="#555555", linewidth=.7)
    axis.legend(); axis.grid(axis="y", alpha=.2)
    return figure


def sensitivity_figure(table: pd.DataFrame, group: str):
    from matplotlib.ticker import PercentFormatter
    from matplotlib.patches import Patch
    figure, axes = _figure(3, height=8)
    labels = []
    for value in table.parameter_value:
        text = str(value).replace("_", " ").title()
        if group == "transaction_cost_bps": text += " bps"
        if group in ("volatility_window", "reversal_window"): text += " sessions"
        labels.append(textwrap.fill(text, width=12))
    colors = ["#245EA8" if value else "#A9BACD" for value in table.is_baseline]
    for axis, metric in zip(axes, ("Annualized Return", "Sharpe Ratio", "Maximum Drawdown"), strict=True):
        axis.bar(np.arange(len(table)), table[metric], color=colors)
        axis.set_ylabel("CAGR" if metric == "Annualized Return" else metric)
        axis.set_xticks(np.arange(len(table)), labels)
        if metric != "Sharpe Ratio": axis.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
        axis.grid(axis="y", alpha=.2)
    figure.suptitle(f"One-at-a-time sensitivity — {GROUP_LABELS[group]}\nAll other parameters fixed; baseline remains unchanged", fontsize=12)
    axes[0].legend(handles=[Patch(color="#245EA8", label="Baseline"), Patch(color="#A9BACD", label="Sensitivity")], fontsize=8)
    return figure


def _phase10a_metadata(root: Path, directory: Path, bundle) -> dict:
    try:
        metadata = json.loads((directory / "analysis_metadata.json").read_text())
        if metadata["source_data_version"] != bundle.version:
            raise ValueError("Phase 10A source version does not match current validated baseline")
        if metadata["analysis_code_sha256"] != _digest(root / "mft109/analysis/data_analysis.py"):
            raise ValueError("Phase 10A code identity does not match approved analysis metadata")
        for relative, digest in metadata["source_sha256"].items():
            if _digest(root / relative) != digest:
                raise ValueError(f"Phase 10A source checksum mismatch: {relative}")
        for name in ANALYSIS_FILES:
            path = directory / name
            if not path.is_file(): raise ValueError(f"Missing approved Phase 10A output: {name}")
            if name != "analysis_metadata.json" and _digest(path) != metadata["files"][name]["sha256"]:
                raise ValueError(f"Phase 10A output checksum mismatch: {name}")
        return metadata
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Approved Phase 10A outputs unavailable/invalid; restore them or explicitly run python -m mft109.analysis.data_analysis") from error


def export_final_report(root: Path = PROJECT_ROOT, output_dir: Path | None = None,
                        analysis_dir: Path | None = None) -> Path:
    """Package existing results; never generate missing Phase 10A outputs silently."""
    root = Path(root).resolve()
    destination = Path(output_dir).resolve() if output_dir is not None else root / "outputs/final_report" / EXPORT_VERSION
    if destination.is_relative_to(root) and not destination.is_relative_to(root / "outputs/final_report" / EXPORT_VERSION):
        raise ValueError("Repository exports are restricted to outputs/final_report/v1")
    analysis = Path(analysis_dir).resolve() if analysis_dir is not None else root / "outputs/final_analysis"
    bundle = load_dashboard_bundle(root)
    phase10a = _phase10a_metadata(root, analysis, bundle)
    extra_sources = ("PROJECT_REQUIREMENTS.md", "mft109/config.py", "mft109/analysis/data_analysis.py",
                     "data/raw/sp500_constituents.csv", "docs/FISV_DATA_REVISION.md",
                     "docs/PHASE8_TESTING_VALIDATION.md", "docs/PHASE1_1_DATA_GAP_REVIEW.md", "docs/PHASE2_RAW_FACTORS.md")
    source_paths = [root / "dashboard/data" / name for name in ("manifest.json", *ARTIFACT_NAMES)]
    source_paths += [analysis / name for name in ANALYSIS_FILES]
    source_paths += [root / name for name in extra_sources]
    source_hashes = {str(p.relative_to(root)) if p.is_relative_to(root) else str(p): _digest(p) for p in source_paths}
    if destination.exists():
        extras = {str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()} - set(PACKAGE_FILES)
        if extras: raise ValueError(f"Refusing to overwrite a directory containing unrelated files: {sorted(extras)}")
    (destination / "figures").mkdir(parents=True, exist_ok=True)
    metrics = bundle.summary.set_index("Metric")
    final = bundle.daily.iloc[-1]
    performance = pd.DataFrame([{
        "Series": label, "Final NAV": final[f"{prefix}_nav"],
        "Cumulative Return": metrics.at["Cumulative Return", label],
        "CAGR": metrics.at["Annualized Return", label],
        "Annualized Volatility": metrics.at["Annualized Volatility", label],
        "Sharpe Ratio": metrics.at["Sharpe Ratio", label], "Maximum Drawdown": metrics.at["Maximum Drawdown", label],
        "Final Portfolio Value (USD)": final.portfolio_value_usd if label == "Strategy" else np.nan,
    } for label, prefix in (("Strategy", "strategy"), ("SPY", "spy"))])
    performance.to_csv(destination / "performance_summary.csv", index=False)
    bundle.annual[["Year", "Strategy", "SPY"]].to_csv(destination / "annual_returns.csv", index=False)
    bundle.daily.to_csv(destination / "baseline_daily.csv", index=False, date_format="%Y-%m-%d")
    bundle.selected.to_csv(destination / "portfolio_snapshots.csv", index=False, date_format="%Y-%m-%d")
    sensitivity_columns = [c for c in next(iter(bundle.sensitivity.values())).columns if c not in ("blocking_date", "blocking_tickers")]
    pd.concat([table[sensitivity_columns] for table in bundle.sensitivity.values()], ignore_index=True).to_csv(destination / "sensitivity_summary.csv", index=False)
    methodology_parameters(root).to_csv(destination / "methodology_parameters.csv", index=False)
    factor_definitions().to_csv(destination / "factor_definitions.csv", index=False)
    data_quality_context().to_csv(destination / "data_quality_context.csv", index=False)
    for name in ("descriptive_statistics.csv", "normality_tests.csv"):
        shutil.copyfile(analysis / name, destination / name)
    for name in ANALYSIS_FILES:
        if name.endswith('.png'): shutil.copyfile(analysis / name, destination / "figures" / name)
    shutil.copyfile(analysis / "analysis_metadata.json", destination / "phase10a_metadata.json")
    shutil.copyfile(analysis / "analysis_summary.md", destination / "phase10a_interpretation.md")
    figures = [("nav_comparison.png", comparison_figure(bundle.daily)),
               ("drawdown_comparison.png", comparison_figure(bundle.daily, drawdown=True)),
               ("annual_returns_comparison.png", annual_figure(bundle.annual))]
    figures += [(f"sensitivity_{group}.png", sensitivity_figure(table, group)) for group, table in bundle.sensitivity.items()]
    for name, figure in figures:
        figure.savefig(destination / "figures" / name, dpi=300)
        figure.clear()
    after = {str(p.relative_to(root)) if p.is_relative_to(root) else str(p): _digest(p) for p in source_paths}
    if after != source_hashes: raise ValueError("Inputs changed during export; package must not be used")
    manifest = {
        "export_version": EXPORT_VERSION, "package_kind": "Validated academic report source materials, not final report/PPT",
        "source_data_version": bundle.version, "source_checkpoint_commit": PHASE10A_CHECKPOINT,
        "methodology_version": {"specification": "PROJECT_REQUIREMENTS.md sections 1–21", "sha256": _digest(root / "PROJECT_REQUIREMENTS.md")},
        "exporter_sha256": _digest(Path(__file__)), "sources_sha256": source_hashes,
        "phase10a_sample": phase10a["sample"],
        "validated_baseline_endpoints": {key: float(final[key]) for key in ("strategy_nav", "portfolio_value_usd", "spy_nav")},
        "maximum_drawdown": metrics.loc["Maximum Drawdown"].to_dict(),
        "units": "Returns/drawdowns/weights in CSV are decimals; Sharpe/skewness/kurtosis are dimensionless; strategy value USD; SPY USD blank (not supplied).",
        "sensitivity": "Six one-at-a-time groups; 21 reported rows including six identical baseline rows; no new baseline selection.",
        "data_quality_context": "Historical Phase 1 reports predate approved FISV revision; no new vendor audit was performed.",
        "phase10a_provenance": "phase10a_metadata.json describes the original Phase 10A folder; this manifest inventories the final package.",
        "documentation": list(DOCUMENTS),
        "software": {name: version(name) for name in ("pandas", "numpy", "matplotlib", "pyarrow")},
        "files": {name: {"bytes": (destination / name).stat().st_size, "sha256": _digest(destination / name)}
                  for name in PACKAGE_FILES if name != "manifest.json"},
        "reproducibility": "No generation timestamp; repeat export with identical inputs/code/software is byte-identical. Source checkpoint is fixed, not current HEAD.",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return destination


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Package validated results without strategy or statistical reruns")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    print(export_final_report(output_dir=args.output_dir))
