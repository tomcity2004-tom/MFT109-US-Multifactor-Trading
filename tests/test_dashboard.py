"""Presentation adapters and Streamlit execution tests, without pixel assertions."""

from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from dashboard.components import charts
from dashboard.components.formatting import (
    number, comparison_table, portfolio_table, sensitivity_view, sensitivity_table,
)
from mft109.config import PROJECT_ROOT
from mft109.visualization.dashboard_data import (
    DashboardDataError, SCORE_LABELS, GROUP_LABELS, bundle_signature, formation_dates,
    load_dashboard_bundle, output_directory, portfolio_view,
)
from phase8_support import offline


class FormattingTests(unittest.TestCase):
    def test_percent_currency_nav_and_ratio(self):
        self.assertEqual(number(.1234,"percent"),"12.34%")
        self.assertEqual(number(123456.78,"currency"),"$123,456.78")
        self.assertEqual(number(1.234567,"nav"),"1.2346")
        self.assertEqual(number(.875,"number"),"0.875")

    def test_missing_and_infinite_values_remain_undefined(self):
        for value in (np.nan,np.inf,-np.inf,None):
            self.assertEqual(number(value),"—")

    def test_comparison_sharpe_is_not_percentage_and_input_not_mutated(self):
        frame=pd.DataFrame({"Metric":["Annualized Return","Sharpe Ratio"],"Strategy":[.2,.8],"SPY":[.1,.6]})
        before=frame.copy(deep=True)
        result=comparison_table(frame)
        self.assertEqual(result.Strategy.tolist(),["20.00%","0.800"])
        self.assertEqual(result.Metric.tolist(),["CAGR","Sharpe Ratio"])
        assert_frame_equal(frame,before)

    def test_sensitivity_labels_and_baseline_are_configuration_based(self):
        frame=pd.DataFrame({"parameter_value":["0","10","20"],"is_baseline":[False,True,False]})
        result=sensitivity_view(frame,"transaction_cost_bps")
        self.assertEqual(result.Setting.tolist(),["0 bps","10 bps","20 bps"])
        self.assertEqual(result.Baseline.tolist(),["Sensitivity","Baseline","Sensitivity"])

    def test_weight_labels(self):
        result=sensitivity_view(pd.DataFrame({"parameter_value":["equal","momentum_tilt"],"is_baseline":[True,False]}),"factor_weights")
        self.assertEqual(result.Setting.tolist(),["Equal weight","Momentum Tilt"])

    def test_portfolio_formatting_preserves_missing_final_weight(self):
        frame=pd.DataFrame({"rank":[1],"ticker":["A"],"composite_score":[1.23],"target_weight":[np.nan],**{c:[.5] for c in SCORE_LABELS}})
        result=portfolio_table(frame)
        self.assertEqual(result["Target weight"].iloc[0],"—")
        self.assertTrue(pd.isna(frame.target_weight.iloc[0]))

    def test_missing_output_reports_clear_error_without_download(self):
        with tempfile.TemporaryDirectory() as name,offline():
            with self.assertRaisesRegex(DashboardDataError,"manifest"):
                load_dashboard_bundle(Path(name))

    def test_invalid_deployment_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            path=root/'dashboard/data'
            path.mkdir(parents=True)
            (path/'manifest.json').write_text('{"schema_version":999,"files":{}}')
            with self.assertRaises(DashboardDataError):
                load_dashboard_bundle(root)


class DashboardDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with offline():
            cls.bundle=load_dashboard_bundle()

    def test_loads_reviewed_baseline_without_backtest_or_download(self):
        with offline(),patch('mft109.backtesting.engine.run_backtest',side_effect=AssertionError('No new backtests')):
            bundle=load_dashboard_bundle()
        self.assertEqual(len(bundle.daily),2514)
        self.assertAlmostEqual(bundle.daily.strategy_nav.iloc[-1],6.225346615575381,places=11)
        self.assertAlmostEqual(bundle.daily.portfolio_value_usd.iloc[-1],622534.6615575381,places=6)
        self.assertAlmostEqual(bundle.daily.spy_nav.iloc[-1],4.002530196823173,places=11)

    def test_formations_chronological_unique_and_include_final_signal(self):
        dates=formation_dates(self.bundle)
        self.assertEqual(len(dates),120)
        self.assertEqual(dates[0],pd.Timestamp('2016-01-29'))
        self.assertEqual(dates[-1],pd.Timestamp('2025-12-31'))
        self.assertEqual(dates,sorted(set(dates)))

    def test_final_formation_never_invents_2026_execution_or_weights(self):
        view=portfolio_view(self.bundle,pd.Timestamp('2025-12-31'))
        self.assertTrue(pd.isna(view.execution_date))
        self.assertIsNone(view.cash_weight)
        self.assertTrue(view.table.target_weight.isna().all())

    def test_executed_portfolio_uses_core_targets_and_preserves_scores(self):
        before=self.bundle.selected.copy(deep=True)
        with offline():
            view=portfolio_view(self.bundle,pd.Timestamp('2025-11-28'))
        self.assertEqual(view.execution_date,pd.Timestamp('2025-12-01'))
        self.assertEqual(len(view.table),20)
        np.testing.assert_allclose(view.table.target_weight,.05)
        self.assertEqual(view.cash_weight,0.)
        self.assertIn('PANW',view.table.ticker.values)
        self.assertNotIn('V',view.table.ticker.values)
        assert_frame_equal(self.bundle.selected,before)

    def test_arbitrary_formation_not_accepted(self):
        with self.assertRaises(DashboardDataError):
            portfolio_view(self.bundle,pd.Timestamp('2025-11-27'))

    def test_all_sensitivity_groups_preserve_catalog_order_and_one_baseline(self):
        self.assertEqual(sum(map(len,self.bundle.sensitivity.values())),21)
        for group,frame in self.bundle.sensitivity.items():
            before=frame.copy(deep=True)
            view=sensitivity_view(frame,group)
            display=sensitivity_table(view)
            self.assertEqual(len(display),len(frame))
            self.assertEqual(view.Baseline.eq('Baseline').sum(),1)
            assert_frame_equal(frame,before)

    def test_signature_contains_source_and_output_identities(self):
        signature=bundle_signature()
        self.assertIn('baseline_daily.parquet',' '.join(row[0] for row in signature))
        self.assertIn('manifest.json',' '.join(row[0] for row in signature))
        self.assertNotIn('data/cache',str(signature))

    def test_modified_saved_metric_is_rejected(self):
        original=pd.read_csv
        def altered(path,*args,**kwargs):
            frame=original(path,*args,**kwargs)
            if Path(path).name=='baseline_performance.csv':
                frame.loc[0,'Strategy']+=1
            return frame
        with patch('mft109.visualization.dashboard_data.pd.read_csv',side_effect=altered),offline():
            with self.assertRaisesRegex(DashboardDataError,'does not match'):
                load_dashboard_bundle()

    def test_mislabeled_baseline_is_rejected(self):
        original=pd.read_csv
        def altered(path,*args,**kwargs):
            frame=original(path,*args,**kwargs)
            if Path(path).name=='phase7_top_n.csv':
                frame['is_baseline']=[True,False,False,False]
            return frame
        with patch('mft109.visualization.dashboard_data.pd.read_csv',side_effect=altered),offline():
            with self.assertRaisesRegex(DashboardDataError,'sensitivity'):
                load_dashboard_bundle()

    def test_missing_sensitivity_field_fails_gracefully(self):
        original=pd.read_csv
        def altered(path,*args,**kwargs):
            frame=original(path,*args,**kwargs)
            return frame.drop(columns='parameter_value') if Path(path).name=='phase7_top_n.csv' else frame
        with patch('mft109.visualization.dashboard_data.pd.read_csv',side_effect=altered),offline():
            with self.assertRaises(DashboardDataError):
                load_dashboard_bundle()

    def test_all_chart_specs_are_valid_and_inputs_unchanged(self):
        b=self.bundle
        before=b.daily.copy(deep=True)
        selected=b.selected.loc[b.selected.formation_date.eq('2025-11-28')]
        view=sensitivity_view(b.sensitivity['top_n'],'top_n')
        for chart in (charts.time_chart(b.daily),charts.time_chart(b.daily,drawdown=True),
                      charts.annual_chart(b.annual),charts.factor_heatmap(selected),
                      charts.sensitivity_chart(view,'Sharpe Ratio')):
            spec=chart.to_dict(validate=True)
            self.assertIn('title',spec)
            self.assertIn('encoding',spec)
        assert_frame_equal(b.daily,before)

    def test_all_page_modules_import_without_data_reads(self):
        paths=[PROJECT_ROOT/'dashboard/Home.py',*sorted((PROJECT_ROOT/'dashboard/pages').glob('*.py'))]
        with patch('pandas.read_parquet',side_effect=AssertionError('Import must not read data')), \
                patch('pandas.read_csv',side_effect=AssertionError('Import must not read data')):
            for i,path in enumerate(paths):
                spec=importlib.util.spec_from_file_location(f'dashboard_page_import_{i}',path)
                module=importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertTrue(callable(module.main))


