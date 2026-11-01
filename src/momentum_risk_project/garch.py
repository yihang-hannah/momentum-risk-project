
"""Out-of-sample GARCH(1,1) volatility forecasts for momentum returns."""

import warnings

import numpy as np
import pandas as pd
from arch import arch_model


def garch_monthly_volatility(
    daily_returns: pd.Series,
    estimation_window: int = 756,
    forecast_horizon: int = 21,
) -> pd.Series:
    """Estimate rolling GARCH(1,1) and forecast monthly volatility.

    At each month-end:
    1. Fit GARCH using the preceding estimation_window daily returns.
    2. Forecast the next forecast_horizon daily conditional variances.
    3. Sum those variances and take the square root.

    The forecast is indexed by the month in which it is generated,
    not the month whose returns it will predict.

    Returns are supplied in decimal units; arch fits percentage returns.
    """

    if not isinstance(daily_returns, pd.Series):
        raise TypeError("daily_returns must be a pandas Series")
    if not isinstance(daily_returns.index, pd.DatetimeIndex):
        raise TypeError("Expected a DatetimeIndex")
    if not daily_returns.index.is_unique:
        raise ValueError("Duplicate daily dates")
    if not daily_returns.index.is_monotonic_increasing:
        raise ValueError("Daily dates must be sorted")
    if estimation_window < 100 or forecast_horizon < 1:
        raise ValueError("Invalid estimation window or forecast horizon")
    if not np.isfinite(daily_returns.to_numpy(dtype=float)).all():
        raise ValueError("Daily returns must be finite")

    forecasts = {}

    for month, observations in daily_returns.groupby(
        daily_returns.index.to_period("M")
    ):
        month_end = observations.index[-1]
        history = daily_returns.loc[:month_end].tail(estimation_window)

        if len(history) < estimation_window:
            forecasts[month] = np.nan
            continue

        # Percentage units improve numerical optimization.
        returns_pct = history * 100.0

        model = arch_model(
            returns_pct,
            mean="Zero",
            vol="GARCH",
            p=1,
            q=1,
            dist="normal",
            rescale=False,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = model.fit(disp="off", show_warning=False)

        if fit.convergence_flag != 0:
            forecasts[month] = np.nan
            continue

        # One origin, multiple future daily conditional variances.
        forecast = fit.forecast(
            horizon=forecast_horizon,
            reindex=False,
        )
        daily_variances_pct = forecast.variance.iloc[-1].to_numpy()

        # Variance aggregation; percentage units -> decimal units.
        monthly_variance = daily_variances_pct.sum() / (100.0 ** 2)
        forecasts[month] = np.sqrt(monthly_variance)

    result = pd.Series(
        forecasts,
        index=pd.PeriodIndex(forecasts.keys(), freq="M"),
        name="garch_monthly_volatility",
        dtype=float,
    )

    return result
