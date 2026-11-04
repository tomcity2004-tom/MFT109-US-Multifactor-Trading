"""Offline descriptive diagnostics of validated returns; no strategy execution.

CSV returns are decimals. Sample SD uses ddof=1; reported skewness and Fisher
excess kurtosis use bias=False. The standard Jarque–Bera test uses its own
biased central-moment estimators, as implemented by SciPy.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from mft109.config import BASELINE, PROJECT_ROOT
from mft109.visualization.dashboard_data import load_dashboard_bundle, ARTIFACT_NAMES

ALPHA = 0.05
SERIES = ("Strategy", "SPY")


@dataclass(frozen=True)
class ReturnSample:
    returns: pd.DataFrame
    metadata: dict


def prepare_returns(daily: pd.DataFrame, *, exclude_initial_anchor: bool = True) -> ReturnSample:
    """Pair valid observations explicitly; never fill returns or remove extremes.

    The validated source's first paired zeros are an accounting NAV anchor, not
    a close-to-close observation. Exclusion follows existing Phase 6 conventions.
    Other genuine zeros, including pre-investment cash days, are retained.
    """
    required = ["date", "strategy_return", "spy_return"]
    if not isinstance(daily, pd.DataFrame) or daily.empty or not set(required).issubset(daily.columns):
        raise ValueError("Nonempty daily date/strategy_return/spy_return columns are required")
    dates = pd.DatetimeIndex(daily.date)
    if (dates.hasnans or dates.tz is not None or dates.has_duplicates
            or not dates.equals(dates.normalize())
            or dates.min() < pd.Timestamp(BASELINE.backtest_start)
            or dates.max() > pd.Timestamp(BASELINE.backtest_end)):
        raise ValueError("Dates must be unique naive daily observations inside official 2016–2025 bounds")
    for column in required[1:]:
        dtype = daily[column].dtype
        if (not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_bool_dtype(dtype)
                or pd.api.types.is_complex_dtype(dtype)):
            raise TypeError("Returns must be real numeric values")
    frame = daily[required].copy(deep=True).set_index("date").sort_index()
    frame.columns = list(SERIES)
    frame = frame.astype(float)
    if np.isinf(frame.to_numpy()).any():
        raise ValueError("Infinite returns are invalid; no values are substituted")
    source_rows = len(frame)
    anchor = None
    if exclude_initial_anchor:
        if not frame.iloc[0].eq(0).all():
            raise ValueError("Expected paired initial zero-return NAV anchor")
        anchor = frame.index[0].date().isoformat()
        frame = frame.iloc[1:].copy()
    valid = frame.notna().all(axis=1)
    counts = {series: int(frame[series].count()) for series in SERIES}
    missing = frame.index[~valid]
    aligned = frame.loc[valid].copy()
    if len(aligned) < 4:
        raise ValueError("At least four paired finite daily returns are required")
    metadata = {
        "official_period": [str(BASELINE.backtest_start), str(BASELINE.backtest_end)],
        "source_first_date": dates.min().date().isoformat(),
        "source_last_date": dates.max().date().isoformat(), "source_rows": source_rows,
        "excluded_initial_anchor_date": anchor,
        "analysis_first_date": aligned.index[0].date().isoformat(),
        "analysis_last_date": aligned.index[-1].date().isoformat(),
        "strategy_observations": counts["Strategy"], "spy_observations": counts["SPY"],
        "aligned_observations": len(aligned), "pairwise_missing_rows_excluded": len(missing),
        "excluded_missing_dates": [d.date().isoformat() for d in missing],
        "missing_value_rule": "Pairwise complete dates only; no fill, clipping or imputation. Infinities fail.",
        "anchor_rule": "Exclude only initial synthetic zero anchor, consistent with Phase 6; retain genuine later zeros.",
        "return_units": "Daily simple returns stored as decimals; 0.01 = 1%.",
    }
    return ReturnSample(aligned, metadata)


def _values(values) -> np.ndarray:
    array = np.asarray(values)
    if (array.ndim != 1 or len(array) < 4 or not np.issubdtype(array.dtype, np.number)
            or np.issubdtype(array.dtype, np.complexfloating)):
        raise ValueError("A one-dimensional real numeric sample with at least four returns is required")
    array = array.astype(float, copy=True)
    if not np.isfinite(array).all():
        raise ValueError("Statistical samples must be finite; align missing dates explicitly first")
    return array


def descriptive_statistics(returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for series in SERIES:
        values = _values(returns[series])
        constant = np.ptp(values) == 0
        rows.append({
            "Series": series, "Count": len(values), "Mean": float(np.mean(values)),
            "Median": float(np.median(values)), "Standard Deviation": float(np.std(values, ddof=1)),
            "Minimum": float(values.min()), "25th Percentile": float(np.quantile(values, .25, method="linear")),
            "75th Percentile": float(np.quantile(values, .75, method="linear")), "Maximum": float(values.max()),
            "Skewness": np.nan if constant else float(stats.skew(values, bias=False)),
            "Excess Kurtosis": np.nan if constant else float(stats.kurtosis(values, fisher=True, bias=False)),
        })
    return pd.DataFrame(rows)


def normality_conclusion(p_value: float, alpha: float = ALPHA) -> str:
    if not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between 0 and 1")
    if np.isnan(p_value):
        return "Undefined: constant sample"
    if not np.isfinite(p_value) or not 0 <= p_value <= 1:
        raise ValueError("p-value must be between 0 and 1, or NaN for an undefined test")
    return "Reject H0" if p_value < alpha else "Do not reject H0"


def normality_tests(returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for series in SERIES:
        values = _values(returns[series])
        if np.ptp(values) == 0:
            statistic, p_value = np.nan, np.nan
        else:
            result = stats.jarque_bera(values)
            statistic, p_value = float(result.statistic), float(result.pvalue)
        rows.append({
            "Series": series, "Test": "Jarque–Bera", "Count": len(values),
            "Statistic": statistic, "p-value": p_value,
            # The chi-square(2) survival function is exactly exp(-statistic/2).
            "Log p-value": -statistic / 2, "Alpha": ALPHA,
            "Conclusion": normality_conclusion(p_value),
            "p-value note": ("Floating-point underflow, not exact zero; see Log p-value" if p_value == 0
                             else "Undefined for constant returns" if np.isnan(p_value) else "Asymptotic chi-square(2) p-value"),
        })
    return pd.DataFrame(rows)


def _figure():
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(7.5, 4.8), layout="constrained")
    FigureCanvasAgg(figure)
    return figure, figure.subplots()


def distribution_plot(values, series: str, bins: np.ndarray):
    """Density histogram and fitted normal PDF, both in decimal-return units."""
    from matplotlib.ticker import PercentFormatter
    values = _values(values)
    edges = np.asarray(bins, dtype=float)
    if (edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all()
            or not np.all(np.diff(edges) > 0) or edges[0] > values.min() or edges[-1] < values.max()):
        raise ValueError("Histogram bin edges must include the full observed sample")
    figure, axis = _figure()
    axis.hist(values, bins=edges, density=True, color="#245EA8" if series == "Strategy" else "#B07A2A",
              alpha=.65, label="Empirical returns", edgecolor="white", linewidth=.4)
    sigma = float(np.std(values, ddof=1))
    if sigma > 0:
        grid = np.linspace(edges[0], edges[-1], 1200)
        axis.plot(grid, stats.norm.pdf(grid, loc=float(values.mean()), scale=sigma),
                  color="#263238", linewidth=1.7, label="Normal reference (sample mean / SD)")
    axis.set(title=f"{series} daily-return distribution", xlabel="Daily return (%)",
             ylabel="Probability density (per decimal return)", xlim=(edges[0], edges[-1]))
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=1))
    axis.legend(fontsize=8)
    axis.grid(axis="y", alpha=.2)
    return figure


def qq_plot(values, series: str):
    """SciPy normal order-statistic Q-Q plot with a least-squares reference line."""
    from matplotlib.ticker import PercentFormatter
    values = _values(values)
    (theoretical, observed), (slope, intercept, _) = stats.probplot(values, dist="norm", fit=True)
    figure, axis = _figure()
    axis.scatter(theoretical, observed, s=10, alpha=.6, color="#245EA8" if series == "Strategy" else "#B07A2A",
                 label="All observed returns")
    axis.plot(theoretical, intercept + slope * theoretical, color="#263238", linewidth=1.5,
              label="Least-squares normal reference")
    axis.set(title=f"{series} normal Q-Q plot", xlabel="Theoretical standard-normal quantile (z)",
             ylabel="Observed daily return (%)")
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    axis.legend(fontsize=8)
    axis.grid(alpha=.2)
    return figure


def interpretation(descriptive: pd.DataFrame, normality: pd.DataFrame, metadata: dict) -> str:
    paragraphs = ["# Phase 10A — Daily-return distribution diagnostics\n",
                  f"Sample: {metadata['analysis_first_date']} through {metadata['analysis_last_date']}; "
                  f"{metadata['aligned_observations']:,} paired daily returns. The initial accounting anchor "
                  "is excluded consistently with Phase 6. Genuine cash-day zeros and all extremes are retained.\n"]
    for _, row in descriptive.iterrows():
        test = normality.loc[normality.Series.eq(row.Series)].iloc[0]
        direction = ("undefined for constant returns" if np.isnan(row.Skewness) else
                     "left asymmetry" if row.Skewness < 0 else "right asymmetry" if row.Skewness > 0 else "zero third moment")
        skew_text = "undefined" if np.isnan(row.Skewness) else f"{row.Skewness:.6f}"
        kurtosis_text = "undefined" if np.isnan(row['Excess Kurtosis']) else f"{row['Excess Kurtosis']:.6f}"
        tail = ("Positive excess kurtosis indicates greater extreme-tail influence than a normal reference in this sample."
                if row['Excess Kurtosis'] > 0 else "Excess kurtosis is undefined for constant returns." if np.isnan(row['Excess Kurtosis'])
                else "Excess kurtosis is not positive in this sample.")
        p_text = ("undefined for constant returns" if np.isnan(test['p-value']) else
                  "numerical underflow below floating-point resolution" if test['p-value'] == 0 else f"{test['p-value']:.6g}")
        paragraphs.append(f"**{row.Series}:** mean daily return {row.Mean:.6%}, median {row.Median:.6%}, "
                          f"sample daily SD {row['Standard Deviation']:.6%}, minimum {row.Minimum:.6%}, "
                          f"maximum {row.Maximum:.6%}; skewness {skew_text} ({direction}), "
                          f"Fisher excess kurtosis {kurtosis_text}. {tail} "
                          f"Jarque–Bera = {test.Statistic:.6f}, p-value = {p_text}, "
                          f"log p-value = {test['Log p-value']:.6f}; alpha = 0.05: **{test.Conclusion}**.\n")
    by_series = descriptive.set_index("Series")
    strategy, spy = by_series.loc["Strategy"], by_series.loc["SPY"]
    relation = lambda a, b: "undefined" if not np.isfinite([a, b]).all() else "higher" if a > b else "lower" if a < b else "equal"
    paragraphs.append(f"Compared with SPY, the strategy has {relation(strategy.Mean, spy.Mean)} "
                      f"mean daily return and {relation(strategy['Standard Deviation'], spy['Standard Deviation'])} "
                      f"daily volatility. Its reported excess kurtosis is "
                      f"{relation(strategy['Excess Kurtosis'], spy['Excess Kurtosis'])}. "
                      "These sample comparisons do not establish causality or future superiority.\n")
    paragraphs.append("Statistics are daily, not annualized. CSV location/scale/quantile values are decimals "
                      "(0.01 = 1%); skewness and excess kurtosis are dimensionless. Sample SD uses ddof=1; "
                      "reported skewness and Fisher excess kurtosis use bias=False. Jarque–Bera uses the "
                      "standard biased central-moment estimators internally, not those adjusted table estimates.\n")
    paragraphs.append("Histograms use common Freedman–Diaconis bins spanning both complete samples and "
                      "density normalization. The normal PDF uses each sample's mean and sample SD; it is "
                      "a visual reference, not an assertion of normality. Q-Q plots retain every observation "
                      "and use SciPy normal order-statistic quantiles with a fitted reference line. Extremes "
                      "may compress the central histogram; none are clipped, winsorized or removed.\n")
    paragraphs.append("Jarque–Bera is an asymptotic diagnostic of skewness and kurtosis. Financial returns "
                      "can exhibit serial dependence and volatility clustering, limiting textbook p-value "
                      "calibration; large samples also detect small departures. Rejecting normality does not "
                      "invalidate the backtest or establish strategy quality or causality. Failing to reject "
                      "does not prove normality. The fixed current S&P 500 universe retains survivorship bias. "
                      "These descriptive results do not change any strategy parameter or validated result.\n")
    return "\n".join(paragraphs)


def export_analysis(root: Path = PROJECT_ROOT, output_dir: Path | None = None) -> Path:
    """Read current tracked artifacts and export only Phase 10A diagnostic outputs."""
    from importlib.metadata import version
    root = Path(root).resolve()
    destination = Path(output_dir).resolve() if output_dir is not None else root / "outputs/final_analysis"
    if destination.is_relative_to(root) and not destination.is_relative_to(root / "outputs/final_analysis"):
        raise ValueError("Inside the repository, exports are restricted to outputs/final_analysis")
    paths = [root / "dashboard/data" / name for name in ("manifest.json", *ARTIFACT_NAMES)]
    try:
        before = {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in paths}
    except OSError as error:
        raise ValueError(f"Required validated source artifact is unavailable: {error.filename}") from error
    bundle = load_dashboard_bundle(root)
    sample = prepare_returns(bundle.daily)
    descriptive, normality = descriptive_statistics(sample.returns), normality_tests(sample.returns)
    bins = np.histogram_bin_edges(sample.returns.to_numpy().ravel(), bins="fd")
    destination.mkdir(parents=True, exist_ok=True)
    descriptive.to_csv(destination / "descriptive_statistics.csv", index=False)
    normality.to_csv(destination / "normality_tests.csv", index=False)
    for series in SERIES:
        for kind, factory in (("return_distribution", lambda: distribution_plot(sample.returns[series], series, bins)),
                              ("qq_plot", lambda: qq_plot(sample.returns[series], series))):
            figure = factory()
            figure.savefig(destination / f"{series.lower()}_{kind}.png", dpi=300)
            figure.clear()
    (destination / "analysis_summary.md").write_text(interpretation(descriptive, normality, sample.metadata))
    if before != {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in paths}:
        raise ValueError("Source artifacts changed during analysis; exported results must not be used")
    manifest = json.loads((root / "dashboard/data/manifest.json").read_text())
    names = ["descriptive_statistics.csv", "normality_tests.csv", "analysis_summary.md",
             "strategy_return_distribution.png", "spy_return_distribution.png", "strategy_qq_plot.png", "spy_qq_plot.png"]
    metadata = {
        "phase": "10A", "source_data_version": bundle.version, "source_sha256": before,
        "analysis_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "primary_source": "dashboard/data/baseline_daily.parquet", "sample": sample.metadata,
        "validated_baseline_endpoints": manifest["endpoints"],
        "validated_maximum_drawdown": bundle.summary.set_index("Metric").loc["Maximum Drawdown"].to_dict(),
        "conventions": {"standard_deviation_ddof": 1, "skewness_bias": False,
                        "kurtosis_fisher": True, "kurtosis_bias": False, "percentile_method": "linear",
                        "jarque_bera_moment_bias": True, "normality_alpha": ALPHA,
                        "histogram_bins": "Common Freedman–Diaconis, full paired sample range",
                        "qq_method": "scipy.stats.probplot: normal order statistics; least-squares reference"},
        "software": {package: version(package) for package in ("numpy", "pandas", "scipy", "matplotlib", "pyarrow")},
        "files": {name: {"bytes": (destination / name).stat().st_size,
                         "sha256": sha256((destination / name).read_bytes()).hexdigest()} for name in names},
        "strategy_or_data_changed": False,
    }
    (destination / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return destination


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Offline Phase 10A diagnostics; no downloads or strategy execution")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    print(export_analysis(output_dir=args.output_dir))
