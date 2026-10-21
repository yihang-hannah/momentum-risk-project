"""Stock-level momentum signal construction."""

import numpy as np
import pandas as pd


def compute_momentum_signal(
    crsp: pd.DataFrame,
    lookback: int = 12,
    skip: int = 1,
) -> pd.DataFrame:
    """
    Compute stock-level 12-2 momentum signals.

    The signal for holding month t uses monthly returns
    from t-12 through t-2, excluding month t-1.

    A complete return history is required. Missing calendar
    months are not treated as adjacent observations.

    Parameters
    ----------
    crsp : pd.DataFrame
        Monthly stock panel containing permno, month, and mthret.
    lookback : int
        Number of months between the holding month and the
        beginning of the formation period.
    skip : int
        Number of recent months excluded before holding.

    Returns
    -------
    pd.DataFrame
        Original stock panel with a momentum_signal column.
    """
    required_columns = {"permno", "month", "mthret"}

    missing_columns = required_columns - set(crsp.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if lookback <= skip:
        raise ValueError("lookback must be greater than skip")

    panel = crsp.copy()
    panel["month"] = pd.PeriodIndex(panel["month"], freq="M")

    if panel.duplicated(["permno", "month"]).any():
        raise ValueError("Duplicate stock-month records found")

    panel = panel.sort_values(["permno", "month"])

    # Convert returns into log gross returns.
    # A -100% return has log gross return equal to -infinity.
    returns = pd.to_numeric(panel["mthret"], errors="coerce")

    valid_returns = returns.ge(-1) & returns.notna()
    gross_returns = 1.0 + returns.where(valid_returns)

    log_gross = np.log(gross_returns)

    # Use a calendar-month offset to prevent gaps from
    # being treated as consecutive monthly observations.
    lookup = pd.DataFrame({
        "permno": panel["permno"].to_numpy(),
        "month": panel["month"].array,
        "log_gross": log_gross.to_numpy(),
    })

    # Build the formation window explicitly.
    formation_returns = []

    for lag in range(skip + 1, lookback + 1):
        lagged = lookup.copy()
        lagged["month"] = lagged["month"] + lag

        lagged = lagged.rename(
            columns={"log_gross": f"lag_{lag}"}
        )

        formation_returns.append(lagged)

    signals = panel[["permno", "month"]].copy()

    for lagged in formation_returns:
        signals = signals.merge(
            lagged,
            on=["permno", "month"],
            how="left",
            validate="one_to_one",
        )

    lag_columns = [
        f"lag_{lag}"
        for lag in range(skip + 1, lookback + 1)
    ]

    # Require all formation-month returns to be available.
    complete_history = signals[lag_columns].notna().all(axis=1)

    signals["momentum_signal"] = np.nan

    signals.loc[complete_history, "momentum_signal"] = (
        np.expm1(
            signals.loc[complete_history, lag_columns].sum(axis=1)
        )
    )

    return panel.merge(
        signals[["permno", "month", "momentum_signal"]],
        on=["permno", "month"],
        how="left",
        validate="one_to_one",
    )

def compute_aligned_wml(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Construct WML using correctly aligned momentum signals.

    Momentum signals correspond to holding month t.
    Stock eligibility, exchange classification, and market
    capitalization come from formation month t-1.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        Monthly portfolio returns and stock-level holdings.
    """
    required = {
        "permno",
        "month",
        "momentum_signal",
        "primaryexch",
        "mthcap",
        "mthret",
    }

    missing = required - set(panel.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = panel.copy()
    data["month"] = pd.PeriodIndex(data["month"], freq="M")

    if data.duplicated(["permno", "month"]).any():
        raise ValueError("Duplicate stock-month records found")

    # Formation-date attributes from month t-1
    formation = data[
        ["permno", "month", "primaryexch", "mthcap"]
    ].copy()

    formation = formation.rename(
        columns={
            "month": "formation_month",
            "primaryexch": "formation_exchange",
            "mthcap": "formation_cap",
        }
    )

    formation["month"] = formation["formation_month"] + 1

    # Holding-month signals and realized returns
    holding = data[
        ["permno", "month", "momentum_signal", "mthret"]
    ].copy()

    # Preserve the formation universe, including unmatched returns
    holdings = formation.merge(
        holding,
        on=["permno", "month"],
        how="left",
        validate="one_to_one",
    )

    # Eligibility is determined at the formation date
    eligible = (
        holdings["formation_exchange"].isin(["N", "A", "Q"])
        & holdings["formation_cap"].notna()
        & np.isfinite(holdings["formation_cap"])
        & holdings["formation_cap"].gt(0)
        & holdings["momentum_signal"].notna()
        & np.isfinite(holdings["momentum_signal"])
    )

    holdings = holdings.loc[eligible].copy()

    # NYSE breakpoints for each holding month
    nyse = holdings.loc[
        holdings["formation_exchange"].eq("N")
    ]

    quantiles = [i / 10 for i in range(1, 10)]

    breakpoints = (
        nyse.groupby("month")["momentum_signal"]
        .quantile(quantiles)
        .unstack()
    )

    breakpoint_columns = [
        f"q{i}" for i in range(10, 100, 10)
    ]

    breakpoints.columns = breakpoint_columns

    holdings = holdings.merge(
        breakpoints,
        left_on="month",
        right_index=True,
        how="left",
        validate="many_to_one",
    )

    signals = holdings["momentum_signal"].to_numpy(
        dtype=float
    )

    thresholds = holdings[breakpoint_columns].to_numpy(
        dtype=float
    )

    valid_breakpoints = np.isfinite(thresholds).all(axis=1)

    deciles = np.full(len(holdings), np.nan)

    deciles[valid_breakpoints] = (
        1
        + (
            signals[valid_breakpoints, None]
            > thresholds[valid_breakpoints]
        ).sum(axis=1)
    )

    holdings["momentum_decile"] = pd.array(
        deciles,
        dtype="Int64",
    )

    holdings = holdings.drop(columns=breakpoint_columns)

    holdings["valid_return"] = (
        holdings["mthret"].notna()
        & np.isfinite(holdings["mthret"])
    )

    valid_holdings = holdings.loc[
        holdings["momentum_decile"].notna()
        & holdings["valid_return"]
    ].copy()

    valid_holdings["weighted_return"] = (
        valid_holdings["formation_cap"]
        * valid_holdings["mthret"]
    )

    portfolios = (
        valid_holdings.groupby(
            ["month", "momentum_decile"],
            observed=True,
        )
        .agg(
            weighted_return_sum=("weighted_return", "sum"),
            total_weight=("formation_cap", "sum"),
            stock_count=("permno", "size"),
        )
        .reset_index()
    )

    portfolios["portfolio_return"] = (
        portfolios["weighted_return_sum"]
        / portfolios["total_weight"]
    )

    monthly = portfolios.pivot(
        index="month",
        columns="momentum_decile",
        values="portfolio_return",
    )

    monthly = monthly.reindex(columns=range(1, 11))

    monthly.columns = [
        f"P{i}" for i in range(1, 11)
    ]

    monthly["WML"] = monthly["P10"] - monthly["P1"]

    return monthly.reset_index(), holdings