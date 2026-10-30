"""Phase 10A statistical diagnostics; synthetic formula checks and artifact export."""

import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from mft109.analysis.data_analysis import (
    prepare_returns, descriptive_statistics, normality_tests, normality_conclusion,
    distribution_plot, qq_plot, export_analysis, interpretation,
)
from mft109.config import PROJECT_ROOT
from mft109.visualization.dashboard_data import load_dashboard_bundle
from phase8_support import offline


def daily_fixture():
    return pd.DataFrame({'date':pd.bdate_range('2020-01-02',periods=8),
                         'strategy_return':[0.,0.,-.04,-.02,.01,.03,.04,.09],
                         'spy_return':[0.,.01,-.02,.03,-.01,.04,.02,.05]})


class ReturnSampleTests(unittest.TestCase):
    def test_initial_anchor_excluded_but_genuine_zero_retained(self):
        frame=daily_fixture();before=frame.copy(deep=True)
        sample=prepare_returns(frame)
        self.assertEqual(len(sample.returns),7)
        self.assertEqual(sample.returns.Strategy.iloc[0],0.)
        self.assertEqual(sample.metadata['excluded_initial_anchor_date'],'2020-01-02')
        self.assertEqual(sample.metadata['pairwise_missing_rows_excluded'],0)
        assert_frame_equal(frame,before,check_exact=True)

    def test_missing_values_are_pairwise_excluded_and_recorded_without_fill(self):
        frame=daily_fixture()
        frame.loc[2,'strategy_return']=np.nan
        frame.loc[3,'spy_return']=np.nan
        sample=prepare_returns(frame)
        self.assertEqual(sample.metadata['strategy_observations'],6)
        self.assertEqual(sample.metadata['spy_observations'],6)
        self.assertEqual(sample.metadata['aligned_observations'],5)
        self.assertEqual(sample.metadata['pairwise_missing_rows_excluded'],2)
        self.assertNotIn(frame.date.iloc[2],sample.returns.index)
        self.assertNotIn(frame.date.iloc[3],sample.returns.index)
        self.assertTrue(pd.isna(frame.strategy_return.iloc[2]))

    def test_unsorted_input_is_aligned_chronologically(self):
        frame=daily_fixture()
        a,b=prepare_returns(frame),prepare_returns(frame.iloc[::-1])
        assert_frame_equal(a.returns,b.returns,check_exact=True)
        self.assertEqual(a.metadata,b.metadata)

    def test_duplicate_dates_missing_schema_and_outside_period_rejected(self):
        frame=daily_fixture()
        for invalid in [pd.concat([frame,frame.iloc[:1]]),frame.drop(columns='spy_return'),
                        frame.assign(date=pd.bdate_range('2015-01-02',periods=8))]:
            with self.assertRaises(ValueError):prepare_returns(invalid)

    def test_bad_anchor_infinities_and_nonnumeric_returns_rejected(self):
        frame=daily_fixture()
        for invalid in [frame.assign(strategy_return=.01),frame.assign(spy_return=np.inf)]:
            with self.assertRaises(ValueError):prepare_returns(invalid)
        with self.assertRaises(TypeError):prepare_returns(frame.assign(strategy_return='bad'))

    def test_insufficient_aligned_sample_rejected(self):
        with self.assertRaises(ValueError):prepare_returns(daily_fixture().iloc[:4])


