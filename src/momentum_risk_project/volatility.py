
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


def ewma_volatility(
    daily_returns: pd.Series,
    decay: float = 0.94,
    initialization_window: int = 126,
    trading_days_per_month: int = 21,
) -> pd.Series:
    """Estimate forward monthly volatility using EWMA daily variance."""

    if not isinstance(daily_returns.index, pd.DatetimeIndex):
        raise TypeError("Expected a DatetimeIndex")

    if not daily_returns.index.is_unique:
        raise ValueError("Duplicate dates detected")

    if not daily_returns.index.is_monotonic_increasing:
        raise ValueError("Dates must be sorted")

    if not 0.0 < decay < 1.0:
        raise ValueError("Decay must be between 0 and 1")

    if initialization_window <= 0 or trading_days_per_month <= 0:
        raise ValueError("Window and trading days must be positive")

    values = daily_returns.to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError("Returns contain non-finite values")

    variances = np.full(len(values), np.nan)

    if len(values) < initialization_window:
        return pd.Series(
            variances,
            index=daily_returns.index,
            name="ewma_volatility",
        )

    # Initialize using the first 126 squared daily returns.
    initial_variance = np.mean(values[:initialization_window] ** 2)
    variances[initialization_window - 1] = initial_variance

    # Update variance after observing each subsequent daily return.
    for i in range(initialization_window, len(values)):
        variances[i] = (
            decay * variances[i - 1]
            + (1.0 - decay) * values[i] ** 2
        )

    # Under EWMA, the multi-step daily variance forecast is constant.
    monthly_volatility = np.sqrt(
        trading_days_per_month * variances
    )

    return pd.Series(
        monthly_volatility,
        index=daily_returns.index,
        name="ewma_volatility",
    )
