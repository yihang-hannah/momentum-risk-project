
"""Validate stock-level transaction-cost accounting.

Uses the exact accounting conventions in simulate_stock_account().

Checks:
1. All scenarios and monthly observations are present.
2. Trading costs equal cost rate times traded notional.
3. Post-cost NAV satisfies the normalized self-financing equation.
4. Net returns satisfy the funded-account accounting identity.
5. Annualized return drag and turnover are economically sensible.

Reads existing outputs only.
"""

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root


PERIODS = ["historical", "extension"]

STRATEGIES = [
    "unmanaged",
    "historical",
    "ewma",
    "garch",
]

COST_SCENARIOS_BPS = [0, 5, 10, 20, 50]

EXPECTED_MONTHS = {
    "historical": 989,
    "extension": 168,
}

# CSV files were saved to approximately 10 significant digits.
TOLERANCE = 1e-8


def check_error(label, actual, expected):
    """Check a numerical identity, reporting maximum absolute error."""

    actual = np.asarray(actual, dtype=float)
    expected = np.asarray(expected, dtype=float)

    if not np.isfinite(actual).all():
        raise ValueError(f"{label}: nonfinite actual values.")

    if not np.isfinite(expected).all():
        raise ValueError(f"{label}: nonfinite expected values.")

    error = np.abs(actual - expected)
    maximum = float(np.max(error))

    print(f"{label}: {maximum:.12e}")

    if maximum > TOLERANCE:
        raise ValueError(
            f"{label} failed: maximum error = {maximum:.12e}"
        )

    return maximum


