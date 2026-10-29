"""Phase 5 scalar accounting, timing, missing-data and causality checks; no I/O."""

from dataclasses import replace
from datetime import date
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from mft109.backtesting.engine import MissingHoldingPriceError, run_backtest
from mft109.backtesting.execution import execution_schedule, official_sessions
from mft109.backtesting.transaction_costs import portfolio_turnover, transaction_cost_fraction
from mft109.benchmark import build_spy_benchmark
from mft109.config import BASELINE
from mft109.portfolio import CASH_ASSET, equal_weight_target
from mft109.ranking import MonthlySelection


SETTINGS = replace(BASELINE, backtest_end=date(2016, 3, 31))


def clock():
    return pd.bdate_range("2015-12-28", "2016-04-04").difference(
        pd.to_datetime(["2016-01-01", "2016-01-18", "2016-02-15", "2016-03-25"]))


def selections(groups=None):
    groups = groups if groups is not None else [["A", "B"]] * 3
    records, summaries = [], []
    for formation, names in zip(pd.to_datetime(["2016-01-29", "2016-02-29", "2016-03-31"]), groups):
        for rank, ticker in enumerate(names, 1):
            records.append(dict(formation_date=formation, ticker=ticker, rank=rank,
                                selected=rank <= 20, eligible=True, composite_score=float(100 - rank)))
        summaries.append(dict(formation_date=formation, eligible_count=len(names),
                              selected_count=min(len(names), 20), fewer_than_top_n=len(names) < 20))
    ranked = pd.DataFrame(records, columns=["formation_date", "ticker", "rank", "selected", "eligible", "composite_score"])
    if ranked.empty:
        ranked = ranked.astype({"formation_date": "datetime64[ns]", "rank": "int64",
                                "selected": "bool", "eligible": "bool", "composite_score": "float64"})
    return MonthlySelection(ranked, pd.DataFrame(summaries))


def data(tickers=("A", "B", "C")):
    rows = [(session, ticker, 100.0, 98765.0) for session in clock() for ticker in tickers]
    return pd.DataFrame(rows, columns=["date", "ticker", "adjusted_close", "close"])


def spy():
    return pd.Series(np.arange(len(clock()), dtype=float) + 100, index=clock())


def run(selection=None, prices=None, benchmark=None):
    return run_backtest(selections() if selection is None else selection,
                        data() if prices is None else prices,
                        spy() if benchmark is None else benchmark,
                        sessions=clock(), baseline=SETTINGS)


def change(prices, ticker, start, value):
    prices.loc[prices.ticker.eq(ticker) & prices.date.ge(pd.Timestamp(start)), "adjusted_close"] = value


