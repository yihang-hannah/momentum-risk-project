
"""Sensitivity analysis for rolling GARCH(1,1) momentum forecasts.

Compare Gaussian and Student-t innovations across four estimation
windows, using identical out-of-sample evaluation dates.

Outputs are separate from the original GARCH replication results.
"""

from pathlib import Path
import time

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.garch import garch_monthly_volatility
from momentum_risk_project.garch_evaluation import (
    forecast_accuracy,
    forecast_loss_test,
)
from momentum_risk_project.strategies import volatility_managed_momentum
from momentum_risk_project.metrics import performance_metrics


WINDOWS = (252, 504, 756, 1260)
DISTRIBUTIONS = ("normal", "t")
FORECAST_HORIZON = 21
TARGET_VOLATILITY = 0.12
HAC_LAGS = 3

SAMPLES = {
    "historical": ("1931-05", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}


def model_name(distribution, window):
    return f"{distribution}_{window}"


def calculate_forecasts(daily, origins, distribution, window, path):
    """Estimate forecasts, resuming from a saved checkpoint."""
    if path.exists():
        saved = pd.read_parquet(path)["forecast"]
        if not saved.index.is_unique:
            raise ValueError(f"Duplicate forecast dates in {path}")
        if not saved.index.isin(origins).all():
            raise ValueError(f"Unexpected forecast dates in {path}")
        saved = saved.sort_index()
    else:
        saved = pd.Series(dtype=float, name="forecast")
        saved.index = pd.PeriodIndex([], freq="M")

    forecasts = saved.to_dict()
    pending = [month for month in origins if month not in forecasts]

    print(
        f"{distribution}, {window} days: "
        f"{len(saved)} cached, {len(pending)} remaining",
        flush=True,
    )

    start = time.perf_counter()

    for i, month in enumerate(pending, start=1):
        history = daily.loc[
            daily.index.to_period("M") <= month
        ].tail(window)

        if len(history) < window:
            forecasts[month] = np.nan
        else:
            # Reuse the existing validated forecasting function.
            result = garch_monthly_volatility(
                history,
                estimation_window=window,
                forecast_horizon=FORECAST_HORIZON,
                distribution=distribution,
            )
            forecasts[month] = float(result.loc[month])

        if i % 12 == 0 or i == len(pending):
            series = pd.Series(
                forecasts,
                name="forecast",
                dtype=float,
            ).sort_index()
            series.to_frame().to_parquet(path)

            print(
                f"  {i}/{len(pending)} completed "
                f"({time.perf_counter() - start:.1f}s)",
                flush=True,
            )

    return pd.read_parquet(path)["forecast"].reindex(origins)


def evaluate_sample(
    name, months, daily, monthly, forecast_origins,
    forecasts, output_dir,
):
    """Evaluate all models on an identical calendar-month sample."""
    sample_dir = output_dir / name
    sample_dir.mkdir(parents=True, exist_ok=True)

    realized = (
        daily.pow(2)
        .groupby(daily.index.to_period("M"))
        .sum()
        .pow(0.5)
        .reindex(months)
    )

    shifted = pd.DataFrame(index=months)

    for model in forecasts:
        series = forecasts[model].copy()
        series.index = series.index + 1
        shifted[model] = series.reindex(months)

    if shifted.isna().any().any():
        missing = shifted.isna().sum()
        raise RuntimeError(
            f"{name}: missing forecasts:\n"
            f"{missing[missing > 0]}"
        )

    if not np.isfinite(shifted.to_numpy()).all():
        raise RuntimeError(f"{name}: nonfinite forecasts")

    if (shifted <= 0).any().any():
        raise RuntimeError(f"{name}: nonpositive forecasts")

    if realized.isna().any():
        raise RuntimeError(f"{name}: missing realized volatility")

    accuracy = forecast_accuracy(realized, shifted)

    performance = {}
    for model in forecasts:
        strategy = volatility_managed_momentum(
            monthly,
            forecasts[model],
            target_volatility=TARGET_VOLATILITY,
        )

        returns = strategy["managed"].reindex(months)
        weights = strategy["weight"].reindex(months)

        if returns.isna().any() or weights.isna().any():
            raise RuntimeError(f"{name}: incomplete strategy {model}")

        metrics = performance_metrics(returns)
        metrics["Average Exposure"] = weights.mean()
        performance[model] = metrics

    performance = pd.DataFrame(performance).T

    baseline = shifted["normal_756"]
    tests = {}

    for model in forecasts:
        if model == "normal_756":
            continue

        tests[model] = forecast_loss_test(
            realized,
            baseline,
            shifted[model],
            hac_lags=HAC_LAGS,
        )

    significance = pd.DataFrame(tests).T

    accuracy.to_csv(sample_dir / "forecast_accuracy.csv")
    performance.to_csv(sample_dir / "portfolio_performance.csv")
    significance.to_csv(sample_dir / "forecast_loss_tests.csv")

    print(f"\n{name.upper()} FORECAST ACCURACY")
    print(accuracy.round(6).to_string())

    print(f"\n{name.upper()} PORTFOLIO PERFORMANCE")
    print(
        performance[
            [
                "Annualized Volatility",
                "Sharpe (rf=0)",
                "Maximum Drawdown",
                "Average Exposure",
            ]
        ].round(6).to_string()
    )

    print(f"\nSaved evaluation tables to {sample_dir}")


def main():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))

    daily = build.daily_reconstructed["WML"]
    monthly = build.monthly_reconstructed["WML"]

    output_dir = root / "outputs" / "garch" / "robustness"
    cache_dir = output_dir / "forecasts"
    cache_dir.mkdir(parents=True, exist_ok=True)

    first_month = pd.Period("1931-05", freq="M")
    last_month = pd.Period("2025-12", freq="M")

    # Forecasts are dated one month before their return targets.
    origins = pd.period_range(
        first_month - 1,
        last_month - 1,
        freq="M",
    )
    
    forecasts = {}

    for distribution in DISTRIBUTIONS:
        for window in WINDOWS:
            name = model_name(distribution, window)
            path = cache_dir / f"{name}.parquet"

            forecasts[name] = calculate_forecasts(
                daily,
                origins,
                distribution,
                window,
                path,
            )

    coverage = pd.DataFrame({
        name: {
            "Total Forecasts": len(series),
            "Missing Forecasts": int(series.isna().sum()),
            "First Origin": str(series.index.min()),
            "Last Origin": str(series.index.max()),
        }
        for name, series in forecasts.items()
    }).T

    coverage.to_csv(output_dir / "forecast_coverage.csv")

    print("\nFORECAST COVERAGE")
    print(coverage.to_string())

    if coverage["Missing Forecasts"].astype(int).sum() > 0:
        raise RuntimeError(
            "One or more models have missing forecasts. "
            "Review forecast_coverage.csv before evaluation."
        )

    for sample, (start, end) in SAMPLES.items():
        months = pd.period_range(start, end, freq="M")

        evaluate_sample(
            sample,
            months,
            daily,
            monthly,
            origins,
            forecasts,
            output_dir,
        )


if __name__ == "__main__":
    main()
