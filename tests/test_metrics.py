import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.metrics import performance_metrics


def test_regular_returns_preserve_wealth_metrics():
    returns = pd.Series([0.10, -0.05, 0.03])
    result = performance_metrics(returns)
    assert result["Terminal Wealth"] == pytest.approx(1.10 * 0.95 * 1.03)
    assert np.isfinite(result["CAGR"])
    assert np.isfinite(result["Maximum Drawdown"])


@pytest.mark.parametrize("extreme_return", [-1.0, -1.20])
def test_extreme_long_short_returns_keep_arithmetic_metrics(extreme_return):
    returns = pd.Series([0.10, extreme_return, 0.05])
    result = performance_metrics(returns)
    assert result["Annualized Mean Return"] == pytest.approx(returns.mean() * 12)
    assert np.isfinite(result["Annualized Volatility"])
    assert np.isfinite(result["Sharpe (rf=0)"])
    assert np.isnan(result["CAGR"])
    assert np.isnan(result["Maximum Drawdown"])
    assert np.isnan(result["Terminal Wealth"])


def test_nonfinite_returns_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        performance_metrics(pd.Series([0.01, np.inf]))
