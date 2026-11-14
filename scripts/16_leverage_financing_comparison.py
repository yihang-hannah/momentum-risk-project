
"""Extension 2: Leverage caps and financing costs.

Compare historical, EWMA and GARCH volatility-managed momentum.

Leverage caps:
    Uncapped, 1.0x, 1.5x, 2.0x

Annualized financing spreads:
    0, 100, 300 basis points

Stock trading costs:
    10 basis points per dollar traded

Samples:
    Historical: 1929-08 through 2011-12
    Extension: 2012-01 through 2025-12

The uncapped, zero-financing scenario is reconciled against
Extension 1's 10-bps transaction-cost results.

All outputs are saved to outputs/leverage_financing/.
"""

from pathlib import Path

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


# ============================================================
# CONFIGURATION
# ============================================================

PERIODS = {
    "historical": ("1929-08", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}

MANAGED_STRATEGIES = [
    "historical",
    "ewma",
    "garch",
]

LEVERAGE_CAPS = {
    "uncapped": None,
    "1.0x": 1.0,
    "1.5x": 1.5,
    "2.0x": 2.0,
}

FINANCING_SPREADS_BPS = [0, 100, 300]

TRANSACTION_COST_BPS = 10.0
TARGET_VOLATILITY = 0.12

BASELINE_TOLERANCE = 1e-7
RECONCILIATION_TOLERANCE = 1e-8


# ============================================================
# DATA PREPARATION
# ============================================================

def to_monthly(daily_volatility):
    """Use the final daily volatility estimate each month."""

    return daily_volatility.groupby(
        daily_volatility.index.to_period("M")
    ).last()


def load_holdings(root):
    """Load the reconstructed stock-level momentum portfolio."""

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

    holdings["scenario_imputed"] = (
        holdings["reconstructed_imputed"]
        .fillna(False)
        .astype(bool)
    )

    return holdings


def build_uncapped_weights(
    monthly_returns,
    historical_vol,
    ewma_vol,
    garch_vol,
    months,
):
    """Construct applied weights with the existing lag convention."""

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

    if not np.isfinite(weights.to_numpy()).all():
        raise ValueError(
            "Missing or nonfinite strategy weights."
        )

    if (weights < 0).any().any():
        raise ValueError(
            "Negative strategy exposure encountered."
        )

    return weights


# ============================================================
# PERFORMANCE METRICS
# ============================================================

def calculate_metrics(returns):
    """Compute performance using monthly arithmetic returns."""

    returns = pd.Series(returns, dtype=float)

    if returns.empty:
        raise ValueError("Empty return series.")

    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Nonfinite monthly returns.")

    annualized_return = 12.0 * returns.mean()

    annualized_volatility = (
        np.sqrt(12.0) * returns.std(ddof=1)
    )

    if annualized_volatility > 0:
        sharpe = annualized_return / annualized_volatility
    else:
        sharpe = np.nan

    wealth = (1.0 + returns).cumprod()

    running_peak = np.maximum(
        1.0,
        wealth.cummax()
    )

    drawdown = wealth / running_peak - 1.0

    maximum_drawdown = float(drawdown.min())

    terminal_wealth = float(wealth.iloc[-1])

    if terminal_wealth > 0:
        cagr = terminal_wealth ** (
            12.0 / len(returns)
        ) - 1.0
    else:
        cagr = np.nan

    return {
        "annualized_mean_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "cagr": cagr,
        "maximum_drawdown": maximum_drawdown,
        "terminal_wealth": terminal_wealth,
        "worst_month": float(returns.min()),
        "best_month": float(returns.max()),
    }


# ============================================================
# ACCOUNT SUMMARY
# ============================================================

def summarize_account(
    ledger,
    strategy,
    cap_label,
    financing_bps,
    weights,
    uncapped_weights,
):
    """Summarize performance, trading and leverage usage."""

    if not ledger["state"].eq("ok").all():

        failures = ledger.loc[
            ledger["state"] != "ok"
        ]

        raise ValueError(
            f"Account failed: {strategy}, "
            f"cap={cap_label}, financing={financing_bps}. "
            f"First failure: {failures.index[0]}"
        )

    metrics = calculate_metrics(
        ledger["net_return"]
    )

    weights = weights.reindex(ledger.index)
    uncapped_weights = uncapped_weights.reindex(
        ledger.index
    )

    cap_binding = (
        weights < uncapped_weights - 1e-12
    )

    leveraged = weights > 1.0 + 1e-12

    summary = {
        "strategy": strategy,
        "leverage_cap": cap_label,
        "financing_spread_bps": financing_bps,
        "transaction_cost_bps": TRANSACTION_COST_BPS,
        "observations": len(ledger),
        **metrics,
        "average_monthly_turnover": float(
            ledger["turnover"].mean()
        ),
        "average_monthly_transaction_cost": float(
            ledger["transaction_cost"].mean()
        ),
        "average_monthly_financing_cost": float(
            ledger["financing_cost"].mean()
        ),
        "average_exposure": float(weights.mean()),
        "median_exposure": float(weights.median()),
        "maximum_exposure": float(weights.max()),
        "fraction_months_leveraged": float(
            leveraged.mean()
        ),
        "fraction_months_cap_binding": float(
            cap_binding.mean()
        ),
        "average_excess_exposure": float(
            np.maximum(weights - 1.0, 0.0).mean()
        ),
    }

    return summary


# ============================================================
# EXTENSION 1 BASELINE RECONCILIATION
# ============================================================

def validate_extension1_baseline(
    root,
    period,
    strategy,
    summary,
    ledger,
):
    """Verify uncapped/zero-financing results match Extension 1."""

    path = (
        root
        / "outputs"
        / "transaction_costs"
        / period
        / "performance_by_cost.csv"
    )

    baseline = pd.read_csv(path)

    selected = baseline.loc[
        (baseline["strategy"] == strategy)
        & (
            baseline["transaction_cost_bps"]
            == TRANSACTION_COST_BPS
        )
    ]

    if len(selected) != 1:
        raise ValueError(
            f"Missing Extension 1 baseline: "
            f"{period}/{strategy}"
        )

    baseline_row = selected.iloc[0]

    columns = [
        "annualized_mean_return",
        "annualized_volatility",
        "sharpe_ratio",
        "average_monthly_turnover",
        "average_monthly_transaction_cost",
    ]

    for column in columns:

        expected = float(baseline_row[column])
        actual = float(summary[column])

        error = abs(actual - expected)

        if error > BASELINE_TOLERANCE:
            raise ValueError(
                f"Baseline mismatch: {period}/{strategy}/"
                f"{column}: {error:.12e}"
            )

    # Check monthly net returns against the saved ledger.

    old_ledger_path = (
        root
        / "outputs"
        / "transaction_costs"
        / period
        / "monthly_account_ledgers.csv"
    )

    old_ledger = pd.read_csv(
        old_ledger_path,
        usecols=[
            "month",
            "strategy",
            "transaction_cost_bps",
            "net_return",
        ],
    )

    old_ledger = old_ledger.loc[
        (old_ledger["strategy"] == strategy)
        & (
            old_ledger["transaction_cost_bps"]
            == TRANSACTION_COST_BPS
        )
    ].copy()

    old_ledger = old_ledger.set_index("month")

    actual_returns = ledger["net_return"].copy()
    actual_returns.index = actual_returns.index.astype(str)

    expected_returns = old_ledger[
        "net_return"
    ].reindex(actual_returns.index)

    if expected_returns.isna().any():
        raise ValueError(
            f"Missing monthly baseline returns: "
            f"{period}/{strategy}"
        )

    error = (
        actual_returns - expected_returns
    ).abs().max()

    if error > BASELINE_TOLERANCE:
        raise ValueError(
            f"Monthly baseline mismatch: "
            f"{period}/{strategy}: {error:.12e}"
        )

    print(
        f"  Extension 1 baseline reconciliation: PASS "
        f"(max monthly error {error:.3e})"
    )


# ============================================================
# SIMULATION
# ============================================================

def run_account(
    sample,
    weights,
    financing_bps,
):
    """Execute the existing funded stock-account simulator."""

    return simulate_stock_account(
        sample,
        weights,
        return_column="return_reconstructed",
        transaction_cost_bps=TRANSACTION_COST_BPS,
        financing_cost_bps=float(financing_bps),
    )


def evaluate_period(
    root,
    period,
    start,
    end,
    monthly_returns,
    historical_vol,
    ewma_vol,
    holdings,
):
    """Run leverage and financing scenarios for one period."""

    months = pd.period_range(
        start,
        end,
        freq="M",
    )

    garch_path = (
        root
        / "outputs"
        / "garch"
        / f"{period}_garch_monthly_volatility.parquet"
    )

    garch_vol = pd.read_parquet(
        garch_path
    )["garch_monthly_volatility"]

    uncapped = build_uncapped_weights(
        monthly_returns,
        historical_vol,
        ewma_vol,
        garch_vol,
        months,
    )

    sample = holdings.loc[
        holdings["month"].isin(months)
    ].copy()

    output_dir = (
        root
        / "outputs"
        / "leverage_financing"
        / period
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("\n" + "=" * 75)
    print(f"LEVERAGE AND FINANCING: {period.upper()}")
    print(f"Period: {start} to {end}")
    print(f"Months: {len(months)}")
    print(f"Stock-month observations: {len(sample)}")
    print("=" * 75)

    summaries = []
    ledgers = []
    weight_records = []

    # --------------------------------------------------------
    # UNMANAGED BENCHMARK
    # --------------------------------------------------------

    print("\nRunning unmanaged benchmark")

    benchmark_weights = uncapped["unmanaged"]

    benchmark_ledger, _ = run_account(
        sample,
        benchmark_weights,
        financing_bps=0,
    )

    benchmark_summary = summarize_account(
        benchmark_ledger,
        strategy="unmanaged",
        cap_label="unmanaged",
        financing_bps=0,
        weights=benchmark_weights,
        uncapped_weights=benchmark_weights,
    )

    validate_extension1_baseline(
        root,
        period,
        "unmanaged",
        benchmark_summary,
        benchmark_ledger,
    )

    summaries.append(benchmark_summary)

    benchmark_copy = benchmark_ledger.copy()
    benchmark_copy["strategy"] = "unmanaged"
    benchmark_copy["leverage_cap"] = "unmanaged"
    benchmark_copy["financing_spread_bps"] = 0
    benchmark_copy["month"] = (
        benchmark_copy.index.astype(str)
    )

    ledgers.append(
        benchmark_copy.reset_index(drop=True)
    )

    # --------------------------------------------------------
    # VOLATILITY-MANAGED STRATEGIES
    # --------------------------------------------------------

    for strategy in MANAGED_STRATEGIES:

        original_weights = uncapped[strategy]

        for cap_label, cap_value in LEVERAGE_CAPS.items():

            if cap_value is None:
                applied_weights = original_weights.copy()
            else:
                applied_weights = original_weights.clip(
                    upper=cap_value
                )

            for financing_bps in FINANCING_SPREADS_BPS:

                print(
                    f"\nRunning {strategy:12s} | "
                    f"cap={cap_label:8s} | "
                    f"financing={financing_bps:3d} bps",
                    flush=True,
                )

                ledger, _ = run_account(
                    sample,
                    applied_weights,
                    financing_bps,
                )

                summary = summarize_account(
                    ledger,
                    strategy=strategy,
                    cap_label=cap_label,
                    financing_bps=financing_bps,
                    weights=applied_weights,
                    uncapped_weights=original_weights,
                )

                summaries.append(summary)

                ledger_copy = ledger.copy()

                ledger_copy["strategy"] = strategy
                ledger_copy["leverage_cap"] = cap_label
                ledger_copy["financing_spread_bps"] = (
                    financing_bps
                )
                ledger_copy["month"] = (
                    ledger_copy.index.astype(str)
                )

                ledgers.append(
                    ledger_copy.reset_index(drop=True)
                )

                # Validate the identical scenario against
                # Extension 1's existing 10-bps results.

                if (
                    cap_value is None
                    and financing_bps == 0
                ):
                    validate_extension1_baseline(
                        root,
                        period,
                        strategy,
                        summary,
                        ledger,
                    )

                # At zero financing, gross stock-level
                # returns must match reconstructed WML
                # multiplied by the capped applied weights.

                if financing_bps == 0:

                    expected_gross = (
                        monthly_returns.reindex(months)
                        * applied_weights
                    )

                    actual_gross = (
                        ledger["gross_factor_return"]
                    )

                    error = (
                        expected_gross - actual_gross
                    ).abs().max()

                    if (
                        not np.isfinite(error)
                        or error > RECONCILIATION_TOLERANCE
                    ):
                        raise ValueError(
                            f"Gross reconciliation failed: "
                            f"{period}/{strategy}/{cap_label}"
                        )

                    print(
                        "  Gross return reconciliation: PASS "
                        f"({error * 10000:.8f} bps)"
                    )

            # Save the applied weights once per cap,
            # rather than duplicating them for financing rates.

            weight_records.append(
                pd.DataFrame({
                    "month": months.astype(str),
                    "strategy": strategy,
                    "leverage_cap": cap_label,
                    "uncapped_weight": (
                        original_weights.to_numpy()
                    ),
                    "applied_weight": (
                        applied_weights.to_numpy()
                    ),
                })
            )

    # --------------------------------------------------------
    # SAVE RESULTS
    # --------------------------------------------------------

    summary_df = pd.DataFrame(summaries)

    ledger_df = pd.concat(
        ledgers,
        ignore_index=True,
    )

    weight_df = pd.concat(
        weight_records,
        ignore_index=True,
    )

    summary_df.to_csv(
        output_dir / "performance_by_scenario.csv",
        index=False,
        float_format="%.10g",
    )

    ledger_df.to_csv(
        output_dir / "monthly_account_ledgers.csv",
        index=False,
        float_format="%.10g",
    )

    weight_df.to_csv(
        output_dir / "leverage_weights.csv",
        index=False,
        float_format="%.10g",
    )

    # --------------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------------

    columns = [
        "strategy",
        "leverage_cap",
        "financing_spread_bps",
        "annualized_mean_return",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "average_exposure",
        "fraction_months_cap_binding",
        "average_monthly_turnover",
    ]

    print("\n" + "=" * 75)
    print(f"PERFORMANCE SUMMARY: {period.upper()}")
    print("=" * 75)

    print(
        summary_df[columns]
        .round(5)
        .to_string(index=False)
    )

    print(f"\nSaved results to: {output_dir}")

    return summary_df


# ============================================================
# MAIN
# ============================================================

def main():

    root = project_root()

    config = load_config(root=root)

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

    historical_vol = to_monthly(
        historical_volatility(
            daily_returns,
            window=126,
            trading_days_per_month=21,
        )
    )

    ewma_vol = to_monthly(
        ewma_volatility(
            daily_returns,
            decay=0.94,
            initialization_window=126,
            trading_days_per_month=21,
        )
    )

    holdings = load_holdings(root)

    all_results = []

    for period, (start, end) in PERIODS.items():

        result = evaluate_period(
            root=root,
            period=period,
            start=start,
            end=end,
            monthly_returns=monthly_returns,
            historical_vol=historical_vol,
            ewma_vol=ewma_vol,
            holdings=holdings,
        )

        result["sample"] = period

        all_results.append(result)

    combined = pd.concat(
        all_results,
        ignore_index=True,
    )

    output_dir = (
        root
        / "outputs"
        / "leverage_financing"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        output_dir / "combined_performance.csv",
        index=False,
        float_format="%.10g",
    )

    print("\n" + "=" * 75)
    print("LEVERAGE AND FINANCING EXPERIMENT COMPLETE")
    print("=" * 75)

    print(
        f"Total scenarios evaluated: {len(combined)}"
    )

    print(
        "Extension 1 baseline reconciliations: PASS"
    )

    print(
        "Zero-financing gross return reconciliations: PASS"
    )

    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
