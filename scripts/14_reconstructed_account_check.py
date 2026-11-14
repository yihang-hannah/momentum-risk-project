
"""Test funded-account feasibility using reconstructed stock returns."""

import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.stock_backtest import simulate_stock_account


PERIODS = {
    "historical": ("1929-08", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}


def main():
    root = project_root()

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

    holdings = pd.read_parquet(
        root / "data/processed/wml_current/holdings.parquet",
        columns=columns,
    )

    holdings["month"] = pd.PeriodIndex(
        holdings["month"],
        freq="M",
    )

    holdings = holdings.loc[
        holdings["momentum_decile"].isin([1, 10])
    ].copy()

    for label, (start, end) in PERIODS.items():
        months = pd.period_range(
            start,
            end,
            freq="M",
        )

        sample = holdings.loc[
            holdings["month"].isin(months)
        ].copy()

        # Use the existing simulator's documented imputation
        # convention for reconstructed stock returns.
        sample["scenario_imputed"] = (
            sample["reconstructed_imputed"]
            .fillna(False)
            .astype(bool)
        )

        weights = pd.Series(
            1.0,
            index=months,
            name="unmanaged",
        )

        ledger, _ = simulate_stock_account(
            sample,
            weights,
            return_column="return_reconstructed",
            transaction_cost_bps=0.0,
            financing_cost_bps=0.0,
        )

        print(f"\n{'=' * 65}")
        print(f"RECONSTRUCTED ACCOUNT: {label.upper()}")
        print(f"Period: {start} to {end}")
        print(f"Expected months: {len(months)}")

        print("\nACCOUNT STATES")
        print(
            ledger["state"]
            .value_counts()
            .to_string()
        )

        valid = ledger["gross_factor_return"].notna()

        print(
            f"\nEvaluable months: {valid.sum()} / {len(months)}"
        )

        failures = ledger.loc[
            ledger["state"] != "ok"
        ]

        if not failures.empty:
            print("\nFIRST FAILURE")
            print(failures.head(1).to_string())
        else:
            print("\nAll months successfully evaluated.")


if __name__ == "__main__":
    main()
