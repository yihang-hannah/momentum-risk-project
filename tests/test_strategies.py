
import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.strategies import (
    volatility_managed_momentum,
)


def test_managed_strategy_uses_previous_month_volatility():
    """Verify that strategy weights use lagged volatility."""

    months = pd.period_range(
        "2020-01",
        periods=3,
        freq="M",
    )

    returns = pd.Series(
        [0.01, 0.05, -0.02],
        index=months,
    )

    volatility = pd.Series(
        [0.04, 0.06, 0.08],
        index=months,
    )

    result = volatility_managed_momentum(
        monthly_returns=returns,
        monthly_volatility=volatility,
        target_volatility=0.12,
    )

    expected_weight_feb = (0.12 / np.sqrt(12)) / 0.04
    expected_return_feb = expected_weight_feb * 0.05

    assert np.isnan(result.loc["2020-01", "managed"])

    assert result.loc["2020-02", "weight"] == pytest.approx(
        expected_weight_feb
    )

    assert result.loc["2020-02", "managed"] == pytest.approx(
        expected_return_feb
    )

def test_current_month_volatility_does_not_affect_current_return():
    """Verify that current-month volatility cannot affect current returns."""

    months = pd.period_range("2020-01", periods=3, freq="M")
    returns = pd.Series([0.01, 0.05, 0.02], index=months)

    volatility_a = pd.Series([0.04, 0.06, 0.08], index=months)
    volatility_b = pd.Series([0.04, 0.60, 0.08], index=months)

    result_a = volatility_managed_momentum(
        returns, volatility_a
    )
    result_b = volatility_managed_momentum(
        returns, volatility_b
    )

    assert result_a.loc["2020-02", "managed"] == pytest.approx(
        result_b.loc["2020-02", "managed"]
    )

    assert result_a.loc["2020-03", "managed"] != pytest.approx(
        result_b.loc["2020-03", "managed"]
    )
