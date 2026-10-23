"""Phase 1 command line and reusable orchestration; no signals or performance."""

import argparse
from datetime import datetime, timezone
import logging

from mft109.config import BASELINE, DATA_SETTINGS
from mft109.data.cache import load_or_download, write_json
from mft109.data.universe import get_universe, universe_fingerprint
from mft109.data.validation import validate_market_data

LOG = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """A run is incomplete; inspect the persisted data-quality report."""


def run_pipeline(*, baseline=BASELINE, settings=DATA_SETTINGS, refresh=False,
                 tickers=None, universe_only=False):
    """Acquire all constituents by default; optional subsets are labelled smoke runs.

    Return a small report, not a second combined copy of all historical data.
    Later phases can load the per-symbol Parquet files. Existing snapshots are
    always reused, including on refresh. A benchmark failure stops before hundreds
    of likely identical network failures; per-stock failures are collected.
    """
    universe = get_universe(settings)
    if universe_only:
        return {"status": "universe_only", "securities": len(universe),
                "snapshot": str(settings.universe_snapshot)}
    candidates = universe.yahoo_ticker.tolist()
    selected = candidates if tickers is None else sorted(set(tickers))
    if not selected or not set(selected).issubset(candidates):
        raise ValueError("Smoke-test tickers must be nonempty Yahoo symbols from the fixed universe")
    report_path = settings.validation_report
    if tickers is not None:
        report_path = report_path.with_name(report_path.stem + ".smoke" + report_path.suffix)
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "running", "mode": "full" if tickers is None else "smoke",
              "universe_securities": len(universe), "requested_stock_tickers": selected,
              "universe_sha256": universe_fingerprint(universe),
              "requested_start": baseline.download_start.isoformat(),
              "requested_end_inclusive": baseline.download_end.isoformat(),
              "stocks": {}, "failed_tickers": {}, "benchmark": None}
    try:
        benchmark, quality = load_or_download(
            baseline.benchmark, report["universe_sha256"], baseline=baseline,
            settings=settings, benchmark=True, refresh=refresh)
        report["benchmark"] = quality
    except Exception as exc:
        report["status"] = "blocked_benchmark"
        report["failed_tickers"][baseline.benchmark] = str(exc)
        write_json(report_path, report)
        raise PipelineError(f"SPY benchmark unavailable; report: {report_path}: {exc}") from exc
    for ticker in selected:
        try:
            frame, quality = load_or_download(
                ticker, report["universe_sha256"], baseline=baseline,
                settings=settings, refresh=refresh)
            # Compare actual observations with SPY sessions, without filling gaps.
            session_quality = validate_market_data(
                frame, ticker, baseline.download_start, baseline.download_end,
                tolerance_days=settings.coverage_tolerance_days,
                reference_dates=benchmark.date)
            quality.update(session_quality)
            report["stocks"][ticker] = quality
            for warning in quality["warnings"]:
                LOG.warning("%s: %s", ticker, warning)
        except Exception as exc:
            report["failed_tickers"][ticker] = str(exc)
            LOG.error("%s failed: %s", ticker, exc)
    report["status"] = "incomplete" if report["failed_tickers"] else "complete"
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(report_path, report)
    if report["failed_tickers"]:
        raise PipelineError(f"Failed tickers: {sorted(report['failed_tickers'])}; "
                            f"report: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refresh prices only; preserve fixed universe")
    parser.add_argument("--universe-only", action="store_true", help="Obtain or validate only the fixed universe")
    parser.add_argument("--tickers", nargs="+", help="Smoke-test subset of fixed-universe Yahoo symbols")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        report = run_pipeline(refresh=args.refresh, tickers=args.tickers, universe_only=args.universe_only)
    except Exception as exc:
        LOG.error("Phase 1 pipeline failed: %s", exc)
        return 1
    LOG.info("Run status: %s; universe securities: %d", report["status"],
             report.get("universe_securities", report.get("securities", 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
