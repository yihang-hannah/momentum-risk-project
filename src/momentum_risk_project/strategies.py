"""Reusable monthly momentum strategy implementations.

The paper-replication notebook independently derives and validates the formulas.
This module encapsulates the validated strategy logic for other experiments.
"""

import numpy as np
import pandas as pd


def _validate_monthly_series(series: pd.Series, label: str) -> None:
    """Require a chronologically ordered monthly Series with unique periods."""
    if not isinstance(series, pd.Series):
        raise TypeError(f"{label} must be a pandas Series")
    if not isinstance(series.index, pd.PeriodIndex):
        raise TypeError(f"{label} must use a monthly PeriodIndex")
    if series.index.freqstr != "M":
        raise ValueError(f"{label} must have monthly frequency")
    if not series.index.is_unique:
        raise ValueError(f"{label} contains duplicate months")
    if not series.index.is_monotonic_increasing:
        raise ValueError(f"{label} must be sorted chronologically")


def unmanaged_momentum(monthly_returns: pd.Series) -> pd.Series:
    """Return an unscaled monthly momentum return series."""
    _validate_monthly_series(monthly_returns, "Monthly returns")
    if not np.isfinite(monthly_returns.to_numpy(dtype=float)).all():
        raise ValueError("Monthly returns must be finite")
    result = monthly_returns.copy()
    result.name = "unmanaged"
    return result


def volatility_managed_momentum(
    monthly_returns: pd.Series,
    monthly_volatility: pd.Series,
    target_volatility: float = 0.12,
) -> pd.DataFrame:
    """Apply lagged inverse-volatility exposure to monthly momentum returns.

    Parameters
    ----------
    monthly_returns : pd.Series
        Decimal WML returns indexed by monthly PeriodIndex, in calendar order.
        Months must be consecutive so a one-row shift means one calendar month.
    monthly_volatility : pd.Series
        Monthly-unit volatility estimates available at each month-end, indexed
        by monthly PeriodIndex. Leading NaNs are allowed for the warm-up window.
        Estimates must not use information from future months.
    target_volatility : float
        Annualized target volatility (0.12 means 12% per year).

    Returns
    -------
    pd.DataFrame
        Columns: mom, estimated_volatility, weight, managed. ``weight`` is
        the exposure determined at the PREVIOUS month-end. The first month
        without a prior forecast has NaN weight and managed return.

    Notes
    -----
    Mirrors the independently tested notebook formula:
    monthly_target = annual_target / sqrt(12)
    weight[t] = monthly_target / volatility[t-1]
    managed[t] = weight[t] * WML[t]
    No leverage cap, transaction costs, or financing charges are imposed.
    """
    if not np.isfinite(target_volatility) or target_volatility <= 0:
        raise ValueError("Target volatility must be positive and finite")

    _validate_monthly_series(monthly_returns, "Monthly returns")
    _validate_monthly_series(monthly_volatility, "Monthly volatility")

    if not monthly_returns.empty:
        expected_months = pd.period_range(
            monthly_returns.index[0], monthly_returns.index[-1], freq="M"
        )
        if not monthly_returns.index.equals(expected_months):
            raise ValueError("Monthly returns must contain consecutive months")

    if not np.isfinite(monthly_returns.to_numpy(dtype=float)).all():
        raise ValueError("Monthly returns must be finite")

    vol_values = monthly_volatility.to_numpy(dtype=float)
    if np.isinf(vol_values).any():
        raise ValueError("Volatility contains infinite values")
    if (monthly_volatility.dropna() <= 0).any():
        raise ValueError("Volatility estimates must be positive")

    # Align month-end forecasts with monthly WML return dates.
    aligned_volatility = monthly_volatility.reindex(monthly_returns.index)

    # The volatility input is already in monthly units.
    target_monthly = target_volatility / np.sqrt(12)
    month_end_weights = target_monthly / aligned_volatility

    # One calendar-month execution lag; no additional daily lag.
    applied_weights = month_end_weights.shift(1)
    managed_returns = applied_weights * monthly_returns

    return pd.DataFrame({
        "mom": monthly_returns,
        "estimated_volatility": aligned_volatility,
        "weight": applied_weights,
        "managed": managed_returns,
    })
