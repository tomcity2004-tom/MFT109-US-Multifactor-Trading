"""Fixed OAT catalog, scalar formulas and end-to-end synthetic scenario checks."""

from dataclasses import FrozenInstanceError, replace
import math
import statistics
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from mft109.analysis.performance import analyze_performance
from mft109.backtesting.engine import run_backtest, MissingHoldingPriceError
from mft109.backtesting.transaction_costs import transaction_cost_fraction
from mft109.config import BASELINE
from mft109.factors import calculate_raw_factors, calculate_volatility, calculate_reversal
from mft109.optimization.scenarios import Scenario, VALUES, WEIGHTS, BASE_VALUES, approved_scenarios
from mft109.optimization.sensitivity import run_sensitivity
from mft109.processing import score_factors
from mft109.ranking import rank_and_select


def sample_prices():
    calendar = pd.bdate_range("2015-01-02", "2025-12-31").difference(pd.DatetimeIndex(["2016-01-01"]))
    t = np.arange(len(calendar), dtype=float)
    tickers = [f"T{i:02}" for i in range(55)]
    rows = []
    for i, ticker in enumerate(tickers):
        price = (30 + i) * np.exp(.00012 * t + .00004 * i * t / 55 + .08 * np.sin(t / (9 + i)))
        rows.append(pd.DataFrame({"date": calendar, "ticker": ticker,
                                  "adjusted_close": price, "volume": 100000. * (i + 1)}))
    return calendar, tickers, pd.concat(rows, ignore_index=True), pd.Series(100 * np.exp(.00015*t), index=calendar)


class CatalogTests(unittest.TestCase):
    def test_exact_six_groups_and_twenty_one_rows(self):
        self.assertEqual(len(approved_scenarios()), 21)
        self.assertEqual([len(v) for v in VALUES.values()], [4, 4, 2, 3, 3, 5])

    def test_exact_top_n_values(self):
        self.assertEqual(VALUES["top_n"], (10, 20, 30, 50))

    def test_exact_cost_values(self):
        self.assertEqual(VALUES["transaction_cost_bps"], (0, 5, 10, 20))

    def test_exact_rebalance_values(self):
        self.assertEqual(VALUES["rebalance_frequency"], ("monthly", "quarterly"))

    def test_exact_volatility_values(self):
        self.assertEqual(VALUES["volatility_window"], (20, 60, 120))

    def test_exact_reversal_values(self):
        self.assertEqual(VALUES["reversal_window"], (5, 10, 20))

    def test_exact_five_weight_scenarios(self):
        self.assertEqual(len(WEIGHTS), 5)
        for name, weights in WEIGHTS.items():
            with self.subTest(name=name):
                self.assertEqual(sum(weights), 1.)
                self.assertEqual(sorted(weights), [.25]*4 if name == "equal" else [.2, .2, .2, .4])

    def test_one_baseline_per_group(self):
        self.assertEqual(sum(s.is_baseline for s in approved_scenarios()), 6)

    def test_one_dimension_changes_only(self):
        for scenario in approved_scenarios():
            different = [key for key in BASE_VALUES if scenario.parameter(key) != BASE_VALUES[key]]
            self.assertEqual(different, [] if scenario.is_baseline else [scenario.experiment])

    def test_invalid_arbitrary_values_and_combination_rejected(self):
        for group, value in (("top_n", 15), ("transaction_cost_bps", 100), ("factor_weights", "custom"),
                             ("combined", "anything"), ("top_n", True), ("top_n", 20.)):
            with self.subTest(group=group, value=value), self.assertRaises(ValueError):
                Scenario(group, value)

    def test_scenarios_and_catalog_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            Scenario("top_n", 10).value = 20
        with self.assertRaises(TypeError):
            VALUES["top_n"] = (1,)

    def test_baseline_config_unchanged(self):
        self.assertEqual((BASELINE.top_n, BASELINE.transaction_cost_rate, BASELINE.rebalance_frequency), (20,.001,"monthly"))


