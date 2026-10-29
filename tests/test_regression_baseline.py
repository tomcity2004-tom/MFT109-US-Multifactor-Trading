"""Approved Phase 7 revised-data reference; no golden values in production logic."""

import unittest

from phase8_support import baseline_run, APPROVED_FINAL_NAV, APPROVED_FINAL_USD, APPROVED_SPY_NAV


class ApprovedBaselineRegressionTests(unittest.TestCase):
    def test_revised_strategy_final_nav(self):
        self.assertAlmostEqual(baseline_run().backtest.daily.strategy_nav.iloc[-1],APPROVED_FINAL_NAV,delta=1e-11)

    def test_revised_strategy_final_usd(self):
        self.assertAlmostEqual(baseline_run().backtest.daily.portfolio_value_usd.iloc[-1],APPROVED_FINAL_USD,delta=1e-6)

    def test_spy_final_nav(self):
        self.assertAlmostEqual(baseline_run().backtest.daily.spy_nav.iloc[-1],APPROVED_SPY_NAV,delta=1e-11)

    def test_reviewed_data_version_selection_change_is_retained(self):
        selected=baseline_run().selection.selected
        names=set(selected.loc[selected.formation_date.eq("2025-11-28"),"ticker"])
        self.assertIn("PANW",names)
        self.assertNotIn("V",names)


if __name__ == "__main__":
    unittest.main()
