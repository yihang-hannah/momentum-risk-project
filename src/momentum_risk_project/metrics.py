import numpy as np
import pandas as pd


def performance_metrics(
    returns: pd.Series,
    periods_per_year: int = 12,
) -> pd.Series:
    """Calculate arithmetic performance and feasible wealth-based metrics.

    A factor or leveraged long-short return can be at or below -100%.
    In that case, arithmetic statistics remain defined, but a standard
    continuously reinvested, limited-liability wealth path is not.
    Wealth-based metrics are reported as NaN rather than extrapolating
    through a zero or negative account value.
    """
    if returns.empty or returns.isna().any():
        raise ValueError("Returns must be non-empty and complete")

    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Returns must be finite")

    if len(returns) < 2:
        raise ValueError("At least two observations are required")

    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")

    annual_mean = returns.mean() * periods_per_year
    annual_vol = returns.std(ddof=1) * np.sqrt(periods_per_year)
    sharpe = annual_mean / annual_vol if annual_vol > 0 else np.nan

    if (returns <= -1).any():
        cagr = np.nan
        max_drawdown = np.nan
        terminal_wealth = np.nan
    else:
        wealth = (1 + returns).cumprod()
        years = len(returns) / periods_per_year
        terminal_wealth = wealth.iloc[-1]
        cagr = terminal_wealth ** (1 / years) - 1

        wealth_with_initial = pd.concat(
            [pd.Series([1.0]), wealth.reset_index(drop=True)],
            ignore_index=True,
        )
        running_peak = wealth_with_initial.cummax()
        max_drawdown = (wealth_with_initial / running_peak - 1).min()

    return pd.Series({
        "Annualized Mean Return": annual_mean,
        "Annualized Volatility": annual_vol,
        "Sharpe (rf=0)": sharpe,
        "CAGR": cagr,
        "Maximum Drawdown": max_drawdown,
        "Terminal Wealth": terminal_wealth,
    })
