"""Phase 8 integration: approved real cache, independent scalar checks, no I/O."""

import math
import statistics
import unittest

import numpy as np
import pandas as pd

from mft109.factors import RAW_FACTOR_COLUMNS
from mft109.portfolio import CASH_ASSET
from phase8_support import approved_cache, baseline_run, UNAVAILABLE


class EndToEndValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = approved_cache()
        cls.pipeline_result = baseline_run()

    def test_all_fixed_names_and_official_sessions_flow_through_pipeline(self):
        self.assertEqual(set(self.pipeline_result.raw.ticker), set(self.cache.universe.yahoo_ticker))
        self.assertEqual(len(self.pipeline_result.raw), len(self.cache.sessions) * 503)
        daily = self.pipeline_result.backtest.daily
        self.assertEqual(len(daily), 2514)
        self.assertEqual(daily.date.iloc[0], pd.Timestamp("2016-01-04"))
        self.assertEqual(daily.date.iloc[-1], pd.Timestamp("2025-12-31"))
        self.assertTrue(daily.date.is_unique and daily.date.is_monotonic_increasing)

    def test_four_real_factor_formulas_against_scalar_prices_and_volume(self):
        for ticker in ("AAPL", "BRK-B", "FISV"):
            stock = self.cache.market.loc[self.cache.market.ticker.eq(ticker)].set_index("date").reindex(self.cache.sessions)
            raw = self.pipeline_result.raw.loc[self.pipeline_result.raw.ticker.eq(ticker)].set_index("date")
            price, volume = stock.adjusted_close.tolist(), stock.volume.tolist()
            for i in (400, 1000, len(price)-1):
                independent = [price[i-21]/price[i-252]-1,
                               statistics.stdev([price[j]/price[j-1]-1 for j in range(i-59,i+1)])*math.sqrt(252),
                               math.log(sum(price[j]*volume[j] for j in range(i-19,i+1))/20),
                               -(price[i]/price[i-20]-1)]
                np.testing.assert_allclose(raw.loc[self.cache.sessions[i], RAW_FACTOR_COLUMNS].to_numpy(dtype=float),
                                           independent, rtol=1e-10, atol=1e-12)

    def test_known_unavailable_and_short_histories_remain_ineligible(self):
        for ticker in UNAVAILABLE:
            raw = self.pipeline_result.raw.loc[self.pipeline_result.raw.ticker.eq(ticker), RAW_FACTOR_COLUMNS]
            self.assertTrue(raw.isna().all().all())
        for ticker in (*sorted(UNAVAILABLE), "SNDK", "Q"):
            scored = self.pipeline_result.scored.loc[self.pipeline_result.scored.ticker.eq(ticker)]
            self.assertFalse(scored.eligible.any())
            self.assertNotIn(ticker, self.pipeline_result.selection.selected.ticker.values)
        fisv = self.pipeline_result.scored.loc[self.pipeline_result.scored.ticker.eq("FISV") & self.pipeline_result.scored.date.isin(
            pd.to_datetime(["2025-11-28", "2025-12-31"]))]
        self.assertEqual(len(fisv), 2)
        self.assertTrue(fisv.eligible.all())

    def test_all_formation_zscores_and_equal_composite_independently(self):
        directions = [("momentum", "momentum_score", 1), ("volatility60", "low_volatility_score", -1),
                      ("liquidity_raw", "liquidity_score", 1), ("reversal20", "reversal_score", 1)]
        dates = set(self.pipeline_result.selection.formation_summary.formation_date)
        for _, group in self.pipeline_result.scored.loc[self.pipeline_result.scored.date.isin(dates)].groupby("date"):
            eligible = group[RAW_FACTOR_COLUMNS].apply(np.isfinite).all(axis=1)
            np.testing.assert_array_equal(group.eligible, eligible)
            valid = group.loc[eligible]
            for raw, score, sign in directions:
                values = valid[raw].tolist()
                mean, std = statistics.mean(values), statistics.pstdev(values)
                expected = [sign*(x-mean)/std if std else 0. for x in values]
                np.testing.assert_allclose(valid[score], expected, rtol=1e-9, atol=1e-10)
                self.assertTrue(group.loc[~eligible, score].isna().all())
            expected = [.25*(r.momentum_score+r.low_volatility_score+r.liquidity_score+r.reversal_score)
                        for r in valid.itertuples()]
            np.testing.assert_allclose(valid.composite_score, expected, rtol=1e-12, atol=1e-12)
            self.assertTrue(group.loc[~eligible, "composite_score"].isna().all())

    def test_all_rankings_and_top_twenty_match_plain_python_order(self):
        for date, ranked in self.pipeline_result.selection.ranked.groupby("formation_date"):
            source = self.pipeline_result.scored.loc[self.pipeline_result.scored.date.eq(date) & self.pipeline_result.scored.eligible]
            order = sorted(source.itertuples(), key=lambda r: (-r.composite_score, r.ticker))
            self.assertEqual(ranked.ticker.tolist(), [r.ticker for r in order])
            self.assertEqual(ranked["rank"].tolist(), list(range(1,len(order)+1)))
            self.assertEqual(ranked.loc[ranked.selected,"ticker"].tolist(), [r.ticker for r in order[:20]])

    def test_all_formations_and_executions_use_real_next_session(self):
        audit = self.pipeline_result.backtest.rebalance_audit
        self.assertEqual(len(audit),120)
        self.assertEqual(audit.formation_date.iloc[0],pd.Timestamp("2016-01-29"))
        self.assertEqual(audit.execution_date.iloc[0],pd.Timestamp("2016-02-01"))
        for row in audit.itertuples():
            month = self.cache.sessions[self.cache.sessions.to_period("M")==row.formation_date.to_period("M")]
            self.assertEqual(row.formation_date,month[-1])
            if pd.notna(row.execution_date):
                self.assertGreater(row.execution_date,row.formation_date)
                self.assertEqual(row.execution_date,self.cache.sessions[self.cache.sessions.searchsorted(row.formation_date,side="right")])
        self.assertTrue(pd.isna(audit.execution_date.iloc[-1]))
        self.assertEqual(audit.execution_date.notna().sum(),119)

    def test_holdings_are_long_only_unique_and_reconcile_to_daily_wealth(self):
        bt = self.pipeline_result.backtest
        self.assertFalse(bt.holdings.duplicated(["date","ticker"]).any())
        self.assertTrue(bt.holdings.weight.ge(0).all() and bt.holdings.units.ge(0).all())
        totals = bt.holdings.groupby("date")[["weight","market_value_usd"]].sum()
        np.testing.assert_allclose(totals.weight,1.,atol=1e-12)
        np.testing.assert_allclose(totals.market_value_usd,bt.daily.portfolio_value_usd,rtol=1e-12,atol=1e-7)
        targets = bt.rebalance_weights.loc[bt.rebalance_weights.executable]
        np.testing.assert_allclose(targets.target_weight,.05,rtol=0,atol=1e-15)
        self.assertTrue(targets.selected.all())
        self.assertNotIn("SPY", bt.holdings.ticker.values)

    def test_every_rebalance_turnover_and_fee_from_old_units_scalar(self):
        bt = self.pipeline_result.backtest
        official = pd.DatetimeIndex(bt.daily.date)
        prices = self.cache.market.pivot(index="date",columns="ticker",values="adjusted_close")
        for event in bt.rebalance_audit.loc[bt.rebalance_audit.execution_date.notna()].itertuples():
            day = event.execution_date
            previous = official[official.get_loc(day)-1]
            old = bt.holdings.loc[bt.holdings.date.eq(previous)].set_index("ticker")
            values = {t:float(r.units)*float(prices.at[day,t]) if t!=CASH_ASSET else float(r.market_value_usd)
                      for t,r in old.iterrows()}
            wealth = sum(values.values())
            names = self.pipeline_result.selection.selected.loc[self.pipeline_result.selection.selected.formation_date.eq(event.formation_date),"ticker"].tolist()
            self.assertEqual(len(names),20)
            target = {**{t:1/len(names) for t in names},CASH_ASSET:0.}
            turnover = .5*sum(abs(target.get(t,0)-values.get(t,0)/wealth) for t in set(target)|set(values))
            self.assertAlmostEqual(event.turnover,turnover,places=12)
            self.assertAlmostEqual(event.transaction_cost_fraction,turnover*.001,places=14)
            self.assertTrue(math.isclose(event.transaction_cost_usd,wealth*turnover*.001,rel_tol=1e-12,abs_tol=1e-8))
            self.assertTrue(math.isclose(event.post_value_usd,wealth*(1-turnover*.001),rel_tol=1e-12))
        self.assertEqual(bt.rebalance_audit.iloc[0].turnover,1.)
        self.assertEqual(bt.rebalance_audit.iloc[0].transaction_cost_usd,100.)

    def test_daily_market_return_and_cost_order_has_no_double_charge(self):
        daily = self.pipeline_result.backtest.daily
        expected = (1+daily.gross_strategy_return)*(1-daily.transaction_cost_fraction)-1
        np.testing.assert_allclose(daily.strategy_return,expected,rtol=1e-10,atol=1e-14)
        event_dates = self.pipeline_result.backtest.rebalance_audit.execution_date.dropna()
        self.assertTrue(daily.loc[~daily.date.isin(event_dates),"transaction_cost_usd"].eq(0).all())

    def test_nav_compounding_and_initial_cash_period(self):
        daily = self.pipeline_result.backtest.daily
        before = daily.loc[daily.date.lt("2016-02-01")]
        self.assertEqual(len(before),19)
        self.assertTrue(before.strategy_return.eq(0).all() and before.strategy_nav.eq(1).all())
        self.assertTrue(before.portfolio_value_usd.eq(100000).all())
        np.testing.assert_allclose((1+daily.strategy_return).cumprod(),daily.strategy_nav,rtol=1e-12)
        np.testing.assert_allclose(daily.portfolio_value_usd,100000*daily.strategy_nav,rtol=1e-12)

    def test_spy_adjusted_buy_and_hold_without_strategy_costs(self):
        daily = self.pipeline_result.backtest.daily
        prices = self.cache.spy.set_index("date").adjusted_close.reindex(daily.date)
        expected = prices/prices.iloc[0]
        np.testing.assert_allclose(daily.spy_nav,expected,rtol=1e-12)
        ret = prices/prices.shift(1)-1
        ret.iloc[0]=0
        np.testing.assert_allclose(daily.spy_return,ret,rtol=1e-12,atol=1e-15)

    def test_strategy_and_spy_metrics_against_independent_scalars(self):
        daily = self.pipeline_result.backtest.daily
        for label,nc,rc in (("Strategy","strategy_nav","strategy_return"),("SPY","spy_nav","spy_return")):
            values = daily[nc].tolist()
            returns = daily[rc].iloc[1:].tolist()
            ratio=values[-1]/values[0]
            annual=ratio**(252/len(returns))-1
            vol=statistics.stdev(returns)*math.sqrt(252)
            peak=values[0]
            drawdowns=[]
            for value in values:
                peak=max(peak,value)
                drawdowns.append(value/peak-1)
            np.testing.assert_allclose(self.pipeline_result.performance.performance_summary[label],
                                       [ratio-1,annual,vol,annual/vol,min(drawdowns)],rtol=1e-12,atol=1e-12)

    def test_all_twenty_annual_returns_from_actual_nav_boundaries(self):
        daily = self.pipeline_result.backtest.daily
        annual = self.pipeline_result.performance.annual_returns
        self.assertEqual(annual.Year.tolist(),list(range(2016,2026)))
        self.assertFalse(annual["Partial Year"].any())
        for row in annual.itertuples(index=False):
            group=daily.loc[daily.date.dt.year.eq(row.Year)]
            earlier=daily.loc[daily.date.dt.year.lt(row.Year)]
            for label,col in (("Strategy","strategy_nav"),("SPY","spy_nav")):
                anchor=earlier[col].iloc[-1] if not earlier.empty else group[col].iloc[0]
                self.assertAlmostEqual(getattr(row,label),group[col].iloc[-1]/anchor-1,places=12)


if __name__ == "__main__":
    unittest.main()