class StatisticalFormulaTests(unittest.TestCase):
    def setUp(self):
        self.values=np.array([-.04,-.02,0.,.01,.03,.09])
        self.returns=pd.DataFrame({'Strategy':self.values,'SPY':self.values[::-1]})
        n=len(self.values);mean=sum(self.values)/n
        self.n=n;self.mean=mean
        self.m2=sum((float(v)-mean)**2 for v in self.values)/n
        self.m3=sum((float(v)-mean)**3 for v in self.values)/n
        self.m4=sum((float(v)-mean)**4 for v in self.values)/n

    def test_count_mean_median_sample_sd_and_extremes(self):
        before=self.returns.copy(deep=True)
        row=descriptive_statistics(self.returns).iloc[0]
        self.assertEqual(row.Count,6)
        self.assertAlmostEqual(row.Mean,self.mean,places=14)
        self.assertAlmostEqual(row.Median,.005,places=14)
        self.assertAlmostEqual(row['Standard Deviation'],math.sqrt(self.n*self.m2/(self.n-1)),places=14)
        self.assertEqual(row.Minimum,-.04);self.assertEqual(row.Maximum,.09)
        assert_frame_equal(self.returns,before,check_exact=True)

    def test_linear_quartiles(self):
        row=descriptive_statistics(self.returns).iloc[0]
        self.assertAlmostEqual(row['25th Percentile'],-.015,places=14)
        self.assertAlmostEqual(row['75th Percentile'],.025,places=14)

    def test_bias_corrected_skewness_independent_formula(self):
        expected=math.sqrt(self.n*(self.n-1))/(self.n-2)*self.m3/self.m2**1.5
        self.assertAlmostEqual(descriptive_statistics(self.returns).iloc[0].Skewness,expected,places=12)

    def test_bias_corrected_fisher_excess_kurtosis_independent_formula(self):
        g2=self.m4/self.m2**2-3
        expected=(self.n-1)/((self.n-2)*(self.n-3))*((self.n+1)*g2+6)
        self.assertAlmostEqual(descriptive_statistics(self.returns).iloc[0]['Excess Kurtosis'],expected,places=12)

    def test_jarque_bera_and_chi_square_two_p_value_independent_formula(self):
        before=self.returns.copy(deep=True)
        g1=self.m3/self.m2**1.5;g2=self.m4/self.m2**2-3
        expected=self.n*(g1*g1/6+g2*g2/24)
        row=normality_tests(self.returns).iloc[0]
        self.assertAlmostEqual(row.Statistic,expected,places=12)
        self.assertAlmostEqual(row['p-value'],math.exp(-expected/2),places=14)
        self.assertAlmostEqual(row['Log p-value'],-expected/2,places=12)
        self.assertEqual(row.Alpha,.05)
        assert_frame_equal(self.returns,before,check_exact=True)

    def test_p_value_threshold_and_invalid_inputs(self):
        self.assertEqual(normality_conclusion(.049999),'Reject H0')
        self.assertEqual(normality_conclusion(.05),'Do not reject H0')
        self.assertEqual(normality_conclusion(1.),'Do not reject H0')
        for invalid in [-.1,1.1,np.inf]:
            with self.assertRaises(ValueError):normality_conclusion(invalid)
        for alpha in [0.,1.,np.nan]:
            with self.assertRaises(ValueError):normality_conclusion(.5,alpha)

    def test_constant_sample_is_undefined_not_a_normality_claim(self):
        frame=pd.DataFrame({'Strategy':[0.]*8,'SPY':[.01]*8})
        descriptive=descriptive_statistics(frame);tests=normality_tests(frame)
        self.assertTrue(descriptive.Skewness.isna().all())
        self.assertTrue(descriptive['Excess Kurtosis'].isna().all())
        self.assertTrue(tests['p-value'].isna().all())
        self.assertTrue(tests.Conclusion.str.startswith('Undefined').all())

    def test_constant_sample_interpretation_does_not_claim_zero_skew_or_normality(self):
        frame=daily_fixture().assign(strategy_return=0.,spy_return=0.)
        sample=prepare_returns(frame)
        text=interpretation(descriptive_statistics(sample.returns),normality_tests(sample.returns),sample.metadata)
        self.assertIn('skewness undefined',text)
        self.assertIn('Excess kurtosis is undefined',text)
        self.assertIn('Undefined: constant sample',text)
        self.assertNotIn('skewness 0.000000',text)

    def test_underflow_is_reported_with_finite_log_p_value(self):
        values=np.zeros(100);values[-1]=1.
        row=normality_tests(pd.DataFrame({'Strategy':values,'SPY':values})).iloc[0]
        self.assertEqual(row['p-value'],0.)
        self.assertTrue(np.isfinite(row['Log p-value']))
        self.assertIn('underflow',row['p-value note'])
        self.assertEqual(row.Conclusion,'Reject H0')

    def test_nonfinite_or_insufficient_samples_rejected(self):
        for values in [[1.,2.,3.],[0.,1.,np.nan,2.],[0.,1.,np.inf,2.]]:
            with self.assertRaises(ValueError):descriptive_statistics(pd.DataFrame({'Strategy':values,'SPY':values}))


class PlotTests(unittest.TestCase):
    def test_histogram_keeps_extremes_and_density_matches_normal_units(self):
        values=np.array([-.2,-.02,-.01,0.,.01,.02,.2])
        bins=np.histogram_bin_edges(values,bins='fd')
        figure=distribution_plot(values,'Strategy',bins)
        axis=figure.axes[0]
        area=sum(rect.get_height()*rect.get_width() for rect in axis.patches)
        self.assertAlmostEqual(area,1.,places=12)
        self.assertLessEqual(axis.get_xlim()[0],values.min())
        self.assertGreaterEqual(axis.get_xlim()[1],values.max())
        self.assertEqual(axis.get_xlabel(),'Daily return (%)')
        grid,density=axis.lines[0].get_data()
        sigma=np.std(values,ddof=1)
        expected=np.exp(-.5*((grid-values.mean())/sigma)**2)/(sigma*np.sqrt(2*np.pi))
        np.testing.assert_allclose(density,expected,rtol=1e-13)
        figure.clear()

    def test_histogram_rejects_clipped_bin_range(self):
        with self.assertRaises(ValueError):distribution_plot([-.2,0,.01,.2],'Strategy',[-.1,0,.1])

    def test_qq_plot_has_every_sorted_observation_and_reference_line(self):
        values=np.array([-.2,-.01,0,.02,.2])
        figure=qq_plot(values,'SPY')
        axis=figure.axes[0]
        observed=np.asarray(axis.collections[0].get_offsets())[:,1]
        np.testing.assert_array_equal(observed,np.sort(values))
        self.assertEqual(len(axis.lines),1)
        self.assertEqual(axis.get_ylabel(),'Observed daily return (%)')
        figure.clear()