class StreamlitSmokeTests(unittest.TestCase):
    def app(self,name):
        with patch('yfinance.download',side_effect=AssertionError('No market-data downloads')):
            app=AppTest.from_file(str(PROJECT_ROOT/'dashboard'/name),default_timeout=30).run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        return app

    def test_home_executes_and_displays_computed_kpis(self):
        app=self.app('Home.py')
        self.assertEqual(len(app.metric),8)
        self.assertIn('$622,534.66',[m.value for m in app.metric])

    def test_performance_page_executes(self):
        app=self.app('pages/1_Performance.py')
        self.assertEqual(len(app.dataframe),2)

    def test_portfolio_default_and_historical_date_control(self):
        app=self.app('pages/2_Portfolio.py')
        self.assertGreater(len(app.info),0)
        self.assertTrue(app.dataframe[0].value['Target weight'].eq('—').all())
        app.selectbox(key="formation_date_portfolio").select_index(118).run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(app.dataframe[0].value['Target weight'].eq('5.00%').all())

    def test_factors_page_executes(self):
        app=self.app('pages/3_Factors.py')
        self.assertEqual(len(app.selectbox),2)

    def test_sensitivity_controls_display_only_predefined_groups(self):
        app=self.app('pages/4_Sensitivity.py')
        self.assertEqual(len(app.selectbox(key="sensitivity_group").options),6)
        app.selectbox(key="sensitivity_group").select_index(5).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.dataframe[0].value),5)

    def test_missing_data_renders_warning_without_fabricated_metrics(self):
        with patch('dashboard.components.loaders.bundle_signature',side_effect=DashboardDataError('Missing baseline_daily.parquet')):
            app=AppTest.from_file(str(PROJECT_ROOT/'dashboard/Home.py'),default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.error),1)
        self.assertEqual(len(app.metric),0)


