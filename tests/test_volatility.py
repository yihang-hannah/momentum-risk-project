
import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.volatility import historical_volatility


def test_historical_volatility_constant_returns():
    """Test volatility estimation using constant daily returns."""

    dates = pd.bdate_range("2020-01-01", periods=126)

    returns = pd.Series(
        0.01,
        index=dates,
    )

    result = historical_volatility(returns)

    expected = np.sqrt(21 * 0.01**2)

    assert result.iloc[-1] == pytest.approx(expected)
    assert result.iloc[:125].isna().all()


def test_historical_volatility_uses_squared_returns():
    """Verify that the estimator does not demean returns."""

    dates = pd.bdate_range("2020-01-01", periods=4)

    returns = pd.Series(
        [0.01, 0.02, -0.01, -0.02],
        index=dates,
    )

    result = historical_volatility(
        returns,
        window=4,
        trading_days_per_month=21,
    )

    expected_variance = 21 * np.mean(
        np.array([0.01, 0.02, -0.01, -0.02]) ** 2
    )

    assert result.iloc[-1] == pytest.approx(
        np.sqrt(expected_variance)
    )


def test_historical_volatility_rejects_invalid_window():
    """Reject non-positive rolling windows."""

    dates = pd.bdate_range("2020-01-01", periods=5)
    returns = pd.Series([0.01] * 5, index=dates)

    with pytest.raises(ValueError):
        historical_volatility(returns, window=0)

def test_historical_volatility_includes_current_day():
    """Verify that the latest daily return enters the estimate."""

    dates = pd.bdate_range("2020-01-01", periods=4)
    returns = pd.Series([0.01, 0.01, 0.01, 0.10], index=dates)

    result = historical_volatility(
        returns,
        window=4,
        trading_days_per_month=21,
    )

    expected = np.sqrt(
        21 * np.mean(np.array([0.01, 0.01, 0.01, 0.10]) ** 2)
    )

    assert result.iloc[-1] == pytest.approx(expected)
