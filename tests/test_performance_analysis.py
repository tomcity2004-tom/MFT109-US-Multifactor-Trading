"""Independent deterministic Phase 6 formulas, annual boundaries and input safety."""

import math
import statistics
import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from mft109.analysis.performance import (
    METRICS, analyze_performance, annual_returns, drawdown_series, performance_metrics,
)


def series(values, dates=None):
    return pd.Series(values, index=pd.to_datetime(dates) if dates is not None
                     else pd.bdate_range("2016-01-04", periods=len(values)), dtype=float)


def returns(nav):
    result = nav / nav.shift(1) - 1
    result.iloc[0] = 0.
    return result


def daily():
    nav = series([1., 1.1, .99, 1.2, 1.08])
    spy = series([1., .9, 1., 1.1, 1.05])
    return pd.DataFrame({"date": nav.index, "strategy_nav": nav.to_numpy(),
                         "strategy_return": returns(nav).to_numpy(),
                         "portfolio_value_usd": nav.to_numpy() * 100000,
                         "spy_nav": spy.to_numpy(), "spy_return": returns(spy).to_numpy()})


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.nav = series([1., 1.1, .99, 1.2, 1.08])
        self.ret = returns(self.nav)
        self.metrics = performance_metrics(self.nav, self.ret)

    def test_cumulative_nav_ratio(self):
        self.assertAlmostEqual(self.metrics["Cumulative Return"], .08)

    def test_cumulative_is_not_sum_of_returns(self):
        self.assertNotAlmostEqual(self.metrics["Cumulative Return"], self.ret.sum())

    def test_non_normalized_nav_ratio(self):
        self.assertAlmostEqual(performance_metrics(self.nav * 100, self.ret)["Cumulative Return"], .08)

    def test_cagr_excludes_initial_anchor(self):
        self.assertAlmostEqual(self.metrics["Annualized Return"], 1.08 ** (252 / 4) - 1)

    def test_cagr_is_not_arithmetic_annualization(self):
        self.assertNotAlmostEqual(self.metrics["Annualized Return"], self.ret.iloc[1:].mean() * 252)

    def test_sample_volatility_matches_independent_stdev(self):
        expected = statistics.stdev(self.ret.iloc[1:].tolist()) * math.sqrt(252)
        self.assertAlmostEqual(self.metrics["Annualized Volatility"], expected)

    def test_anchor_is_not_a_volatility_observation(self):
        self.assertNotAlmostEqual(self.metrics["Annualized Volatility"], statistics.stdev(self.ret.tolist()) * math.sqrt(252))

    def test_sharpe_uses_cagr_over_volatility(self):
        expected = (1.08 ** (252 / 4) - 1) / (statistics.stdev(self.ret.iloc[1:].tolist()) * math.sqrt(252))
        self.assertAlmostEqual(self.metrics["Sharpe Ratio"], expected)

    def test_zero_volatility_sharpe_nan(self):
        nav = series([1., 1., 1.])
        metric = performance_metrics(nav, returns(nav))
        self.assertEqual(metric["Annualized Volatility"], 0.)
        self.assertTrue(math.isnan(metric["Sharpe Ratio"]))

    def test_constant_positive_returns_zero_volatility(self):
        nav = series([1., 1.01, 1.01 ** 2, 1.01 ** 3])
        ret = series([0., .01, .01, .01])
        metric = performance_metrics(nav, ret)
        self.assertEqual(metric["Annualized Volatility"], 0.)
        self.assertTrue(math.isnan(metric["Sharpe Ratio"]))

    def test_running_peak(self):
        nav = series([1., 1.2, .9, 1.1, 1.3, .65])
        np.testing.assert_allclose(drawdown_series(nav).running_peak, [1., 1.2, 1.2, 1.2, 1.3, 1.3])

    def test_daily_drawdown(self):
        nav = series([1., 1.2, .9, 1.1, 1.3, .65])
        np.testing.assert_allclose(drawdown_series(nav).drawdown, [0, 0, -.25, 1.1 / 1.2 - 1, 0, -.5])

    def test_maximum_drawdown_is_minimum(self):
        nav = series([1., 1.2, .9, 1.1, 1.3, .65])
        self.assertAlmostEqual(performance_metrics(nav, returns(nav))["Maximum Drawdown"], -.5)

    def test_monotone_nav_drawdown_zero(self):
        nav = series([1., 1.1, 1.2])
        self.assertTrue(drawdown_series(nav).drawdown.eq(0).all())

    def test_single_observation(self):
        result = performance_metrics(series([1.]), series([0.]))
        self.assertEqual(result["Cumulative Return"], 0.)
        self.assertEqual(result["Maximum Drawdown"], 0.)
        self.assertTrue(result.iloc[1:4].isna().all())

    def test_single_return_has_undefined_sample_volatility(self):
        nav = series([1., 1.01])
        result = performance_metrics(nav, returns(nav))
        self.assertAlmostEqual(result["Annualized Return"], 1.01 ** 252 - 1)
        self.assertTrue(math.isnan(result["Annualized Volatility"]))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            performance_metrics(series([]), series([]))

    def test_missing_nonpositive_infinite_nav_rejected(self):
        for value in (np.nan, 0., -1., np.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                performance_metrics(series([1., value]), series([0., .1]))

    def test_missing_returns_rejected(self):
        ret = self.ret.copy()
        ret.iloc[2] = np.nan
        with self.assertRaises(ValueError):
            performance_metrics(self.nav, ret)

    def test_duplicate_dates_rejected(self):
        nav = series([1., 1.1], ["2016-01-04", "2016-01-04"])
        with self.assertRaises(ValueError):
            performance_metrics(nav, returns(nav))

    def test_unsorted_dates_sorted_deterministically(self):
        actual = performance_metrics(self.nav.iloc[::-1], self.ret.iloc[::-1])
        assert_series_equal(actual, self.metrics)

    def test_misaligned_dates_rejected(self):
        ret = self.ret.copy()
        ret.index = ret.index + pd.Timedelta(days=30)
        with self.assertRaises(ValueError):
            performance_metrics(self.nav, ret)

    def test_inconsistent_returns_rejected(self):
        ret = self.ret.copy()
        ret.iloc[2] = .7
        with self.assertRaises(ValueError):
            performance_metrics(self.nav, ret)

    def test_nonzero_anchor_rejected(self):
        ret = self.ret.copy()
        ret.iloc[0] = .01
        with self.assertRaises(ValueError):
            performance_metrics(self.nav, ret)

    def test_nonnumeric_nav_rejected(self):
        with self.assertRaises(TypeError):
            performance_metrics(self.nav.astype(str), self.ret)

    def test_timezone_or_intraday_dates_rejected(self):
        for index in (self.nav.index.tz_localize("UTC"), self.nav.index + pd.Timedelta(hours=1)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                drawdown_series(pd.Series(self.nav.to_numpy(), index=index))


class AnnualTests(unittest.TestCase):
    def setUp(self):
        self.nav = series([1., 1.1, 1.21, 1.32], ["2016-01-04", "2016-12-30", "2017-01-03", "2017-12-29"])

    def test_first_year_anchor(self):
        self.assertAlmostEqual(annual_returns(self.nav).iloc[0]["Return"], .1)

    def test_january_move_not_lost(self):
        self.assertAlmostEqual(annual_returns(self.nav).iloc[1]["Return"], .2)

    def test_no_december_31_session_required(self):
        result = annual_returns(self.nav)
        self.assertEqual(result.iloc[1]["End Date"], pd.Timestamp("2017-12-29"))
        self.assertFalse(result["Partial Year"].any())

    def test_annual_returns_link_to_total_return(self):
        self.assertAlmostEqual(float((1 + annual_returns(self.nav)["Return"]).prod()), 1.32)

    def test_partial_year_flag(self):
        nav = series([1., 1.1], ["2016-06-01", "2016-07-01"])
        self.assertTrue(annual_returns(nav)["Partial Year"].all())

    def test_missing_intervening_year_not_bridged(self):
        nav = series([1., 2., 3.], ["2016-12-30", "2018-01-02", "2018-12-31"])
        result = annual_returns(nav)
        self.assertEqual(result.Year.tolist(), [2016, 2018])
        self.assertAlmostEqual(result.iloc[-1]["Return"], .5)
        self.assertTrue(result.iloc[-1]["Partial Year"])

    def test_annual_future_invariance(self):
        prefix = annual_returns(self.nav.loc[:"2016-12-31"])
        changed = self.nav.copy()
        changed.loc[changed.index.year == 2017] *= 2
        assert_frame_equal(prefix, annual_returns(changed).iloc[:1])


class AnalysisTests(unittest.TestCase):
    def test_summary_structure_and_independent_values(self):
        frame = daily()
        result = analyze_performance(frame)
        self.assertEqual(result.performance_summary.columns.tolist(), ["Metric", "Strategy", "SPY"])
        self.assertEqual(result.performance_summary.Metric.tolist(), METRICS)
        self.assertAlmostEqual(result.performance_summary.Strategy.iloc[0], .08)
        self.assertAlmostEqual(result.performance_summary.SPY.iloc[0], .05)

    def test_daily_columns_and_drawdowns(self):
        result = analyze_performance(daily())
        self.assertEqual(len(result.daily_performance.columns), 8)
        self.assertIn("strategy_drawdown", result.daily_performance)
        self.assertIn("spy_drawdown", result.daily_performance)

    def test_initial_nav_and_capital(self):
        result = analyze_performance(daily()).daily_performance
        self.assertEqual(result.strategy_nav.iloc[0], 1.)
        self.assertEqual(result.portfolio_value_usd.iloc[0], 100000.)

    def test_capital_nav_identity(self):
        frame = analyze_performance(daily()).daily_performance
        np.testing.assert_allclose(frame.portfolio_value_usd, frame.strategy_nav * 100000)

    def test_phase_five_columns_and_final_nav_preserved_exactly(self):
        original = daily()
        result = analyze_performance(original).daily_performance
        assert_frame_equal(result[original.columns], original)
        self.assertEqual(result.strategy_nav.iloc[-1], original.strategy_nav.iloc[-1])
        self.assertEqual(result.spy_nav.iloc[-1], original.spy_nav.iloc[-1])

    def test_input_not_mutated(self):
        frame = daily()
        original = frame.copy(deep=True)
        analyze_performance(frame)
        assert_frame_equal(frame, original)

    def test_shuffled_daily_rows(self):
        first = analyze_performance(daily())
        second = analyze_performance(daily().sample(frac=1, random_state=11))
        for name in first.__dataclass_fields__:
            assert_frame_equal(getattr(first, name), getattr(second, name))

    def test_invalid_capital_rejected(self):
        frame = daily()
        frame.loc[2, "portfolio_value_usd"] += 10
        with self.assertRaises(ValueError):
            analyze_performance(frame)

    def test_invalid_initial_nav_rejected(self):
        frame = daily()
        frame.strategy_nav *= 2
        frame.portfolio_value_usd *= 2
        with self.assertRaises(ValueError):
            analyze_performance(frame)

    def test_outside_official_bounds_rejected(self):
        frame = daily()
        frame.date += pd.DateOffset(years=20)
        with self.assertRaises(ValueError):
            analyze_performance(frame)

    def test_missing_daily_column_rejected(self):
        with self.assertRaises(ValueError):
            analyze_performance(daily().drop(columns="spy_return"))

    def test_incomplete_official_sample_rejected_with_clock(self):
        with self.assertRaises(ValueError):
            analyze_performance(daily(), sessions=pd.bdate_range("2016-01-04", "2025-12-31"))

    def test_future_data_does_not_change_completed_prefix_metrics(self):
        frame = daily()
        changed = frame.copy(deep=True)
        changed.loc[4, "strategy_nav"] = 1.4
        changed.loc[4, "strategy_return"] = 1.4 / 1.2 - 1
        changed.loc[4, "portfolio_value_usd"] = 140000.
        first = analyze_performance(frame.iloc[:4])
        second = analyze_performance(changed.iloc[:4])
        for name in first.__dataclass_fields__:
            assert_frame_equal(getattr(first, name), getattr(second, name))
        assert_frame_equal(analyze_performance(frame).daily_performance.iloc[:4],
                           analyze_performance(changed).daily_performance.iloc[:4])


if __name__ == "__main__":
    unittest.main()
