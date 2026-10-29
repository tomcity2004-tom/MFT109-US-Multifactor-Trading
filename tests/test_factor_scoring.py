"""Deterministic cross-sectional scoring tests; no ranking or market downloads."""

from dataclasses import replace
import math
import statistics
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from mft109.config import BASELINE
from mft109.factors import RAW_FACTOR_COLUMNS, calculate_raw_factors
from mft109.processing import (
    SCORE_COLUMNS, baseline_factor_weights, score_factors,
    scoring_eligibility, standardize_factors,
)


ALL_SCORES = SCORE_COLUMNS + ["composite_score"]


def cross_section(date: str = "2020-01-31") -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime([date] * 3), "ticker": ["AAA", "BBB", "CCC"],
        "momentum": [1.0, 2.0, 3.0], "volatility60": [0.1, 0.2, 0.3],
        "liquidity_raw": [10.0, 20.0, 30.0], "reversal20": [-0.2, 0.0, 0.2],
    })


def manual_z(values: list[float]) -> list[float]:
    mean = sum(values) / len(values)
    deviation = statistics.pstdev(values)
    return [(value - mean) / deviation for value in values]


class EligibilityTests(unittest.TestCase):
    def test_all_four_finite_including_zero_volatility_are_eligible(self):
        raw = cross_section()
        raw.loc[0, "volatility60"] = 0.0
        self.assertTrue(scoring_eligibility(raw).all())

    def test_each_missing_factor_excludes_the_row(self):
        for column in RAW_FACTOR_COLUMNS:
            with self.subTest(column=column):
                raw = cross_section()
                raw.loc[1, column] = np.nan
                self.assertEqual(scoring_eligibility(raw).tolist(), [True, False, True])
                output = score_factors(raw)
                self.assertTrue(output.loc[1, ALL_SCORES].isna().all())
                self.assertTrue(pd.isna(output.loc[1, column]))

    def test_either_infinity_in_any_raw_factor_excludes_the_row(self):
        for column in RAW_FACTOR_COLUMNS:
            for value in [np.inf, -np.inf]:
                with self.subTest(column=column, value=value):
                    raw = cross_section()
                    raw.loc[1, column] = value
                    output = score_factors(raw)
                    self.assertFalse(output.loc[1, "eligible"])
                    self.assertTrue(output.loc[1, ALL_SCORES].isna().all())
                    self.assertEqual(output.loc[1, column], value)

    def test_eligibility_is_date_specific_and_ticker_recovers(self):
        first, second = cross_section(), cross_section("2020-02-28")
        first.loc[1, "momentum"] = np.nan
        output = score_factors(pd.concat([first, second], ignore_index=True))
        stock = output[output.ticker.eq("BBB")]
        self.assertEqual(stock.eligible.tolist(), [False, True])
        self.assertTrue(stock.iloc[0][ALL_SCORES].isna().all())
        self.assertTrue(stock.iloc[1][ALL_SCORES].notna().all())

    def test_excluded_stock_cannot_influence_any_factor_statistics(self):
        raw = cross_section()
        raw.loc[1, "liquidity_raw"] = np.nan
        raw.loc[1, ["momentum", "volatility60", "reversal20"]] = 1e100
        output = score_factors(raw)
        np.testing.assert_allclose(output.loc[[0, 2], "momentum_score"], [-1.0, 1.0])
        np.testing.assert_allclose(output.loc[[0, 2], "low_volatility_score"], [1.0, -1.0])
        np.testing.assert_allclose(output.loc[[0, 2], "liquidity_score"], [-1.0, 1.0])
        np.testing.assert_allclose(output.loc[[0, 2], "reversal_score"], [-1.0, 1.0])
        self.assertTrue(output.loc[1, ALL_SCORES].isna().all())

    def test_zero_eligible_date_retains_only_unscored_rows(self):
        first, second = cross_section(), cross_section("2020-02-28")
        first["momentum"] = np.nan
        output = score_factors(pd.concat([first, second], ignore_index=True))
        first_date = output[output.date.eq(pd.Timestamp("2020-01-31"))]
        self.assertFalse(first_date.eligible.any())
        self.assertTrue(first_date[ALL_SCORES].isna().all().all())
        self.assertEqual(output.eligible.sum(), 3)
        self.assertEqual(len(output), 6)

    def test_nullable_missing_factor_is_not_filled(self):
        raw = cross_section().astype({column: "Float64" for column in RAW_FACTOR_COLUMNS})
        raw.loc[1, "momentum"] = pd.NA
        output = score_factors(raw)
        self.assertEqual(output.eligible.tolist(), [True, False, True])
        self.assertTrue(output.loc[1, ALL_SCORES].isna().all())
        self.assertTrue(pd.isna(output.loc[1, "momentum"]))

    def test_eligibility_mask_preserves_input_row_index(self):
        raw = cross_section().iloc[::-1].copy()
        raw.loc[1, "reversal20"] = np.nan
        expected = pd.Series([True, False, True], index=raw.index, name="eligible")
        assert_series_equal(scoring_eligibility(raw), expected)


