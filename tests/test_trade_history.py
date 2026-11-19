"""Engine units/cash/cost reconciliation and repository-only bilingual trade UI."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from mft109.backtesting.trades import TRADE_COLUMNS, rebalance_trades, reconcile_trade_log
from mft109.backtesting.engine import MissingHoldingPriceError
from mft109.config import PROJECT_ROOT
from mft109.visualization.dashboard_data import DashboardDataError
from mft109.visualization.trade_history import filter_trades, load_trade_history, validate_trade_log
from test_portfolio_backtest import run, selections, data, change
from phase8_support import baseline_run, offline


class EngineTradeTests(unittest.TestCase):
    def test_initial_entries_use_actual_adjusted_price_and_fractional_units(self):
        result = run()
        first = result.trade_log.iloc[:2]
        self.assertEqual(first.ticker.tolist(), ['A', 'B'])
        self.assertEqual(first.side.tolist(), ['BUY', 'BUY'])
        self.assertEqual(first.trade_type.tolist(), ['NEW_ENTRY', 'NEW_ENTRY'])
        self.assertEqual(first.execution_date.tolist(), [pd.Timestamp('2016-02-01')]*2)
        self.assertTrue(first.formation_date.eq('2016-01-29').all())
        np.testing.assert_array_equal(first.quantity, [499.5, 499.5])
        self.assertTrue(first.adjusted_execution_price.eq(100).all())
        self.assertAlmostEqual(first.transaction_cost_usd.sum(), 100.)
        self.assertTrue(first.portfolio_value_usd.eq(99900).all())
        reconcile_trade_log(result)

    def test_retained_tickers_have_both_increase_and_decrease(self):
        prices = data()
        change(prices, 'A', '2016-03-01', 200)
        result = run(prices=prices)
        trades = result.trade_log.loc[result.trade_log.execution_date.eq('2016-03-01')].set_index('ticker')
        self.assertEqual(trades.at['A', 'side'], 'SELL')
        self.assertEqual(trades.at['A', 'trade_type'], 'DECREASE')
        self.assertEqual(trades.at['B', 'side'], 'BUY')
        self.assertEqual(trades.at['B', 'trade_type'], 'INCREASE')
        reconcile_trade_log(result)

    def test_full_exit_new_entry_and_cost_cash_reconcile(self):
        result = run(selection=selections([['A','B'], ['B','C'], ['B','C']]))
        rows = result.trade_log.loc[result.trade_log.execution_date.eq('2016-03-01')].set_index('ticker')
        self.assertEqual(rows.at['A', 'trade_type'], 'FULL_EXIT')
        self.assertEqual(rows.at['A', 'post_trade_units'], 0.)
        self.assertEqual(rows.at['C', 'trade_type'], 'NEW_ENTRY')
        # Retained B also sells units to finance the existing fee.
        self.assertEqual(rows.at['B', 'trade_type'], 'DECREASE')
        reconcile_trade_log(result)

    def test_exit_to_cash(self):
        result = run(selection=selections([['A','B'], [], []]))
        rows = result.trade_log.loc[result.trade_log.execution_date.eq('2016-03-01')]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows.side.eq('SELL').all())
        self.assertTrue(rows.trade_type.eq('FULL_EXIT').all())
        reconcile_trade_log(result)

    def test_no_rebalance_unit_change_produces_no_spurious_trades(self):
        result = run()
        self.assertEqual(len(result.trade_log), 2)
        self.assertFalse(result.trade_log.execution_date.eq('2016-03-01').any())

    def test_all_cash_empty_log_has_schema(self):
        result = run(selection=selections([[],[],[]]))
        self.assertTrue(result.trade_log.empty)
        self.assertEqual(result.trade_log.columns.tolist(), TRADE_COLUMNS)
        reconcile_trade_log(result)

    def test_invalid_initial_execution_prices_are_not_trades(self):
        prices = data()
        prices.loc[prices.ticker.eq('A'), 'adjusted_close'] = np.nan
        result = run(selection=selections([['A'],['A'],['A']]), prices=prices)
        self.assertTrue(result.trade_log.empty)
        reconcile_trade_log(result)

    def test_noise_ignored_but_small_real_delta_logged_without_rounding(self):
        kwargs = dict(execution_date=pd.Timestamp('2016-02-01'), formation_date=pd.Timestamp('2016-01-29'),
                      before={'A':100.}, prices={'A':100.}, transaction_cost_usd=0., portfolio_value_usd=10000.)
        self.assertEqual(rebalance_trades(after={'A':100.+1e-13}, **kwargs), [])
        rows = rebalance_trades(after={'A':100.+1e-8}, **kwargs)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['quantity'], (100.+1e-8)-100.)

    def test_observer_does_not_change_any_existing_accounting_table(self):
        prices = data()
        change(prices, 'A', '2016-03-01', 200.)
        actual = run(prices=prices)
        with patch('mft109.backtesting.engine.rebalance_trades', return_value=[]):
            without_logging = run(prices=prices)
        for field in ('daily','holdings','rebalance_audit','rebalance_weights','missing_price_events'):
            assert_frame_equal(getattr(actual,field), getattr(without_logging,field), check_exact=True)

    def test_fees_are_allocated_once_not_recomputed_at_ten_bps_per_notional(self):
        result = run()
        np.testing.assert_allclose(result.trade_log.groupby('execution_date').transaction_cost_usd.sum(), [100.])
        # Existing initial turnover fee is $100; not $99.90 nor another $100.
        self.assertEqual(result.daily.transaction_cost_usd.sum(), 100.)
        self.assertEqual(result.daily.portfolio_value_usd.iloc[-1], 99900.)

    def test_partial_result_retains_only_prior_executed_trades(self):
        prices = data()
        prices.loc[prices.ticker.eq('A') & prices.date.eq('2016-02-03'), 'adjusted_close'] = np.nan
        with self.assertRaises(MissingHoldingPriceError) as caught:
            run(prices=prices)
        self.assertEqual(len(caught.exception.partial_result.trade_log),2)
        self.assertTrue(caught.exception.partial_result.trade_log.execution_date.lt('2016-02-03').all())

    def test_future_price_change_does_not_change_past_trades(self):
        prices = data()
        before = run(prices=prices).trade_log
        change(prices,'A','2016-03-01',200.)
        after = run(prices=prices).trade_log
        assert_frame_equal(before.loc[before.execution_date.lt('2016-03-01')],
                           after.loc[after.execution_date.lt('2016-03-01')],check_exact=True)

    def test_reconciliation_detects_missing_or_duplicate_cost_trade(self):
        result = run()
        with self.assertRaisesRegex(ValueError,'Missing'):
            reconcile_trade_log(replace(result, trade_log=result.trade_log.iloc[1:].copy()))
        corrupt = result.trade_log.copy()
        corrupt.loc[0,'transaction_cost_usd'] += 1
        with self.assertRaisesRegex(ValueError,'cost'):
            reconcile_trade_log(replace(result, trade_log=corrupt))


class TradeArtifactTests(unittest.TestCase):
    def test_official_log_reconciles_all_executions_and_baseline_unchanged(self):
        result = baseline_run().backtest
        reconcile_trade_log(result)
        loaded = load_trade_history()
        self.assertEqual(len(loaded),len(result.trade_log))
        self.assertEqual(loaded.execution_date.nunique(),119)
        self.assertEqual(set(loaded.execution_date.dt.year),set(range(2016,2026)))
        self.assertEqual(result.daily.strategy_nav.iloc[-1],6.225346615575381)
        self.assertEqual(result.daily.portfolio_value_usd.iloc[-1],622534.6615575381)
        self.assertEqual(result.daily.spy_nav.iloc[-1],4.002530196823173)
        self.assertFalse(loaded.execution_date.gt('2025-12-31').any())
        self.assertTrue(loaded.trade_type.isin(['INCREASE','DECREASE']).any())
        for column in TRADE_COLUMNS[5:]:
            np.testing.assert_allclose(loaded[column],result.trade_log[column],rtol=1e-14,atol=1e-9)

    def test_tracked_final_csv_equals_dashboard_csv_and_manifest_hash(self):
        source=PROJECT_ROOT/'dashboard/data/trade_log.csv'
        destination=PROJECT_ROOT/'outputs/final_report/v1/trade_log.csv'
        self.assertEqual(source.read_bytes(),destination.read_bytes())
        manifest=json.loads((destination.parent/'manifest.json').read_text())
        self.assertEqual(manifest['files']['trade_log.csv']['sha256'],sha256(source.read_bytes()).hexdigest())
        self.assertEqual(manifest['trade_history']['trade_count'],len(load_trade_history()))

    def test_date_ticker_side_filters_are_inclusive_and_do_not_mutate(self):
        table = load_trade_history()
        original=table.copy(deep=True)
        row=table.iloc[0]
        result=filter_trades(table,start=row.execution_date,end=row.execution_date,
                             tickers=[row.ticker],sides=[row.side])
        self.assertEqual(len(result),1)
        assert_frame_equal(result,table.loc[[0]],check_exact=True)
        self.assertTrue(filter_trades(table,start='2026-01-01').empty)
        assert_frame_equal(table,original,check_exact=True)

    def test_invalid_directions_and_fabricated_quantity_are_rejected(self):
        for column,value in [('side','SELL'),('quantity',-1),('trade_type','FULL_EXIT')]:
            bad=load_trade_history().iloc[:1].copy()
            bad.loc[0,column]=value
            with self.assertRaises(ValueError):validate_trade_log(bad)

    def test_missing_data_reports_clear_error_without_download(self):
        with tempfile.TemporaryDirectory() as name,offline():
            with self.assertRaisesRegex(DashboardDataError,'unavailable'):
                load_trade_history(Path(name))

    def test_repository_only_load_and_corruption_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            shutil.copytree(PROJECT_ROOT/'dashboard/data',root/'dashboard/data')
            with offline(),patch('mft109.backtesting.engine.run_backtest',side_effect=AssertionError('No live backtest')):
                table=load_trade_history(root)
                self.assertGreater(len(table),0)
            with (root/'dashboard/data/trade_log.csv').open('a') as handle:handle.write('bad')
            with self.assertRaisesRegex(DashboardDataError,'checksum'):
                load_trade_history(root)

    def test_missing_approved_cache_stops_offline_export_before_writes(self):
        import shutil
        from mft109.backtesting.export import export_official_trade_log
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            shutil.copytree(PROJECT_ROOT/'dashboard/data',root/'dashboard/data')
            shutil.copytree(PROJECT_ROOT/'data/raw',root/'data/raw')
            before=(root/'dashboard/data/trade_log.csv').read_bytes()
            with offline(),self.assertRaisesRegex(ValueError,'Approved cache missing: SPY'):
                export_official_trade_log(root)
            self.assertEqual(before,(root/'dashboard/data/trade_log.csv').read_bytes())


class TradePageTests(unittest.TestCase):
    def app(self,language='en'):
        app=AppTest.from_file(str(PROJECT_ROOT/'dashboard/pages/3_Trade_History.py'),default_timeout=30)
        app.session_state['dashboard_language']=language
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        return app

    def test_english_and_traditional_chinese_load_same_financial_data(self):
        for language,title in [('en','Trade History'),('zh_TW','交易紀錄')]:
            app=self.app(language)
            self.assertEqual(app.title[0].value,title)
            self.assertEqual(int(app.metric[0].value),len(load_trade_history()))
            self.assertEqual(len(app.dataframe[0].value),len(load_trade_history()))
            self.assertTrue(app.get('download_button'))

    def test_ui_filters_ticker_side_and_date_range(self):
        app=self.app()
        row=load_trade_history().iloc[0]
        app.multiselect(key='trade_tickers').select(row.ticker).run()
        app.multiselect(key='trade_sides').select('BUY').run()
        app.date_input(key='trade_date_range').set_value((row.execution_date.date(),row.execution_date.date())).run()
        self.assertFalse(app.exception)
        self.assertEqual(int(app.metric[0].value),1)
        self.assertEqual(int(app.metric[1].value),1)
        self.assertEqual(int(app.metric[2].value),0)
        self.assertEqual(len(app.dataframe[0].value),1)

    def test_ui_empty_filter_message_and_zero_summary(self):
        app=self.app('zh_TW')
        row=load_trade_history().iloc[0]
        app.multiselect(key='trade_sides').select('SELL').run()
        app.date_input(key='trade_date_range').set_value((row.execution_date.date(),row.execution_date.date())).run()
        self.assertFalse(app.exception)
        self.assertEqual(int(app.metric[0].value),0)
        self.assertTrue(app.info)

    def test_missing_or_empty_artifact_is_clear_and_does_not_crash(self):
        with patch('dashboard.components.loaders.cached_trades',side_effect=DashboardDataError('Missing trade log')):
            app=self.app()
            self.assertTrue(app.warning)
        empty=load_trade_history().iloc[:0].copy()
        with patch('dashboard.components.loaders.cached_trades',return_value=empty):
            app=self.app()
            self.assertEqual(int(app.metric[0].value),0)
            self.assertTrue(app.info)
