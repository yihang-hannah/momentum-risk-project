
import numpy as np
import pandas as pd


def historical_volatility(
    daily_returns: pd.Series,
    window: int = 126,
    trading_days_per_month: int = 21,
) -> pd.Series:
    """Estimate monthly volatility using past squared daily returns."""

    if not isinstance(daily_returns.index, pd.DatetimeIndex):
        raise TypeError("Expected a DatetimeIndex")

    if not daily_returns.index.is_unique:
        raise ValueError("Duplicate dates detected")

    if not daily_returns.index.is_monotonic_increasing:
        raise ValueError("Dates must be sorted")

    if window <= 0 or trading_days_per_month <= 0:
        raise ValueError("Window and trading days must be positive")

    if not np.isfinite(daily_returns.to_numpy()).all():
        raise ValueError("Returns contain non-finite values")

    # Calculate the rolling mean of squared daily returns
    rolling_mean_squared = (
        daily_returns.pow(2)
        .rolling(window=window, min_periods=window)
        .mean()
    )

    # Convert daily variance to monthly variance
    monthly_variance = (
        trading_days_per_month * rolling_mean_squared
    )

    # Convert variance to volatility
    monthly_volatility = np.sqrt(monthly_variance)

    monthly_volatility.name = "historical_volatility"

    return monthly_volatility

