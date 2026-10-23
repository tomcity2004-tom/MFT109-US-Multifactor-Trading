"""Conservative cleaning: invalid values become missing; no filling or outliers."""

import numpy as np
import pandas as pd

from mft109.data.validation import COLUMNS, VALUE_COLUMNS, DataValidationError, check_structure


def clean_market_data(frame):
    """Collapse exact duplicate rows; reject conflicting duplicates.

    Nonfinite/nonpositive prices and nonfinite/negative volume become NaN.
    Zero volume remains valid. Invalid dates, identifiers, and nonnumeric schemas
    are rejected instead of silently dropped. No rows or calendar gaps are filled.
    """
    check_structure(frame)
    result = frame[COLUMNS].copy()
    result["date"] = pd.to_datetime(result.date)
    count = len(result)
    result = result.drop_duplicates()
    if result.duplicated(["date", "ticker"]).any():
        raise DataValidationError("Conflicting duplicate date/ticker observations")
    report = {"exact_duplicates_removed": count - len(result), "invalid_values_to_missing": {}}
    for column in VALUE_COLUMNS:
        bad = result[column].notna() & (~np.isfinite(result[column]) | (
            result[column].lt(0) if column == "volume" else result[column].le(0)))
        report["invalid_values_to_missing"][column] = int(bad.sum())
        result[column] = result[column].astype("float64").mask(bad)
    return result.sort_values(["date", "ticker"]).reset_index(drop=True), report
