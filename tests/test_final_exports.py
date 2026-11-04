"""Final-package identity, financial-data preservation and reproducibility checks."""

import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from mft109.analysis.final_exports import (
    export_final_report, PACKAGE_FILES, CSV_FILES, FIGURE_FILES, DOCUMENTS,
    PHASE10A_CHECKPOINT, methodology_parameters, factor_definitions,
    comparison_figure, annual_figure, sensitivity_figure,
)
from mft109.config import BASELINE, PROJECT_ROOT
from mft109.visualization.dashboard_data import load_dashboard_bundle
from phase8_support import offline

PACKAGE=PROJECT_ROOT/'outputs/final_report/v1'
ANALYSIS=PROJECT_ROOT/'outputs/final_analysis'


class FinalPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=load_dashboard_bundle()
        cls.manifest=json.loads((PACKAGE/'manifest.json').read_text())

    def test_required_files_are_complete_and_eligible_for_tracking(self):
        files={str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob('*') if p.is_file()}
        self.assertEqual(files,set(PACKAGE_FILES))
        self.assertEqual(len(files),26)
        for name in files:
            self.assertNotEqual(subprocess.run(['git','check-ignore','-q',str(PACKAGE/name)],cwd=PROJECT_ROOT).returncode,0,name)

    def test_performance_schema_and_exact_official_values(self):
        table=pd.read_csv(PACKAGE/'performance_summary.csv')
        self.assertEqual(table.columns.tolist(),['Series','Final NAV','Cumulative Return','CAGR','Annualized Volatility','Sharpe Ratio','Maximum Drawdown','Final Portfolio Value (USD)'])
        self.assertEqual(table.Series.tolist(),['Strategy','SPY'])
        values=table.set_index('Series')
        self.assertEqual(values.at['Strategy','Final NAV'],6.225346615575381)
        self.assertEqual(values.at['SPY','Final NAV'],4.002530196823173)
        self.assertEqual(values.at['Strategy','Final Portfolio Value (USD)'],622534.6615575381)
        self.assertEqual(values.at['Strategy','Maximum Drawdown'],-.35452504758611847)
        self.assertTrue(pd.isna(values.at['SPY','Final Portfolio Value (USD)']))
        for source,target in [('Annualized Return','CAGR'),('Cumulative Return','Cumulative Return'),
                              ('Annualized Volatility','Annualized Volatility'),('Sharpe Ratio','Sharpe Ratio'),('Maximum Drawdown','Maximum Drawdown')]:
            np.testing.assert_array_equal(values[target],self.bundle.summary.set_index('Metric').loc[source])

    def test_annual_return_coverage_and_values(self):
        actual=pd.read_csv(PACKAGE/'annual_returns.csv')
        self.assertEqual(actual.Year.tolist(),list(range(2016,2026)))
        assert_frame_equal(actual,self.bundle.annual[['Year','Strategy','SPY']],check_exact=True)

    def test_daily_returns_nav_and_drawdowns_are_unmodified(self):
        actual=pd.read_csv(PACKAGE/'baseline_daily.csv',parse_dates=['date'])
        expected=self.bundle.daily.copy()
        np.testing.assert_array_equal(actual.date.to_numpy(),expected.date.to_numpy())
        assert_frame_equal(actual.drop(columns='date'),expected.drop(columns='date'),check_exact=True)
        self.assertEqual(len(actual),2514)
        self.assertTrue((actual[['strategy_drawdown','spy_drawdown']]<=0).all().all())

    def test_portfolio_scores_targets_and_unexecuted_final_signal(self):
        actual=pd.read_csv(PACKAGE/'portfolio_snapshots.csv',parse_dates=['formation_date','execution_date'])
        expected=self.bundle.selected
        for column in ['formation_date','execution_date']:
            np.testing.assert_array_equal(actual[column].to_numpy(),expected[column].to_numpy())
        assert_frame_equal(actual.drop(columns=['formation_date','execution_date']),expected.drop(columns=['formation_date','execution_date']),check_exact=True)
        self.assertEqual(len(actual),2400)
        self.assertEqual(actual.formation_date.nunique(),120)
        last=actual.loc[actual.formation_date.eq('2025-12-31')]
        self.assertTrue(last[['execution_date','target_weight','cash_weight']].isna().all().all())

    def test_phase10a_csvs_figures_and_provenance_copied_exactly(self):
        mappings={name:name for name in ['descriptive_statistics.csv','normality_tests.csv']}
        mappings.update({f'figures/{name}':name for name in ['strategy_return_distribution.png','spy_return_distribution.png','strategy_qq_plot.png','spy_qq_plot.png']})
        mappings.update({'phase10a_metadata.json':'analysis_metadata.json','phase10a_interpretation.md':'analysis_summary.md'})
        for exported,source in mappings.items():
            self.assertEqual((PACKAGE/exported).read_bytes(),(ANALYSIS/source).read_bytes(),exported)
        tests=pd.read_csv(PACKAGE/'normality_tests.csv')
        self.assertEqual(tests.Alpha.tolist(),[.05,.05])
        self.assertTrue(tests.Conclusion.eq('Reject H0').all())
        self.assertTrue(tests['p-value note'].str.contains('underflow').all())

    def test_sensitivity_matches_all_source_rows_catalog_and_baselines(self):
        actual=pd.read_csv(PACKAGE/'sensitivity_summary.csv',dtype={'parameter_value':str})
        columns=[c for c in next(iter(self.bundle.sensitivity.values())).columns if c not in ['blocking_date','blocking_tickers']]
        expected=pd.concat([f[columns] for f in self.bundle.sensitivity.values()],ignore_index=True)
        assert_frame_equal(actual,expected,check_exact=True)
        self.assertEqual(len(actual),21)
        self.assertEqual(int(actual.is_baseline.sum()),6)
        self.assertEqual(actual.groupby('experiment',sort=False).size().tolist(),[4,4,2,3,3,5])

    def test_methodology_values_match_every_locked_configuration_field(self):
        table=pd.read_csv(PACKAGE/'methodology_parameters.csv',dtype=str,keep_default_na=False)
        values=table.set_index('Parameter').Value
        for key,value in asdict(BASELINE).items():self.assertEqual(values[key],str(value),key)
        self.assertEqual(values['warm_up_period'],'2015-01-01 through 2015-12-31')
        self.assertEqual(values['universe_snapshot_rows'],'503')
        self.assertEqual(values['cross_sectional_zscore_ddof'],'0')
        self.assertEqual(values['forward_fill'],'Never')
        self.assertFalse(table.Parameter.duplicated().any())

    def test_factor_definitions_exact_windows_signs_and_equal_weights(self):
        table=pd.read_csv(PACKAGE/'factor_definitions.csv')
        self.assertEqual(len(table),4)
        self.assertEqual(table['Lookback Sessions'].tolist(),[252,60,20,20])
        self.assertEqual(table['Skip Sessions'].tolist(),[21,0,0,0])
        self.assertTrue(table['Composite Weight'].eq(.25).all())
        self.assertEqual(table['Raw Definition'].iloc[0],'P(i,t-21) / P(i,t-252) - 1')
        self.assertIn('ddof=1',table['Raw Definition'].iloc[1])
        self.assertIn('sqrt(252)',table['Raw Definition'].iloc[1])
        self.assertIn('mean(DV(i,t-19:t))',table['Raw Definition'].iloc[2])
        self.assertIn('ln(ADV20(i,t))',table['Raw Definition'].iloc[2])
        self.assertEqual(table['Raw Definition'].iloc[3],'Reversal(i,t) = -(P(i,t)/P(i,t-20)-1)')
        self.assertEqual(table['Standardized Score'].tolist(),['M(i,t) = Z(Momentum(i,t))','LV(i,t) = -Z(Volatility(i,t))','L(i,t) = Z(LiquidityRaw(i,t))','R(i,t) = Z(Reversal(i,t))'])

    def test_manifest_output_hashes_paths_and_baseline_identifiers(self):
        manifest=self.manifest
        self.assertEqual(manifest['export_version'],'v1')
        self.assertEqual(manifest['source_checkpoint_commit'],PHASE10A_CHECKPOINT)
        self.assertEqual(manifest['source_data_version'],'fisv_revision_20261029T170124Z')
        self.assertEqual(set(manifest['files']),set(PACKAGE_FILES)-{'manifest.json'})
        for name,record in manifest['files'].items():
            path=PACKAGE/name
            self.assertEqual(path.stat().st_size,record['bytes'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),record['sha256'])
        for name,digest in manifest['sources_sha256'].items():
            self.assertEqual(hashlib.sha256((PROJECT_ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(manifest['validated_baseline_endpoints']['strategy_nav'],6.225346615575381)
        for name in manifest['documentation']:self.assertTrue((PROJECT_ROOT/name).is_file(),name)

    def test_figure_files_are_high_resolution_pngs(self):
        self.assertEqual(len(FIGURE_FILES),13)
        for name in FIGURE_FILES:
            data=(PACKAGE/'figures'/name).read_bytes()
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
            width,height=struct.unpack('>II',data[16:24])
            self.assertGreaterEqual(width,2000);self.assertGreaterEqual(height,1400)

    def test_data_quality_context_distinguishes_historical_and_revised_evidence(self):
        table=pd.read_csv(PACKAGE/'data_quality_context.csv')
        self.assertTrue(table['Evidence status'].str.contains('Historical').any())
        self.assertIn('predates',table.loc[table.Topic.eq('Older quality report'),'Evidence / treatment'].iloc[0])
        self.assertIn('restored',table.loc[table.Topic.eq('FISV gap'),'Evidence / treatment'].iloc[0])
        self.assertIn('not a fresh vendor audit',table.loc[table.Topic.eq('Available histories'),'Evidence status'].iloc[0])

    def test_new_documents_and_readme_link_to_existing_material(self):
        for relative in ['README.md',*DOCUMENTS]:
            path=PROJECT_ROOT/relative;text=path.read_text()
            self.assertNotIn('625,050',text);self.assertNotIn('625050',text)
            for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
                if link.startswith(('https://','http://','#')):continue
                self.assertTrue((path.parent/link.split('#')[0]).exists(),(relative,link))
        index=(PROJECT_ROOT/'docs/FINAL_EXPORT_INDEX.md').read_text()
        for name in PACKAGE_FILES:self.assertIn(Path(name).name,index)
        self.assertIn('awaiting review',(PROJECT_ROOT/'README.md').read_text())
        self.assertIn('normality',(PROJECT_ROOT/'docs/ASSIGNMENT_MAPPING.md').read_text())

    def test_static_figures_plot_original_observations_without_mutation(self):
        before=self.bundle.daily.copy(deep=True)
        for drawdown in [False,True]:
            figure=comparison_figure(self.bundle.daily,drawdown=drawdown)
            for line,prefix in zip(figure.axes[0].lines,['strategy','spy'],strict=True):
                np.testing.assert_array_equal(line.get_ydata(),self.bundle.daily[f"{prefix}_{'drawdown' if drawdown else 'nav'}"])
                self.assertEqual(len(line.get_xdata()),2514)
            figure.clear()
        for group,table in self.bundle.sensitivity.items():
            original=table.copy(deep=True);figure=sensitivity_figure(table,group)
            for axis,metric in zip(figure.axes,['Annualized Return','Sharpe Ratio','Maximum Drawdown'],strict=True):
                np.testing.assert_array_equal([p.get_height() for p in axis.patches],table[metric])
            figure.clear();assert_frame_equal(table,original,check_exact=True)
        assert_frame_equal(self.bundle.daily,before,check_exact=True)


class FinalExportRegenerationTests(unittest.TestCase):
    def test_repeat_export_is_byte_identical_without_research_or_input_writes(self):
        sources=list((PROJECT_ROOT/'dashboard/data').iterdir())+list(ANALYSIS.iterdir())
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        with tempfile.TemporaryDirectory() as name,offline(), \
                patch('mft109.backtesting.engine.run_backtest',side_effect=AssertionError('No backtest')), \
                patch('mft109.optimization.sensitivity.run_sensitivity',side_effect=AssertionError('No new scenarios')), \
                patch('mft109.analysis.data_analysis.export_analysis',side_effect=AssertionError('Copy approved diagnostics only')):
            directory=export_final_report(output_dir=Path(name))
            for relative in PACKAGE_FILES:
                self.assertEqual(hashlib.sha256((directory/relative).read_bytes()).digest(),hashlib.sha256((PACKAGE/relative).read_bytes()).digest(),relative)
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})

    def test_missing_approved_analysis_fails_without_creating_outputs(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(ValueError,'Phase 10A'):
                export_final_report(output_dir=Path(name)/'result',analysis_dir=Path(name)/'missing')
            self.assertFalse((Path(name)/'result').exists())

    def test_corrupt_phase10a_output_is_not_recomputed(self):
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/'source';shutil.copytree(ANALYSIS,source)
            with (source/'descriptive_statistics.csv').open('a') as stream:stream.write('corruption')
            with self.assertRaisesRegex(ValueError,'checksum'):
                export_final_report(output_dir=Path(name)/'result',analysis_dir=source)
            self.assertFalse((Path(name)/'result').exists())

    def test_protected_and_unrelated_destinations_are_rejected(self):
        for destination in [PROJECT_ROOT/'dashboard/data',PROJECT_ROOT/'outputs/final_analysis']:
            with self.assertRaises(ValueError):export_final_report(output_dir=destination)
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'user_file.txt';path.write_text('preserve')
            with self.assertRaisesRegex(ValueError,'unrelated'):
                export_final_report(output_dir=Path(name))
            self.assertEqual(path.read_text(),'preserve')