class ValidatedArtifactAnalysisTests(unittest.TestCase):
    def test_current_source_and_official_aligned_counts(self):
        with offline(),patch('mft109.backtesting.engine.run_backtest',side_effect=AssertionError('No strategy execution')):
            b=load_dashboard_bundle();sample=prepare_returns(b.daily)
        self.assertEqual(sample.metadata['source_rows'],2514)
        self.assertEqual(sample.metadata['excluded_initial_anchor_date'],'2016-01-04')
        self.assertEqual(sample.metadata['analysis_first_date'],'2016-01-05')
        self.assertEqual(sample.metadata['analysis_last_date'],'2025-12-31')
        self.assertEqual(sample.metadata['strategy_observations'],2513)
        self.assertEqual(sample.metadata['spy_observations'],2513)
        self.assertEqual(sample.metadata['aligned_observations'],2513)
        self.assertEqual(sample.metadata['pairwise_missing_rows_excluded'],0)
        self.assertEqual(b.daily.strategy_nav.iloc[-1],6.225346615575381)
        self.assertEqual(b.daily.portfolio_value_usd.iloc[-1],622534.6615575381)
        self.assertEqual(b.daily.spy_nav.iloc[-1],4.002530196823173)
        self.assertEqual(b.summary.set_index('Metric').at['Maximum Drawdown','Strategy'],-.35452504758611847)

    def test_source_missing_or_corrupt_fails_without_download(self):
        with tempfile.TemporaryDirectory() as name,offline():
            with self.assertRaises(ValueError):export_analysis(Path(name),Path(name)/'outputs/final_analysis')

    def test_corrupt_source_is_not_analyzed_or_replaced(self):
        import shutil
        with tempfile.TemporaryDirectory() as name,offline():
            root=Path(name)
            shutil.copytree(PROJECT_ROOT/'dashboard/data',root/'dashboard/data')
            with (root/'dashboard/data/baseline_daily.parquet').open('ab') as stream:
                stream.write(b'corruption')
            with self.assertRaisesRegex(ValueError,'checksum'):
                export_analysis(root)
            self.assertFalse((root/'outputs/final_analysis').exists())

    def test_export_csv_schema_figures_metadata_and_source_immutability(self):
        sources=list((PROJECT_ROOT/'dashboard/data').iterdir())
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        with tempfile.TemporaryDirectory() as name,offline(),patch('mft109.backtesting.engine.run_backtest',side_effect=AssertionError('No backtest')):
            directory=export_analysis(output_dir=Path(name))
            self.assertEqual(len(list(directory.iterdir())),8)
            table=pd.read_csv(directory/'descriptive_statistics.csv')
            self.assertEqual(table.columns.tolist(),['Series','Count','Mean','Median','Standard Deviation','Minimum','25th Percentile','75th Percentile','Maximum','Skewness','Excess Kurtosis'])
            self.assertEqual(table.Count.tolist(),[2513,2513])
            tests=pd.read_csv(directory/'normality_tests.csv')
            self.assertEqual(tests.Series.tolist(),['Strategy','SPY'])
            self.assertIn('Statistic',tests.columns);self.assertIn('p-value',tests.columns)
            self.assertEqual(tests.Alpha.tolist(),[.05,.05])
            metadata=json.loads((directory/'analysis_metadata.json').read_text())
            self.assertEqual(metadata['primary_source'],'dashboard/data/baseline_daily.parquet')
            self.assertEqual(metadata['source_data_version'],'fisv_revision_20261029T170124Z')
            self.assertFalse(metadata['strategy_or_data_changed'])
            self.assertEqual(len(metadata['source_sha256']),11)
            for path in directory.glob('*.png'):
                data=path.read_bytes()
                self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
                width,height=struct.unpack('>II',data[16:24])
                self.assertGreaterEqual(width,2000);self.assertGreaterEqual(height,1400)
            text=(directory/'analysis_summary.md').read_text()
            self.assertIn('does not prove normality',text)
            self.assertIn('volatility clustering',text)
            for _,row in tests.iterrows():
                if row['p-value']==0:
                    self.assertIn('not exact zero',row['p-value note'])
        self.assertEqual(hashes,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})

    def test_export_refuses_protected_destination(self):
        for destination in [PROJECT_ROOT/'dashboard/data',PROJECT_ROOT/'outputs/optimization']:
            with self.assertRaises(ValueError):export_analysis(output_dir=destination)
