"""Deterministic Phase 1 tests; no external network requests or market returns."""

from dataclasses import replace
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from mft109.config import BASELINE, DATA_SETTINGS
from mft109.data.acquisition import download_daily, normalize_download
from mft109.data.cache import load_or_download
from mft109.data.cleaning import clean_market_data
from mft109.data.pipeline import PipelineError, run_pipeline
from mft109.data.universe import get_universe, universe_fingerprint, validate_universe, yahoo_ticker
from mft109.data.validation import COLUMNS, DataValidationError, validate_market_data


SHORT_BASELINE = replace(BASELINE, download_start=date(2015, 1, 1), download_end=date(2015, 1, 5))


def sample(ticker="AAPL"):
    return pd.DataFrame({
        "date": pd.to_datetime(["2015-01-02", "2015-01-05"]),
        "ticker": [ticker, ticker], "open": [100.0, 101.0],
        "high": [102.0, 103.0], "low": [99.0, 100.0],
        "close": [101.0, 102.0], "adjusted_close": [101.0, 102.0],
        "volume": [1000.0, 0.0],
    })[COLUMNS]


def universe():
    return pd.DataFrame({"ticker": ["AAPL", "BRK.B"],
                         "yahoo_ticker": ["AAPL", "BRK-B"],
                         "company_name": ["Apple", "Berkshire Hathaway"],
                         "sector": ["Information Technology", "Financials"]})


class TemporaryDataTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.settings = replace(DATA_SETTINGS,
            universe_snapshot=self.root / "raw" / "sp500_constituents.csv",
            market_cache=self.root / "cache", validation_report=self.root / "quality.json")

    def save_universe(self):
        self.settings.universe_snapshot.parent.mkdir(parents=True, exist_ok=True)
        universe().to_csv(self.settings.universe_snapshot, index=False)


class UniverseTests(TemporaryDataTest):
    def test_ticker_conversion(self):
        self.assertEqual(yahoo_ticker("BRK.B"), "BRK-B")
        self.assertEqual(yahoo_ticker(" bf.b "), "BF-B")
        self.assertEqual(yahoo_ticker("AAPL"), "AAPL")
        with self.assertRaises(ValueError):
            yahoo_ticker("../../escape")

    def test_existing_snapshot_is_used_without_network(self):
        self.save_universe()
        before = self.settings.universe_snapshot.read_bytes()
        with patch("mft109.data.universe.urlopen", side_effect=AssertionError("network forbidden")):
            result = get_universe(self.settings)
        self.assertEqual(len(result), 2)
        self.assertEqual(self.settings.universe_snapshot.read_bytes(), before)

    def test_invalid_existing_snapshot_is_not_overwritten(self):
        self.settings.universe_snapshot.parent.mkdir(parents=True)
        self.settings.universe_snapshot.write_text("invalid\n1\n")
        with patch("mft109.data.universe.urlopen") as network:
            with self.assertRaises(ValueError):
                get_universe(self.settings)
            network.assert_not_called()
        self.assertEqual(self.settings.universe_snapshot.read_text(), "invalid\n1\n")

    def test_source_snapshot_and_provenance_saved_once(self):
        source = "Symbol,Security,GICS Sector\n" + "".join(
            f"T{i},Company {i},Sector\n" for i in range(500))
        with patch("mft109.data.universe.urlopen", return_value=BytesIO(source.encode())) as network:
            first = get_universe(self.settings)
            second = get_universe(self.settings)
        network.assert_called_once()
        assert_frame_equal(first, second)
        metadata = json.loads(self.settings.universe_snapshot.with_suffix(".metadata.json").read_text())
        self.assertEqual(metadata["securities"], 500)
        self.assertEqual(metadata["universe_sha256"], universe_fingerprint(first))

    def test_duplicate_and_benchmark_contamination_rejected(self):
        with self.assertRaises(ValueError):
            validate_universe(pd.concat([universe(), universe()]))
        frame = universe()
        frame.loc[0, ["ticker", "yahoo_ticker"]] = "SPY"
        with self.assertRaises(ValueError):
            validate_universe(frame)

    def test_symbol_mapping_collision_rejected(self):
        frame = universe()
        frame.loc[0, ["ticker", "yahoo_ticker"]] = ["BRK-B", "BRK-B"]
        with self.assertRaises(ValueError):
            validate_universe(frame)

    def test_fingerprint_independent_of_row_order(self):
        self.assertEqual(universe_fingerprint(universe()), universe_fingerprint(universe().iloc[::-1]))

    def test_changed_snapshot_is_rejected_when_provenance_exists(self):
        self.save_universe()
        self.settings.universe_snapshot.with_suffix(".metadata.json").write_text(
            json.dumps({"universe_sha256": "wrong-hash"}))
        with patch("mft109.data.universe.urlopen") as network:
            with self.assertRaisesRegex(ValueError, "provenance hash"):
                get_universe(self.settings)
            network.assert_not_called()


