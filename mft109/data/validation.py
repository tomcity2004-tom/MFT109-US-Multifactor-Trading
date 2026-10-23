"""Structural errors and explicit market-data quality diagnostics; no imputation."""

import numpy as np
import pandas as pd

PRICE_COLUMNS = ["open", "high", "low", "close", "adjusted_close"]
VALUE_COLUMNS = PRICE_COLUMNS + ["volume"]
COLUMNS = ["date", "ticker"] + VALUE_COLUMNS


class DataValidationError(ValueError):
    """An unusable or structurally ambiguous dataset."""


def check_structure(frame, ticker=None):
    if frame.empty:
        raise DataValidationError("Market dataset is empty")
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise DataValidationError(f"Missing market columns: {sorted(missing)}")
    dates = pd.to_datetime(frame.date, errors="coerce")
    if dates.isna().any():
        raise DataValidationError("Market dataset contains invalid dates")
    if dates.dt.tz is not None or not dates.eq(dates.dt.normalize()).all():
        raise DataValidationError("Dates must be timezone-naive daily session dates")
    if frame.ticker.isna().any() or frame.ticker.astype(str).str.strip().eq("").any():
        raise DataValidationError("Market dataset contains unidentified tickers")
    if ticker is not None and set(frame.ticker) != {ticker}:
        raise DataValidationError(f"Expected ticker {ticker}, found {sorted(set(frame.ticker))}")
    for column in VALUE_COLUMNS:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise DataValidationError(f"Non-numeric market column: {column}")


def validate_market_data(frame, ticker, start, end, *, tolerance_days=7,
                         benchmark=False, reference_dates=None):
    """Validate a cleaned single-ticker dataset and report incomplete history.

    Coverage tolerance accommodates weekends/holidays at request boundaries.
    Short stock histories are reported, never fabricated. Benchmark history is
    required across the requested period. Reference dates are SPY sessions, not
    a synthetic weekday calendar that would incorrectly count exchange holidays.
    """
    check_structure(frame, ticker)
    dates = pd.to_datetime(frame.date)
    if pd.DataFrame({"date": dates, "ticker": frame.ticker}).duplicated().any():
        raise DataValidationError("Duplicate date/ticker observations")
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if (dates.lt(start) | dates.gt(end)).any():
        raise DataValidationError("Observations lie outside requested inclusive date boundaries")
    invalid = {}
    for column in VALUE_COLUMNS:
        present = frame[column].notna()
        bad = present & (~np.isfinite(frame[column]) | (
            frame[column].lt(0) if column == "volume" else frame[column].le(0)))
        invalid[column] = int(bad.sum())
    if any(invalid.values()):
        raise DataValidationError(f"Invalid values remain after cleaning: {invalid}")
    valid_prices = frame.adjusted_close.notna()
    if not valid_prices.any():
        raise DataValidationError(f"No usable adjusted prices for {ticker}; download failed or history unavailable")
    valid_dates = dates[valid_prices]
    first, last = valid_dates.min(), valid_dates.max()
    warnings = []
    if (first - start).days > tolerance_days:
        warnings.append(f"Usable history begins late: {first.date()}")
    if (end - last).days > tolerance_days:
        warnings.append(f"Usable history ends early: {last.date()}")
    missing_values = {column: int(frame[column].isna().sum()) for column in VALUE_COLUMNS}
    if any(missing_values.values()):
        warnings.append("Missing market values preserved; consult missing_values counts")
    absent_dates = []
    if reference_dates is not None:
        absent_dates = sorted(set(pd.to_datetime(reference_dates)) - set(dates))
        if absent_dates:
            warnings.append(f"{len(absent_dates)} SPY sessions have no stock observation")
    if benchmark and (warnings or absent_dates):
        raise DataValidationError(f"Benchmark {ticker} is incomplete: {warnings}")
    return {"ticker": ticker, "rows": len(frame),
            "first_valid_price_date": first.date().isoformat(),
            "last_valid_price_date": last.date().isoformat(),
            "missing_values": missing_values,
            "missing_price_rows": int(frame[PRICE_COLUMNS].isna().any(axis=1).sum()),
            "missing_volume_rows": missing_values["volume"],
            "absent_reference_sessions": len(absent_dates),
            "absent_reference_dates": [d.date().isoformat() for d in absent_dates],
            "warnings": warnings}
