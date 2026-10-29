"""Deterministic Phase 4 formations and Top 20 membership; no market downloads."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_index_equal

from mft109.config import BASELINE
from mft109.factors import RAW_FACTOR_COLUMNS
from mft109.processing import SCORE_COLUMNS, score_factors
from mft109.ranking import monthly_formation_dates, rank_and_select


def spy_sessions() -> pd.DatetimeIndex:
    """Synthetic weekday clock with explicit holiday exclusions for boundary tests."""
    calendar = pd.bdate_range("2015-01-01", "2026-02-02")
    return calendar.difference(pd.to_datetime(["2016-01-01", "2021-05-31", "2024-03-29"]))


def scores(count: int = 25, date: str = "2016-01-29") -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime([date] * count),
        "ticker": [f"T{i:02}" for i in range(count)],
        "eligible": [True] * count,
        "composite_score": [float(count - i) for i in range(count)],
    })


class FormationDateTests(unittest.TestCase):
    def test_one_last_supplied_session_per_official_month(self):
        calendar = spy_sessions()
        actual = monthly_formation_dates(calendar)
        self.assertEqual(len(actual), 120)
        self.assertEqual(actual.to_period("M").nunique(), 120)
        for date in actual:
            same_month = calendar[calendar.to_period("M") == date.to_period("M")]
            self.assertEqual(date, same_month.max())

    def test_first_formation_is_january_2016_not_december_2015(self):
        actual = monthly_formation_dates(spy_sessions())
        self.assertEqual(actual[0], pd.Timestamp("2016-01-29"))
        self.assertFalse((actual < pd.Timestamp("2016-01-01")).any())

    def test_no_post_2025_formations(self):
        actual = monthly_formation_dates(spy_sessions())
        self.assertEqual(actual[-1], pd.Timestamp("2025-12-31"))
        self.assertFalse((actual > pd.Timestamp("2025-12-31")).any())

    def test_weekend_calendar_month_end_is_not_invented(self):
        actual = monthly_formation_dates(spy_sessions())
        self.assertNotIn(pd.Timestamp("2016-01-31"), actual)
        self.assertTrue((actual.day_of_week < 5).all())

    def test_holiday_month_end_uses_supplied_prior_session(self):
        actual = monthly_formation_dates(spy_sessions())
        self.assertIn(pd.Timestamp("2021-05-28"), actual)
        self.assertNotIn(pd.Timestamp("2021-05-31"), actual)
        self.assertIn(pd.Timestamp("2024-03-28"), actual)
        self.assertNotIn(pd.Timestamp("2024-03-29"), actual)

    def test_unsorted_calendar_is_sorted_deterministically(self):
        calendar = spy_sessions()
        assert_index_equal(monthly_formation_dates(calendar[::-1]), monthly_formation_dates(calendar))

    def test_duplicate_sessions_are_rejected(self):
        calendar = spy_sessions()
        with self.assertRaisesRegex(ValueError, "unique"):
            monthly_formation_dates(calendar.append(calendar[:1]))

    def test_missing_baseline_month_is_not_silently_omitted(self):
        calendar = spy_sessions()
        calendar = calendar[calendar.to_period("M") != pd.Period("2020-10", freq="M")]
        with self.assertRaisesRegex(ValueError, "2020-10"):
            monthly_formation_dates(calendar)

    def test_partial_calendar_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "every official baseline month"):
            monthly_formation_dates(pd.bdate_range("2016-01-04", "2016-01-29"))

    def test_invalid_weekend_timezone_and_intraday_sessions_are_rejected(self):
        calendar = spy_sessions()
        for invalid in [calendar.append(pd.DatetimeIndex(["2016-01-31"])),
                        calendar.tz_localize("UTC"), calendar + pd.Timedelta(hours=1),
                        pd.DatetimeIndex([pd.NaT])]:
            with self.subTest(calendar=invalid):
                with self.assertRaises(ValueError):
                    monthly_formation_dates(invalid)

    def test_future_calendar_extension_does_not_change_official_formations(self):
        calendar = spy_sessions()
        prefix = calendar[calendar <= pd.Timestamp("2025-12-31")]
        assert_index_equal(monthly_formation_dates(calendar), monthly_formation_dates(prefix))


class RankingTests(unittest.TestCase):
    def rank(self, data: pd.DataFrame):
        return rank_and_select(data, sessions=spy_sessions())

    def test_highest_score_rank_one_and_descending_order(self):
        data = scores(3)
        data["composite_score"] = [-2.0, 10.0, 0.5]
        ranked = self.rank(data).ranked
        self.assertEqual(ranked.ticker.tolist(), ["T01", "T02", "T00"])
        self.assertEqual(ranked["rank"].tolist(), [1, 2, 3])
        self.assertTrue(ranked.composite_score.is_monotonic_decreasing)

    def test_sequential_integer_ranks_are_unique_even_for_all_ties(self):
        data = scores(25)
        data["composite_score"] = 1.0
        ranked = self.rank(data).ranked
        self.assertEqual(ranked["rank"].tolist(), list(range(1, 26)))
        self.assertTrue(pd.api.types.is_integer_dtype(ranked["rank"].dtype))
        self.assertTrue(ranked["rank"].is_unique)

    def test_each_date_ranked_independently_without_mixing_tickers(self):
        first, second = scores(3), scores(2, "2016-02-29")
        second["composite_score"] = [100.0, 200.0]
        ranked = self.rank(pd.concat([second, first], ignore_index=True)).ranked
        for date, rows in ranked.groupby("formation_date"):
            self.assertEqual(rows["rank"].tolist(), list(range(1, len(rows) + 1)))
        self.assertEqual(ranked.loc[ranked.formation_date.eq(pd.Timestamp("2016-02-29")), "ticker"].tolist(), ["T01", "T00"])

    def test_exact_ties_use_alphabetical_ticker(self):
        data = scores(3)
        data["ticker"] = ["NVDA", "AAPL", "MSFT"]
        data["composite_score"] = 1.0
        data["volatility60"] = [0.01, 0.3, 0.2]
        data["liquidity_raw"] = [1000.0, 10.0, 100.0]
        ranked = self.rank(data).ranked
        self.assertEqual(ranked.ticker.tolist(), ["AAPL", "MSFT", "NVDA"])
        self.assertEqual(ranked["rank"].tolist(), [1, 2, 3])

    def test_only_exact_ties_not_nearby_scores_use_ticker(self):
        data = scores(2)
        data["ticker"] = ["ZZZ", "AAA"]
        data["composite_score"] = [np.nextafter(1.0, 2.0), 1.0]
        self.assertEqual(self.rank(data).ranked.ticker.tolist(), ["ZZZ", "AAA"])

    def test_shuffled_row_order_does_not_change_rank_or_selection(self):
        data = pd.concat([scores(30), scores(22, "2016-02-29")], ignore_index=True)
        data.loc[:24, "composite_score"] = 1.0
        first = self.rank(data)
        second = self.rank(data.sample(frac=1, random_state=47))
        assert_frame_equal(first.ranked, second.ranked)
        assert_frame_equal(first.selected, second.selected)
        assert_frame_equal(first.formation_summary, second.formation_summary)

    def test_repeated_runs_are_identical(self):
        data = scores(25)
        first, second = self.rank(data), self.rank(data)
        assert_frame_equal(first.ranked, second.ranked)
        assert_frame_equal(first.formation_summary, second.formation_summary)

    def test_composite_is_not_recalculated_or_rounded(self):
        data = scores(3)
        data["composite_score"] = [0.123456789012345, -100.0, 7.25]
        for column in SCORE_COLUMNS:
            data[column] = 1.0
        ranked = self.rank(data).ranked.set_index("ticker")
        for row in data.itertuples():
            self.assertEqual(ranked.loc[row.ticker, "composite_score"], row.composite_score)
        self.assertEqual(ranked.loc["T02", "rank"], 1)


class Top20Tests(unittest.TestCase):
    def select(self, data: pd.DataFrame):
        return rank_and_select(data, sessions=spy_sessions())

    def test_more_than_twenty_selects_exact_ranks_one_to_twenty(self):
        result = self.select(scores(30))
        self.assertEqual(len(result.selected), 20)
        self.assertEqual(result.selected["rank"].tolist(), list(range(1, 21)))
        self.assertFalse(result.ranked.loc[result.ranked["rank"].eq(21), "selected"].iloc[0])
        summary = result.formation_summary.iloc[0]
        self.assertEqual(summary.eligible_count, 30)
        self.assertEqual(summary.selected_count, 20)
        self.assertFalse(summary.fewer_than_top_n)

    def test_exactly_twenty_selects_every_eligible_stock(self):
        result = self.select(scores(20))
        self.assertEqual(len(result.selected), 20)
        self.assertTrue(result.ranked.selected.all())

    def test_tie_at_twentieth_place_selects_alphabetically_first_twenty(self):
        data = scores(25).iloc[::-1].copy()
        data["composite_score"] = 1.0
        result = self.select(data)
        self.assertEqual(result.selected.ticker.tolist(), [f"T{i:02}" for i in range(20)])
        self.assertEqual(result.ranked.loc[result.ranked["rank"].eq(21), "ticker"].iloc[0], "T20")
        self.assertFalse(result.ranked.loc[result.ranked["rank"].eq(21), "selected"].iloc[0])

    def test_fewer_than_twenty_selects_only_available_and_records_shortage(self):
        result = self.select(scores(7))
        self.assertEqual(len(result.selected), 7)
        summary = result.formation_summary.iloc[0]
        self.assertEqual(summary.eligible_count, 7)
        self.assertEqual(summary.selected_count, 7)
        self.assertTrue(summary.fewer_than_top_n)

    def test_zero_eligible_stocks_produces_no_fabricated_rows(self):
        data = scores(30)
        data["eligible"] = False
        result = self.select(data)
        self.assertTrue(result.ranked.empty)
        self.assertTrue(result.selected.empty)
        self.assertTrue(result.formation_summary.eligible_count.eq(0).all())
        self.assertTrue(result.formation_summary.selected_count.eq(0).all())
        self.assertTrue(result.formation_summary.fewer_than_top_n.all())

    def test_empty_scores_still_report_all_official_months(self):
        result = self.select(scores(0))
        self.assertEqual(len(result.formation_summary), 120)
        self.assertTrue(result.ranked.empty)
        self.assertTrue(result.formation_summary.eligible_count.eq(0).all())

    def test_shortage_months_include_absent_formation_score_dates(self):
        result = self.select(scores(25))
        missing_months = result.formation_summary.iloc[1:]
        self.assertEqual(len(missing_months), 119)
        self.assertTrue(missing_months.fewer_than_top_n.all())
        self.assertTrue(missing_months.selected_count.eq(0).all())

    def test_no_invalid_stock_is_used_to_fill_twenty(self):
        data = scores(25)
        data.loc[:14, "eligible"] = False
        data.loc[15:19, "composite_score"] = np.nan
        result = self.select(data)
        self.assertEqual(len(result.selected), 5)
        self.assertEqual(set(result.selected.ticker), {f"T{i:02}" for i in range(20, 25)})

    def test_locked_top_n_comes_from_existing_configuration(self):
        self.assertEqual(BASELINE.top_n, 20)
        with patch("mft109.ranking.selection.BASELINE", replace(BASELINE, top_n=10)):
            with self.assertRaisesRegex(ValueError, "top_n=20"):
                self.select(scores(30))

    def test_selected_property_returns_a_separate_table(self):
        result = self.select(scores(30))
        original = result.ranked.copy(deep=True)
        selected = result.selected
        selected.loc[:, "composite_score"] = -999.0
        assert_frame_equal(result.ranked, original)


class SelectionSafeguardTests(unittest.TestCase):
    def select(self, data: pd.DataFrame):
        return rank_and_select(data, sessions=spy_sessions())

    def test_only_exact_formation_day_scores_are_used(self):
        old, current, future = scores(1, "2016-01-28"), scores(1), scores(1, "2016-02-01")
        old["ticker"], old["composite_score"] = "STALE", 1e100
        future["ticker"], future["composite_score"] = "STALE", 1e200
        result = self.select(pd.concat([old, current, future], ignore_index=True))
        self.assertEqual(result.ranked.ticker.tolist(), ["T00"])
        self.assertEqual(result.ranked.composite_score.tolist(), [1.0])

    def test_missing_nonfinite_and_noneligible_scores_do_not_enter_ranking(self):
        data = scores(6)
        data.loc[0, "eligible"] = False
        data.loc[1:3, "composite_score"] = [np.nan, np.inf, -np.inf]
        data.loc[4, "composite_score"] = 0.0
        result = self.select(data)
        self.assertEqual(set(result.ranked.ticker), {"T04", "T05"})
        self.assertTrue(np.isfinite(result.ranked.composite_score).all())

    def test_nullable_unknown_eligibility_and_missing_scores_are_not_filled(self):
        data = scores(3).astype({"eligible": "boolean", "composite_score": "Float64"})
        data.loc[0, "eligible"] = pd.NA
        data.loc[1, "composite_score"] = pd.NA
        result = self.select(data)
        self.assertEqual(result.ranked.ticker.tolist(), ["T02"])
        self.assertTrue(pd.isna(data.loc[0, "eligible"]))
        self.assertTrue(pd.isna(data.loc[1, "composite_score"]))

    def test_warmup_and_post_backtest_scores_never_become_official(self):
        raw = pd.concat([scores(1, "2015-12-31"), scores(1), scores(1, "2026-01-30")], ignore_index=True)
        result = self.select(raw)
        self.assertEqual(result.ranked.formation_date.tolist(), [pd.Timestamp("2016-01-29")])

    def test_future_and_next_month_changes_cannot_change_prior_selection(self):
        first, second = scores(30), scores(30, "2016-02-29")
        data = pd.concat([first, second], ignore_index=True)
        baseline = self.select(data)
        revised = data.copy()
        revised.loc[30:, "composite_score"] *= -100
        revised.loc[30:34, "eligible"] = False
        changed = self.select(revised)
        january = pd.Timestamp("2016-01-29")
        assert_frame_equal(baseline.ranked[baseline.ranked.formation_date.eq(january)], changed.ranked[changed.ranked.formation_date.eq(january)])
        assert_frame_equal(self.select(first).ranked, baseline.ranked.iloc[:30])

    def test_inputs_and_useful_phase3_columns_are_preserved(self):
        data = scores(3)
        for i, column in enumerate(RAW_FACTOR_COLUMNS + SCORE_COLUMNS):
            data[column] = [100.0 + i, 200.0 + i, 300.0 + i]
        original = data.copy(deep=True)
        ranked = self.select(data).ranked
        assert_frame_equal(data, original)
        recovered = ranked.rename(columns={"formation_date": "date"})[original.columns]
        assert_frame_equal(recovered, original)

    def test_ranking_does_not_call_a_second_factor_or_scoring_pipeline(self):
        with patch("mft109.factors.calculate_raw_factors", side_effect=AssertionError("no recalculation")), \
             patch("mft109.processing.score_factors", side_effect=AssertionError("no rescoring")):
            self.assertEqual(len(self.select(scores(25)).selected), 20)

    def test_phase3_eligibility_marker_is_required(self):
        with self.assertRaises(ValueError):
            self.select(scores(3).drop(columns="eligible"))

    def test_duplicate_date_ticker_rows_are_rejected(self):
        data = scores(3)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.select(pd.concat([data, data.iloc[:1]], ignore_index=True))

    def test_invalid_score_and_eligibility_schemas_are_rejected(self):
        for column, dtype in [("composite_score", str), ("composite_score", bool),
                              ("composite_score", complex), ("eligible", str)]:
            with self.subTest(column=column, dtype=dtype):
                data = scores(3)
                data[column] = data[column].astype(dtype)
                with self.assertRaises(TypeError):
                    self.select(data)

    def test_invalid_dates_identifiers_and_duplicate_columns_are_rejected(self):
        for column, value in [("date", pd.NaT), ("date", pd.Timestamp("2016-01-29 12:00")),
                              ("date", pd.Timestamp("2016-01-31")),
                              ("ticker", None), ("ticker", ""), ("ticker", "SPY")]:
            with self.subTest(column=column, value=value):
                data = scores(3)
                data.loc[0, column] = value
                with self.assertRaises(ValueError):
                    self.select(data)
        data = scores(3)
        with self.assertRaises(ValueError):
            self.select(pd.concat([data, data[["composite_score"]]], axis=1))

    def test_already_ranked_input_is_not_silently_reprocessed(self):
        for column in ["rank", "selected", "formation_date"]:
            with self.subTest(column=column):
                data = scores(3)
                data[column] = 1
                with self.assertRaises(ValueError):
                    self.select(data)

    def test_no_portfolio_execution_or_backtest_outputs(self):
        result = self.select(scores(25))
        self.assertEqual(result.ranked.columns.tolist(), ["formation_date", "ticker", "eligible", "composite_score", "rank", "selected"])
        self.assertEqual(result.formation_summary.columns.tolist(), ["formation_date", "eligible_count", "selected_count", "fewer_than_top_n"])

    def test_existing_phase3_scores_are_consumed_without_modification(self):
        dates = pd.to_datetime(["2016-01-29"] * 3)
        raw = pd.DataFrame({"date": dates, "ticker": ["AAA", "BBB", "CCC"],
                            "momentum": [1.0, 2.0, 3.0], "volatility60": [0.1, 0.2, 0.3],
                            "liquidity_raw": [10.0, 20.0, 30.0], "reversal20": [-0.1, 0.0, 0.1]})
        scored = score_factors(raw)
        original = scored.copy(deep=True)
        result = self.select(scored)
        assert_frame_equal(scored, original)
        recovered = result.ranked.rename(columns={"formation_date": "date"}).sort_values("ticker").reset_index(drop=True)
        assert_frame_equal(recovered[original.columns], original)


if __name__ == "__main__":
    unittest.main()
