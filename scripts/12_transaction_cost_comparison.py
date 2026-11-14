
"""Transaction-cost and turnover comparison for momentum strategies.

Strategies:
    1. Unmanaged momentum
    2. Historical volatility targeting
    3. EWMA volatility targeting
    4. GARCH volatility targeting

Samples:
    Historical: 1929-08 to 2011-12
    Extension:  2012-01 to 2025-12

Transaction-cost scenarios:
    0, 5, 10, 20, and 50 basis points per dollar traded.

Uses reconstructed stock returns and the existing stock-account simulator.
Original replication, EWMA, and GARCH outputs are not modified.
"""

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.volatility import (
    historical_volatility,
    ewma_volatility,
)
from momentum_risk_project.strategies import (
    volatility_managed_momentum,
)
from momentum_risk_project.stock_backtest import (
    simulate_stock_account,
)
from momentum_risk_project.metrics import performance_metrics


# ============================================================
# CONFIGURATION
# ============================================================

PERIODS = {
    "historical": ("1929-08", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}

STRATEGIES = [
    "unmanaged",
    "historical",
    "ewma",
    "garch",
]

COST_SCENARIOS_BPS = [0, 5, 10, 20, 50]

TARGET_VOLATILITY = 0.12

FINANCING_COST_BPS = 0.0

RECONCILIATION_TOLERANCE = 1e-8


# ============================================================
# VOLATILITY AND STRATEGY WEIGHTS
# ============================================================

def to_monthly(daily_volatility):
    """Select the final daily volatility estimate each month."""

    return daily_volatility.groupby(
        daily_volatility.index.to_period("M")
    ).last()


def build_weights(
    monthly_returns,
    historical_vol,
    ewma_vol,
    garch_vol,
    months,
):
    """Construct applied weights with the existing one-month lag."""

    forecasts = {
        "historical": historical_vol,
        "ewma": ewma_vol,
        "garch": garch_vol,
    }

    weights = pd.DataFrame(index=months)

    weights["unmanaged"] = 1.0

    for name, forecast in forecasts.items():

        strategy = volatility_managed_momentum(
            monthly_returns,
            forecast,
            target_volatility=TARGET_VOLATILITY,
        )

        weights[name] = strategy["weight"].reindex(months)

    weights = weights[STRATEGIES]

    if not np.isfinite(weights.to_numpy()).all():
        raise ValueError(
            "Strategy weights contain missing or infinite values."
        )

    if (weights < 0).any().any():
        raise ValueError(
            "Negative factor exposure encountered."
        )

    return weights


# ============================================================
# STOCK HOLDINGS
# ============================================================

def load_holdings(root):
    """Load only the columns needed for stock-account simulation."""

    columns = [
        "month",
        "permno",
        "momentum_decile",
        "leg_weight",
        "return_reconstructed",
        "reconstructed_imputed",
        "mthretx",
        "delistingdt",
    ]

    path = (
        root
        / "data"
        / "processed"
        / "wml_current"
        / "holdings.parquet"
    )

    holdings = pd.read_parquet(
        path,
        columns=columns,
    )

    holdings["month"] = pd.PeriodIndex(
        holdings["month"],
        freq="M",
    )

    holdings = holdings.loc[
        holdings["momentum_decile"].isin([1, 10])
    ].copy()

    # The existing simulator uses this flag to apply the
    # documented reconstructed-return drift convention.
    #
    # This is a sensitivity assumption for imputed observations,
    # not a claim that their missing prices were observed.

    holdings["scenario_imputed"] = (
        holdings["reconstructed_imputed"]
        .fillna(False)
        .astype(bool)
    )

    return holdings


# ============================================================
# PERFORMANCE STATISTICS
# ============================================================

def calculate_performance(returns):
    """Compute explicit annualized statistics and repository metrics.

    Sharpe is calculated directly to avoid dependence on
    the naming conventions used by performance_metrics().
    """

    returns = pd.Series(returns, dtype=float)

    if returns.empty:
        raise ValueError("Empty return series.")

    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Nonfinite returns encountered.")

    annualized_mean = returns.mean() * 12.0

    annualized_volatility = returns.std(ddof=1) * np.sqrt(12.0)

    if annualized_volatility > 0:
        sharpe_ratio = (
            annualized_mean / annualized_volatility
        )
    else:
        sharpe_ratio = np.nan

    result = {
        "annualized_mean_return": annualized_mean,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
    }

    # Preserve the project's existing performance metrics,
    # without relying on their column names for Sharpe.

    original_metrics = performance_metrics(returns)

    if hasattr(original_metrics, "to_dict"):
        original_metrics = original_metrics.to_dict()
    else:
        original_metrics = dict(original_metrics)

    for key, value in original_metrics.items():
        result[f"repository_{key}"] = value

    return result


def summarize_account(
    ledger,
    strategy,
    cost_bps,
):
    """Summarize a complete stock-level funded-account simulation."""

    if not ledger["state"].eq("ok").all():

        failures = ledger.loc[
            ledger["state"] != "ok"
        ]

        raise ValueError(
            f"{strategy}, {cost_bps} bps: "
            f"account not evaluable. "
            f"First failure: {failures.index[0]}"
        )

    net_returns = ledger["net_return"].astype(float)

    metrics = calculate_performance(net_returns)

    result = {
        "strategy": strategy,
        "transaction_cost_bps": cost_bps,
        "observations": len(ledger),
        **metrics,
        "average_monthly_turnover": (
            ledger["turnover"].mean()
        ),
        "median_monthly_turnover": (
            ledger["turnover"].median()
        ),
        "average_monthly_transaction_cost": (
            ledger["transaction_cost"].mean()
        ),
        "average_exposure": (
            ledger["factor_weight"].mean()
        ),
        "average_monthly_gross_factor_return": (
            ledger["gross_factor_return"].mean()
        ),
        "average_monthly_net_return": (
            ledger["net_return"].mean()
        ),
    }

    return result


# ============================================================
# ZERO-COST RECONCILIATION
# ============================================================

def validate_reconciliation(
    ledger,
    monthly_returns,
    weights,
    months,
    label,
    strategy,
):
    """Check stock-level gross returns against reconstructed WML."""

    expected = (
        monthly_returns.reindex(months)
        * weights.reindex(months)
    )

    actual = ledger["gross_factor_return"].reindex(months)

    if expected.isna().any() or actual.isna().any():
        raise ValueError(
            f"{label}/{strategy}: missing reconciliation data."
        )

    errors = (actual - expected).abs()

    max_error = float(errors.max())

    print(
        "  Zero-cost maximum reconciliation error: "
        f"{max_error * 10000:.8f} bps"
    )

    if (
        not np.isfinite(max_error)
        or max_error > RECONCILIATION_TOLERANCE
    ):
        raise ValueError(
            f"{label}/{strategy}: "
            "zero-cost gross reconciliation failed."
        )

    return max_error


# ============================================================
# TRANSACTION-COST EXPERIMENT
# ============================================================

def evaluate_period(
    label,
    start,
    end,
    monthly_returns,
    historical_vol,
    ewma_vol,
    holdings,
    root,
):
    """Run all strategies and transaction-cost scenarios."""

    months = pd.period_range(
        start,
        end,
        freq="M",
    )

    garch_path = (
        root
        / "outputs"
        / "garch"
        / f"{label}_garch_monthly_volatility.parquet"
    )

    garch_vol = pd.read_parquet(
        garch_path
    )["garch_monthly_volatility"]

    weights = build_weights(
        monthly_returns,
        historical_vol,
        ewma_vol,
        garch_vol,
        months,
    )

    sample = holdings.loc[
        holdings["month"].isin(months)
    ].copy()

    print(f"\n{'=' * 75}")
    print(f"TRANSACTION-COST EXPERIMENT: {label.upper()}")
    print(f"Period: {start} to {end}")
    print(f"Months: {len(months)}")
    print(f"Stock-month observations: {len(sample)}")

    results = []
    ledgers = []
    reconciliation_results = []

    for strategy in STRATEGIES:

        strategy_weights = weights[strategy]

        for cost_bps in COST_SCENARIOS_BPS:

            print(
                f"Running {strategy:12s} | "
                f"cost = {cost_bps:2d} bps",
                flush=True,
            )

            ledger, _ = simulate_stock_account(
                sample,
                strategy_weights,
                return_column="return_reconstructed",
                transaction_cost_bps=float(cost_bps),
                financing_cost_bps=FINANCING_COST_BPS,
            )

            summary = summarize_account(
                ledger,
                strategy,
                cost_bps,
            )

            results.append(summary)

            ledger_copy = ledger.copy()

            ledger_copy["strategy"] = strategy
            ledger_copy["transaction_cost_bps"] = cost_bps
            ledger_copy["month"] = (
                ledger_copy.index.astype(str)
            )

            ledgers.append(
                ledger_copy.reset_index(drop=True)
            )

            if cost_bps == 0:

                max_error = validate_reconciliation(
                    ledger=ledger,
                    monthly_returns=monthly_returns,
                    weights=strategy_weights,
                    months=months,
                    label=label,
                    strategy=strategy,
                )

                reconciliation_results.append({
                    "strategy": strategy,
                    "maximum_absolute_error_bps": (
                        max_error * 10000
                    ),
                    "observations": len(ledger),
                })

    # --------------------------------------------------------
    # COMBINE RESULTS
    # --------------------------------------------------------

    results = pd.DataFrame(results)

    ledgers = pd.concat(
        ledgers,
        ignore_index=True,
    )

    reconciliation = pd.DataFrame(
        reconciliation_results
    )

    # --------------------------------------------------------
    # SHARPE DETERIORATION
    # --------------------------------------------------------

    # Use the explicitly calculated Sharpe column.
    # This avoids the previous StopIteration error.

    baseline_sharpe = (
        results.loc[
            results["transaction_cost_bps"] == 0,
            ["strategy", "sharpe_ratio"],
        ]
        .set_index("strategy")["sharpe_ratio"]
    )

    results["sharpe_change_vs_zero_cost"] = (
        results["sharpe_ratio"]
        - results["strategy"].map(baseline_sharpe)
    )

    # --------------------------------------------------------
    # ANNUALIZED TRADING-COST MEASURE
    # --------------------------------------------------------

    results["annualized_average_transaction_cost"] = (
        results["average_monthly_transaction_cost"] * 12.0
    )

    # This is an annualized average monthly cost fraction,
    # not a compounded annual return drag.

    # --------------------------------------------------------
    # OUTPUT DIRECTORY
    # --------------------------------------------------------

    output_dir = (
        root
        / "outputs"
        / "transaction_costs"
        / label
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # SAVE FILES
    # --------------------------------------------------------

    results.to_csv(
        output_dir / "performance_by_cost.csv",
        index=False,
        float_format="%.10g",
    )

    ledgers.to_csv(
        output_dir / "monthly_account_ledgers.csv",
        index=False,
        float_format="%.10g",
    )

    weights.to_csv(
        output_dir / "strategy_weights.csv",
        index_label="month",
        float_format="%.10g",
    )

    reconciliation.to_csv(
        output_dir / "zero_cost_reconciliation.csv",
        index=False,
        float_format="%.10g",
    )

    # --------------------------------------------------------
    # PRINT COMPACT PERFORMANCE SUMMARY
    # --------------------------------------------------------

    summary_columns = [
        "strategy",
        "transaction_cost_bps",
        "annualized_mean_return",
        "annualized_volatility",
        "sharpe_ratio",
        "average_monthly_turnover",
        "average_monthly_transaction_cost",
        "sharpe_change_vs_zero_cost",
    ]

    print("\nPERFORMANCE SUMMARY")
    print(
        results[summary_columns]
        .round(6)
        .to_string(index=False)
    )

    print("\nZERO-COST RECONCILIATION")
    print(
        reconciliation
        .round(8)
        .to_string(index=False)
    )

    print(f"\nSaved results to: {output_dir}")

    return results


# ============================================================
# MAIN
# ============================================================

def main():
    root = project_root()

    config = load_config(
        root=root,
    )

    build = load_build(
        configured_path(
            config,
            "build",
            root,
        )
    )

    daily_returns = (
        build.daily_reconstructed["WML"]
    )

    monthly_returns = (
        build.monthly_reconstructed["WML"]
    )

    # Historical volatility: 126-day rolling estimator.

    historical_vol = to_monthly(
        historical_volatility(
            daily_returns,
            window=126,
            trading_days_per_month=21,
        )
    )

    # EWMA volatility: RiskMetrics decay of 0.94.

    ewma_vol = to_monthly(
        ewma_volatility(
            daily_returns,
            decay=0.94,
            initialization_window=126,
            trading_days_per_month=21,
        )
    )

    # Read existing stock-level holdings.

    holdings = load_holdings(root)

    all_results = []

    for label, (start, end) in PERIODS.items():

        period_results = evaluate_period(
            label=label,
            start=start,
            end=end,
            monthly_returns=monthly_returns,
            historical_vol=historical_vol,
            ewma_vol=ewma_vol,
            holdings=holdings,
            root=root,
        )

        period_results["sample"] = label

        all_results.append(period_results)

    # --------------------------------------------------------
    # SAVE COMBINED SUMMARY
    # --------------------------------------------------------

    combined = pd.concat(
        all_results,
        ignore_index=True,
    )

    combined_dir = (
        root
        / "outputs"
        / "transaction_costs"
    )

    combined_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        combined_dir / "combined_performance.csv",
        index=False,
        float_format="%.10g",
    )

    print(f"\n{'=' * 75}")
    print("TRANSACTION-COST EXPERIMENT COMPLETE")
    print(f"{'=' * 75}")

    print(
        f"Total scenarios evaluated: {len(combined)}"
    )

    print(
        "All zero-cost gross-return reconciliations passed."
    )

    print(
        f"Combined results saved to: {combined_dir}"
    )


if __name__ == "__main__":
    main()
