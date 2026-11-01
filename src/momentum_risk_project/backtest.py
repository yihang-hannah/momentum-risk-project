"""Monthly factor-level backtest; costs are exposure-adjustment proxies."""

import numpy as np
import pandas as pd

from .data import validate_cleaned_data
from .metrics import performance_metrics
from .strategies import unmanaged_momentum, volatility_managed_momentum
from .volatility import historical_volatility


def run_backtest(
    daily_returns: pd.Series,
    monthly_returns: pd.Series,
    *,
    transaction_cost_bps: float = 0.0,
    financing_cost_bps: float = 0.0,
    target_volatility: float = 0.12,
    leverage_cap: float | None = None,
    window: int = 126,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return monthly ledger and common-sample gross/net performance.

    WML is +1 winner / -1 loser per unit exposure. Traded notional proxy is
    2*abs(weight[t]-weight[t-1]); initial exposure is zero. The per-side bps
    fee applies to this notional. Financing is a simple annual bps charge on
    max(abs(weight)-1, 0), divided by 12. It excludes short borrow/rebates,
    margin, underlying constituent turnover, drift and liquidation trades.
    start/end select an independent investment episode AFTER risk warm-up.
    """
    for name, value in (("transaction_cost_bps", transaction_cost_bps),
                        ("financing_cost_bps", financing_cost_bps)):
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    if leverage_cap is not None and (
        not np.isfinite(leverage_cap) or leverage_cap <= 0
    ):
        raise ValueError("leverage_cap must be finite and positive")
    for series, frequency in ((daily_returns, "daily"),
                              (monthly_returns, "monthly")):
        validate_cleaned_data(series.rename("mom").to_frame(), frequency)
    sigma = historical_volatility(daily_returns, window=window)
    # Preserve missing month-end estimates instead of carrying stale risk forward.
    monthly_sigma = sigma.groupby(sigma.index.to_period("M")).agg(
        lambda values: values.iloc[-1]
    )
    managed = volatility_managed_momentum(
        monthly_returns, monthly_sigma, target_volatility=target_volatility
    )
    weight = managed["weight"]
    if leverage_cap is not None:
        weight = weight.clip(upper=leverage_cap)
    valid = weight.dropna()
    if valid.empty:
        raise ValueError("No investable months after volatility warm-up")
    # Leading warm-up is allowed; missing risk within the episode is not.
    selected = weight.loc[valid.index[0]:].loc[start:end]
    if selected.isna().any():
        raise ValueError("Missing lagged volatility within investment episode")
    if len(selected) < 2:
        raise ValueError("At least two investable months are required")
    baseline = unmanaged_momentum(monthly_returns).reindex(selected.index)
    frames = []
    summaries = {}
    for name, applied in (("unmanaged", pd.Series(1.0, index=selected.index)),
                          ("managed", selected)):
        previous = applied.shift(1, fill_value=0.0)
        frame = pd.DataFrame({"weight": applied, "wml": baseline})
        frame["turnover_proxy"] = 2 * (applied - previous).abs()
        frame["transaction_cost"] = frame["turnover_proxy"] * transaction_cost_bps / 10000
        frame["financing_cost"] = (applied.abs() - 1).clip(lower=0) * financing_cost_bps / 10000 / 12
        frame["gross_return"] = applied * baseline
        frame["net_return"] = frame["gross_return"] - frame["transaction_cost"] - frame["financing_cost"]
        for kind in ("gross", "net"):
            returns = frame[f"{kind}_return"]
            frame[f"{kind}_wealth"] = ((1 + returns).cumprod()
                                         if (returns > -1).all() else np.nan)
            summaries[f"{name}_{kind}"] = performance_metrics(returns)
        frames.append(frame)
    ledger = pd.concat(frames, keys=["unmanaged", "managed"], names=["strategy", "month"])
    return ledger, pd.DataFrame(summaries).T
