"""Validate baseline configuration and scaffold importability without market data."""

from dataclasses import FrozenInstanceError
from datetime import date
import importlib
import pkgutil
import unittest

import mft109
from mft109.config import BASELINE, PROJECT_ROOT, BASELINE_OUTPUT_DIR, OPTIMIZATION_OUTPUT_DIR


class ConfigurationTests(unittest.TestCase):
    def test_approved_baseline_settings(self):
        self.assertEqual(
            (BASELINE.momentum_lookback_days, BASELINE.momentum_skip_days,
             BASELINE.volatility_lookback_days, BASELINE.liquidity_lookback_days,
             BASELINE.reversal_lookback_days),
            (252, 21, 60, 20, 20),
        )
        weights = (BASELINE.momentum_weight, BASELINE.low_volatility_weight,
                   BASELINE.liquidity_weight, BASELINE.reversal_weight)
        self.assertEqual(weights, (0.25, 0.25, 0.25, 0.25))
        self.assertEqual(sum(weights), 1.0)
        self.assertEqual(BASELINE.top_n, 20)
        self.assertEqual(BASELINE.transaction_cost_rate, 10 / 10_000)
        self.assertEqual(BASELINE.risk_free_rate, 0.0)
        self.assertEqual(BASELINE.initial_capital_usd, 100_000.0)
        self.assertEqual(BASELINE.initial_nav, 1.0)
        self.assertEqual(BASELINE.benchmark, "SPY")
        self.assertEqual(BASELINE.price_basis, "adjusted")
        self.assertTrue(BASELINE.require_all_four_factors)

    def test_research_dates_and_output_separation(self):
        self.assertEqual(BASELINE.download_start, date(2015, 1, 1))
        self.assertEqual(BASELINE.backtest_start, date(2016, 1, 1))
        self.assertEqual(BASELINE.download_end, date(2025, 12, 31))
        self.assertEqual(BASELINE.backtest_end, BASELINE.download_end)
        self.assertLess(BASELINE.download_start, BASELINE.backtest_start)
        self.assertNotEqual(BASELINE_OUTPUT_DIR, OPTIMIZATION_OUTPUT_DIR)
        self.assertTrue((PROJECT_ROOT / "PROJECT_REQUIREMENTS.md").is_file())

    def test_baseline_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            BASELINE.top_n = 10

    def test_scaffold_modules_import(self):
        modules = list(pkgutil.walk_packages(mft109.__path__, mft109.__name__ + "."))
        self.assertTrue(modules)
        for module in modules:
            with self.subTest(module=module.name):
                importlib.import_module(module.name)


if __name__ == "__main__":
    unittest.main()