class StandardizationTests(unittest.TestCase):
    def test_known_population_zscores_use_ddof_zero(self):
        raw = cross_section()
        output = standardize_factors(raw)
        expected = [-math.sqrt(1.5), 0.0, math.sqrt(1.5)]
        np.testing.assert_allclose(output.momentum_score, expected, atol=1e-14)
        sample_z = (1.0 - 2.0) / statistics.stdev([1.0, 2.0, 3.0])
        self.assertNotAlmostEqual(output.momentum_score.iloc[0], sample_z)

    def test_all_directions_match_independent_scalar_statistics(self):
        raw = cross_section()
        output = standardize_factors(raw)
        for column, score, direction in [
            ("momentum", "momentum_score", 1),
            ("volatility60", "low_volatility_score", -1),
            ("liquidity_raw", "liquidity_score", 1),
            ("reversal20", "reversal_score", 1),
        ]:
            with self.subTest(score=score):
                expected = [direction * z for z in manual_z(raw[column].tolist())]
                np.testing.assert_allclose(output[score], expected, atol=1e-14)

    def test_nonconstant_score_mean_zero_and_population_std_one(self):
        output = score_factors(cross_section())
        for column in SCORE_COLUMNS:
            with self.subTest(column=column):
                self.assertAlmostEqual(output[column].mean(), 0.0, places=14)
                self.assertAlmostEqual(output[column].std(ddof=0), 1.0, places=14)

    def test_same_date_cross_section_not_ticker_time_series(self):
        first, second = cross_section(), cross_section("2020-02-28")
        for column in RAW_FACTOR_COLUMNS:
            second[column] = first[column].to_numpy() * 10 + 1000
        result = score_factors(pd.concat([first, second], ignore_index=True))
        np.testing.assert_allclose(result.iloc[:3][SCORE_COLUMNS], result.iloc[3:][SCORE_COLUMNS], atol=1e-11)
        self.assertLess(result.loc[0, "momentum_score"], 0)
        self.assertLess(result.loc[3, "momentum_score"], 0)

    def test_dates_with_different_eligible_populations_are_independent(self):
        first, second = cross_section(), cross_section("2020-02-28")
        second.loc[1, "momentum"] = np.nan
        result = score_factors(pd.concat([first, second], ignore_index=True))
        assert_frame_equal(result.iloc[:3].reset_index(drop=True), score_factors(first))
        np.testing.assert_allclose(result.loc[[3, 5], "momentum_score"], [-1.0, 1.0])

    def test_higher_momentum_has_higher_score(self):
        result = score_factors(cross_section())
        self.assertTrue(result.momentum_score.is_monotonic_increasing)

    def test_lower_volatility_has_higher_score_sign_reversed_once(self):
        raw = cross_section()
        result = score_factors(raw)
        np.testing.assert_allclose(result.low_volatility_score, -np.array(manual_z(raw.volatility60.tolist())), atol=1e-14)
        self.assertGreater(result.low_volatility_score.iloc[0], result.low_volatility_score.iloc[-1])
        self.assertTrue(result.volatility60.gt(0).all())
        assert_series_equal(result.volatility60, raw.volatility60)

    def test_higher_liquidity_has_higher_score(self):
        result = score_factors(cross_section())
        self.assertTrue(result.liquidity_score.is_monotonic_increasing)

    def test_reversal_is_not_negated_again(self):
        raw = cross_section()
        result = score_factors(raw)
        np.testing.assert_allclose(result.reversal_score, manual_z(raw.reversal20.tolist()), atol=1e-14)
        self.assertGreater(result.reversal_score.iloc[-1], result.reversal_score.iloc[0])

    def test_one_zero_variance_factor_is_neutral_others_still_contribute(self):
        raw = cross_section()
        raw["momentum"] = 0.1
        result = score_factors(raw)
        self.assertTrue(result.momentum_score.eq(0.0).all())
        self.assertTrue(np.isfinite(result[ALL_SCORES].to_numpy()).all())
        expected = (result.low_volatility_score + result.liquidity_score + result.reversal_score) * 0.25
        np.testing.assert_allclose(result.composite_score, expected)
        self.assertGreater(result.composite_score.abs().max(), 0)

    def test_all_constant_factors_produce_zero_scores(self):
        raw = cross_section()
        for column in RAW_FACTOR_COLUMNS:
            raw[column] = 0.1
        result = score_factors(raw)
        self.assertTrue(result[ALL_SCORES].eq(0.0).all().all())

    def test_single_eligible_stock_scores_zero_without_filling_invalid_peer(self):
        raw = cross_section()
        raw.loc[[1, 2], "momentum"] = np.nan
        result = score_factors(raw)
        self.assertTrue(result.loc[0, ALL_SCORES].eq(0.0).all())
        self.assertTrue(result.loc[[1, 2], ALL_SCORES].isna().all().all())

    def test_extreme_finite_factors_do_not_overflow_or_get_clipped(self):
        raw = cross_section()
        raw["momentum"] = [-1e308, 0.0, 1e308]
        result = score_factors(raw)
        np.testing.assert_allclose(result.momentum_score, [-math.sqrt(1.5), 0, math.sqrt(1.5)], atol=1e-14)
        self.assertTrue(np.isfinite(result[ALL_SCORES].to_numpy()).all())
        self.assertEqual(result.momentum.tolist(), raw.momentum.tolist())

    def test_tiny_nonzero_variance_is_not_neutralized(self):
        raw = cross_section()
        raw["momentum"] = [1e-300, 2e-300, 3e-300]
        result = score_factors(raw)
        np.testing.assert_allclose(result.momentum_score, [-math.sqrt(1.5), 0, math.sqrt(1.5)], atol=1e-14)

    def test_outlier_score_above_three_is_not_capped_or_removed(self):
        raw = pd.concat([cross_section().iloc[[0]]] * 30, ignore_index=True)
        raw["ticker"] = [f"T{i:02}" for i in range(30)]
        raw["momentum"] = [0.0] * 29 + [1e12]
        result = score_factors(raw)
        self.assertEqual(len(result), 30)
        self.assertTrue(result.eligible.all())
        self.assertAlmostEqual(result.momentum_score.iloc[-1], math.sqrt(29))
        self.assertGreater(result.momentum_score.iloc[-1], 3)


