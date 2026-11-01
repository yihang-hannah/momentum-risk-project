# GARCH(1,1) Extension — Empirical Results

## 1. Research objective

Evaluate whether replacing the historical volatility estimator in
Barroso and Santa-Clara's "Momentum Has Its Moments" with a rolling
GARCH(1,1) model improves volatility forecasting and the risk-adjusted
performance of volatility-managed momentum.

## 2. Data and methodology

- Data: Independently reconstructed CRSP daily and monthly WML returns.
- Evaluation period: January 2012 – December 2025 (168 months).
- Historical estimator: 126-day rolling mean squared daily returns,
  scaled to 21 trading days.
- GARCH estimator: Gaussian GARCH(1,1), zero conditional mean.
- GARCH estimation window: 756 trading days.
- Forecast horizon: 21 trading days.
- Annual volatility target: 12%.
- Portfolio weights: Determined using the previous month-end forecast.
- Returns: Gross of transaction costs and financing charges.

## 3. Portfolio performance

| Metric | Unmanaged | Historical | GARCH |
|---|---:|---:|---:|
| Annualized mean return | 4.63% | 4.20% | 4.13% |
| Annualized volatility | 27.15% | 12.47% | 12.99% |
| Sharpe ratio | 0.1706 | 0.3368 | 0.3177 |
| Maximum drawdown | -63.29% | -22.51% | -25.86% |
| Average exposure | 1.0000 | 0.5222 | 0.5304 |

Correlation between historical and GARCH volatility forecasts: 0.8499.

## 4. Volatility forecasting accuracy

Realized monthly volatility is calculated as the square root of the
sum of squared daily WML returns within the subsequent calendar month.

| Metric | Historical | GARCH |
|---|---:|---:|
| MAE | 0.022692 | 0.020138 |
| RMSE | 0.031546 | 0.029090 |
| Forecast bias | 0.002343 | 0.001250 |
| Correlation with realized volatility | 0.6618 | 0.7129 |

GARCH reduces MAE by approximately 11.3% and RMSE by approximately 7.8%.

## 5. Statistical significance

Test: Paired squared forecast-loss differential.

Loss differential:
d_t = historical_error_t^2 - garch_error_t^2

Inference: OLS intercept test with HAC (Newey-West) standard errors,
using three monthly lags.

- Mean loss differential: 0.00014894
- HAC t-statistic: 1.0085
- Two-sided p-value: 0.3132
- 95% confidence interval: [-0.00014053, 0.00043841]

Interpretation: The observed improvement in GARCH forecast accuracy
is not statistically significant at conventional levels.

## 6. Preliminary conclusion

Both volatility-managed strategies improve risk-adjusted performance
relative to unmanaged momentum.

GARCH produces lower volatility forecast errors than the historical
estimator but slightly worse portfolio performance.

The results suggest that greater volatility forecasting accuracy does
not necessarily translate into better volatility-managed momentum
performance. Further robustness analysis is required.

## 7. Limitations and planned robustness checks

- Compare forecast horizons consistently: fixed 21-day forecasts
  versus realized volatility over calendar months of varying length.
- Test alternative GARCH estimation windows.
- Examine leverage constraints.
- Evaluate the statistical significance of portfolio performance differences.
- Assess sensitivity to volatility regimes and sample periods.
- Consider transaction costs and financing assumptions.
- Automate the generation of all results from the repository.

## 8. Reproducibility

GARCH forecasts:
outputs/garch/extension_garch_monthly_volatility.parquet

GARCH implementation:
src/momentum_risk_project/garch.py

Status: Results recorded from interactive experiments.
Automated results generation and regression tests remain to be implemented.
