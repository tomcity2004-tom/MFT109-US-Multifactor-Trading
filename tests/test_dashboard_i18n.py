"""Phase 9.1 display-only localization and cross-page session behavior."""

import ast
import hashlib
import json
from pathlib import Path
from string import Formatter
import subprocess
import unittest
from unittest.mock import patch

import numpy as np
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from dashboard.components.i18n import LANGUAGES, TRANSLATIONS, t
from dashboard.components import charts
from dashboard.components.formatting import comparison_table, portfolio_table, sensitivity_view, sensitivity_table
from mft109.config import PROJECT_ROOT
from mft109.visualization.dashboard_data import load_dashboard_bundle, portfolio_view, GROUP_LABELS
from phase8_support import offline


PAGES = ['Home.py', 'pages/1_Performance.py', 'pages/2_Portfolio.py',
         'pages/3_Factors.py', 'pages/4_Sensitivity.py']


class TranslationTests(unittest.TestCase):
    def test_supported_languages_and_english_default(self):
        self.assertEqual(LANGUAGES, {'en': 'English', 'zh_TW': '繁體中文'})
        self.assertEqual(t('Performance'), 'Performance')
        self.assertEqual(t('Performance', 'zh_TW'), '績效分析')

    def test_dictionary_keys_and_format_placeholders_match(self):
        self.assertEqual(set(TRANSLATIONS['en']), set(TRANSLATIONS['zh_TW']))
        for key, english in TRANSLATIONS['en'].items():
            fields=lambda text: {f for _,f,_,_ in Formatter().parse(text) if f is not None}
            self.assertTrue(TRANSLATIONS['zh_TW'][key].strip(), key)
            self.assertEqual(fields(english), fields(TRANSLATIONS['zh_TW'][key]), key)

    def test_missing_keys_locales_and_placeholders_fail_explicitly(self):
        for action in (lambda: t('missing-key'), lambda: t('Performance','unsupported'),
                       lambda: t('{value} sessions','zh_TW')):
            with self.assertRaises(KeyError): action()

    def test_all_literal_translation_keys_exist(self):
        for path in (PROJECT_ROOT/'dashboard').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                        and node.func.id in ('t','configure','translated_choice') and node.args
                        and isinstance(node.args[0],ast.Constant)):
                    self.assertIn(node.args[0].value,TRANSLATIONS['en'],str(path))

    def test_critical_financial_and_sensitivity_terms_are_translated(self):
        keys=['Cumulative Return','CAGR','Annualized Volatility','Sharpe Ratio','Maximum Drawdown',
              'CompositeScore','Target weight','Momentum','Low Volatility','Liquidity','Reversal',
              *GROUP_LABELS.values()]
        for key in keys:
            self.assertTrue(any('\u3400' <= c <= '\u9fff' for c in t(key,'zh_TW')),key)

    def test_formulas_are_identical_to_reviewed_phase9(self):
        path='dashboard/pages/3_Factors.py'
        original=subprocess.check_output(['git','show',f'HEAD:{path}'],cwd=PROJECT_ROOT,text=True)
        def formulas(source):
            return [n.args[0].value for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call)
                    and isinstance(n.func,ast.Attribute) and n.func.attr=='latex']
        self.assertEqual(formulas(original),formulas((PROJECT_ROOT/path).read_text()))


class BilingualDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=load_dashboard_bundle()

    def test_baseline_values_are_exact_and_language_independent(self):
        b=self.bundle
        self.assertEqual(b.daily.strategy_nav.iloc[-1],6.225346615575381)
        self.assertEqual(b.daily.portfolio_value_usd.iloc[-1],622534.6615575381)
        self.assertEqual(b.daily.spy_nav.iloc[-1],4.002530196823173)
        en=comparison_table(b.summary,'en')
        zh=comparison_table(b.summary,'zh_TW')
        np.testing.assert_array_equal(en.iloc[:,1:].to_numpy(),zh.iloc[:,1:].to_numpy())
        self.assertEqual(zh.columns.tolist(),['指標','策略','SPY'])

    def test_portfolio_and_all_sensitivity_tables_preserve_values_and_inputs(self):
        b=self.bundle;before=b.selected.copy(deep=True)
        view=portfolio_view(b,'2025-11-28')
        np.testing.assert_array_equal(portfolio_table(view.table,'en').to_numpy(),portfolio_table(view.table,'zh_TW').to_numpy())
        for group,source in b.sensitivity.items():
            original=source.copy(deep=True)
            en=sensitivity_table(sensitivity_view(source,group,'en'),'en')
            zh=sensitivity_table(sensitivity_view(source,group,'zh_TW'),'zh_TW')
            np.testing.assert_array_equal(en.iloc[:,2:].to_numpy(),zh.iloc[:,2:].to_numpy())
            self.assertEqual(len(en),len(zh))
            assert_frame_equal(source,original,check_exact=True)
        assert_frame_equal(b.selected,before,check_exact=True)

    def test_chart_schemas_localize_without_changing_numeric_points(self):
        b=self.bundle;before=b.daily.copy(deep=True)
        selected=b.selected.loc[b.selected.formation_date.eq('2025-11-28')]
        for factory in [lambda lang: charts.time_chart(b.daily,language=lang),
                        lambda lang: charts.time_chart(b.daily,drawdown=True,language=lang),
                        lambda lang: charts.annual_chart(b.annual,language=lang),
                        lambda lang: charts.factor_heatmap(selected,language=lang),
                        lambda lang: charts.sensitivity_chart(sensitivity_view(b.sensitivity['top_n'],'top_n',lang),'Sharpe Ratio',language=lang)]:
            en,zh=factory('en'),factory('zh_TW')
            self.assertNotEqual(en.to_dict(validate=True)['title'],zh.to_dict(validate=True)['title'])
            np.testing.assert_array_equal(en.data.select_dtypes(include=np.number).to_numpy(),zh.data.select_dtypes(include=np.number).to_numpy())
        assert_frame_equal(b.daily,before,check_exact=True)

    def test_drawdown_y_padding_preserves_original_dates_and_nonpositive_daily_series(self):
        b=self.bundle
        before=b.daily.copy(deep=True)
        for language in ('en','zh_TW'):
            chart=charts.time_chart(b.daily,drawdown=True,language=language)
            spec=chart.to_dict(validate=True)
            x=spec['encoding']['x']
            self.assertEqual(x['type'],'temporal')
            self.assertEqual(x,{'field':'date','title':t('Date',language),'type':'temporal'})
            y=spec['encoding']['y']
            self.assertEqual(y['scale'],{'domain':[-.40,.05],'nice':False})
            self.assertEqual(y['axis']['format'],'.0%')
            self.assertEqual(y['axis']['values'],[tick/100 for tick in range(-40,6,5)])
            self.assertEqual(y['title'],t('Drawdown',language))
            self.assertTrue((chart.data[[t('Strategy',language),'SPY']]<=0).all().all())
            expected=b.daily[['date','strategy_drawdown','spy_drawdown']].rename(
                columns={'strategy_drawdown':t('Strategy',language),'spy_drawdown':'SPY'})
            assert_frame_equal(chart.data,expected,check_exact=True)
            self.assertEqual(len(chart.data),2514)
            self.assertEqual(spec['transform'],[{'fold':[t('Strategy',language),'SPY'],'as':['Series','Value']}])
            self.assertNotIn('timeUnit',x)
            self.assertEqual(spec['encoding']['tooltip'][0]['format'],'%Y-%m-%d')
            self.assertEqual(spec['encoding']['tooltip'][2]['format'],'.2%')
            nav_x=charts.time_chart(b.daily,language=language).to_dict(validate=True)['encoding']['x']
            self.assertEqual(nav_x,{'field':'date','title':t('Date',language),'type':'temporal'})
            nav_y=charts.time_chart(b.daily,language=language).to_dict(validate=True)['encoding']['y']
            self.assertNotIn('scale',nav_y)
            self.assertEqual(nav_y['axis'],{'format':'.1f'})
        assert_frame_equal(b.daily,before,check_exact=True)

    def test_deployment_artifact_bytes_match_git_main(self):
        for path in (PROJECT_ROOT/'dashboard/data').iterdir():
            saved=subprocess.check_output(['git','show',f'HEAD:{path.relative_to(PROJECT_ROOT)}'],cwd=PROJECT_ROOT)
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),hashlib.sha256(saved).digest())