def validate_period(root, period):
    """Validate the transaction-cost outputs for one sample."""

    output_dir = (
        root / "outputs" / "transaction_costs" / period
    )

    results = pd.read_csv(
        output_dir / "performance_by_cost.csv"
    )

    ledger = pd.read_csv(
        output_dir / "monthly_account_ledgers.csv"
    )

    print("\n" + "=" * 75)
    print(f"TRANSACTION-COST VALIDATION: {period.upper()}")
    print("=" * 75)

    # --------------------------------------------------------
    # 1. DATA COMPLETENESS
    # --------------------------------------------------------

    print("\n1. DATA COMPLETENESS")

    expected_scenarios = len(STRATEGIES) * len(
        COST_SCENARIOS_BPS
    )

    if len(results) != expected_scenarios:
        raise ValueError(
            f"Expected {expected_scenarios} scenarios, "
            f"found {len(results)}."
        )

    expected_rows = (
        expected_scenarios * EXPECTED_MONTHS[period]
    )

    if len(ledger) != expected_rows:
        raise ValueError(
            f"Expected {expected_rows} ledger rows, "
            f"found {len(ledger)}."
        )

    if not ledger["state"].eq("ok").all():
        raise ValueError(
            "At least one account month is not evaluable."
        )

    for strategy in STRATEGIES:
        for cost_bps in COST_SCENARIOS_BPS:
            subset = ledger.loc[
                (ledger["strategy"] == strategy)
                & (ledger["transaction_cost_bps"] == cost_bps)
            ]

            if len(subset) != EXPECTED_MONTHS[period]:
                raise ValueError(
                    f"Incomplete ledger: {strategy}, "
                    f"{cost_bps} bps."
                )

            if subset["month"].duplicated().any():
                raise ValueError(
                    f"Duplicate months: {strategy}, "
                    f"{cost_bps} bps."
                )

    print(f"Scenarios: {expected_scenarios}")
    print(f"Ledger rows: {len(ledger)}")
    print("Status: PASS")

    # --------------------------------------------------------
    # 2. TRANSACTION-COST IDENTITY
    # --------------------------------------------------------

    print("\n2. TRANSACTION-COST IDENTITY")

    expected_cost = (
        ledger["turnover"]
        * ledger["transaction_cost_bps"]
        / 10000.0
    )

    check_error(
        "Maximum cost error",
        ledger["transaction_cost"],
        expected_cost,
    )

    # --------------------------------------------------------
    # 3. SELF-FINANCING IDENTITY
    # --------------------------------------------------------

    print("\n3. SELF-FINANCING IDENTITY")

    # Simulator:
    #
    # x + fee * sum(abs(x*q - pre)) = 1
    #
    # x = postcost_nav / pretrade_nav
    #
    # transaction_cost = fee * turnover
    #
    # Therefore:
    #
    # x + transaction_cost = 1

    pretrade_nav = ledger["pretrade_nav"].to_numpy(
        dtype=float
    )

    postcost_nav = ledger["postcost_nav"].to_numpy(
        dtype=float
    )

    if (pretrade_nav <= 0).any():
        raise ValueError(
            "Nonpositive pretrade NAV encountered."
        )

    x = postcost_nav / pretrade_nav

    expected_x = 1.0 - ledger[
        "transaction_cost"
    ].to_numpy(dtype=float)

    check_error(
        "Maximum normalized NAV error",
        x,
        expected_x,
    )

    if (x <= 0).any() or (x > 1.0 + TOLERANCE).any():
        raise ValueError(
            "Post-trading NAV fraction outside valid range."
        )

    # --------------------------------------------------------
    # 4. NET-RETURN ACCOUNTING
    # --------------------------------------------------------

    print("\n4. NET-RETURN ACCOUNTING")

    # Simulator:
    #
    # net = x * (1 + gross - financing) - 1
    #
    # Ledger stores:
    #
    # financing_cost = x * financing
    #
    # Thus:
    #
    # net = x * (1 + gross) - 1 - financing_cost

    gross = ledger["gross_factor_return"].to_numpy(
        dtype=float
    )

    financing_cost = ledger["financing_cost"].to_numpy(
        dtype=float
    )

    expected_net = (
        x * (1.0 + gross)
        - 1.0
        - financing_cost
    )

    check_error(
        "Maximum net-return error",
        ledger["net_return"],
        expected_net,
    )

    # Independently verify the end-of-month NAV identity.

    end_nav = ledger["end_nav"].to_numpy(
        dtype=float
    )

    expected_end_nav_ratio = (
        1.0 + ledger["net_return"].to_numpy(
            dtype=float
        )
    )

    check_error(
        "Maximum normalized end-NAV error",
        end_nav / pretrade_nav,
        expected_end_nav_ratio,
    )

    # --------------------------------------------------------
    # 5. RETURN DRAG
    # --------------------------------------------------------

    print("\n5. RETURN DRAG AND TRADING COSTS")

    rows = []

    for strategy in STRATEGIES:

        strategy_results = results.loc[
            results["strategy"] == strategy
        ].copy()

        strategy_results = strategy_results.sort_values(
            "transaction_cost_bps"
        )

        baseline = strategy_results.loc[
            strategy_results["transaction_cost_bps"] == 0
        ]

        if len(baseline) != 1:
            raise ValueError(
                f"Missing baseline for {strategy}."
            )

        baseline_return = float(
            baseline["annualized_mean_return"].iloc[0]
        )

        for _, row in strategy_results.iterrows():

            cost_bps = int(
                row["transaction_cost_bps"]
            )

            annualized_drag = (
                baseline_return
                - row["annualized_mean_return"]
            )

            annualized_cost = (
                12.0
                * row["average_monthly_transaction_cost"]
            )

            rows.append({
                "strategy": strategy,
                "cost_bps": cost_bps,
                "annualized_return_drag_pct": (
                    100.0 * annualized_drag
                ),
                "annualized_trading_cost_pct": (
                    100.0 * annualized_cost
                ),
                "average_monthly_turnover": (
                    row["average_monthly_turnover"]
                ),
                "sharpe_ratio": row["sharpe_ratio"],
            })

    comparison = pd.DataFrame(rows)

    print(
        comparison.round(6).to_string(index=False)
    )

    # --------------------------------------------------------
    # 6. ECONOMIC SANITY CHECKS
    # --------------------------------------------------------

    print("\n6. ECONOMIC SANITY CHECKS")

    for strategy in STRATEGIES:

        subset = results.loc[
            results["strategy"] == strategy
        ].sort_values("transaction_cost_bps")

        returns = subset[
            "annualized_mean_return"
        ].to_numpy(dtype=float)

        costs = subset[
            "average_monthly_transaction_cost"
        ].to_numpy(dtype=float)

        if np.any(np.diff(returns) > TOLERANCE):
            raise ValueError(
                f"{strategy}: mean return increased with costs."
            )

        if np.any(np.diff(costs) < -TOLERANCE):
            raise ValueError(
                f"{strategy}: average trading costs decreased."
            )

        print(f"{strategy:12s}: PASS")

    print(
        f"\n{period.upper()}: ALL VALIDATION CHECKS PASSED"
    )

    return comparison


def main():

    root = project_root()

    comparisons = []

    for period in PERIODS:

        comparison = validate_period(
            root,
            period,
        )

        comparison["period"] = period
        comparisons.append(comparison)

    combined = pd.concat(
        comparisons,
        ignore_index=True,
    )

    print("\n" + "=" * 75)
    print("TRANSACTION-COST ECONOMIC VALIDATION COMPLETE")
    print("=" * 75)

    print(f"Scenarios validated: {len(combined)}")

    print(
        "Self-financing, transaction-cost, and "
        "net-return identities validated."
    )


if __name__ == "__main__":
    main()