class DeploymentArtifactTests(unittest.TestCase):
    def test_required_artifacts_exist_and_are_not_ignored(self):
        import subprocess
        from mft109.visualization.dashboard_data import ARTIFACT_NAMES
        for name in ("manifest.json", *ARTIFACT_NAMES):
            path=PROJECT_ROOT/'dashboard/data'/name
            self.assertTrue(path.is_file(), name)
            self.assertNotEqual(subprocess.run(['git','check-ignore','-q',str(path)],cwd=PROJECT_ROOT).returncode,0)

    def test_loads_from_repository_copy_without_cache_or_outputs(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            shutil.copytree(PROJECT_ROOT/'dashboard/data',root/'dashboard/data')
            with offline(), patch('mft109.backtesting.engine.run_backtest', side_effect=AssertionError('No backtest')):
                bundle=load_dashboard_bundle(root)
                view=portfolio_view(bundle,pd.Timestamp('2025-11-28'),root)
            self.assertEqual(len(bundle.daily),2514)
            self.assertEqual(len(bundle.summary),5)
            self.assertEqual(len(bundle.annual),10)
            self.assertEqual(len(bundle.selected),2400)
            self.assertEqual(sum(map(len,bundle.sensitivity.values())),21)
            self.assertEqual(view.execution_date,pd.Timestamp('2025-12-01'))
            np.testing.assert_array_equal(view.table.target_weight,.05)
            self.assertFalse((root/'data').exists())
            self.assertFalse((root/'outputs').exists())

    def test_default_paths_are_independent_of_working_directory(self):
        import os
        before=Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as name:
                os.chdir(name)
                self.assertEqual(output_directory(),PROJECT_ROOT/'dashboard/data')
                self.assertEqual(len(load_dashboard_bundle().summary),5)
        finally:
            os.chdir(before)

    def test_export_preserves_all_reviewed_numeric_tables_and_targets(self):
        from dashboard.export_data import load_dashboard_bundle as source_bundle, portfolio_view as source_view
        from phase8_support import approved_cache
        approved_cache()
        source=source_bundle()
        deployed=load_dashboard_bundle()
        assert_frame_equal(source.daily,deployed.daily,check_exact=True)
        assert_frame_equal(source.summary,deployed.summary,check_exact=True)
        assert_frame_equal(source.annual,deployed.annual,check_exact=True)
        for group in source.sensitivity:
            assert_frame_equal(source.sensitivity[group],deployed.sensitivity[group],check_exact=True)
        cols=['formation_date','ticker','rank','composite_score',*SCORE_LABELS]
        assert_frame_equal(source.selected[cols],deployed.selected[cols],check_exact=True)
        for date in formation_dates(source):
            a=source_view(source,date)
            b=portfolio_view(deployed,date)
            self.assertEqual(str(a.execution_date),str(b.execution_date))
            self.assertEqual(a.cash_weight,b.cash_weight)
            np.testing.assert_array_equal(a.table.target_weight,b.table.target_weight)

    def test_artifact_corruption_fails_instead_of_substituting(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            shutil.copytree(PROJECT_ROOT/'dashboard/data',root/'dashboard/data')
            with (root/'dashboard/data/baseline_performance.csv').open('a') as stream:
                stream.write('corruption')
            with self.assertRaisesRegex(DashboardDataError,'checksum'):
                load_dashboard_bundle(root)

    def test_export_provenance_identifies_unchanged_approved_sources(self):
        from phase8_support import approved_cache
        approved_cache()
        import json
        import hashlib
        manifest=json.loads((output_directory()/'manifest.json').read_text())
        for name,digest in manifest['source_sha256'].items():
            self.assertEqual(hashlib.sha256((PROJECT_ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(manifest['baseline_settings']['top_n'],20)
        self.assertEqual(manifest['baseline_settings']['transaction_cost_rate'],.001)
        self.assertEqual(manifest['baseline_settings']['risk_free_rate'],0.)

    def test_bundle_endpoints_are_exact_approved_values(self):
        b=load_dashboard_bundle()
        self.assertEqual(b.daily.strategy_nav.iloc[-1],6.225346615575381)
        self.assertEqual(b.daily.portfolio_value_usd.iloc[-1],622534.6615575381)
        self.assertEqual(b.daily.spy_nav.iloc[-1],4.002530196823173)

    def test_console_launcher_imports_all_pages_without_repository_on_sys_path(self):
        import subprocess
        import sys
        for path in [PROJECT_ROOT/'dashboard/Home.py',*sorted((PROJECT_ROOT/'dashboard/pages').glob('*.py'))]:
            code = "\n".join([
                "import sys; from pathlib import Path",
                "from streamlit.testing.v1 import AppTest",
                f"root=Path({str(PROJECT_ROOT)!r})",
                "sys.path=[p for p in sys.path if p and Path(p).resolve()!=root]",
                f"app=AppTest.from_file({str(path)!r},default_timeout=30).run()",
                "assert not app.exception, str(app.exception)",
                "assert not app.error, str(app.error)",
            ])
            result=subprocess.run([sys.executable,'-B','-c',code],cwd=PROJECT_ROOT,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_runtime_adapter_has_no_quantitative_or_export_imports(self):
        import ast
        source=(PROJECT_ROOT/'mft109/visualization/dashboard_data.py').read_text()
        modules=[node.module for node in ast.walk(ast.parse(source)) if isinstance(node,ast.ImportFrom)]
        self.assertEqual([m for m in modules if m.startswith('mft109.')],['mft109.config'])
        self.assertNotIn('dashboard.export_data',source)


if __name__ == '__main__':
    unittest.main()
