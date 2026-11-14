
"""Extension 3: Statistical robustness of momentum strategies.

Paired circular moving-block bootstrap of monthly net returns.

Primary specification:
    Transaction costs: 10 bps
    Financing costs: 0 bps
    Leverage: uncapped
    Bootstrap draws: 5,000
    Block length: 6 months

Robustness:
    Block lengths: 3, 6, 12 months
    Leverage: uncapped and 1.0x

Reads existing outputs only. Does not modify earlier results.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from momentum_risk_project.paths import project_root


# ============================================================
# CONFIGURATION
# ============================================================

PERIODS = {
    "historical": 989,
    "extension": 168,
}

STRATEGIES = [
    "unmanaged",
    "historical",
    "ewma",
    "garch",
]

PAIRS = [
    ("historical", "unmanaged"),
    ("ewma", "unmanaged"),
    ("garch", "unmanaged"),
    ("ewma", "historical"),
    ("garch", "historical"),
    ("ewma", "garch"),
]

LEVERAGE_CAPS = [
    "uncapped",
    "1.0x",
]

BLOCK_LENGTHS = [3, 6, 12]

PRIMARY_BLOCK_LENGTH = 6
BOOTSTRAP_REPLICATIONS = 5000
CONFIDENCE_LEVEL = 0.95
RANDOM_SEED = 20261113

TRANSACTION_COST_BPS = 10
FINANCING_SPREAD_BPS = 0

RECONCILIATION_TOLERANCE = 1e-8
CHUNK_SIZE = 250


# ============================================================
# METRICS
# ============================================================

def sharpe_ratio(returns):
    """Annualized Sharpe with zero risk-free benchmark."""

    returns = np.asarray(returns, dtype=float)

    mean = returns.mean()
    volatility = returns.std(ddof=1)

    if volatility <= 0 or not np.isfinite(volatility):
        raise ValueError("Invalid return volatility.")

    return np.sqrt(12.0) * mean / volatility


def annualized_mean_return(returns):
    """Arithmetic annualized mean return."""

    return 12.0 * np.asarray(
        returns, dtype=float
    ).mean()


def sample_statistics(frame):
    """Calculate individual strategy performance statistics."""

    rows = []

    for strategy in STRATEGIES:

        returns = frame[strategy].to_numpy(
            dtype=float
        )

        rows.append({
            "strategy": strategy,
            "observations": len(returns),
            "annualized_mean_return":
                annualized_mean_return(returns),
            "annualized_volatility":
                np.sqrt(12.0)
                * returns.std(ddof=1),
            "sharpe_ratio": sharpe_ratio(returns),
        })

    return pd.DataFrame(rows)


# ============================================================
# DATA LOADING
# ============================================================

def load_strategy_returns(root, period, leverage_cap):
    """Load aligned monthly net returns from Extension 2."""

    path = (
        root
        / "outputs"
        / "leverage_financing"
        / period
        / "monthly_account_ledgers.csv"
    )

    ledger = pd.read_csv(path)

    if not np.isclose(
        TRANSACTION_COST_BPS, 10
    ):
        raise ValueError(
            "This experiment assumes the validated "
            "10-bps Extension 2 transaction-cost setting."
        )

    required = {
        "month",
        "strategy",
        "leverage_cap",
        "financing_spread_bps",
        "net_return",
        "state",
    }

    missing = required - set(ledger.columns)

    if missing:
        raise ValueError(
            f"Missing ledger columns: {sorted(missing)}"
        )

    selected = ledger.loc[
        (
            ledger["financing_spread_bps"]
            == FINANCING_SPREAD_BPS
        )
        & (
            (
                (ledger["strategy"] == "unmanaged")
                & (ledger["leverage_cap"] == "unmanaged")
            )
            |
            (
                ledger["strategy"].isin(
                    STRATEGIES[1:]
                )
                & (ledger["leverage_cap"] == leverage_cap)
            )
        )
    ].copy()

    if not selected["state"].eq("ok").all():
        raise ValueError(
            f"Invalid account state: {period}/{leverage_cap}"
        )

    if selected.duplicated(
        ["month", "strategy"]
    ).any():
        raise ValueError(
            f"Duplicate month-strategy observations: "
            f"{period}/{leverage_cap}"
        )

    selected["month"] = pd.PeriodIndex(
        selected["month"],
        freq="M",
    )

    frame = selected.pivot(
        index="month",
        columns="strategy",
        values="net_return",
    )

    frame = frame.reindex(
        columns=STRATEGIES
    ).sort_index()

    expected_months = PERIODS[period]

    if len(frame) != expected_months:
        raise ValueError(
            f"Expected {expected_months} months for "
            f"{period}; found {len(frame)}."
        )

    expected_index = pd.period_range(
        frame.index.min(),
        frame.index.max(),
        freq="M",
    )

    if not frame.index.equals(expected_index):
        raise ValueError(
            f"Nonconsecutive monthly index: {period}"
        )

    if not np.isfinite(
        frame.to_numpy(dtype=float)
    ).all():
        raise ValueError(
            f"Missing/nonfinite returns: "
            f"{period}/{leverage_cap}"
        )

    return frame


# ============================================================
# BASELINE RECONCILIATION
# ============================================================

def validate_primary_baseline(root, period, frame):
    """Reconcile primary returns against Extension 1."""

    path = (
        root
        / "outputs"
        / "transaction_costs"
        / period
        / "monthly_account_ledgers.csv"
    )

    old = pd.read_csv(
        path,
        usecols=[
            "month",
            "strategy",
            "transaction_cost_bps",
            "net_return",
        ],
    )

    old = old.loc[
        old["transaction_cost_bps"]
        == TRANSACTION_COST_BPS
    ].copy()

    old["month"] = pd.PeriodIndex(
        old["month"],
        freq="M",
    )

    if old.duplicated(
        ["month", "strategy"]
    ).any():
        raise ValueError(
            "Duplicate observations in Extension 1."
        )

    reference = old.pivot(
        index="month",
        columns="strategy",
        values="net_return",
    )

    reference = reference.reindex(
        index=frame.index,
        columns=STRATEGIES,
    )

    if reference.isna().any().any():
        raise ValueError(
            f"Missing Extension 1 baseline: {period}"
        )

    error = np.max(
        np.abs(
            frame.to_numpy()
            - reference.to_numpy()
        )
    )

    if error > RECONCILIATION_TOLERANCE:
        raise ValueError(
            f"Extension 1 reconciliation failed: "
            f"{period}, error={error:.12e}"
        )

    print(
        f"  Extension 1 reconciliation: PASS "
        f"(maximum error {error:.3e})"
    )


# ============================================================
# PAIRED CIRCULAR BLOCK BOOTSTRAP
# ============================================================

def bootstrap_indices(
    rng,
    replications,
    observations,
    block_length,
):
    """Generate circular moving-block bootstrap indices.

    The same indices are applied to all strategies, preserving
    the cross-sectional dependence of monthly strategy returns.
    """

    number_of_blocks = int(
        np.ceil(observations / block_length)
    )

    starts = rng.integers(
        0,
        observations,
        size=(replications, number_of_blocks),
    )

    offsets = np.arange(block_length)

    indices = (
        starts[:, :, None]
        + offsets[None, None, :]
    ) % observations

    return indices.reshape(
        replications,
        -1,
    )[:, :observations]


def bootstrap_statistics(
    frame,
    block_length,
    replications,
    seed,
):
    """Generate paired bootstrap Sharpe and return estimates."""

    values = frame[STRATEGIES].to_numpy(
        dtype=float
    )

    observations, number_of_strategies = values.shape

    rng = np.random.default_rng(seed)

    bootstrap_sharpes = np.empty(
        (replications, number_of_strategies),
        dtype=float,
    )

    bootstrap_means = np.empty_like(
        bootstrap_sharpes
    )

    completed = 0

    while completed < replications:

        batch_size = min(
            CHUNK_SIZE,
            replications - completed,
        )

        indices = bootstrap_indices(
            rng,
            batch_size,
            observations,
            block_length,
        )

        # Dimensions:
        # batch x month x strategy

        sampled = values[indices, :]

        means = sampled.mean(axis=1)
        volatilities = sampled.std(
            axis=1,
            ddof=1,
        )

        if (
            not np.isfinite(volatilities).all()
            or (volatilities <= 0).any()
        ):
            raise ValueError(
                "Invalid bootstrap volatility."
            )

        bootstrap_sharpes[
            completed:completed + batch_size
        ] = (
            np.sqrt(12.0)
            * means
            / volatilities
        )

        bootstrap_means[
            completed:completed + batch_size
        ] = 12.0 * means

        completed += batch_size

    return bootstrap_sharpes, bootstrap_means


# ============================================================
# INFERENCE
# ============================================================

def inference_for_difference(
    observed_difference,
    bootstrap_differences,
):
    """Percentile CI and centered-bootstrap two-sided p-value.

    The centered-bootstrap p-value approximates the null
    distribution by centering the bootstrap statistic around
    the observed statistic. It is not an exact null-imposed
    bootstrap test.
    """

    alpha = 1.0 - CONFIDENCE_LEVEL

    ci_lower, ci_upper = np.quantile(
        bootstrap_differences,
        [
            alpha / 2.0,
            1.0 - alpha / 2.0,
        ],
    )

    centered = (
        bootstrap_differences
        - observed_difference
    )

    # Plus-one finite-simulation correction.

    exceedances = np.count_nonzero(
        np.abs(centered)
        >= abs(observed_difference)
    )

    p_value = (
        exceedances + 1
    ) / (
        len(centered) + 1
    )

    return {
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "p_value_centered": float(p_value),
        "ci_excludes_zero": bool(
            ci_lower > 0 or ci_upper < 0
        ),
    }


def analyze_configuration(
    frame,
    period,
    leverage_cap,
    block_length,
    seed,
):
    """Analyze all six paired strategy comparisons."""

    print(
        f"  Bootstrap: cap={leverage_cap:8s}, "
        f"block={block_length:2d}, "
        f"draws={BOOTSTRAP_REPLICATIONS}"
    )

    boot_sharpes, boot_means = bootstrap_statistics(
        frame=frame,
        block_length=block_length,
        replications=BOOTSTRAP_REPLICATIONS,
        seed=seed,
    )

    observed_sharpes = np.array([
        sharpe_ratio(frame[s])
        for s in STRATEGIES
    ])

    observed_means = np.array([
        annualized_mean_return(frame[s])
        for s in STRATEGIES
    ])

    strategy_index = {
        name: i
        for i, name in enumerate(STRATEGIES)
    }

    rows = []

    for strategy_a, strategy_b in PAIRS:

        ia = strategy_index[strategy_a]
        ib = strategy_index[strategy_b]

        observed_sharpe_difference = (
            observed_sharpes[ia]
            - observed_sharpes[ib]
        )

        observed_mean_difference = (
            observed_means[ia]
            - observed_means[ib]
        )

        boot_sharpe_difference = (
            boot_sharpes[:, ia]
            - boot_sharpes[:, ib]
        )

        boot_mean_difference = (
            boot_means[:, ia]
            - boot_means[:, ib]
        )

        sharpe_inference = inference_for_difference(
            observed_sharpe_difference,
            boot_sharpe_difference,
        )

        mean_inference = inference_for_difference(
            observed_mean_difference,
            boot_mean_difference,
        )

        rows.append({
            "period": period,
            "leverage_cap": leverage_cap,
            "block_length": block_length,
            "bootstrap_replications":
                BOOTSTRAP_REPLICATIONS,
            "strategy_a": strategy_a,
            "strategy_b": strategy_b,
            "observations": len(frame),

            "sharpe_difference":
                observed_sharpe_difference,
            "sharpe_ci_lower":
                sharpe_inference["ci_lower"],
            "sharpe_ci_upper":
                sharpe_inference["ci_upper"],
            "sharpe_p_value_centered":
                sharpe_inference["p_value_centered"],
            "sharpe_ci_excludes_zero":
                sharpe_inference["ci_excludes_zero"],

            "annualized_mean_difference":
                observed_mean_difference,
            "mean_ci_lower":
                mean_inference["ci_lower"],
            "mean_ci_upper":
                mean_inference["ci_upper"],
            "mean_p_value_centered":
                mean_inference["p_value_centered"],
            "mean_ci_excludes_zero":
                mean_inference["ci_excludes_zero"],
        })

    return pd.DataFrame(rows)


# ============================================================
# REPORTING
# ============================================================

def print_primary_results(results, period):
    """Print primary 6-month uncapped Sharpe comparisons."""

    selected = results.loc[
        (results["period"] == period)
        & (results["leverage_cap"] == "uncapped")
        & (
            results["block_length"]
            == PRIMARY_BLOCK_LENGTH
        )
    ].copy()

    selected["comparison"] = (
        selected["strategy_a"]
        + " - "
        + selected["strategy_b"]
    )

    columns = [
        "comparison",
        "sharpe_difference",
        "sharpe_ci_lower",
        "sharpe_ci_upper",
        "sharpe_p_value_centered",
        "sharpe_ci_excludes_zero",
    ]

    print("\n" + "=" * 75)
    print(
        f"PRIMARY BOOTSTRAP RESULTS: {period.upper()}"
    )
    print("=" * 75)

    print(
        selected[columns]
        .round(5)
        .to_string(index=False)
    )


def main():

    root = project_root()

    output_dir = (
        root
        / "outputs"
        / "statistical_robustness"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_inference = []
    all_performance = []

    for period in PERIODS:

        print("\n" + "=" * 75)
        print(
            f"STATISTICAL ROBUSTNESS: {period.upper()}"
        )
        print("=" * 75)

        for leverage_cap in LEVERAGE_CAPS:

            frame = load_strategy_returns(
                root,
                period,
                leverage_cap,
            )

            print(
                f"\nSample: {period}, "
                f"cap={leverage_cap}, "
                f"months={len(frame)}"
            )

            if leverage_cap == "uncapped":
                validate_primary_baseline(
                    root,
                    period,
                    frame,
                )

            statistics = sample_statistics(frame)

            statistics["period"] = period
            statistics["leverage_cap"] = leverage_cap

            all_performance.append(statistics)

            # Seed varies by configuration, while the same
            # bootstrap draws are shared by all strategies
            # within each configuration.

            for block_length in BLOCK_LENGTHS:

                cap_index = LEVERAGE_CAPS.index(
                    leverage_cap
                )

                period_index = list(
                    PERIODS
                ).index(period)

                seed = (
                    RANDOM_SEED
                    + 10000 * period_index
                    + 1000 * cap_index
                    + block_length
                )

                inference = analyze_configuration(
                    frame=frame,
                    period=period,
                    leverage_cap=leverage_cap,
                    block_length=block_length,
                    seed=seed,
                )

                all_inference.append(inference)

    inference_df = pd.concat(
        all_inference,
        ignore_index=True,
    )

    performance_df = pd.concat(
        all_performance,
        ignore_index=True,
    )

    # --------------------------------------------------------
    # SAVE OUTPUTS
    # --------------------------------------------------------

    inference_df.to_csv(
        output_dir / "bootstrap_all_comparisons.csv",
        index=False,
        float_format="%.12g",
    )

    performance_df.to_csv(
        output_dir / "strategy_performance.csv",
        index=False,
        float_format="%.12g",
    )

    primary = inference_df.loc[
        (
            inference_df["leverage_cap"]
            == "uncapped"
        )
        & (
            inference_df["block_length"]
            == PRIMARY_BLOCK_LENGTH
        )
    ].copy()

    primary.to_csv(
        output_dir / "primary_bootstrap_results.csv",
        index=False,
        float_format="%.12g",
    )

    robustness = inference_df.loc[
        inference_df["block_length"].isin(
            BLOCK_LENGTHS
        )
    ].copy()

    robustness.to_csv(
        output_dir / "robustness_comparisons.csv",
        index=False,
        float_format="%.12g",
    )

    # --------------------------------------------------------
    # DISPLAY PRIMARY RESULTS
    # --------------------------------------------------------

    for period in PERIODS:
        print_primary_results(
            inference_df,
            period,
        )

    print("\n" + "=" * 75)
    print("STATISTICAL ROBUSTNESS EXPERIMENT COMPLETE")
    print("=" * 75)

    print(
        f"Total pairwise comparisons: "
        f"{len(inference_df)}"
    )

    print(
        f"Bootstrap replications per configuration: "
        f"{BOOTSTRAP_REPLICATIONS}"
    )

    print(
        f"Block lengths: {BLOCK_LENGTHS}"
    )

    print(
        f"Leverage specifications: {LEVERAGE_CAPS}"
    )

    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
