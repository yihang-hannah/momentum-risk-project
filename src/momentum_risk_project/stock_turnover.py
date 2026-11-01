"""Stock-level target and drift-adjusted turnover under explicit monthly conventions.

Turnover is total absolute stock notional traded per unit of pre-trade gross NAV,
not half-turnover. Positions use total-return reinvestment units. This is not a
broker/share settlement simulator; corporate-action, dividend reinvestment and
delisting cash settlement trades are not separately observable here.
"""

import numpy as np
import pandas as pd


def stock_level_turnover(
    holdings: pd.DataFrame,
    factor_weights: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build P10/P1 signed targets and compare them with drifted prior holdings.

    Required columns: permno, month, momentum_decile, formation_cap, mthret.
    Each month's target uses only formation caps and decile assignments. Returns
    of month t affect only turnover at t+1, never the target for month t.
    Missing returns invalidate that month's gross P&L and next month's drift.
    They never cause a held stock to be dropped or its return to be set to zero.

    Drift uses a one-step, gross-of-cost reference NAV: 1 + previous gross WML
    P&L, including previous factor scale. Costs/funding are excluded from that
    denominator. No recursive net account or terminal liquidation is simulated.
    Each month's diagnostic assumes its target was reached; after an unresolved
    prior month, its trade amount is unknown rather than a simulated restart.
    """
    required = {"permno", "month", "momentum_decile", "formation_cap", "mthret"}
    missing = required - set(holdings.columns)
    if missing:
        raise ValueError(f"Missing holdings columns: {sorted(missing)}")
    data = holdings.copy()
    data["month"] = pd.PeriodIndex(data["month"], freq="M")
    if data.empty or data[["permno", "month"]].isna().any().any():
        raise ValueError("Holdings need non-empty stock/month identifiers")
    if data.duplicated(["permno", "month"]).any():
        raise ValueError("Duplicate stock-month holdings")
    data = data.loc[data["momentum_decile"].isin([1, 10])].copy()
    if data.empty:
        raise ValueError("No P1/P10 holdings")
    months = pd.PeriodIndex(sorted(data["month"].unique()), freq="M")
    if not months.equals(pd.period_range(months[0], months[-1], freq="M")):
        raise ValueError("Holdings must contain consecutive months")
    counts = data.groupby(["month", "momentum_decile"]).size().unstack(fill_value=0)
    if not {1, 10}.issubset(counts.columns) or (counts[[1, 10]] == 0).any().any():
        raise ValueError("Both P1 and P10 are required each month")
    caps = data["formation_cap"].to_numpy(dtype=float)
    if not np.isfinite(caps).all() or (caps <= 0).any():
        raise ValueError("Formation caps must be finite and positive")
    if factor_weights is None:
        factor_weights = pd.Series(1.0, index=months)
    if not isinstance(factor_weights, pd.Series) or not isinstance(factor_weights.index, pd.PeriodIndex):
        raise TypeError("Factor weights must be a monthly Series")
    if factor_weights.index.freqstr != "M" or not factor_weights.index.is_unique:
        raise ValueError("Factor weights need unique monthly periods")
    weights = factor_weights.reindex(months).astype(float)
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("Factor weights must cover every month and be non-negative finite")
    total_cap = data.groupby(["month", "momentum_decile"])["formation_cap"].transform("sum")
    data["leg_weight"] = data["formation_cap"] / total_cap
    data["target_weight"] = (
        data["leg_weight"] * np.where(data["momentum_decile"].eq(10), 1.0, -1.0)
        * data["month"].map(weights)
    )
    data["mthret"] = pd.to_numeric(data["mthret"], errors="raise")
    data["valid_return"] = np.isfinite(data["mthret"]) & data["mthret"].ge(-1)
    data["mthret"] = data["mthret"].where(data["valid_return"])
    previous = None
    previous_pnl = None
    previous_valid = True
    records, month_rows = [], []
    for month, group in data.groupby("month", sort=True):
        current = group.set_index("permno")
        target = current["target_weight"]
        ids = target.index if previous is None else target.index.union(previous.index)
        trades = pd.DataFrame(index=ids)
        trades.index.name = "permno"
        trades["month"] = month
        trades["target_weight"] = target.reindex(ids, fill_value=0.0)
        trades["in_previous_target"] = False if previous is None else ids.isin(previous.index)
        trades["in_current_target"] = ids.isin(current.index)
        prior_nav = 1.0 if previous is None else 1.0 + previous_pnl
        drift_valid = previous is None or (previous_valid and np.isfinite(prior_nav) and prior_nav > 0)
        if previous is None:
            trades["pretrade_weight"] = 0.0
        elif drift_valid:
            drift = previous["target_weight"] * (1 + previous["mthret"])
            # Zero positions require no return observation.
            drift = drift.where(previous["target_weight"].ne(0), 0.0)
            trades["pretrade_weight"] = drift.reindex(ids, fill_value=0.0) / prior_nav
        else:
            trades["pretrade_weight"] = np.nan
        trades["trade_weight"] = trades["target_weight"] - trades["pretrade_weight"]
        trades["absolute_trade"] = trades["trade_weight"].abs()
        held = current["target_weight"].ne(0)
        current_valid = bool(current.loc[held, "valid_return"].all())
        pnl = float((current.loc[held, "target_weight"] * current.loc[held, "mthret"]).sum()) if current_valid else np.nan
        turnover = float(trades["absolute_trade"].sum()) if drift_valid else np.nan
        month_rows.append({
            "month": month, "factor_weight": float(weights.loc[month]),
            "target_gross_exposure": float(target.abs().sum()),
            "target_net_exposure": float(target.sum()),
            "gross_return": pnl, "turnover": turnover,
            "turnover_known": bool(drift_valid), "return_known": current_valid,
            "missing_return_stocks": int((~current.loc[held, "valid_return"]).sum()),
            "entry_notional": float(trades.loc[~trades.in_previous_target, "absolute_trade"].sum()) if drift_valid else np.nan,
            "exit_notional": float(trades.loc[~trades.in_current_target, "absolute_trade"].sum()) if drift_valid else np.nan,
            "continuing_notional": float(trades.loc[trades.in_previous_target & trades.in_current_target, "absolute_trade"].sum()) if drift_valid else np.nan,
            "prior_gross_nav_multiplier": prior_nav,
        })
        records.append(trades.reset_index())
        previous, previous_pnl, previous_valid = current, pnl, current_valid
    return pd.concat(records, ignore_index=True), pd.DataFrame(month_rows).set_index("month")