class AcquisitionTests(TemporaryDataTest):
    def yahoo_sample(self):
        return sample().set_index("date")[["open", "high", "low", "close", "volume"]].rename(columns=str.title)

    def test_adjusted_close_without_adj_close_column(self):
        raw = self.yahoo_sample()
        result = normalize_download(raw, "AAPL")
        self.assertEqual(result.adjusted_close.tolist(), raw.Close.tolist())
        self.assertEqual(result.volume.tolist(), [1000.0, 0.0])
        self.assertEqual(result.columns.tolist(), COLUMNS)

    def test_both_yahoo_multiindex_orientations(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                raw = self.yahoo_sample()
                raw.columns = pd.MultiIndex.from_tuples([(c, "AAPL") for c in raw.columns])
                if reverse:
                    raw.columns = raw.columns.swaplevel()
                assert_frame_equal(normalize_download(raw, "AAPL"), sample())

    def test_exchange_local_dates_preserved(self):
        raw = self.yahoo_sample()
        raw.index = raw.index.tz_localize("America/New_York")
        assert_frame_equal(normalize_download(raw, "AAPL"), sample())

    def test_explicit_adjustment_and_inclusive_end(self):
        with patch("mft109.data.acquisition.yf.download", return_value=self.yahoo_sample()) as download:
            download_daily("AAPL", SHORT_BASELINE, self.settings)
        kwargs = download.call_args.kwargs
        self.assertTrue(kwargs["auto_adjust"])
        self.assertTrue(kwargs["keepna"])
        self.assertFalse(kwargs["repair"])
        self.assertEqual(kwargs["start"], "2015-01-01")
        self.assertEqual(kwargs["end"], "2015-01-06")
        self.assertEqual(kwargs["interval"], "1d")

    def test_empty_or_incomplete_download_rejected(self):
        for raw in (None, pd.DataFrame(), self.yahoo_sample().drop(columns="Close")):
            with self.subTest(raw_type=type(raw).__name__):
                with self.assertRaises(DataValidationError):
                    normalize_download(raw, "AAPL")


class ValidationCleaningTests(unittest.TestCase):
    def validate(self, frame, **kwargs):
        return validate_market_data(frame, "AAPL", SHORT_BASELINE.download_start,
                                    SHORT_BASELINE.download_end, **kwargs)

    def test_structural_failures(self):
        bad_date, unidentified, wrong_ticker, wrong_type = (sample() for _ in range(4))
        bad_date["date"] = ["not-a-date", "2015-01-05"]
        unidentified.loc[0, "ticker"] = None
        wrong_ticker["ticker"] = "SPY"
        wrong_type["volume"] = ["bad", "data"]
        for frame in (pd.DataFrame(), sample().drop(columns="close"), bad_date,
                      unidentified, wrong_ticker, wrong_type):
            with self.subTest(columns=frame.columns.tolist()):
                with self.assertRaises(DataValidationError):
                    self.validate(frame)

    def test_duplicate_detection_and_exact_duplicate_cleaning(self):
        frame = pd.concat([sample(), sample().iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(DataValidationError, "Duplicate"):
            self.validate(frame)
        cleaned, report = clean_market_data(frame)
        self.assertEqual(report["exact_duplicates_removed"], 1)
        assert_frame_equal(cleaned, sample())

    def test_conflicting_duplicates_raise(self):
        extra = sample().iloc[[0]].copy()
        extra["close"] = 999.0
        with self.assertRaisesRegex(DataValidationError, "Conflicting"):
            clean_market_data(pd.concat([sample(), extra]))

    def test_missing_values_are_never_filled_and_zero_volume_is_preserved(self):
        frame = sample()
        frame.loc[1, ["close", "adjusted_close"]] = np.nan
        frame.loc[0, "volume"] = np.nan
        cleaned, _ = clean_market_data(frame)
        self.assertTrue(pd.isna(cleaned.loc[1, "adjusted_close"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "volume"]))
        self.assertEqual(cleaned.loc[1, "volume"], 0.0)
        report = self.validate(cleaned)
        self.assertEqual(report["missing_price_rows"], 1)
        self.assertEqual(report["missing_volume_rows"], 1)
        self.assertTrue(report["warnings"])

    def test_invalid_values_become_missing_with_counts(self):
        frame = sample()
        frame.loc[0, "open"] = -1.0
        frame.loc[0, "high"] = np.inf
        frame.loc[0, "low"] = 0.0
        frame.loc[0, "volume"] = -100.0
        with self.assertRaisesRegex(DataValidationError, "Invalid values"):
            self.validate(frame)
        cleaned, report = clean_market_data(frame)
        for column in ("open", "high", "low", "volume"):
            self.assertTrue(pd.isna(cleaned.loc[0, column]))
            self.assertEqual(report["invalid_values_to_missing"][column], 1)
        self.assertEqual(len(cleaned), len(frame))

    def test_no_outlier_removal(self):
        frame = sample()
        frame.loc[1, "close"] = 1_000_000.0
        cleaned, _ = clean_market_data(frame)
        self.assertEqual(cleaned.loc[1, "close"], 1_000_000.0)

    def test_all_missing_prices_rejected(self):
        frame = sample()
        frame["adjusted_close"] = np.nan
        with self.assertRaisesRegex(DataValidationError, "No usable"):
            self.validate(frame)

    def test_coverage_warning_for_stocks_but_error_for_benchmark(self):
        for benchmark in (False, True):
            with self.subTest(benchmark=benchmark):
                if benchmark:
                    with self.assertRaisesRegex(DataValidationError, "incomplete"):
                        validate_market_data(sample(), "AAPL", date(2014, 1, 1), date(2015, 1, 5), benchmark=True)
                else:
                    report = validate_market_data(sample(), "AAPL", date(2014, 1, 1), date(2015, 1, 5))
                    self.assertIn("begins late", report["warnings"][0])

    def test_absent_sessions_reported_without_inserting_rows(self):
        frame = sample().iloc[[1]]
        report = self.validate(frame, reference_dates=sample().date)
        self.assertEqual(report["absent_reference_sessions"], 1)
        self.assertEqual(report["absent_reference_dates"], ["2015-01-02"])
        self.assertEqual(len(frame), 1)

    def test_out_of_period_and_intraday_dates_rejected(self):
        for value in (pd.Timestamp("2014-12-31"), pd.Timestamp("2015-01-02 12:00")):
            frame = sample()
            frame.loc[0, "date"] = value
            with self.assertRaises(DataValidationError):
                self.validate(frame)


class CacheTests(TemporaryDataTest):
    def load(self, **kwargs):
        return load_or_download("AAPL", "snapshot-one", baseline=SHORT_BASELINE,
                                settings=self.settings, **kwargs)

    def test_parquet_roundtrip_then_network_free_cache_hit(self):
        frame = sample()
        frame.loc[0, "volume"] = np.nan
        with patch("mft109.data.cache.download_daily", return_value=frame) as download:
            first, report = self.load()
            second, cached_report = self.load()
        download.assert_called_once()
        assert_frame_equal(first, second)
        self.assertFalse(report["cache_hit"])
        self.assertTrue(cached_report["cache_hit"])
        self.assertEqual(cached_report["missing_volume_rows"], 1)

    def test_refresh_and_changed_universe_invalidate_cache(self):
        with patch("mft109.data.cache.download_daily", return_value=sample()) as download:
            self.load()
            self.load(refresh=True)
            load_or_download("AAPL", "snapshot-two", baseline=SHORT_BASELINE, settings=self.settings)
        self.assertEqual(download.call_count, 3)

    def test_changed_dates_invalidate_cache(self):
        with patch("mft109.data.cache.download_daily", return_value=sample()) as download:
            self.load()
            load_or_download("AAPL", "snapshot-one", baseline=replace(SHORT_BASELINE, download_end=date(2015, 1, 6)), settings=self.settings)
        self.assertEqual(download.call_count, 2)

    def test_corrupt_parquet_detected_and_replaced(self):
        with patch("mft109.data.cache.download_daily", return_value=sample()) as download:
            self.load()
            (self.settings.market_cache / "stocks/AAPL.parquet").write_bytes(b"corrupt")
            _, report = self.load()
        self.assertEqual(download.call_count, 2)
        self.assertFalse(report["cache_hit"])

    def test_failed_refresh_preserves_previous_good_cache(self):
        with patch("mft109.data.cache.download_daily", return_value=sample()):
            self.load()
        path = self.settings.market_cache / "stocks/AAPL.parquet"
        before = path.read_bytes()
        with patch("mft109.data.cache.download_daily", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                self.load(refresh=True)
            _, report = self.load()
        self.assertTrue(report["cache_hit"])
        self.assertEqual(path.read_bytes(), before)

    def test_benchmark_cached_separately(self):
        with patch("mft109.data.cache.download_daily", return_value=sample("SPY")):
            load_or_download("SPY", "any", baseline=SHORT_BASELINE,
                             settings=self.settings, benchmark=True)
        self.assertTrue((self.settings.market_cache / "benchmark/SPY.parquet").exists())
        self.assertFalse((self.settings.market_cache / "stocks/SPY.parquet").exists())


class PipelineTests(TemporaryDataTest):
    def setUp(self):
        super().setUp()
        self.save_universe()

    def run_pipeline(self, **kwargs):
        return run_pipeline(baseline=SHORT_BASELINE, settings=self.settings, **kwargs)

    def test_end_to_end_then_all_cache_hits_and_fixed_snapshot(self):
        before = self.settings.universe_snapshot.read_bytes()
        with patch("mft109.data.cache.download_daily", side_effect=lambda ticker, *args: sample(ticker)) as download:
            first = self.run_pipeline()
            second = self.run_pipeline()
            self.assertEqual(download.call_count, 3)
            self.assertTrue(all(x["cache_hit"] for x in second["stocks"].values()))
            self.assertTrue(second["benchmark"]["cache_hit"])
            self.run_pipeline(refresh=True)
            self.assertEqual(download.call_count, 6)
        self.assertEqual(first["status"], "complete")
        self.assertNotIn("SPY", first["stocks"])
        self.assertEqual(self.settings.universe_snapshot.read_bytes(), before)

    def test_benchmark_failure_stops_early_and_persists_error(self):
        with patch("mft109.data.cache.download_daily", side_effect=RuntimeError("network blocked")) as download:
            with self.assertRaisesRegex(PipelineError, "benchmark unavailable"):
                self.run_pipeline()
        self.assertEqual(download.call_count, 1)
        report = json.loads(self.settings.validation_report.read_text())
        self.assertEqual(report["status"], "blocked_benchmark")
        self.assertIn("SPY", report["failed_tickers"])

    def test_stock_failure_is_not_silently_omitted(self):
        def fake_download(ticker, *args):
            if ticker == "BRK-B":
                raise RuntimeError("no history")
            return sample(ticker)
        with patch("mft109.data.cache.download_daily", side_effect=fake_download):
            with self.assertRaisesRegex(PipelineError, "BRK-B"):
                self.run_pipeline()
        report = json.loads(self.settings.validation_report.read_text())
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("AAPL", report["stocks"])
        self.assertIn("BRK-B", report["failed_tickers"])

    def test_smoke_mode_label_and_invalid_candidates(self):
        self.settings.validation_report.write_text('{"previous": "full run"}')
        with patch("mft109.data.cache.download_daily", side_effect=lambda ticker, *args: sample(ticker)):
            report = self.run_pipeline(tickers=["AAPL"])
        self.assertEqual(report["mode"], "smoke")
        self.assertEqual(report["requested_stock_tickers"], ["AAPL"])
        self.assertEqual(json.loads(self.settings.validation_report.read_text()),
                         {"previous": "full run"})
        self.assertTrue((self.root / "quality.smoke.json").is_file())
        for tickers in ([], ["SPY"], ["NOT-IN-UNIVERSE"]):
            with self.assertRaises(ValueError):
                self.run_pipeline(tickers=tickers)


if __name__ == "__main__":
    unittest.main()
