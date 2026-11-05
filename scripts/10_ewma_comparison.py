
"""Compare historical, EWMA, and GARCH momentum volatility management."""

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.volatility import (
    historical_volatility,
    ewma_volatility,
)
from momentum_risk_project.strategies import volatility_managed_momentum
from momentum_risk_project.metrics import performance_metrics
from momentum_risk_project.garch_evaluation import (
    forecast_accuracy,
    forecast_loss_test,
)


PERIODS = {
    "historical": ("1929-08", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}


def to_monthly(daily_volatility):
    """Select the final available daily estimate in each month."""
    return daily_volatility.groupby(
        daily_volatility.index.to_period("M")
    ).last()


def evaluate_period(
    label,
    start,
    end,
    monthly_returns,
    daily_returns,
    forecasts,
    output_root,
):
    months = pd.period_range(start, end, freq="M")

    strategies = {
        name: volatility_managed_momentum(
            monthly_returns,
            forecast,
            target_volatility=0.12,
        )
        for name, forecast in forecasts.items()
    }

    returns = pd.DataFrame({
        "unmanaged": monthly_returns.reindex(months),
        **{
            name: strategy["managed"].reindex(months)
            for name, strategy in strategies.items()
        },
    })

    weights = pd.DataFrame({
        name: strategy["weight"].reindex(months)
        for name, strategy in strategies.items()
    })

    # Align forecast made at month-end t with realized volatility in t+1.
    next_month_forecasts = pd.DataFrame({
        name: forecast.rename(
            index=lambda period: period + 1
        ).reindex(months)
        for name, forecast in forecasts.items()
    })

    realized = (
        daily_returns.pow(2)
        .groupby(daily_returns.index.to_period("M"))
        .sum()
        .pow(0.5)
        .reindex(months)
    )

    # Enforce identical observations for all strategies and forecasts.
    complete = (
        returns.notna().all(axis=1)
        & weights.notna().all(axis=1)
        & next_month_forecasts.notna().all(axis=1)
        & realized.notna()
    )

    if not complete.all():
        missing = months[~complete.to_numpy()]
        raise ValueError(
            f"{label}: incomplete observations: {list(missing)}"
        )

    performance = pd.DataFrame({
        name: performance_metrics(returns[name])
        for name in returns.columns
    }).T

    performance["Average Exposure"] = pd.Series({
        "unmanaged": 1.0,
        **{
            name: weights[name].mean()
            for name in weights.columns
        },
    })

    accuracy = forecast_accuracy(
        realized,
        next_month_forecasts,
    )

    tests = {}

    for first, second in [
        ("historical", "ewma"),
        ("garch", "ewma"),
    ]:
        tests[f"{first}_minus_{second}"] = forecast_loss_test(
            realized,
            next_month_forecasts[first],
            next_month_forecasts[second],
            hac_lags=3,
        )

    significance = pd.DataFrame(tests).T

    output_dir = output_root / label
    output_dir.mkdir(parents=True, exist_ok=True)

    performance.to_csv(
        output_dir / "portfolio_performance.csv",
        index_label="strategy",
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
    print(f"EWMA COMPARISON: {label.upper()}")
    print(f"Period: {start} to {end}")
    print(f"Observations: {len(months)}")

    print("\nPORTFOLIO PERFORMANCE")
    print(performance.round(6).to_string())

    print("\nVOLATILITY FORECAST ACCURACY")
    print(accuracy.round(6).to_string())

    print("\nHAC FORECAST LOSS TESTS")
    print(significance.round(6).to_string())

    print(f"\nSaved results to: {output_dir}")


def main():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))

    daily = build.daily_reconstructed["WML"]
    monthly = build.monthly_reconstructed["WML"]

    historical = to_monthly(
        historical_volatility(
            daily,
            window=126,
            trading_days_per_month=21,
        )
    )

    ewma = to_monthly(
        ewma_volatility(
            daily,
            decay=0.94,
            initialization_window=126,
            trading_days_per_month=21,
        )
    )

    garch_dir = root / "outputs" / "garch"
    output_root = root / "outputs" / "ewma"

    for label, (start, end) in PERIODS.items():
        garch_path = (
            garch_dir / f"{label}_garch_monthly_volatility.parquet"
        )

        garch = pd.read_parquet(garch_path)[
            "garch_monthly_volatility"
        ]

        forecasts = {
            "historical": historical,
            "ewma": ewma,
            "garch": garch,
        }

        evaluate_period(
            label=label,
            start=start,
            end=end,
            monthly_returns=monthly,
            daily_returns=daily,
            forecasts=forecasts,
            output_root=output_root,
        )


if __name__ == "__main__":
    main()
