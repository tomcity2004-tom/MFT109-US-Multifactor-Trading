"""Repeat the full approved baseline, not only reads of saved output files."""

import unittest
from pandas.testing import assert_frame_equal

from phase8_support import baseline_run


class ReproducibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first, cls.second = baseline_run(), baseline_run(repeat=True)

    def test_repeated_raw_scores_rankings_and_selected_names(self):
        for a,b in ((self.first.raw,self.second.raw),(self.first.scored,self.second.scored),
                    (self.first.selection.ranked,self.second.selection.ranked),
                    (self.first.selection.formation_summary,self.second.selection.formation_summary)):
            assert_frame_equal(a,b,check_exact=False,rtol=1e-12,atol=1e-12)

    def test_repeated_holdings_weights_turnover_costs_returns_and_nav(self):
        for name in self.first.backtest.__dataclass_fields__:
            assert_frame_equal(getattr(self.first.backtest,name),getattr(self.second.backtest,name),
                               check_exact=False,rtol=1e-12,atol=1e-10)

    def test_repeated_performance_daily_and_annual_tables(self):
        for name in self.first.performance.__dataclass_fields__:
            assert_frame_equal(getattr(self.first.performance,name),getattr(self.second.performance,name),
                               check_exact=False,rtol=1e-12,atol=1e-12)


if __name__ == "__main__":
    unittest.main()
