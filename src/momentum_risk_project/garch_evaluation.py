"""Evaluation functions for the GARCH momentum extension."""

import numpy as np
import pandas as pd
import statsmodels.api as sm


def forecast_accuracy(
    realized: pd.Series,
    forecasts: pd.DataFrame,
) -> pd.DataFrame:
    """Compare volatility forecasts against subsequent realized volatility."""
    if not realized.index.equals(forecasts.index):
        raise ValueError("Forecast and realized-volatility indices must match")

    if forecasts.empty or forecasts.isna().any().any() or realized.isna().any():
        raise ValueError("Forecast evaluation requires complete observations")

    if not np.isfinite(forecasts.to_numpy(dtype=float)).all():
        raise ValueError("Forecasts must be finite")

    if not np.isfinite(realized.to_numpy(dtype=float)).all():
        raise ValueError("Realized volatility must be finite")

    results = {}

    for name in forecasts.columns:
        error = forecasts[name] - realized

        results[name] = {
            "MAE": error.abs().mean(),
            "RMSE": np.sqrt(error.pow(2).mean()),
            "Bias": error.mean(),
            "Correlation": forecasts[name].corr(realized),
        }

    return pd.DataFrame(results).T


def forecast_loss_test(
    realized: pd.Series,
    historical: pd.Series,
    garch: pd.Series,
    hac_lags: int = 3,
) -> pd.Series:
    """HAC test of historical minus GARCH squared forecast loss."""
    if not realized.index.equals(historical.index):
        raise ValueError("Historical forecast index does not match realized index")

    if not realized.index.equals(garch.index):
        raise ValueError("GARCH forecast index does not match realized index")

    if hac_lags < 0:
        raise ValueError("hac_lags must be nonnegative")

    values = np.column_stack([
        realized.to_numpy(dtype=float),
        historical.to_numpy(dtype=float),
        garch.to_numpy(dtype=float),
    ])

    if len(realized) < 2 or not np.isfinite(values).all():
        raise ValueError("At least two complete finite observations are required")

    error_h = historical - realized
    error_g = garch - realized

    differential = error_h.pow(2) - error_g.pow(2)

    model = sm.OLS(
        differential.to_numpy(),
        np.ones((len(differential), 1)),
    ).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": hac_lags},
    )

    confidence_interval = model.conf_int()[0]

    return pd.Series({
        "Observations": len(differential),
        "Mean Loss Difference": differential.mean(),
        "HAC t-statistic": float(model.tvalues[0]),
        "Two-sided p-value": float(model.pvalues[0]),
        "95% CI Lower": float(confidence_interval[0]),
        "95% CI Upper": float(confidence_interval[1]),
        "HAC Lags": hac_lags,
    })