class TargetTests(unittest.TestCase):
    def test_twenty_stocks_have_five_percent_weights(self):
        names = [f"T{i:02}" for i in range(20)]
        target = equal_weight_target(names, pd.Series(100., index=names))
        self.assertTrue(target.weights.drop(CASH_ASSET).eq(.05).all())

    def test_fewer_stocks_equal_weight(self):
        target = equal_weight_target(["A", "B", "C"], pd.Series({"A": 10., "B": 20., "C": np.nan}))
        self.assertEqual(target.weights.to_dict(), {"A": .5, "B": .5, CASH_ASSET: 0.})

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(equal_weight_target(["A"], pd.Series({"A": 3.})).weights.sum(), 1.)

    def test_zero_executable_is_cash(self):
        self.assertEqual(equal_weight_target(["A"], pd.Series({"A": np.nan})).weights.to_dict(), {CASH_ASSET: 1.})

    def test_unselected_never_allocated(self):
        self.assertNotIn("B", equal_weight_target(["A"], pd.Series({"A": 1., "B": 3.})).weights)

    def test_invalid_prices_all_excluded(self):
        target = equal_weight_target(["A", "B", "C", "D"], pd.Series({"A": 0., "B": -1., "C": np.inf, "D": np.nan}))
        self.assertEqual(target.excluded_tickers, ("A", "B", "C", "D"))

    def test_duplicate_and_over_twenty_rejected(self):
        for names in (["A", "A"], [str(i) for i in range(21)]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                equal_weight_target(names, pd.Series(dtype=float))

    def test_cash_and_spy_are_not_stock_targets(self):
        for ticker in (CASH_ASSET, "SPY"):
            with self.subTest(ticker=ticker), self.assertRaises(ValueError):
                equal_weight_target([ticker], pd.Series({ticker: 1.}))


class ExecutionTests(unittest.TestCase):
    def test_january_formation_executes_february_first(self):
        schedule = execution_schedule(pd.DatetimeIndex(["2016-01-29"]), sessions=clock(), baseline=SETTINGS)
        self.assertEqual(schedule.execution_date.iloc[0], pd.Timestamp("2016-02-01"))

    def test_holiday_and_weekend_are_skipped(self):
        schedule = execution_schedule(pd.DatetimeIndex(["2016-02-12"]), sessions=clock(), baseline=SETTINGS)
        self.assertEqual(schedule.execution_date.iloc[0], pd.Timestamp("2016-02-16"))

    def test_execution_is_strictly_later(self):
        schedule = execution_schedule(pd.DatetimeIndex(["2016-01-29", "2016-02-29"]), sessions=clock(), baseline=SETTINGS)
        self.assertTrue(schedule.execution_date.gt(schedule.formation_date).all())

    def test_final_signal_not_executed_past_boundary(self):
        schedule = execution_schedule(pd.DatetimeIndex(["2016-03-31"]), sessions=clock(), baseline=SETTINGS)
        self.assertTrue(pd.isna(schedule.execution_date.iloc[0]))

    def test_december_2025_signal_does_not_trade_in_2026(self):
        sessions = pd.bdate_range("2016-01-04", "2026-01-05")
        schedule = execution_schedule(pd.DatetimeIndex(["2025-12-31"]), sessions=sessions)
        self.assertTrue(pd.isna(schedule.execution_date.iloc[0]))

    def test_official_calendar_excludes_warmup_and_future(self):
        actual = official_sessions(clock(), SETTINGS)
        self.assertEqual(actual[0], pd.Timestamp("2016-01-04"))
        self.assertEqual(actual[-1], pd.Timestamp("2016-03-31"))

    def test_weekend_clock_rejected(self):
        with self.assertRaises(ValueError):
            official_sessions(clock().union(pd.DatetimeIndex(["2016-02-06"])), SETTINGS)

    def test_incomplete_clock_rejected(self):
        with self.assertRaises(ValueError):
            official_sessions(clock()[clock() > "2016-02-01"], SETTINGS)


class TurnoverTests(unittest.TestCase):
    def check(self, pre, target, expected):
        self.assertAlmostEqual(portfolio_turnover(pd.Series(pre), pd.Series(target)), expected)

    def test_unchanged_zero(self):
        self.check({"A": .5, "B": .5}, {"A": .5, "B": .5}, 0)

    def test_same_names_drifted_weights(self):
        self.check({"A": .6, "B": .4}, {"A": .5, "B": .5}, .1)

    def test_partial_replacement(self):
        self.check({"A": .5, "B": .5}, {"A": .5, "C": .5}, .5)

    def test_full_replacement(self):
        self.check({"A": 1.}, {"B": 1.}, 1.)

    def test_initial_cash_to_stocks(self):
        self.check({CASH_ASSET: 1.}, {"A": .5, "B": .5}, 1.)

    def test_all_cash_no_double_count(self):
        self.check({CASH_ASSET: 1.}, {CASH_ASSET: 1.}, 0.)

    def test_liquidation_to_cash(self):
        self.check({"A": 1.}, {CASH_ASSET: 1.}, 1.)

    def test_cost_scalar_ten_bps(self):
        self.assertAlmostEqual(transaction_cost_fraction(.3), .0003)

    def test_zero_turnover_has_zero_cost(self):
        self.assertEqual(transaction_cost_fraction(0.), 0.)

    def test_invalid_complete_weights_rejected(self):
        for pre in ({"A": .5}, {"A": -1., "B": 2.}, {"A": np.nan}):
            with self.subTest(pre=pre), self.assertRaises(ValueError):
                portfolio_turnover(pd.Series(pre), pd.Series({"A": 1.}))

    def test_invalid_turnover_rejected(self):
        for value in (-.1, 1.1, np.nan, np.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                transaction_cost_fraction(value)


class EngineAccountingTests(unittest.TestCase):
    def test_initial_nav_and_capital(self):
        first = run().daily.iloc[0]
        self.assertEqual(first.strategy_nav, 1.)
        self.assertEqual(first.portfolio_value_usd, 100000.)

    def test_initial_cash_period_is_preserved(self):
        before = run().daily.query('date < "2016-02-01"')
        self.assertTrue(before.strategy_return.eq(0).all())
        self.assertTrue(before.strategy_nav.eq(1).all())
        self.assertTrue(before.cash_weight.eq(1).all())

    def test_initial_turnover_and_cost_reduce_wealth(self):
        row = run().rebalance_audit.iloc[0]
        self.assertEqual(row.turnover, 1.)
        self.assertEqual(row.transaction_cost_usd, 100.)
        self.assertEqual(row.post_value_usd, 99900.)

    def test_no_formation_day_trade(self):
        result = run()
        self.assertEqual(result.daily.set_index("date").at[pd.Timestamp("2016-01-29"), "cash_weight"], 1.)

    def test_new_positions_do_not_earn_execution_day_move(self):
        prices = data()
        change(prices, "A", "2016-02-01", 200.)
        first = run(prices=prices).daily.loc[lambda f: f.date.eq(pd.Timestamp("2016-02-01"))].iloc[0]
        self.assertAlmostEqual(first.strategy_return, -.001)

    def test_fixed_units_and_weight_drift(self):
        prices = data()
        change(prices, "A", "2016-02-02", 110.)
        result = run(prices=prices)
        a = result.holdings.query('ticker == "A" and date < "2016-03-01"')
        self.assertTrue(a.units.eq(499.5).all())
        self.assertAlmostEqual(a.loc[a.date.eq("2016-02-02"), "weight"].iloc[0], 11 / 21)

    def test_daily_return_uses_actual_holdings(self):
        prices = data()
        change(prices, "A", "2016-02-02", 110.)
        row = run(prices=prices).daily.loc[lambda f: f.date.eq(pd.Timestamp("2016-02-02"))].iloc[0]
        self.assertAlmostEqual(row.strategy_return, .05)
        self.assertAlmostEqual(row.portfolio_value_usd, 104895.)

    def test_next_rebalance_turnover_uses_drift(self):
        prices = data()
        change(prices, "A", "2016-02-02", 110.)
        row = run(prices=prices).rebalance_audit.iloc[1]
        self.assertAlmostEqual(row.turnover, abs(11 / 21 - .5))
        self.assertAlmostEqual(row.transaction_cost_usd, 104895 * abs(11 / 21 - .5) * .001)

    def test_new_holdings_equal_weight_after_cost_and_drift(self):
        prices = data()
        change(prices, "A", "2016-02-02", 110.)
        result = run(prices=prices)
        stocks = result.holdings.loc[result.holdings.date.eq("2016-03-01")
                                     & result.holdings.ticker.ne(CASH_ASSET)]
        self.assertEqual(len(stocks), 2)
        np.testing.assert_allclose(stocks.weight, .5)

    def test_daily_holdings_reconcile_to_value_and_weights(self):
        prices = data()
        change(prices, "A", "2016-02-02", 115.)
        result = run(prices=prices)
        totals = result.holdings.groupby("date")[["market_value_usd", "weight"]].sum()
        np.testing.assert_allclose(totals.market_value_usd, result.daily.portfolio_value_usd)
        np.testing.assert_allclose(totals.weight, 1.)

    def test_old_holdings_earn_execution_day_return(self):
        prices = data()
        change(prices, "A", "2016-03-01", 120.)
        result = run(selections([["A"], ["B"], ["B"]]), prices)
        row = result.daily.loc[lambda f: f.date.eq(pd.Timestamp("2016-03-01"))].iloc[0]
        self.assertAlmostEqual(row.gross_strategy_return, .2)
        self.assertAlmostEqual(row.strategy_return, 1.2 * .999 - 1)

    def test_cost_charged_once_only_on_rebalances(self):
        result = run()
        self.assertAlmostEqual(result.daily.transaction_cost_usd.sum(), 100.)
        self.assertEqual(result.daily.transaction_cost_usd.gt(0).sum(), 1)

    def test_nav_compounds_daily_returns(self):
        prices = data()
        change(prices, "B", "2016-02-03", 125.)
        result = run(prices=prices)
        np.testing.assert_allclose((1 + result.daily.strategy_return).cumprod(), result.daily.strategy_nav)

    def test_value_equals_initial_capital_times_nav(self):
        result = run()
        np.testing.assert_allclose(result.daily.portfolio_value_usd, 100000 * result.daily.strategy_nav)

    def test_nav_not_reset_at_rebalance(self):
        prices = data()
        change(prices, "A", "2016-02-02", 120.)
        result = run(prices=prices)
        self.assertGreater(result.daily.loc[lambda f: f.date.eq(pd.Timestamp("2016-03-01"))].strategy_nav.iloc[0], 1.)

    def test_zero_selected_remains_cash(self):
        with self.assertLogs("mft109.backtesting.engine", level="WARNING"):
            result = run(selections([[], [], []]))
        self.assertTrue(result.daily.strategy_nav.eq(1).all())
        self.assertTrue(result.rebalance_audit.iloc[:2].executable_count.eq(0).all())

    def test_missing_execution_excludes_without_fill(self):
        prices = data()
        prices.loc[prices.date.eq("2016-02-01") & prices.ticker.eq("A"), "adjusted_close"] = np.nan
        with self.assertLogs("mft109.backtesting.engine", level="WARNING"):
            result = run(prices=prices)
        weights = result.rebalance_weights.loc[lambda f: f.execution_date.eq(pd.Timestamp("2016-02-01"))].set_index("ticker")
        self.assertEqual(weights.at["A", "target_weight"], 0.)
        self.assertEqual(weights.at["B", "target_weight"], 1.)
        self.assertEqual(result.missing_price_events.iloc[0].action, "exclude_without_replacement")

    def test_rank_twenty_one_never_replaces_missing_selected(self):
        names = [f"T{i:02}" for i in range(21)]
        prices = data(names)
        prices.loc[prices.date.eq("2016-02-01") & prices.ticker.eq(names[0]), "adjusted_close"] = np.nan
        with self.assertLogs("mft109.backtesting.engine", level="WARNING"):
            result = run(selections([names] * 3), prices)
        targets = result.rebalance_weights.loc[lambda f: f.execution_date.eq(pd.Timestamp("2016-02-01"))]
        self.assertNotIn(names[20], targets.ticker.tolist())
        self.assertEqual(result.rebalance_audit.iloc[0].executable_count, 19)

    def test_zero_executable_moves_to_cash_and_audits(self):
        prices = data()
        prices.loc[prices.date.eq("2016-02-01"), "adjusted_close"] = np.nan
        with self.assertLogs("mft109.backtesting.engine", level="WARNING"):
            result = run(prices=prices)
        row = result.rebalance_audit.iloc[0]
        self.assertEqual(row.turnover, 0.)
        self.assertIn("zero_executable_stocks", row["flags"])
        self.assertEqual(row.target_cash_weight, 1.)

    def test_liquidating_to_cash_charges_turnover(self):
        with self.assertLogs("mft109.backtesting.engine", level="WARNING"):
            result = run(selections([["A"], [], ["A"]]))
        self.assertAlmostEqual(result.rebalance_audit.iloc[1].turnover, 1.)
        self.assertAlmostEqual(result.daily.iloc[-1].portfolio_value_usd, 100000 * .999 ** 2)

    def test_missing_held_price_stops_without_invented_return(self):
        prices = data()
        prices.loc[prices.date.eq("2016-02-03") & prices.ticker.eq("A"), "adjusted_close"] = np.nan
        with self.assertLogs("mft109.backtesting.engine", level="ERROR"), self.assertRaises(MissingHoldingPriceError) as caught:
            run(prices=prices)
        error = caught.exception
        self.assertEqual(error.date, pd.Timestamp("2016-02-03"))
        self.assertEqual(error.tickers, ("A",))
        self.assertEqual(error.partial_result.daily.date.max(), pd.Timestamp("2016-02-02"))
        self.assertEqual(error.partial_result.missing_price_events.iloc[0].action, "stop_without_valuation")

    def test_missing_held_price_on_rebalance_cannot_be_sold_at_zero(self):
        prices = data()
        prices.loc[prices.date.eq("2016-03-01") & prices.ticker.eq("A"), "adjusted_close"] = np.nan
        with self.assertLogs("mft109.backtesting.engine", level="ERROR"), self.assertRaises(MissingHoldingPriceError):
            run(selections([["A"], ["B"], ["B"]]), prices)

    def test_nonpositive_or_infinite_held_price_stops(self):
        for invalid in (0., -1., np.inf):
            prices = data()
            prices.loc[prices.date.eq("2016-02-03") & prices.ticker.eq("A"), "adjusted_close"] = invalid
            with self.subTest(invalid=invalid), self.assertLogs("mft109.backtesting.engine", level="ERROR"), self.assertRaises(MissingHoldingPriceError):
                run(prices=prices)

    def test_missing_unheld_price_does_not_create_missing_holding(self):
        prices = data()
        prices.loc[prices.ticker.eq("C"), "adjusted_close"] = np.nan
        self.assertTrue(run(prices=prices).missing_price_events.empty)

    def test_absent_held_row_is_not_filled(self):
        prices = data()
        prices = prices.loc[~(prices.date.eq("2016-02-03") & prices.ticker.eq("A"))]
        with self.assertLogs("mft109.backtesting.engine", level="ERROR"), self.assertRaises(MissingHoldingPriceError):
            run(prices=prices)

    def test_final_formation_retained_without_trade(self):
        audit = run().rebalance_audit.iloc[-1]
        self.assertEqual(audit.formation_date, pd.Timestamp("2016-03-31"))
        self.assertTrue(pd.isna(audit.execution_date))
        self.assertTrue(pd.isna(audit.executable_count))
        self.assertEqual(audit.status, "not_executed_within_backtest")

    def test_raw_close_not_used(self):
        original = data()
        changed = original.assign(close=np.nan)
        assert_frame_equal(run(prices=original).daily, run(prices=changed).daily)


class BenchmarkTests(unittest.TestCase):
    def test_first_official_nav_one_and_return_zero(self):
        benchmark = build_spy_benchmark(spy(), sessions=clock(), baseline=SETTINGS)
        self.assertEqual(benchmark.iloc[0].spy_nav, 1.)
        self.assertEqual(benchmark.iloc[0].spy_return, 0.)

    def test_buy_and_hold_adjusted_price_ratios(self):
        benchmark = build_spy_benchmark(spy(), sessions=clock(), baseline=SETTINGS)
        official = spy().reindex(official_sessions(clock(), SETTINGS))
        np.testing.assert_allclose(benchmark.spy_nav, official / official.iloc[0])

    def test_no_strategy_transaction_cost_on_spy(self):
        result = run()
        expected = build_spy_benchmark(spy(), sessions=clock(), baseline=SETTINGS)
        np.testing.assert_allclose(result.daily.spy_nav, expected.spy_nav)

    def test_missing_benchmark_price_is_error(self):
        prices = spy()
        prices.loc["2016-02-03"] = np.nan
        with self.assertRaisesRegex(ValueError, "SPY benchmark"):
            run(benchmark=prices)

    def test_warmup_and_future_prices_do_not_affect_benchmark(self):
        prices = spy()
        prices.loc[(prices.index < "2016-01-01") | (prices.index > "2016-03-31")] *= 100
        assert_frame_equal(run().daily, run(benchmark=prices).daily)


class IntegrityTests(unittest.TestCase):
    def test_shuffled_inputs_produce_identical_outputs(self):
        selection = selections()
        shuffled = MonthlySelection(selection.ranked.sample(frac=1, random_state=1),
                                     selection.formation_summary.sample(frac=1, random_state=2))
        first, second = run(), run(shuffled, data().sample(frac=1, random_state=3))
        for name in first.__dataclass_fields__:
            assert_frame_equal(getattr(first, name), getattr(second, name))

    def test_future_prices_cannot_change_earlier_results(self):
        prices = data()
        change(prices, "A", "2016-03-02", 250.)
        first, second = run(), run(prices=prices)
        for name in ("daily", "holdings"):
            a, b = getattr(first, name), getattr(second, name)
            assert_frame_equal(a.loc[a.date.le("2016-03-01")], b.loc[b.date.le("2016-03-01")])
        assert_frame_equal(first.rebalance_weights, second.rebalance_weights)
        assert_frame_equal(first.rebalance_audit, second.rebalance_audit)

    def test_future_selections_cannot_change_earlier_results(self):
        first, second = run(), run(selections([["A", "B"], ["C"], ["C"]]))
        for name in ("daily", "holdings"):
            a, b = getattr(first, name), getattr(second, name)
            assert_frame_equal(a.loc[a.date.lt("2016-03-01")], b.loc[b.date.lt("2016-03-01")])
        assert_frame_equal(first.rebalance_audit.iloc[:1], second.rebalance_audit.iloc[:1])

    def test_inputs_not_mutated(self):
        selection, prices, benchmark = selections(), data(), spy()
        originals = (selection.ranked.copy(deep=True), selection.formation_summary.copy(deep=True), prices.copy(deep=True), benchmark.copy(deep=True))
        run(selection, prices, benchmark)
        for actual, expected in zip((selection.ranked, selection.formation_summary, prices), originals[:3]):
            assert_frame_equal(actual, expected)
        pd.testing.assert_series_equal(benchmark, originals[3])

    def test_duplicate_market_observations_rejected(self):
        prices = data()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            run(prices=pd.concat([prices, prices.iloc[:1]]))

    def test_inconsistent_phase_four_summary_rejected(self):
        selection = selections()
        selection.formation_summary.loc[0, "selected_count"] = 1
        with self.assertRaises(ValueError):
            run(selection)

    def test_missing_formation_summary_rejected(self):
        selection = selections()
        with self.assertRaises(ValueError):
            run(MonthlySelection(selection.ranked, selection.formation_summary.iloc[1:]))

    def test_duplicate_phase_four_ranks_rejected(self):
        selection = selections()
        selection.ranked.loc[1, "rank"] = 1
        with self.assertRaises(ValueError):
            run(selection)

    def test_changed_economic_settings_rejected(self):
        with self.assertRaises(ValueError):
            run_backtest(selections(), data(), spy(), sessions=clock(),
                         baseline=replace(SETTINGS, transaction_cost_rate=.01))

    def test_no_factor_or_scoring_recalculation(self):
        with patch("mft109.factors.calculate_raw_factors", side_effect=AssertionError), \
                patch("mft109.processing.score_factors", side_effect=AssertionError), \
                patch("mft109.ranking.rank_and_select", side_effect=AssertionError):
            run()

    def test_no_phase_six_statistics_in_output(self):
        result = run()
        forbidden = {"annualized_return", "annualized_volatility", "sharpe", "maximum_drawdown", "optimization"}
        for name in result.__dataclass_fields__:
            self.assertFalse(forbidden.intersection(getattr(result, name).columns))


if __name__ == "__main__":
    unittest.main()
