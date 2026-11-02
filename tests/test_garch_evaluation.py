"""Tests for GARCH extension evaluation functions."""

import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.garch_evaluation import (
    forecast_accuracy,
    forecast_loss_test,
)


def test_forecast_accuracy_known_values():
    months = pd.period_range("2020-01", periods=4, freq="M")

    realized = pd.Series([0.10, 0.20, 0.30, 0.40], index=months)

    forecasts = pd.DataFrame({
        "historical": [0.12, 0.18, 0.33, 0.37],
        "garch": [0.11, 0.19, 0.31, 0.39],
    }, index=months)

    result = forecast_accuracy(realized, forecasts)

    assert result.loc["historical", "MAE"] == pytest.approx(0.025)
    assert result.loc["garch", "MAE"] == pytest.approx(0.01)
    assert result.loc["historical", "RMSE"] == pytest.approx(
        np.sqrt((0.02**2 + 0.02**2 + 0.03**2 + 0.03**2) / 4)
    )
    assert result.loc["garch", "Bias"] == pytest.approx(0.0)


def test_forecast_loss_test_known_values():
    months = pd.period_range("2020-01", periods=6, freq="M")

    realized = pd.Series(
        [0.10, 0.12, 0.09, 0.15, 0.11, 0.14],
        index=months,
    )

    historical = realized + pd.Series(
        [0.03, -0.02, 0.04, -0.03, 0.02, -0.04],
        index=months,
    )

    garch = realized + pd.Series(
        [0.01, -0.01, 0.02, -0.01, 0.01, -0.02],
        index=months,
    )

    result = forecast_loss_test(
        realized, historical, garch, hac_lags=1
    )

    assert result["Observations"] == 6
    assert result["Mean Loss Difference"] > 0
    assert np.isfinite(result["HAC t-statistic"])
    assert 0 <= result["Two-sided p-value"] <= 1


def test_forecast_accuracy_rejects_misaligned_indices():
    realized = pd.Series(
        [0.1, 0.2],
        index=pd.period_range("2020-01", periods=2, freq="M"),
    )

    forecasts = pd.DataFrame(
        {"garch": [0.1, 0.2]},
        index=pd.period_range("2020-02", periods=2, freq="M"),
    )

    with pytest.raises(ValueError, match="indices must match"):
        forecast_accuracy(realized, forecasts)