class CompositeScoreTests(unittest.TestCase):
    def test_configured_weights_are_equal_and_sum_exactly_one(self):
        weights = baseline_factor_weights()
        self.assertEqual(set(weights), set(SCORE_COLUMNS))
        self.assertEqual(list(weights.values()), [0.25] * 4)
        self.assertEqual(sum(weights.values()), 1.0)

    def test_hand_calculable_composite(self):
        raw = cross_section().iloc[:2].copy()
        raw["momentum"] = [2.0, 1.0]
        raw["volatility60"] = [0.1, 0.3]
        raw["liquidity_raw"] = [4.0, 1.0]
        raw["reversal20"] = [0.2, -0.2]
        result = score_factors(raw)
        np.testing.assert_allclose(result.loc[0, SCORE_COLUMNS].to_numpy(dtype=float), [1.0] * 4, atol=1e-14)
        np.testing.assert_allclose(result.composite_score, [1.0, -1.0], atol=1e-14)

    def test_composite_is_exact_fixed_weighted_sum(self):
        raw = cross_section()
        result = score_factors(raw)
        for index in range(3):
            z = {column: manual_z(raw[column].tolist())[index] for column in RAW_FACTOR_COLUMNS}
            expected = 0.25 * z["momentum"] - 0.25 * z["volatility60"] + 0.25 * z["liquidity_raw"] + 0.25 * z["reversal20"]
            self.assertAlmostEqual(result.composite_score.iloc[index], expected)

    def test_missing_factor_does_not_trigger_reweighting_or_zero_composite(self):
        raw = cross_section()
        raw.loc[0, "momentum"] = np.nan
        result = score_factors(raw)
        self.assertTrue(pd.isna(result.composite_score.iloc[0]))
        self.assertTrue(result.loc[0, SCORE_COLUMNS].isna().all())

    def test_invalid_or_nonbaseline_weights_are_rejected(self):
        for config in [replace(BASELINE, momentum_weight=0.5),
                       replace(BASELINE, momentum_weight=np.nan),
                       replace(BASELINE, momentum_weight=0.4, low_volatility_weight=0.1)]:
            with self.subTest(config=config):
                with patch("mft109.processing.scoring.BASELINE", config):
                    with self.assertRaises(ValueError):
                        score_factors(cross_section())

    def test_output_has_no_rank_selection_or_portfolio_columns(self):
        raw = cross_section()
        result = score_factors(raw)
        self.assertEqual(result.columns.tolist(), ["date", "ticker"] + RAW_FACTOR_COLUMNS + ["eligible"] + ALL_SCORES)
        self.assertEqual(set(result.ticker), set(raw.ticker))


