
import pandas as pd
import numpy as np

def unmanaged_momentum(
    monthly_returns: pd.Series,
) -> pd.Series:
    """Return the unmanaged momentum strategy returns."""

    if not isinstance(monthly_returns.index, pd.PeriodIndex):
        raise TypeError("Expected a monthly PeriodIndex")

    if monthly_returns.index.freqstr != "M":
        raise ValueError("Expected monthly frequency")

    if monthly_returns.isna().any():
        raise ValueError("Returns contain missing values")

    result = monthly_returns.copy()
    result.name = "unmanaged"

    return result


def volatility_managed_momentum(
    monthly_returns: pd.Series,
    monthly_volatility: pd.Series,
    target_volatility: float = 0.12,
) -> pd.DataFrame:
    """Construct a monthly volatility-managed momentum strategy."""

    if target_volatility <= 0 or not np.isfinite(target_volatility):
        raise ValueError("Target volatility must be positive and finite")

    if not isinstance(monthly_returns.index, pd.PeriodIndex):
        raise TypeError("Expected monthly PeriodIndex for returns")

    if not isinstance(monthly_volatility.index, pd.PeriodIndex):
        raise TypeError("Expected monthly PeriodIndex for volatility")

    if monthly_returns.index.freqstr != "M":
        raise ValueError("Expected monthly returns")

    if monthly_volatility.index.freqstr != "M":
        raise ValueError("Expected monthly volatility")

    if not monthly_returns.index.is_unique:
        raise ValueError("Duplicate return months detected")

    if not monthly_volatility.index.is_unique:
        raise ValueError("Duplicate volatility months detected")

    if monthly_returns.isna().any():
        raise ValueError("Monthly returns contain missing values")

    if not np.isfinite(monthly_returns.to_numpy()).all():
        raise ValueError("Monthly returns contain non-finite values")

    if np.isinf(monthly_volatility.to_numpy()).any():
        raise ValueError("Volatility contains infinite values")

    if (monthly_volatility.dropna() <= 0).any():
        raise ValueError("Volatility estimates must be positive")

    # Align the volatility estimates to the return months
    aligned_volatility = monthly_volatility.reindex(
        monthly_returns.index
    )

    # Convert annualized target volatility to monthly units
    target_monthly = target_volatility / np.sqrt(12)

    # Calculate weights at each month-end
    month_end_weights = target_monthly / aligned_volatility

    # Apply month-end weights to the following month's returns
    applied_weights = month_end_weights.shift(1)

    # Calculate managed strategy returns
    managed_returns = applied_weights * monthly_returns

    result = pd.DataFrame({
        "mom": monthly_returns,
        "estimated_volatility": aligned_volatility,
        "weight": applied_weights,
        "managed": managed_returns,
    })

    return result
