
"""Diagnose historical WML reconciliation discrepancies."""

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build


def main():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))

    monthly = build.monthly_reconstructed["WML"]

    columns = [
        "month",
        "permno",
        "momentum_decile",
        "leg_weight",
        "return_reference",
        "return_reconstructed",
        "reference_imputed",
        "reconstructed_imputed",
    ]

    holdings = pd.read_parquet(
        root / "data/processed/wml_current/holdings.parquet",
        columns=columns,
    )

    holdings["month"] = pd.PeriodIndex(
        holdings["month"], freq="M"
    )

    holdings = holdings.loc[
        holdings["momentum_decile"].isin([1, 10])
    ].copy()

    holdings["signed_weight"] = np.where(
        holdings["momentum_decile"] == 10,
        holdings["leg_weight"],
        -holdings["leg_weight"],
    )

    holdings["reference_contribution"] = (
        holdings["signed_weight"] * holdings["return_reference"]
    )

    holdings["reconstructed_contribution"] = (
        holdings["signed_weight"] * holdings["return_reconstructed"]
    )

    comparison = holdings.groupby("month")[
        ["reference_contribution", "reconstructed_contribution"]
    ].sum()

    comparison.columns = [
        "reference_wml",
        "holdings_reconstructed_wml",
    ]

    comparison["pipeline_wml"] = monthly.reindex(
        comparison.index
    )

    comparison["reference_error_bps"] = (
        comparison["reference_wml"]
        - comparison["pipeline_wml"]
    ) * 10000

    comparison["reconstructed_error_bps"] = (
        comparison["holdings_reconstructed_wml"]
        - comparison["pipeline_wml"]
    ) * 10000

    historical = comparison.loc["1929-08":"2011-12"].copy()

    print("\nTOP 10 HISTORICAL RECONCILIATION ERRORS")
    print(
        historical.reindex(
            historical["reference_error_bps"]
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .index
        ).round(6).to_string()
    )

    worst_month = (
        historical["reference_error_bps"].abs().idxmax()
    )

    print(f"\nWORST MONTH: {worst_month}")

    detail = holdings.loc[
        holdings["month"] == worst_month
    ].copy()

    detail["difference_bps"] = (
        detail["reference_contribution"]
        - detail["reconstructed_contribution"]
    ) * 10000

    print("\nTOP 15 STOCK CONTRIBUTION DIFFERENCES")
    print(
        detail.reindex(
            detail["difference_bps"]
            .abs()
            .sort_values(ascending=False)
            .head(15)
            .index
        )[
            [
                "permno",
                "momentum_decile",
                "leg_weight",
                "return_reference",
                "return_reconstructed",
                "reference_imputed",
                "reconstructed_imputed",
                "difference_bps",
            ]
        ].round(6).to_string(index=False)
    )


if __name__ == "__main__":
    main()
