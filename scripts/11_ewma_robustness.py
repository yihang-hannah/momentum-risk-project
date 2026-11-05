
"""Evaluate EWMA momentum strategies across alternative decay factors."""

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.volatility import ewma_volatility
from momentum_risk_project.strategies import volatility_managed_momentum
from momentum_risk_project.metrics import performance_metrics
from momentum_risk_project.garch_evaluation import (
    forecast_accuracy,
    forecast_loss_test,
)


DECAYS = (0.90, 0.94, 0.97, 0.99)

PERIODS = {
    "historical": ("1929-08", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}


def main():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))

    daily = build.daily_reconstructed["WML"]
    monthly = build.monthly_reconstructed["WML"]

    forecasts = {}

    for decay in DECAYS:
        name = f"ewma_{decay:.2f}"

        daily_forecast = ewma_volatility(
            daily,
            decay=decay,
            initialization_window=126,
            trading_days_per_month=21,
        )

        forecasts[name] = daily_forecast.groupby(
            daily_forecast.index.to_period("M")
        ).last()

    strategies = {
        name: volatility_managed_momentum(
            monthly,
            forecast,
            target_volatility=0.12,
        )
        for name, forecast in forecasts.items()
    }

    realized = (
        daily.pow(2)
        .groupby(daily.index.to_period("M"))
        .sum()
        .pow(0.5)
    )

    output_root = root / "outputs" / "ewma" / "robustness"

    for label, (start, end) in PERIODS.items():
        months = pd.period_range(start, end, freq="M")

        returns = pd.DataFrame({
            name: strategy["managed"].reindex(months)
            for name, strategy in strategies.items()
        })

        weights = pd.DataFrame({
            name: strategy["weight"].reindex(months)
            for name, strategy in strategies.items()
        })

        next_forecasts = pd.DataFrame({
            name: forecast.rename(
                index=lambda period: period + 1
            ).reindex(months)
            for name, forecast in forecasts.items()
        })

        realized_period = realized.reindex(months)

        if (
            returns.isna().any().any()
            or weights.isna().any().any()
            or next_forecasts.isna().any().any()
            or realized_period.isna().any()
        ):
            raise ValueError(f"Incomplete data in {label} sample")

        performance = pd.DataFrame({
            name: performance_metrics(returns[name])
            for name in returns.columns
        }).T

        performance["Average Exposure"] = weights.mean()

        accuracy = forecast_accuracy(
            realized_period,
            next_forecasts,
        )

        tests = {}

        for name in next_forecasts.columns:
            if name == "ewma_0.94":
                continue

            tests[f"{name}_minus_ewma_0.94"] = forecast_loss_test(
                realized_period,
                next_forecasts[name],
                next_forecasts["ewma_0.94"],
                hac_lags=3,
            )

        significance = pd.DataFrame(tests).T

        output_dir = output_root / label
        output_dir.mkdir(parents=True, exist_ok=True)

        performance.to_csv(
            output_dir / "portfolio_performance.csv",
            index_label="model",
            float_format="%.10g",
        )

        accuracy.to_csv(
            output_dir / "forecast_accuracy.csv",
            index_label="model",
            float_format="%.10g",
        )

        significance.to_csv(
            output_dir / "forecast_loss_tests.csv",
            index_label="comparison",
            float_format="%.10g",
        )

        print(f"\n{'=' * 70}")
        print(f"EWMA ROBUSTNESS: {label.upper()}")
        print(f"Period: {start} to {end}")
        print(f"Observations: {len(months)}")

        print("\nPORTFOLIO PERFORMANCE")
        print(performance.round(6).to_string())

        print("\nFORECAST ACCURACY")
        print(accuracy.round(6).to_string())

        print("\nHAC FORECAST LOSS TESTS")
        print(significance.round(6).to_string())

        print(f"\nSaved results to: {output_dir}")


if __name__ == "__main__":
    main()
