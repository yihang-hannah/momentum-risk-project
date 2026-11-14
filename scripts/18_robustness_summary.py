
"""Summarize Extension 3 bootstrap robustness results.

Reads previously generated bootstrap comparisons.
No simulations or bootstrap resampling required.
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/statistical_robustness/bootstrap_all_comparisons.csv"
OUTPUT = ROOT / "outputs/statistical_robustness"

PAIRS = [
    ("historical", "unmanaged"),
    ("ewma", "unmanaged"),
    ("garch", "unmanaged"),
    ("ewma", "historical"),
    ("garch", "historical"),
    ("ewma", "garch"),
]


def main():
    df = pd.read_csv(INPUT)

    if len(df) != 72:
        raise ValueError(f"Expected 72 comparisons; found {len(df)}")

    df["comparison"] = (
        df["strategy_a"] + " - " + df["strategy_b"]
    )

    df["significant_5pct"] = (
        (df["sharpe_ci_lower"] > 0)
        | (df["sharpe_ci_upper"] < 0)
    )

    # Bonferroni correction for six pairwise tests
    # within each sample/cap/block configuration.
    df["bonferroni_significant"] = (
        df["sharpe_p_value_centered"] < 0.05 / 6
    )

    rows = []

    for period in ["historical", "extension"]:
        print("\n" + "=" * 90)
        print(f"ROBUSTNESS ANALYSIS: {period.upper()}")
        print("=" * 90)

        for a, b in PAIRS:
            subset = df.loc[
                (df["period"] == period)
                & (df["strategy_a"] == a)
                & (df["strategy_b"] == b)
            ].sort_values(["leverage_cap", "block_length"])

            rows.append({
                "period": period,
                "comparison": f"{a} - {b}",
                "significant_configurations":
                    int(subset["significant_5pct"].sum()),
                "total_configurations": len(subset),
                "bonferroni_significant_configurations":
                    int(subset["bonferroni_significant"].sum()),
                "minimum_sharpe_difference":
                    subset["sharpe_difference"].min(),
                "maximum_sharpe_difference":
                    subset["sharpe_difference"].max(),
                "minimum_p_value":
                    subset["sharpe_p_value_centered"].min(),
                "maximum_p_value":
                    subset["sharpe_p_value_centered"].max(),
            })

            print(f"\n{a.upper()} - {b.upper()}")

            print(
                subset[
                    [
                        "leverage_cap",
                        "block_length",
                        "sharpe_difference",
                        "sharpe_ci_lower",
                        "sharpe_ci_upper",
                        "sharpe_p_value_centered",
                        "significant_5pct",
                        "bonferroni_significant",
                    ]
                ].round(4).to_string(index=False)
            )

    summary = pd.DataFrame(rows)

    summary.to_csv(
        OUTPUT / "robustness_significance_summary.csv",
        index=False,
    )

    print("\n" + "=" * 90)
    print("ROBUSTNESS OVERVIEW")
    print("=" * 90)

    print(summary.to_string(index=False))

    print("\nInterpretation:")
    print("6/6: Significant in every tested configuration.")
    print("0/6: Not significant in any tested configuration.")
    print("1-5/6: Sensitivity to block length or leverage cap.")
    print(
        "Bonferroni results are exploratory adjustments "
        "within each six-comparison family."
    )


if __name__ == "__main__":
    main()
