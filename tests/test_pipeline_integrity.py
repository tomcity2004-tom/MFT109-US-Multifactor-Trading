"""Cross-module leakage, stale-score exclusion and approved scenario integration."""

import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from mft109.config import BASELINE
from mft109.factors import calculate_raw_factors
from mft109.optimization.scenarios import BASE_VALUES, VALUES, approved_scenarios
from mft109.processing import score_factors
from mft109.ranking import rank_and_select
from phase8_support import approved_cache, baseline_run, pipeline, sensitivity_run, protected_hashes, offline


class CrossModuleLookAheadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache=approved_cache()
        cls.tickers=["AAPL","MSFT","BRK-B"]
        market=cls.cache.market.loc[cls.cache.market.ticker.isin(cls.tickers)].copy()
        future=market.copy(deep=True)
        cls.cutoff=pd.Timestamp("2020-07-01")
        future.loc[future.date.ge(cls.cutoff)&future.ticker.eq("AAPL"),"adjusted_close"]*=2
        spy=cls.cache.spy.set_index("date").adjusted_close
        cls.before=pipeline(market,cls.cache.sessions,cls.tickers,spy)
        cls.changed=pipeline(future,cls.cache.sessions,cls.tickers,spy)
        cls.original_market=market

    def test_future_prices_do_not_change_past_raw_standardized_or_composite_values(self):
        for name in ("raw","scored"):
            a,b=getattr(self.before,name),getattr(self.changed,name)
            assert_frame_equal(a.loc[a.date.lt(self.cutoff)],b.loc[b.date.lt(self.cutoff)])

    def test_future_prices_do_not_change_earlier_rankings_or_selection(self):
        a,b=self.before.selection.ranked,self.changed.selection.ranked
        assert_frame_equal(a.loc[a.formation_date.lt(self.cutoff)],b.loc[b.formation_date.lt(self.cutoff)])

    def test_future_prices_do_not_change_prior_execution_weights_turnover_costs_or_nav(self):
        for name,col in (("daily","date"),("holdings","date"),
                         ("rebalance_audit","execution_date"),("rebalance_weights","execution_date")):
            a,b=getattr(self.before.backtest,name),getattr(self.changed.backtest,name)
            assert_frame_equal(a.loc[a[col].lt(self.cutoff)],b.loc[b[col].lt(self.cutoff)])

    def test_missing_formation_observation_is_not_replaced_with_previous_scores(self):
        market=self.original_market.loc[~(self.original_market.ticker.eq("AAPL")
                                        &self.original_market.date.eq("2020-05-29"))].copy()
        with offline():
            raw=calculate_raw_factors(market,sessions=self.cache.sessions,tickers=self.tickers)
            scored=score_factors(raw)
            selection=rank_and_select(scored,sessions=self.cache.sessions)
        row=scored.loc[scored.ticker.eq("AAPL")&scored.date.eq("2020-05-29")]
        self.assertEqual(len(row),1)
        self.assertFalse(row.eligible.iloc[0])
        self.assertTrue(pd.isna(row.composite_score.iloc[0]))
        self.assertTrue(row[["volatility60","liquidity_raw","reversal20"]].isna().all().all())
        self.assertNotIn("AAPL",selection.selected.loc[selection.selected.formation_date.eq("2020-05-29"),"ticker"].values)
        previous=scored.loc[scored.ticker.eq("AAPL")&scored.date.eq("2020-05-28")]
        self.assertTrue(previous.eligible.iloc[0])


class SensitivityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache=approved_cache()
        cls.baseline=baseline_run()
        cls.result=sensitivity_run()

    def test_exact_approved_oat_scenarios_not_a_cartesian_search(self):
        self.assertEqual(len(self.result.runs),21)
        self.assertEqual(sum(map(len,self.result.tables.values())),21)
        for scenario in approved_scenarios():
            changes=[key for key in BASE_VALUES if scenario.parameter(key)!=BASE_VALUES[key]]
            self.assertEqual(changes,[] if scenario.is_baseline else [scenario.experiment])
        for group,values in VALUES.items():
            table=self.result.tables[group]
            self.assertEqual(table.parameter_value.tolist(),list(map(str,values)))
            self.assertEqual(table.is_baseline.sum(),1)

    def test_all_21_revised_data_scenarios_complete_with_required_metrics(self):
        required=["Cumulative Return","Annualized Return","Annualized Volatility","Sharpe Ratio",
                  "Maximum Drawdown","Final NAV","Final Portfolio Value"]
        for table in self.result.tables.values():
            self.assertTrue(table.official_period_complete.all())
            self.assertTrue(table.status.eq("complete").all())
            self.assertTrue(np.isfinite(table[required].to_numpy()).all())
        for run in self.result.runs.values():
            self.assertIsNone(run.error)
            self.assertEqual(len(run.backtest.daily),2514)
            self.assertEqual(run.backtest.daily.date.iloc[-1],pd.Timestamp("2025-12-31"))
            self.assertTrue(run.backtest.missing_price_events.empty)

    def test_six_baseline_rows_match_independent_full_baseline_run(self):
        for group,value in BASE_VALUES.items():
            run=self.result.runs[f"{group}:{value}"]
            assert_frame_equal(run.selection.ranked,self.baseline.selection.ranked)
            assert_frame_equal(run.backtest.daily,self.baseline.backtest.daily)
            assert_frame_equal(run.backtest.rebalance_weights,self.baseline.backtest.rebalance_weights)
            assert_frame_equal(run.performance.performance_summary,self.baseline.performance.performance_summary)

    def test_two_previously_blocked_scenarios_use_reported_price_without_stop(self):
        for name in ("reversal_window:5","factor_weights:reversal_tilt"):
            run=self.result.runs[name]
            holding=run.backtest.holdings.loc[run.backtest.holdings.date.eq("2025-11-12")
                                            &run.backtest.holdings.ticker.eq("FISV")]
            self.assertEqual(len(holding),1)
            self.assertAlmostEqual(holding.adjusted_close.iloc[0],64.37999725341797,places=12)
            self.assertGreater(holding.units.iloc[0],0)
            self.assertTrue(run.backtest.missing_price_events.empty)

    def test_shared_spy_and_quarterly_schedule_unchanged(self):
        for run in self.result.runs.values():
            np.testing.assert_array_equal(run.backtest.daily.spy_nav,self.baseline.backtest.daily.spy_nav)
        quarter=self.result.runs["rebalance_frequency:quarterly"].backtest.rebalance_audit
        self.assertEqual(len(quarter),40)
        self.assertEqual(quarter.execution_date.notna().sum(),39)
        self.assertEqual(quarter.execution_date.iloc[0],pd.Timestamp("2016-04-01"))
        for row in quarter.loc[quarter.execution_date.notna()].itertuples():
            self.assertIn(row.formation_date.month,(3,6,9,12))
            self.assertEqual(row.execution_date,self.cache.sessions[self.cache.sessions.searchsorted(row.formation_date,side="right")])

    def test_no_cache_universe_output_configuration_or_production_file_changes(self):
        self.assertEqual(protected_hashes(),self.cache.hashes)
        self.assertEqual((BASELINE.top_n,BASELINE.transaction_cost_rate,BASELINE.volatility_lookback_days,
                          BASELINE.reversal_lookback_days,BASELINE.momentum_weight,BASELINE.low_volatility_weight,
                          BASELINE.liquidity_weight,BASELINE.reversal_weight),
                         (20,.001,60,20,.25,.25,.25,.25))


if __name__ == "__main__":
    unittest.main()