class BilingualPageTests(unittest.TestCase):
    def app(self,page='Home.py',language='en'):
        with offline():
            app=AppTest.from_file(str(PROJECT_ROOT/'dashboard'/page),default_timeout=30).run()
            if language=='zh_TW':app.selectbox(key='_language_choice').select('繁體中文').run()
        self.assertFalse(app.exception,str(app.exception));self.assertFalse(app.error,str(app.error))
        return app

    def test_english_pages_render(self):
        for page in PAGES:
            with self.subTest(page=page):
                app=self.app(page)
                self.assertEqual(app.selectbox(key='_language_choice').value,'English')

    def test_chinese_pages_render_with_charts_tables_and_no_english_body(self):
        for page in PAGES:
            with self.subTest(page=page):
                app=self.app(page,'zh_TW')
                self.assertTrue(any('\u3400' <= c <= '\u9fff' for c in app.title[0].value))
                for element in [*app.caption,*app.subheader,*app.info,*app.markdown]:
                    value=element.value
                    # MFT109 sidebar title and mathematical expressions retain identifiers.
                    self.assertTrue(any('\u3400' <= c <= '\u9fff' for c in value),value)
                if 'Performance' in page or 'Portfolio' in page or 'Sensitivity' in page:
                    self.assertTrue(app.dataframe)
                if 'Portfolio' not in page:
                    self.assertTrue(app.get('vega_lite_chart'))

    def test_language_persists_through_native_page_navigation_and_back(self):
        app=self.app(language='zh_TW')
        for page in PAGES[1:]+[PAGES[0]]:
            with offline():app.switch_page(page).run()
            self.assertFalse(app.exception,str(app.exception))
            self.assertEqual(app.session_state['dashboard_language'],'zh_TW')
            self.assertEqual(app.selectbox(key='_language_choice').value,'繁體中文')
        app.selectbox(key='_language_choice').select('English').run()
        app.switch_page(PAGES[1]).run()
        self.assertEqual(app.title[0].value,'Performance')
        self.assertEqual(app.session_state['dashboard_language'],'en')

    def test_switching_language_preserves_kpi_numbers(self):
        app=self.app()
        before=[m.value for m in app.metric]
        app.selectbox(key='_language_choice').select('繁體中文').run()
        self.assertEqual(before,[m.value for m in app.metric])
        self.assertIn('$622,534.66',before)
        self.assertIn('最終投資組合價值（美元）',[m.label for m in app.metric])
        app.selectbox(key='_language_choice').select('English').run()
        self.assertEqual(before,[m.value for m in app.metric])

    def test_chinese_historical_portfolio_weights_and_final_signal(self):
        app=self.app('pages/2_Portfolio.py','zh_TW')
        self.assertTrue(app.dataframe[0].value['目標權重'].eq('—').all())
        app.selectbox(key='formation_date_portfolio').select_index(118).run()
        self.assertFalse(app.exception,str(app.exception))
        self.assertTrue(app.dataframe[0].value['目標權重'].eq('5.00%').all())
        app.selectbox(key='_language_choice').select('English').run()
        self.assertTrue(app.dataframe[0].value['Target weight'].eq('5.00%').all())

    def test_sensitivity_choices_preserved_when_language_changes(self):
        app=self.app('pages/4_Sensitivity.py')
        app.selectbox(key='sensitivity_group').select_index(5).run()
        app.selectbox(key='sensitivity_metric').select_index(1).run()
        before=app.dataframe[0].value.iloc[:,2:].to_numpy()
        app.selectbox(key='_language_choice').select('繁體中文').run()
        self.assertFalse(app.exception,str(app.exception))
        self.assertEqual(app.session_state['choice_sensitivity_group'],'factor_weights')
        self.assertEqual(app.session_state['choice_sensitivity_metric'],'Sharpe Ratio')
        np.testing.assert_array_equal(before,app.dataframe[0].value.iloc[:,2:].to_numpy())

    def test_all_chinese_sensitivity_groups_and_metrics_render(self):
        app=self.app('pages/4_Sensitivity.py','zh_TW')
        for group in range(6):
            app.selectbox(key='sensitivity_group').select_index(group).run()
            for metric in range(3):
                app.selectbox(key='sensitivity_metric').select_index(metric).run()
                self.assertFalse(app.exception,str(app.exception))
                self.assertFalse(app.error,str(app.error))

    def test_chinese_missing_data_has_translated_error_without_fake_kpis(self):
        app=self.app(language='zh_TW')
        from mft109.visualization.dashboard_data import DashboardDataError
        with patch('dashboard.components.loaders.bundle_signature',side_effect=DashboardDataError('Missing artifact')):
            app.run()
        self.assertFalse(app.exception,str(app.exception))
        self.assertEqual(len(app.metric),0)
        self.assertEqual(app.error[0].value,t('Reviewed project data could not be loaded. No results have been substituted.','zh_TW'))
        self.assertEqual(app.warning[0].value,t('Required deployment data are missing or inconsistent.','zh_TW'))
