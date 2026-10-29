"""Independent mathematical fixtures for raw factors; no network or downloads."""

import math
import statistics
import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from mft109.factors import (
    RAW_FACTOR_COLUMNS, calculate_adv20, calculate_daily_returns,
    calculate_dollar_volume, calculate_liquidity, calculate_momentum,
    calculate_raw_factors, calculate_reversal, calculate_volatility,
)


def prices(count: int = 300) -> pd.Series:
    """Nonlinear positive prices on an explicit synthetic session calendar."""
    return pd.Series([100.0 + i + i * i / 100 for i in range(count)],
                     index=pd.bdate_range("2020-01-02", periods=count))


def from_returns(returns: list[float]) -> pd.Series:
    values = [100.0]
    for value in returns:
        values.append(values[-1] * (1 + value))
    return pd.Series(values, index=pd.bdate_range("2020-01-02", periods=len(values)))


def observations(price: pd.Series, ticker: str = "AAA", volume: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({"date": price.index, "ticker": ticker,
                         "adjusted_close": price.to_numpy(), "volume": volume,
                         "close": 999_999.0})  # Deliberately different unadjusted alias.


class MomentumTests(unittest.TestCase):
    def test_exact_skipped_formula_and_first_valid_boundary(self):
        price = prices()
        actual = calculate_momentum(price, sessions=price.index)
        self.assertTrue(actual.iloc[:252].isna().all())
        self.assertAlmostEqual(actual.iloc[252], price.iloc[231] / price.iloc[0] - 1)
        self.assertAlmostEqual(actual.iloc[-1], price.iloc[278] / price.iloc[47] - 1)
        self.assertNotAlmostEqual(actual.iloc[252], price.iloc[252] / price.iloc[0] - 1)

    def test_current_price_and_recent_20_sessions_are_not_used(self):
        price = prices(253)
        expected = price.iloc[231] / price.iloc[0] - 1
        price.iloc[232:] = np.nan
        self.assertAlmostEqual(calculate_momentum(price, sessions=price.index).iloc[-1], expected)

    def test_insufficient_history(self):
        price = prices(252)
        self.assertTrue(calculate_momentum(price, sessions=price.index).isna().all())

    def test_missing_or_invalid_required_endpoints(self):
        for position in [0, 231]:
            for value in [np.nan, 0.0, -1.0, np.inf]:
                with self.subTest(position=position, value=value):
                    price = prices(253)
                    price.iloc[position] = value
                    self.assertTrue(pd.isna(calculate_momentum(price, sessions=price.index).iloc[-1]))

    def test_absent_row_does_not_compress_session_lags(self):
        price = prices(253)
        sparse = price.drop(price.index[200])
        actual = calculate_momentum(sparse, sessions=price.index)
        self.assertAlmostEqual(actual.iloc[-1], price.iloc[231] / price.iloc[0] - 1)
        self.assertEqual(len(actual), 253)


class VolatilityTests(unittest.TestCase):
    def test_daily_returns_and_no_implicit_fill(self):
        calendar = pd.bdate_range("2020-01-02", periods=5)
        price = pd.Series([100.0, 110.0, np.nan, 121.0, 133.1], index=calendar)
        actual = calculate_daily_returns(price, sessions=calendar)
        expected = pd.Series([np.nan, 0.1, np.nan, np.nan, 0.1],
                             index=calendar.rename("date"), name="daily_return")
        assert_series_equal(actual, expected, atol=1e-14, rtol=1e-14)

    def test_exact_60_return_window_sample_ddof_and_annualization(self):
        # A large earlier return must be excluded from the final 60-return window.
        known_returns = [0.4, -0.3] + [0.01, -0.02, 0.03] * 20
        price = from_returns(known_returns)
        actual = calculate_volatility(price, sessions=price.index)
        self.assertTrue(actual.iloc[:60].isna().all())
        expected = statistics.stdev(known_returns[-60:]) * math.sqrt(252)
        self.assertAlmostEqual(actual.iloc[-1], expected, places=12)
        self.assertAlmostEqual(actual.iloc[60], statistics.stdev(known_returns[:60]) * math.sqrt(252), places=12)
        self.assertNotAlmostEqual(actual.iloc[-1], statistics.pstdev(known_returns[-60:]) * math.sqrt(252), places=8)
        self.assertGreater(actual.iloc[-1], 0)

    def test_60_prices_are_insufficient_for_60_returns(self):
        price = prices(60)
        self.assertTrue(calculate_volatility(price, sessions=price.index).isna().all())

    def test_missing_price_invalidates_two_returns_and_recovers_after_full_window(self):
        price = prices(180)
        price.iloc[70] = np.nan
        result = calculate_volatility(price, sessions=price.index)
        self.assertTrue(pd.notna(result.iloc[69]))
        self.assertTrue(result.iloc[70:131].isna().all())
        self.assertTrue(pd.notna(result.iloc[131]))

    def test_absent_row_is_not_skipped(self):
        price = prices(180)
        actual = calculate_volatility(price.drop(price.index[70]), sessions=price.index)
        self.assertTrue(actual.iloc[70:131].isna().all())
        self.assertTrue(pd.notna(actual.iloc[131]))

    def test_invalid_price_breaks_window(self):
        for value in [0.0, -1.0, np.inf, -np.inf]:
            with self.subTest(value=value):
                price = prices(80)
                price.iloc[30] = value
                self.assertTrue(pd.isna(calculate_volatility(price, sessions=price.index).iloc[-1]))

    def test_constant_returns_have_zero_raw_volatility(self):
        price = pd.Series(100.0, index=prices(61).index)
        self.assertEqual(calculate_volatility(price, sessions=price.index).iloc[-1], 0.0)


class LiquidityTests(unittest.TestCase):
    def test_dollar_volume_uses_price_times_reported_volume(self):
        price = prices(3)
        volume = pd.Series([2.0, 0.0, 4.0], index=price.index)
        result = calculate_dollar_volume(price, volume, sessions=price.index)
        self.assertEqual(result.tolist(), [price.iloc[0] * 2, 0.0, price.iloc[2] * 4])

    def test_exact_window_including_current_and_natural_log(self):
        price = prices(22)
        volume = pd.Series([1.0 + i for i in range(22)], index=price.index)
        adv = calculate_adv20(price, volume, sessions=price.index)
        result = calculate_liquidity(price, volume, sessions=price.index)
        self.assertTrue(result.iloc[:19].isna().all())
        first = sum(float(price.iloc[i]) * float(volume.iloc[i]) for i in range(20)) / 20
        last = sum(float(price.iloc[i]) * float(volume.iloc[i]) for i in range(2, 22)) / 20
        self.assertAlmostEqual(adv.iloc[19], first)
        self.assertAlmostEqual(adv.iloc[-1], last)
        self.assertAlmostEqual(result.iloc[19], math.log(first))
        self.assertAlmostEqual(result.iloc[-1], math.log(last))

    def test_19_observations_are_insufficient(self):
        price = prices(19)
        self.assertTrue(calculate_liquidity(price, price * 0 + 1, sessions=price.index).isna().all())

    def test_missing_price_or_volume_breaks_complete_window_and_recovers(self):
        for column in ["price", "volume"]:
            with self.subTest(column=column):
                price = prices(70)
                volume = pd.Series(10.0, index=price.index)
                (price if column == "price" else volume).iloc[25] = np.nan
                result = calculate_liquidity(price, volume, sessions=price.index)
                self.assertTrue(pd.notna(result.iloc[24]))
                self.assertTrue(result.iloc[25:45].isna().all())
                self.assertTrue(pd.notna(result.iloc[45]))

    def test_missing_volume_row_is_not_forward_filled(self):
        price = prices(21)
        volume = pd.Series(10.0, index=price.index).drop(price.index[10])
        result = calculate_liquidity(price, volume, sessions=price.index)
        self.assertTrue(result.isna().all())

    def test_zero_adv_is_missing_before_log(self):
        price = prices(21)
        volume = pd.Series(0.0, index=price.index)
        self.assertEqual(calculate_adv20(price, volume, sessions=price.index).iloc[19], 0.0)
        self.assertTrue(calculate_liquidity(price, volume, sessions=price.index).isna().all())

    def test_zero_volume_is_included_in_positive_adv(self):
        price = pd.Series(100.0, index=prices(20).index)
        volume = pd.Series([0.0] * 19 + [20.0], index=price.index)
        self.assertEqual(calculate_adv20(price, volume, sessions=price.index).iloc[-1], 100.0)
        self.assertAlmostEqual(calculate_liquidity(price, volume, sessions=price.index).iloc[-1], math.log(100))

    def test_negative_or_nonfinite_volume_is_missing(self):
        for value in [-10.0, np.inf, -np.inf]:
            with self.subTest(value=value):
                price = prices(20)
                volume = pd.Series(10.0, index=price.index)
                volume.iloc[10] = value
                self.assertTrue(pd.isna(calculate_liquidity(price, volume, sessions=price.index).iloc[-1]))

    def test_overflowing_dollar_volume_is_missing(self):
        price = pd.Series(1e300, index=prices(20).index)
        volume = pd.Series(1e300, index=price.index)
        self.assertTrue(calculate_liquidity(price, volume, sessions=price.index).isna().all())


class ReversalTests(unittest.TestCase):
    def test_exact_formula_and_first_valid_boundary(self):
        price = prices(22)
        actual = calculate_reversal(price, sessions=price.index)
        self.assertTrue(actual.iloc[:20].isna().all())
        self.assertAlmostEqual(actual.iloc[20], -(price.iloc[20] / price.iloc[0] - 1))
        self.assertAlmostEqual(actual.iloc[21], -(price.iloc[21] / price.iloc[1] - 1))
        self.assertLess(actual.iloc[20], 0)

    def test_poor_recent_return_has_positive_reversal(self):
        price = pd.Series([100.0] * 20 + [80.0], index=prices(21).index)
        self.assertAlmostEqual(calculate_reversal(price, sessions=price.index).iloc[-1], 0.2)

    def test_insufficient_history(self):
        price = prices(20)
        self.assertTrue(calculate_reversal(price, sessions=price.index).isna().all())

    def test_missing_or_invalid_endpoints(self):
        for position in [0, 20]:
            for value in [np.nan, 0.0, -1.0, np.inf]:
                with self.subTest(position=position, value=value):
                    price = prices(21)
                    price.iloc[position] = value
                    self.assertTrue(pd.isna(calculate_reversal(price, sessions=price.index).iloc[-1]))

    def test_missing_interior_price_does_not_change_endpoint_formula(self):
        price = prices(21)
        expected = -(price.iloc[20] / price.iloc[0] - 1)
        self.assertAlmostEqual(calculate_reversal(price.drop(price.index[10]), sessions=price.index).iloc[-1], expected)


class CombinedFactorTests(unittest.TestCase):
    def test_tickers_are_isolated_and_adjusted_close_is_used(self):
        a = prices()
        b = from_returns([-0.001, 0.002, -0.003] * 100).iloc[:300]
        data = pd.concat([observations(a), observations(b, "BBB", 200.0)], ignore_index=True)
        actual = calculate_raw_factors(data, sessions=a.index, tickers=["AAA", "BBB"])
        a_only = calculate_raw_factors(observations(a), sessions=a.index, tickers=["AAA"])
        b_only = calculate_raw_factors(observations(b, "BBB", 200.0), sessions=a.index, tickers=["BBB"])
        assert_frame_equal(actual[actual.ticker.eq("AAA")].reset_index(drop=True), a_only)
        assert_frame_equal(actual[actual.ticker.eq("BBB")].reset_index(drop=True), b_only)
        self.assertAlmostEqual(a_only.momentum.iloc[252], a.iloc[231] / a.iloc[0] - 1)
        self.assertEqual(actual.columns.tolist(), ["date", "ticker"] + RAW_FACTOR_COLUMNS)

    def test_unsorted_observations_and_calendar_produce_chronological_output(self):
        price = prices()
        data = observations(price)
        expected = calculate_raw_factors(data, sessions=price.index, tickers=["AAA"])
        actual = calculate_raw_factors(data.iloc[::-1], sessions=price.index[::-1], tickers=["AAA"])
        assert_frame_equal(actual, expected)
        direct = calculate_momentum(price.iloc[::-1], sessions=price.index[::-1])
        assert_series_equal(direct, calculate_momentum(price, sessions=price.index))

    def test_missing_stock_rows_are_retained_on_session_grid(self):
        price = prices(100)
        data = observations(price).drop(index=70)
        output = calculate_raw_factors(data, sessions=price.index, tickers=["AAA"])
        self.assertEqual(len(output), 100)
        self.assertTrue(pd.isna(output.volatility60.iloc[70]))
        self.assertTrue(output.liquidity_raw.iloc[70:90].isna().all())
        self.assertTrue(pd.notna(output.liquidity_raw.iloc[90]))

    def test_unavailable_fixed_universe_stocks_remain_with_nan_factors(self):
        price = prices()
        tickers = ["AAA", "FDXF", "HONA", "VYLR"]
        result = calculate_raw_factors(observations(price), sessions=price.index, tickers=tickers)
        self.assertEqual(set(result.ticker), set(tickers))
        missing = result[result.ticker.ne("AAA")]
        self.assertEqual(len(missing), 3 * len(price))
        self.assertTrue(missing[RAW_FACTOR_COLUMNS].isna().all().all())

    def test_entirely_empty_input_keeps_requested_securities(self):
        price = prices(10)
        result = calculate_raw_factors(observations(price).iloc[:0], sessions=price.index, tickers=["FDXF", "HONA", "VYLR"])
        self.assertEqual(len(result), 30)
        self.assertTrue(result[RAW_FACTOR_COLUMNS].isna().all().all())

    def test_future_changes_and_future_calendar_do_not_change_past_factors(self):
        price = prices(330)
        original = observations(price)
        cutoff = price.index[270]
        modified = original.copy()
        modified.loc[modified.date.gt(cutoff), "adjusted_close"] *= 1000
        modified.loc[modified.date.gt(cutoff), "volume"] = 0.0
        baseline = calculate_raw_factors(original, sessions=price.index, tickers=["AAA"])
        changed = calculate_raw_factors(modified, sessions=price.index, tickers=["AAA"])
        historical = baseline[baseline.date.le(cutoff)].reset_index(drop=True)
        assert_frame_equal(changed[changed.date.le(cutoff)].reset_index(drop=True), historical)
        prefix = calculate_raw_factors(original[original.date.le(cutoff)], sessions=price.index[:271], tickers=["AAA"])
        assert_frame_equal(prefix, historical)

    def test_inputs_are_not_modified(self):
        price = prices()
        data = observations(price)
        copy = data.copy(deep=True)
        calculate_raw_factors(data, sessions=price.index, tickers=["AAA"])
        assert_frame_equal(data, copy)

    def test_no_outlier_clipping(self):
        price = prices(253)
        price.iloc[231] = 1e9
        actual = calculate_momentum(price, sessions=price.index)
        self.assertAlmostEqual(actual.iloc[-1], 1e9 / price.iloc[0] - 1)

    def test_duplicate_observations_raise(self):
        price = prices(10)
        data = observations(price)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            calculate_raw_factors(pd.concat([data, data.iloc[[0]]]), sessions=price.index, tickers=["AAA"])

    def test_bad_ticker_requests_and_missing_schema_raise(self):
        price = prices(10)
        data = observations(price)
        for tickers in [[], ["AAA", "AAA"], ["AAA", "SPY"], [""], [None], [" AAA"]]:
            with self.subTest(tickers=tickers):
                with self.assertRaises(ValueError):
                    calculate_raw_factors(data, sessions=price.index, tickers=tickers)
        with self.assertRaises(ValueError):
            calculate_raw_factors(data, sessions=price.index, tickers=["BBB"])
        with self.assertRaises(ValueError):
            calculate_raw_factors(data.drop(columns="adjusted_close"), sessions=price.index, tickers=["AAA"])


class InputValidationTests(unittest.TestCase):
    def test_duplicate_or_invalid_calendars_raise(self):
        price = prices(10)
        for calendar in [price.index.append(price.index[:1]), pd.DatetimeIndex([]),
                         pd.DatetimeIndex([pd.NaT]), price.index.tz_localize("UTC"),
                         price.index + pd.Timedelta(hours=1)]:
            with self.subTest(calendar=calendar):
                with self.assertRaises(ValueError):
                    calculate_momentum(price, sessions=calendar)

    def test_duplicate_dates_and_outside_sessions_raise(self):
        price = prices(10)
        with self.assertRaises(ValueError):
            calculate_momentum(pd.concat([price, price.iloc[:1]]), sessions=price.index)
        with self.assertRaises(ValueError):
            calculate_momentum(price, sessions=price.index[1:])

    def test_nonnumeric_or_nondate_series_raise(self):
        price = prices(10)
        for value in [price.astype(str), price.astype(bool), price.astype(complex), price.reset_index(drop=True)]:
            with self.subTest(dtype=value.dtype):
                with self.assertRaises(TypeError):
                    calculate_momentum(value, sessions=price.index)


if __name__ == "__main__":
    unittest.main()
