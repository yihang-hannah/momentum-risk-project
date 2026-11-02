"""Reproduce the GARCH momentum extension from saved CRSP data."""

import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.volatility import historical_volatility
from momentum_risk_project.strategies import volatility_managed_momentum
from momentum_risk_project.metrics import performance_metrics
from momentum_risk_project.garch_evaluation import (
    forecast_accuracy,
    forecast_loss_test,
)


def main():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))

    daily = build.daily_reconstructed["WML"]
    monthly = build.monthly_reconstructed["WML"]

    historical_daily = historical_volatility(
        daily, window=126, trading_days_per_month=21
    )
    historical = historical_daily.groupby(
        historical_daily.index.to_period("M")
    ).last()

    garch_path = (
        root / "outputs" / "garch"
        / "extension_garch_monthly_volatility.parquet"
    )
    garch = pd.read_parquet(garch_path)["garch_monthly_volatility"]

    historical_strategy = volatility_managed_momentum(
        monthly, historical, target_volatility=0.12
    )
    garch_strategy = volatility_managed_momentum(
        monthly, garch, target_volatility=0.12
    )

    months = pd.period_range("2012-01", "2025-12", freq="M")

    returns = pd.DataFrame({
        "unmanaged": monthly.reindex(months),
        "historical": historical_strategy["managed"].reindex(months),
        "garch": garch_strategy["managed"].reindex(months),
    })

    weights = pd.DataFrame({
        "historical": historical_strategy["weight"].reindex(months),
        "garch": garch_strategy["weight"].reindex(months),
    })

    if returns.isna().any().any() or weights.isna().any().any():
        raise ValueError("Missing strategy returns or portfolio weights")

    performance = pd.DataFrame({
        name: performance_metrics(returns[name])
        for name in returns.columns
    }).T

    performance["Average Exposure"] = pd.Series({
        "unmanaged": 1.0,
        "historical": weights["historical"].mean(),
        "garch": weights["garch"].mean(),
    })

    print("GARCH EXTENSION — PORTFOLIO PERFORMANCE")
    print(performance.round(6).to_string())
    print(f"\nObservations: {len(returns)}")

    # Forecasts are indexed by their month-end estimation date.
    # Shift the index forward for comparison with next-month realized volatility.
    historical_next = historical.copy()
    historical_next.index = historical_next.index + 1

    garch_next = garch.copy()
    garch_next.index = garch_next.index + 1

    realized = (
        daily.pow(2)
        .groupby(daily.index.to_period("M"))
        .sum()
        .pow(0.5)
        .reindex(months)
    )

    forecasts = pd.DataFrame({
        "historical": historical_next.reindex(months),
        "garch": garch_next.reindex(months),
    })

    accuracy = forecast_accuracy(realized, forecasts)
    significance = forecast_loss_test(
        realized,
        forecasts["historical"],
        forecasts["garch"],
        hac_lags=3,
    )

    print("\nVOLATILITY FORECAST ACCURACY")
    print(accuracy.round(6).to_string())

    print("\nHAC FORECAST LOSS TEST")
    print(significance.round(6).to_string())

    # Save reproducible tables for the final paper.
    output_dir = root / "outputs" / "garch"
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
    significance.rename("value").to_csv(
        output_dir / "forecast_loss_test.csv",
        index_label="statistic",
        float_format="%.10g",
    )

    print("\nSaved three CSV tables to:", output_dir)

    # Save reproducible tables for the final paper.
    output_dir = root / "outputs" / "garch"
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
    significance.rename("value").to_csv(
        output_dir / "forecast_loss_test.csv",
        index_label="statistic",
        float_format="%.10g",
    )

    print("\nSaved three CSV tables to:", output_dir)


if __name__ == "__main__":
    main()
