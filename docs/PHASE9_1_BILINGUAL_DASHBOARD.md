# Phase 9.1 — Bilingual Dashboard Enhancement

## Scope

The existing five-page dashboard supports **English** and **繁體中文** using the
same validated financial data, page architecture and charts. This phase changes
presentation text only. Phase 10 has not started. No quantitative methodology,
market cache, universe, deployment data, financial result or dependency pin is
changed. Entry point remains **dashboard/Home.py**.

## Language selection and session behavior

The sidebar selector is labeled **Language / 語言**, with English as the default
for a new session. The supported locale identifiers are `en` and `zh_TW`.
Selection applies immediately to the active page and persists during native
Streamlit navigation between Home, Performance, Portfolio, Factors and
Sensitivity.

`dashboard_language` is durable per-user Streamlit session state. The widget uses
separate `_language_choice` state and copies changes through its callback; this
avoids losing the preference when Streamlit cleans page-specific widget state.
No preference is written to disk or shared between users. Refreshing into a new
session may restore the English default; no cross-session persistence is promised.

Sensitivity controls similarly retain stable experiment/metric identifiers in
session state independently of translated display labels. Changing language does
not change the selected experiment, financial metric, historical target or any
calculation. Portfolio and Factors formation-date controls still select only
existing reviewed snapshots. All data caches remain language-independent.

## Translation architecture

`dashboard/components/i18n.py` owns the supported locales and centralized
`TRANSLATIONS` dictionaries. English phrases are stable translation keys. Both
languages have identical keys and matching formatting placeholders. The pure
helper `t(key, language="en", **values)` raises on unknown keys, locales or missing
placeholders, rather than silently displaying an incomplete mixed-language UI.
There is no external translation service or new dependency.

Pages obtain the locale from shared `configure`, pass it explicitly to display
helpers, and translate text through `t`. Chinese translations are centralized;
the sidebar's fixed bilingual selector label is the deliberate exception.

Shared modules localize page framing, warnings, limitations, KPI labels,
comparison/portfolio/sensitivity tables, scenario labels, chart titles, axes,
legends and tooltips. Chart adapters translate copied display fields without
changing their numerical observations. Financial formatting, units, rounding,
undefined-value `—` rendering and all formula strings are unchanged.

Traditional Chinese terminology includes 動能、低波動、流動性、短期反轉、橫斷面標準化、
綜合因子分數、再平衡、換手率、年化報酬率、夏普比率及最大回撤. Established identifiers
such as NAV, CAGR, SPY, S&P 500, Top 20 and bps remain recognizable. The interface
continues to explain fixed current constituents, survivorship bias, vendor data
revisions, simplified adjusted-close execution and academic/non-advisory use.

## Preserved navigation and technical text

Native filename-based navigation labels (Home, Performance, Portfolio, Factors,
Sensitivity) remain English. Dynamic translation would require changing the
navigation architecture; no duplicate pages or fragile routing were added.
All controllable page/sidebar body text is localized.

Mathematical variable names, ticker symbols, file paths, standard abbreviations,
numeric date/currency formats and native third-party controls are retained where
appropriate. Low-level failure messages are preserved verbatim inside a localized
**Technical diagnostic (original message)** expander. The primary error, warning,
recovery explanation and empty-state guidance are translated, with no fabricated
results or suppressed diagnostics. Native Streamlit/browser chrome is outside
the application translation dictionary.

## Protected data and deployment

The presentation adapter `mft109/visualization/dashboard_data.py`, offline export
utility, all eleven `dashboard/data/` artifacts, configuration, quantitative
modules and prior Phase 0–8 tests remain unchanged. The existing Community Cloud
architecture remains cache-free at runtime: reads only tracked artifacts, with
no live Yahoo requests, credentials, API keys or automatic backtests.

The approved endpoints remain:

- Strategy NAV: `6.225346615575381`
- Strategy portfolio value: `622534.6615575381` USD
- SPY NAV: `4.002530196823173`

No export utility is run during this enhancement and no artifact is regenerated.

## Validation

```bash
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -B -m pip check
git diff --check
streamlit run dashboard/Home.py --server.headless true
```

`tests/test_dashboard_i18n.py` adds 18 tests covering dictionary/key/placeholder
parity, explicit missing-key errors, financial terminology, unchanged formulas,
identical baseline values and table numbers, non-mutating chart/data formatting,
unchanged artifact bytes, both languages on all pages, native page navigation,
KPI stability, historical portfolio targets, sensitivity-choice persistence,
all six sensitivity groups and three metrics in Chinese, and localized failure
handling without fabricated KPIs.

Existing Phase 9 UI tests use stable control keys instead of selector positions
now that every page has a language selector. No financial assertion is weakened
or prior-phase quantitative test changed. The full suite includes 350 Phase 0–8,
35 Phase 9 and 18 Phase 9.1 tests.

A repository-only simulation copies tracked files plus the proposed Phase 9.1
files into an isolated directory, excluding ignored caches and research outputs.
It runs all five pages in both languages, exercises native navigation and
controls, checks unchanged financial values, and verifies headless startup.
No actual cloud deployment or graphical browser/screenshot review is performed.
The existing dependencies and official entry point are retained.

Final validation results:

| Check | Result |
| --- | --- |
| Complete approved-cache suite | 403 passed; 0 failures/errors; 0 skipped |
| Existing Phase 0–8 tests | All 350 passed |
| Existing Phase 9 tests | All 35 passed |
| New Phase 9.1 tests | All 18 passed |
| English / Traditional Chinese page execution | All five pages passed in each language |
| Native navigation, KPI consistency and sensitivity controls | PASS |
| Cache-free repository-only simulation | Both languages passed |
| Headless app shell / health | HTTP 200 / HTTP 200 |
| Dependency check / git diff --check | PASS / PASS |
| Protected existing files | 1,151 unchanged |
| Core, cached data and deployment artifact modifications | 0 |

Expected warnings remain Streamlit bare-mode/test-harness diagnostics and the
prior Phase 1 invalid-date/mocked-data diagnostics. There were no application
exceptions after validation. No actual graphical-browser or cloud redeployment
was performed. The temporary headless server was stopped.

Work remains uncommitted for review; no push, pull request, merge, report
generation or Phase 10 work is included.

**PHASE 9.1 READY FOR REVIEW: YES**
