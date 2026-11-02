from pathlib import Path
import pandas as pd

ROOT = Path("outputs/garch")
OUT = ROOT / "latex"
OUT.mkdir(parents=True, exist_ok=True)

performance = pd.read_csv(ROOT / "comparison_portfolio_performance.csv")
accuracy = pd.read_csv(ROOT / "comparison_forecast_accuracy.csv")
significance = pd.read_csv(ROOT / "comparison_forecast_significance.csv")

PERIODS = ["1929-2011", "2012-2025"]
PERIOD_LABELS = {
    "1929-2011": "August 1929--December 2011",
    "2012-2025": "January 2012--December 2025",
}
STRATEGIES = {
    "unmanaged": "Unmanaged momentum",
    "historical": "Historical volatility (126-day)",
    "garch": "GARCH(1,1)",
}

def save(name, content):
    path = OUT / name
    path.write_text(content + "\n", encoding="utf-8")
    print("Saved:", path)

def pct(x):
    return f"{100 * x:.2f}"

# Table 1: Portfolio performance
lines = [
    r"\begin{table}[htbp]",
    r"\centering",
    r"\caption{Momentum Portfolio Performance: Historical and Extension Samples}",
    r"\label{tab:garch_portfolio_performance}",
    r"\small",
    r"\begin{tabular}{lrrrrr}",
    r"\toprule",
    r"Strategy & Return (\%) & Volatility (\%) & Sharpe & Max DD (\%) & Exposure \\",
    r"\midrule",
]

for period in PERIODS:
    subset = performance.set_index(["Period", "Strategy"])
    lines.append(
        rf"\multicolumn{{6}}{{l}}{{\textit{{{PERIOD_LABELS[period]}}}}} \\"
    )
    for strategy, label in STRATEGIES.items():
        row = subset.loc[(period, strategy)]
        lines.append(
            f"{label} & "
            f"{pct(row['Annualized Mean Return'])} & "
            f"{pct(row['Annualized Volatility'])} & "
            f"{row['Sharpe (rf=0)']:.3f} & "
            f"{pct(row['Maximum Drawdown'])} & "
            f"{row['Average Exposure']:.3f} "
            + r"\\"
        )
    if period != PERIODS[-1]:
        lines.append(r"\midrule")

lines += [
    r"\bottomrule",
    r"\end{tabular}",
    r"\par\vspace{0.3em}",
    r"\begin{minipage}{0.95\linewidth}",
    r"\footnotesize\textit{Notes:} Gross returns, without transaction costs or financing costs. "
    r"Annualized return is the arithmetic mean multiplied by 12; Sharpe ratios assume "
    r"a zero risk-free rate. Volatility-managed strategies target 12\% annualized volatility. "
    r"All strategies are evaluated on identical months within each sample.",
    r"\end{minipage}",
    r"\end{table}",
]
save("portfolio_performance.tex", "\n".join(lines))

# Table 2: Forecast accuracy
lines = [
    r"\begin{table}[htbp]",
    r"\centering",
    r"\caption{Out-of-Sample Volatility Forecast Accuracy}",
    r"\label{tab:garch_forecast_accuracy}",
    r"\small",
    r"\begin{tabular}{lrrrr}",
    r"\toprule",
    r"Estimator & MAE & RMSE & Bias & Correlation \\",
    r"\midrule",
]

for period in PERIODS:
    lines.append(
        rf"\multicolumn{{5}}{{l}}{{\textit{{{PERIOD_LABELS[period]}}}}} \\"
    )
    subset = accuracy[accuracy["Period"] == period].set_index("Estimator")
    for estimator, label in [
        ("historical", "Historical volatility (126-day)"),
        ("garch", "GARCH(1,1)"),
    ]:
        row = subset.loc[estimator]
        lines.append(
            f"{label} & {row['MAE']:.4f} & {row['RMSE']:.4f} & "
            f"{row['Bias']:.4f} & {row['Correlation']:.3f} "
            + r"\\"
        )
    if period != PERIODS[-1]:
        lines.append(r"\midrule")

lines += [
    r"\bottomrule",
    r"\end{tabular}",
    r"\par\vspace{0.3em}",
    r"\begin{minipage}{0.9\linewidth}",
    r"\footnotesize\textit{Notes:} Forecasts formed at month-end are compared with "
    r"the following month's realized volatility, measured as the square root of "
    r"the sum of squared daily momentum returns. Both estimators use the same "
    r"forecast origins within each period.",
    r"\end{minipage}",
    r"\end{table}",
]
save("forecast_accuracy.tex", "\n".join(lines))

# Table 3: HAC significance
lines = [
    r"\begin{table}[htbp]",
    r"\centering",
    r"\caption{Statistical Significance of GARCH Forecast Improvements}",
    r"\label{tab:garch_forecast_significance}",
    r"\small",
    r"\begin{tabular}{lrrrr}",
    r"\toprule",
    r"Sample & Months & Mean Loss Diff. & HAC $t$ & $p$-value \\",
    r"\midrule",
]

for period in PERIODS:
    row = significance.set_index("Period").loc[period]
    lines.append(
        f"{PERIOD_LABELS[period]} & "
        f"{int(row['Observations'])} & "
        f"{row['Mean Loss Difference']:.6f} & "
        f"{row['HAC t-statistic']:.3f} & "
        f"{row['Two-sided p-value']:.4f} "
        + r"\\"
    )

lines += [
    r"\bottomrule",
    r"\end{tabular}",
    r"\par\vspace{0.3em}",
    r"\begin{minipage}{0.9\linewidth}",
    r"\footnotesize\textit{Notes:} The loss differential equals the squared "
    r"forecast error of historical volatility minus that of GARCH(1,1). "
    r"Positive values favor GARCH. Inference uses heteroskedasticity- "
    r"and autocorrelation-consistent (HAC) standard errors with three lags. "
    r"Reported $p$-values are two-sided.",
    r"\end{minipage}",
    r"\end{table}",
]
save("forecast_significance.tex", "\n".join(lines))

print("\nGenerated all three LaTeX tables successfully.")