class ScoringSafeguardTests(unittest.TestCase):
    def test_input_and_raw_values_are_not_mutated(self):
        raw = cross_section().iloc[::-1].copy()
        raw.loc[1, "momentum"] = np.inf
        original = raw.copy(deep=True)
        result = score_factors(raw)
        assert_frame_equal(raw, original)
        expected_raw = original.sort_values(["date", "ticker"]).reset_index(drop=True)
        assert_frame_equal(result[expected_raw.columns], expected_raw)

    def test_deterministic_date_ticker_order_is_not_score_order(self):
        first, second = cross_section(), cross_section("2020-02-28")
        raw = pd.concat([second.iloc[::-1], first.iloc[::-1]], ignore_index=True)
        result = score_factors(raw)
        self.assertEqual(result.ticker.tolist(), ["AAA", "BBB", "CCC"] * 2)
        self.assertTrue(result.date.is_monotonic_increasing)
        self.assertLess(result.composite_score.iloc[0], result.composite_score.iloc[2])
        assert_frame_equal(result, score_factors(raw.iloc[::-1]))

    def test_changing_future_values_or_eligibility_does_not_change_past_scores(self):
        first, second = cross_section(), cross_section("2020-02-28")
        raw = pd.concat([first, second], ignore_index=True)
        baseline = score_factors(raw)
        changed = raw.copy()
        changed.loc[3:, "momentum"] = [1e200, np.nan, -1e200]
        changed.loc[3:, "volatility60"] = [100.0, 200.0, 300.0]
        revised = score_factors(changed)
        assert_frame_equal(revised.iloc[:3], baseline.iloc[:3])
        assert_frame_equal(score_factors(first), baseline.iloc[:3])

    def test_ineligible_rows_are_not_forward_or_backward_filled(self):
        first, middle, last = cross_section(), cross_section("2020-02-28"), cross_section("2020-03-31")
        middle.loc[0, "liquidity_raw"] = np.nan
        result = score_factors(pd.concat([first, middle, last], ignore_index=True))
        stock = result[result.ticker.eq("AAA")]
        self.assertEqual(stock.eligible.tolist(), [True, False, True])
        self.assertTrue(stock.iloc[1][ALL_SCORES].isna().all())
        self.assertTrue(pd.isna(stock.iloc[1].liquidity_raw))

    def test_fixed_universe_unavailable_symbols_are_retained_unscored(self):
        raw = cross_section()
        absent = raw.iloc[:3].copy()
        absent["ticker"] = ["FDXF", "HONA", "VYLR"]
        absent[RAW_FACTOR_COLUMNS] = np.nan
        result = score_factors(pd.concat([raw, absent], ignore_index=True))
        missing = result[result.ticker.isin(["FDXF", "HONA", "VYLR"])]
        self.assertEqual(len(missing), 3)
        self.assertFalse(missing.eligible.any())
        self.assertTrue(missing[ALL_SCORES].isna().all().all())

    def test_existing_phase2_raw_calculations_remain_unchanged(self):
        calendar = pd.bdate_range("2019-01-02", periods=300)
        data = pd.concat([pd.DataFrame({
            "date": calendar, "ticker": ticker,
            "adjusted_close": [100.0 + i * slope + (i % 7) for i in range(300)],
            "volume": [1000.0 + i * 2 for i in range(300)],
        }) for ticker, slope in [("AAA", 1.0), ("BBB", 2.0), ("CCC", 3.0)]], ignore_index=True)
        raw = calculate_raw_factors(data, sessions=calendar, tickers=["AAA", "BBB", "CCC"])
        original = raw.copy(deep=True)
        result = score_factors(raw)
        assert_frame_equal(raw, original)
        assert_frame_equal(calculate_raw_factors(data, sessions=calendar, tickers=["AAA", "BBB", "CCC"]), original)
        self.assertTrue(result[result.date.eq(calendar[-1])].eligible.all())

    def test_empty_input_returns_empty_scoring_schema(self):
        empty = pd.DataFrame(columns=["date", "ticker"] + RAW_FACTOR_COLUMNS)
        result = score_factors(empty)
        self.assertTrue(result.empty)
        self.assertEqual(result.columns.tolist(), ["date", "ticker"] + RAW_FACTOR_COLUMNS + ["eligible"] + ALL_SCORES)

    def test_duplicate_date_ticker_rows_are_rejected(self):
        raw = cross_section()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            score_factors(pd.concat([raw, raw.iloc[:1]], ignore_index=True))

    def test_missing_or_duplicate_columns_are_rejected(self):
        raw = cross_section()
        with self.assertRaises(ValueError):
            score_factors(raw.drop(columns="momentum"))
        with self.assertRaises(ValueError):
            score_factors(pd.concat([raw, raw[["momentum"]]], axis=1))

    def test_invalid_dates_and_tickers_are_rejected(self):
        for column, value in [("date", pd.NaT), ("date", pd.Timestamp("2020-01-31 12:00")),
                              ("ticker", None), ("ticker", ""), ("ticker", "SPY")]:
            with self.subTest(column=column, value=value):
                raw = cross_section()
                raw.loc[0, column] = value
                with self.assertRaises(ValueError):
                    score_factors(raw)

    def test_nonnumeric_factor_schema_is_not_silently_coerced(self):
        for dtype in [str, bool, complex]:
            with self.subTest(dtype=dtype):
                raw = cross_section()
                raw["momentum"] = raw.momentum.astype(dtype)
                with self.assertRaises(TypeError):
                    score_factors(raw)


if __name__ == "__main__":
    unittest.main()
