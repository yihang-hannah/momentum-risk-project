"""Generate the two manuscript figures from authorized local CRSP/WRDS build data.

Run from the repository root:
    python scripts/19_paper_figures.py
No licensed stock-level data are exported. Outputs are figures only.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.volatility import historical_volatility, ewma_volatility
from momentum_risk_project.strategies import volatility_managed_momentum

PERIODS = {
    "historical": ("1929-08", "2011-12"),
    "extension": ("2012-01", "2025-12"),
}
COLORS = {
    "Unmanaged": "#404040",
    "Historical": "#0072B2",
    "EWMA": "#009E73",
    "GARCH": "#D55E00",
}

def month_end(s):
    return s.groupby(s.index.to_period("M")).last()

def inputs():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))
    daily = build.daily_reconstructed["WML"]
    monthly = build.monthly_reconstructed["WML"]
    forecasts = {
        "Historical": month_end(historical_volatility(daily, window=126, trading_days_per_month=21)),
        "EWMA": month_end(ewma_volatility(daily, decay=0.94, initialization_window=126, trading_days_per_month=21)),
    }
    return root, daily, monthly, forecasts

def main():
    root, daily, monthly, base = inputs()
    output = root / "outputs" / "paper_figures"
    output.mkdir(parents=True, exist_ok=True)
    panels = {}
    for label, (start, end) in PERIODS.items():
        months = pd.period_range(start, end, freq="M")
        garch = pd.read_parquet(root / "outputs" / "garch" / f"{label}_garch_monthly_volatility.parquet")["garch_monthly_volatility"]
        forecasts = {**base, "GARCH": garch}
        returns = pd.DataFrame({"Unmanaged": monthly.reindex(months)})
        predicted = {}
        for name, forecast in forecasts.items():
            returns[name] = volatility_managed_momentum(monthly, forecast, target_volatility=0.12)["managed"].reindex(months)
            # Month-end t forecasts predict month t+1, so shift the PeriodIndex.
            predicted[name] = forecast.rename(index=lambda p: p + 1).reindex(months)
        pred = pd.DataFrame(predicted, index=months)
        realized = daily.pow(2).groupby(daily.index.to_period("M")).sum().pow(0.5).reindex(months)
        if not (returns.notna().all().all() and pred.notna().all().all() and realized.notna().all()):
            raise ValueError(f"Incomplete or misaligned monthly observations for {label}")
        if len(months) != (989 if label == "historical" else 168):
            raise AssertionError(f"Unexpected sample length: {label}")
        panels[label] = (returns, pred, realized)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.4), layout="constrained")
    for ax, (label, (returns, _, _)) in zip(axes, panels.items()):
        dates = returns.index.to_timestamp()
        for name in COLORS:
            wealth = (1 + returns[name]).cumprod()
            # Negative or zero wealth cannot be represented on a logarithmic axis.
            if (wealth <= 0).any():
                raise ValueError(f"Nonpositive wealth: {label}/{name}")
            ax.plot(dates, wealth, label=name, color=COLORS[name], linewidth=1.5)
        ax.set_yscale("log")
        ax.set_title(f"{'Historical' if label == 'historical' else 'Extension'} sample ({PERIODS[label][0]} to {PERIODS[label][1]})")
        ax.set_ylabel("Cumulative wealth (start = 1; log scale)")
        ax.grid(alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)
    fig.savefig(output / "cumulative_performance.pdf", bbox_inches="tight")
    fig.savefig(output / "cumulative_performance.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.4), layout="constrained")
    for ax, (label, (_, pred, realized)) in zip(axes, panels.items()):
        dates = pred.index.to_timestamp()
        ax.plot(dates, 100*np.sqrt(12)*realized.to_numpy(), color="#777777", alpha=0.65, linewidth=1, label="Realized")
        for name in ("Historical", "EWMA", "GARCH"):
            ax.plot(dates, 100*np.sqrt(12)*pred[name].to_numpy(), color=COLORS[name], linewidth=1.1, label=name)
        ax.set_title(f"{'Historical' if label == 'historical' else 'Extension'} sample")
        ax.set_ylabel("Monthly volatility, annualized (%)")
        ax.grid(alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)
    fig.savefig(output / "volatility_forecasts.pdf", bbox_inches="tight")
    fig.savefig(output / "volatility_forecasts.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved 2 PDF and 2 PNG figures to {output}")

if __name__ == "__main__":
    main()
