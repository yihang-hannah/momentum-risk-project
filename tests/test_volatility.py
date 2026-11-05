
import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.volatility import (
    historical_volatility,
    ewma_volatility,
)


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


def test_ewma_constant_returns():
    """Constant returns should produce constant EWMA volatility."""
    dates = pd.bdate_range("2020-01-01", periods=130)
    returns = pd.Series(0.01, index=dates)

    result = ewma_volatility(returns)

    expected = np.sqrt(21 * 0.01**2)

    assert result.iloc[:125].isna().all()
    np.testing.assert_allclose(
        result.iloc[125:].to_numpy(),
        expected,
    )


def test_ewma_recursion():
    """Verify the EWMA variance update after a volatility shock."""
    dates = pd.bdate_range("2020-01-01", periods=127)
    returns = pd.Series(
        [0.01] * 126 + [0.02],
        index=dates,
    )

    result = ewma_volatility(returns, decay=0.94)

    initial_variance = 0.01**2
    updated_variance = (
        0.94 * initial_variance
        + 0.06 * 0.02**2
    )

    assert result.iloc[125] == pytest.approx(
        np.sqrt(21 * initial_variance)
    )
    assert result.iloc[126] == pytest.approx(
        np.sqrt(21 * updated_variance)
    )


def test_ewma_does_not_use_future_returns():
    """Changing a future return must not change earlier estimates."""
    dates = pd.bdate_range("2020-01-01", periods=130)

    original = pd.Series([0.01] * 130, index=dates)
    modified = original.copy()
    modified.iloc[-1] = 0.50

    original_vol = ewma_volatility(original)
    modified_vol = ewma_volatility(modified)

    pd.testing.assert_series_equal(
        original_vol.iloc[:-1],
        modified_vol.iloc[:-1],
    )

    assert modified_vol.iloc[-1] > original_vol.iloc[-1]


@pytest.mark.parametrize(
    "decay,window,horizon",
    [
        (0.0, 126, 21),
        (1.0, 126, 21),
        (-0.1, 126, 21),
        (1.1, 126, 21),
        (0.94, 0, 21),
        (0.94, 126, 0),
    ],
)
def test_ewma_rejects_invalid_parameters(decay, window, horizon):
    """Reject invalid decay factors and estimation settings."""
    dates = pd.bdate_range("2020-01-01", periods=130)
    returns = pd.Series(0.01, index=dates)

    with pytest.raises(ValueError):
        ewma_volatility(
            returns,
            decay=decay,
            initialization_window=window,
            trading_days_per_month=horizon,
        )


def test_ewma_insufficient_data():
    """Return missing estimates until initialization is possible."""
    dates = pd.bdate_range("2020-01-01", periods=50)
    returns = pd.Series(0.01, index=dates)

    result = ewma_volatility(
        returns,
        initialization_window=126,
    )

    assert len(result) == len(returns)
    assert result.isna().all()