class FormulaTests(unittest.TestCase):
    def setUp(self):
        self.sessions = pd.bdate_range("2015-01-02", periods=300)
        t = np.arange(300, dtype=float)
        self.price = pd.Series(30*np.exp(.001*t+.02*np.sin(t/7)), index=self.sessions)

    def test_volatility_20_scalar(self):
        self.check_volatility(20)

    def test_volatility_60_scalar(self):
        self.check_volatility(60)

    def test_volatility_120_scalar(self):
        self.check_volatility(120)

    def check_volatility(self, k):
        actual = calculate_volatility(self.price, sessions=self.sessions, window=k)
        scalar = [float(self.price.iloc[j])/float(self.price.iloc[j-1])-1 for j in range(200-k+1,201)]
        self.assertAlmostEqual(actual.iloc[200], statistics.stdev(scalar)*math.sqrt(252), places=12)
        self.assertTrue(actual.iloc[:k].isna().all())
        self.assertTrue(pd.notna(actual.iloc[k]))

    def test_reversal_5_scalar(self):
        self.check_reversal(5)

    def test_reversal_10_scalar(self):
        self.check_reversal(10)

    def test_reversal_20_scalar(self):
        self.check_reversal(20)

    def check_reversal(self, k):
        actual = calculate_reversal(self.price, sessions=self.sessions, window=k)
        self.assertAlmostEqual(actual.iloc[200], -(self.price.iloc[200]/self.price.iloc[200-k]-1))
        self.assertTrue(actual.iloc[:k].isna().all())

    def test_missing_inside_volatility_window_not_filled(self):
        price = self.price.copy()
        price.iloc[180] = np.nan
        for k in (20,60,120):
            self.assertTrue(pd.isna(calculate_volatility(price,sessions=self.sessions,window=k).iloc[190]))

    def test_missing_reversal_endpoint_not_filled(self):
        for k in (5,10,20):
            price = self.price.copy()
            price.iloc[200-k] = np.nan
            self.assertTrue(pd.isna(calculate_reversal(price,sessions=self.sessions,window=k).iloc[200]))

    def test_cost_rates_scalar_and_monotonic(self):
        values=[transaction_cost_fraction(.3, scenario=Scenario("transaction_cost_bps", bps)) for bps in (0,5,10,20)]
        np.testing.assert_allclose(values,[0,.00015,.00030,.00060],rtol=0,atol=1e-18)
        self.assertEqual(values, sorted(values))

    def test_unapproved_windows_rejected(self):
        for fn in (calculate_volatility,calculate_reversal):
            with self.assertRaises(ValueError):
                fn(self.price,sessions=self.sessions,window=7)

    def test_changed_future_prices_leave_raw_factor_prefix_unchanged(self):
        future=self.price.copy()
        future.iloc[220:]*=2
        for fn,windows in ((calculate_volatility,(20,60,120)),(calculate_reversal,(5,10,20))):
            for k in windows:
                assert_series_equal(fn(self.price,sessions=self.sessions,window=k).iloc[:220],
                                    fn(future,sessions=self.sessions,window=k).iloc[:220])


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions,cls.tickers,cls.market,cls.spy = sample_prices()
        cls.original = cls.market.copy(deep=True)
        with patch("yfinance.download",side_effect=AssertionError("No downloads")):
            cls.results = run_sensitivity(cls.market,cls.spy,sessions=cls.sessions,tickers=cls.tickers)
        cls.raw = calculate_raw_factors(cls.market,sessions=cls.sessions,tickers=cls.tickers)
        cls.scored = score_factors(cls.raw)
        cls.selection = rank_and_select(cls.scored,sessions=cls.sessions)
        cls.bt = run_backtest(cls.selection,cls.market,cls.spy,sessions=cls.sessions)
        cls.performance = analyze_performance(cls.bt.daily,sessions=cls.sessions)

    def run_for(self,group,value):
        return self.results.runs[Scenario(group,value).name]

    def test_baseline_reproduction_all_six_groups(self):
        for group,value in BASE_VALUES.items():
            run=self.run_for(group,value)
            assert_frame_equal(run.selection.ranked,self.selection.ranked)
            assert_frame_equal(run.backtest.daily,self.bt.daily)
            assert_frame_equal(run.performance.performance_summary,self.performance.performance_summary)

    def test_top_n_10(self):
        self.check_n(10)

    def test_top_n_20(self):
        self.check_n(20)

    def test_top_n_30(self):
        self.check_n(30)

    def test_top_n_50(self):
        self.check_n(50)

    def check_n(self,n):
        run=self.run_for("top_n",n)
        self.assertTrue(run.selection.formation_summary.selected_count.eq(n).all())
        target=run.backtest.rebalance_weights.query("executable")
        np.testing.assert_allclose(target.target_weight,1/n)

    def test_rankings_unchanged_across_top_n(self):
        for n in (10,20,30,50):
            run=self.run_for("top_n",n)
            assert_frame_equal(run.selection.ranked.drop(columns="selected"),self.selection.ranked.drop(columns="selected"))

    def test_shortage_selects_only_available_names(self):
        run=rank_and_select(self.scored.loc[self.scored.ticker.isin(self.tickers[:8])],sessions=self.sessions,scenario=Scenario("top_n",50))
        self.assertTrue(run.formation_summary.selected_count.eq(8).all())

    def test_cost_paths_preserve_selection_and_turnover(self):
        for bps in (0,5,10,20):
            run=self.run_for("transaction_cost_bps",bps)
            assert_frame_equal(run.selection.ranked,self.selection.ranked)
            a=run.backtest.rebalance_audit.query('status == "executed"')
            base=self.bt.rebalance_audit.query('status == "executed"')
            np.testing.assert_allclose(a.turnover,base.turnover,atol=1e-14)
            np.testing.assert_allclose(a.transaction_cost_fraction,a.turnover*bps/10000,atol=1e-16)

    def test_cost_10_bps_exact_baseline(self):
        assert_frame_equal(self.run_for("transaction_cost_bps",10).backtest.daily,self.bt.daily)

    def test_quarterly_formation_dates(self):
        run=self.run_for("rebalance_frequency","quarterly")
        dates=run.selection.formation_summary.formation_date
        self.assertEqual(len(dates),40)
        self.assertTrue(dates.dt.month.isin([3,6,9,12]).all())
        self.assertEqual(dates.iloc[0],pd.Timestamp("2016-03-31"))

    def test_quarterly_execution_and_end_boundary(self):
        audit=self.run_for("rebalance_frequency","quarterly").backtest.rebalance_audit
        self.assertEqual(audit.execution_date.iloc[0],pd.Timestamp("2016-04-01"))
        self.assertEqual(audit.execution_date.notna().sum(),39)
        self.assertTrue(pd.isna(audit.execution_date.iloc[-1]))
        for row in audit.loc[audit.execution_date.notna()].itertuples():
            self.assertEqual(row.execution_date,self.sessions[self.sessions.searchsorted(row.formation_date,side="right")])

    def test_quarterly_cash_before_first_execution(self):
        d=self.run_for("rebalance_frequency","quarterly").backtest.daily
        self.assertTrue(d.loc[d.date.lt("2016-04-01"),"strategy_nav"].eq(1).all())

    def test_all_weight_composites_and_directions(self):
        for name,weights in WEIGHTS.items():
            scored=score_factors(self.raw,scenario=Scenario("factor_weights",name))
            expected=(weights[0]*scored.momentum_score+weights[1]*scored.low_volatility_score
                      +weights[2]*scored.liquidity_score+weights[3]*scored.reversal_score)
            np.testing.assert_allclose(scored.composite_score,expected,equal_nan=True)
            for col in ("momentum_score","low_volatility_score","liquidity_score","reversal_score"):
                assert_series_equal(scored[col],self.scored[col])

    def test_equal_weights_exact_baseline_score(self):
        assert_frame_equal(score_factors(self.raw,scenario=Scenario("factor_weights","equal")),self.scored)

    def test_all_tables_required_fields_and_counts(self):
        required={"experiment","scenario","parameter_value","is_baseline","Cumulative Return",
                  "Annualized Return","Annualized Volatility","Sharpe Ratio","Maximum Drawdown","Final NAV","Final Portfolio Value"}
        self.assertEqual(sum(map(len,self.results.tables.values())),21)
        for group,values in VALUES.items():
            table=self.results.tables[group]
            self.assertEqual(len(table),len(values))
            self.assertTrue(required.issubset(table.columns))
            self.assertEqual(table.is_baseline.sum(),1)

    def test_input_immutability(self):
        assert_frame_equal(self.market,self.original)

    def test_spy_identical_for_every_scenario(self):
        for run in self.results.runs.values():
            assert_series_equal(run.backtest.daily.spy_nav,self.bt.daily.spy_nav)

    def test_window_changes_preserve_other_raw_factors_and_missing_eligibility(self):
        subset=self.market.loc[self.market.ticker.isin(self.tickers[:3])].copy()
        for group,value,changed in (("volatility_window",120,"volatility60"),("reversal_window",5,"reversal20")):
            base=calculate_raw_factors(subset,sessions=self.sessions,tickers=self.tickers[:3])
            variant=calculate_raw_factors(subset,sessions=self.sessions,tickers=self.tickers[:3],scenario=Scenario(group,value))
            assert_frame_equal(base.drop(columns=changed),variant.drop(columns=changed))
            scored=score_factors(variant)
            self.assertFalse(scored.loc[scored[changed].isna(),"eligible"].any())

    def test_future_change_preserves_scenario_scores_rank_selection_and_returns(self):
        scenario=Scenario("factor_weights","reversal_tilt")
        future=self.raw.copy()
        future.loc[future.date.ge("2025-01-01"),"reversal20"] *= -3
        scores1=score_factors(self.raw,scenario=scenario)
        scores2=score_factors(future,scenario=scenario)
        assert_frame_equal(scores1.loc[scores1.date.lt("2025-01-01")],scores2.loc[scores2.date.lt("2025-01-01")])
        a=rank_and_select(scores1,sessions=self.sessions,scenario=scenario)
        b=rank_and_select(scores2,sessions=self.sessions,scenario=scenario)
        assert_frame_equal(a.ranked.loc[a.ranked.formation_date.lt("2025-01-01")],b.ranked.loc[b.ranked.formation_date.lt("2025-01-01")])
        first=run_backtest(a,self.market,self.spy,sessions=self.sessions,scenario=scenario)
        second=run_backtest(b,self.market,self.spy,sessions=self.sessions,scenario=scenario)
        assert_frame_equal(first.daily.loc[first.daily.date.lt("2025-01-01")],second.daily.loc[second.daily.date.lt("2025-01-01")])

    def test_shuffled_scores_deterministic_for_nonbaseline_top_n(self):
        s=Scenario("top_n",30)
        a=rank_and_select(self.scored,sessions=self.sessions,scenario=s)
        b=rank_and_select(self.scored.sample(frac=1,random_state=4),sessions=self.sessions,scenario=s)
        assert_frame_equal(a.ranked,b.ranked)

    def test_missing_held_price_policy_preserved_for_scenario(self):
        s=Scenario("top_n",10)
        run=self.run_for("top_n",10)
        day=pd.Timestamp("2016-02-02")
        ticker=run.selection.selected.ticker.iloc[0]
        market=self.market.copy()
        market.loc[market.date.eq(day)&market.ticker.eq(ticker),"adjusted_close"]=np.nan
        with self.assertLogs("mft109.backtesting.engine",level="ERROR"),self.assertRaises(MissingHoldingPriceError):
            run_backtest(run.selection,market,self.spy,sessions=self.sessions,scenario=s)

    def test_blocked_scenario_retained_without_official_performance_and_others_continue(self):
        prefix=replace(self.bt,daily=self.bt.daily.loc[self.bt.daily.date.lt("2016-02-02")].copy())
        error=MissingHoldingPriceError(pd.Timestamp("2016-02-02"),("T01",),prefix)
        def execute(*args,scenario=None,**kwargs):
            if scenario is None:
                return self.bt
            if scenario == Scenario("top_n",30):
                raise error
            return self.results.runs[scenario.name].backtest
        with patch("mft109.optimization.sensitivity.run_backtest",side_effect=execute), \
                patch("mft109.optimization.sensitivity.calculate_raw_factors",return_value=self.raw):
            result=run_sensitivity(self.market,self.spy,sessions=self.sessions,tickers=self.tickers)
        self.assertEqual(sum(map(len,result.tables.values())),21)
        row=result.tables["top_n"].loc[lambda t:t.scenario.eq("top_n:30")].iloc[0]
        self.assertEqual(row.status,"blocked_missing_holding_price")
        self.assertFalse(row.official_period_complete)
        self.assertTrue(pd.isna(row["Annualized Return"]))
        self.assertTrue(pd.isna(row["Final NAV"]))
        self.assertEqual(row.blocking_date,pd.Timestamp("2016-02-02"))
        self.assertEqual(row.blocking_tickers,"T01")
        self.assertIsNone(result.runs["top_n:30"].performance)
        self.assertTrue(result.tables["factor_weights"].official_period_complete.all())


if __name__ == "__main__":
    unittest.main()
