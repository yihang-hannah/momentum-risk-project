# Cost-aware momentum MVP

This additive engine reuses `data.py`, `volatility.py`, `strategies.py`, and
`metrics.py`. Existing replication modules and notebooks are unchanged.

From the repository root, using the existing Notebook 02 raw decile caches:

```bash
uv run python -m momentum_risk_project.cli \
  --daily data/raw/02_kf_momentum_deciles_daily_vw.parquet \
  --monthly data/raw/02_kf_momentum_deciles_monthly_vw.parquet \
  --raw-deciles --start 1927-05 --end 2011-12 \
  --transaction-cost-bps 10 --financing-cost-bps 100 \
  --output-dir outputs/backtest_10bps_100fin
uv run pytest tests/ -v
```

Use a new output directory on each run. The CLI refuses to overwrite an existing
directory. It writes `monthly_ledger.csv`, `summary.csv`, and `run.json` with
parameters, input-series SHA256 fingerprints, coverage and pandas version.
Use `uv sync --frozen` to recreate the locked environment. Omit the two file
arguments to use the standard `data.py` cache/download loader; this may download
and populate its normal caches. Explicit files make an offline run reproducible.
Returns must be decimals with a `mom` column, daily DatetimeIndex and consecutive
monthly PeriodIndex. The CLI does not infer percent units or silently fill gaps.

## Accounting conventions

The 126-day squared-return estimator produces monthly volatility. Month-end
estimates are lagged exactly once through the existing strategy implementation.
Default annual volatility target is 12%; `--leverage-cap` optionally caps applied
managed exposure. Both strategies use the same investable evaluation months.
Risk warm-up uses history before `--start`; each selected investment episode
starts from zero exposure, including its own entry charge.

For WML exposure w, the idealized long and short legs are +w and -w:

- Gross return = w * monthly WML return.
- Traded-notional proxy = 2 * abs(w - previous_w).
- Transaction cost = proxy * transaction_cost_bps / 10,000.
- Financing cost = max(abs(w) - 1, 0) * financing_cost_bps / 10,000 / 12.
- Net return = gross return minus both costs.

Transaction bps is per dollar traded per side, not a round-trip quote. The first
month pays entry on both legs; no terminal liquidation is modeled. Financing is
an optional annual simple spread on factor exposure above one, an explicit
scenario convention rather than a full funding model. Defaults are zero costs.
The unmanaged factor consequently pays entry only in this proxy model.

## Interpretation and limits

Factor returns do not reveal stock holdings. This proxy measures changes in
factor scale only: it omits constituent reconstitution, weight drift, ongoing
winner/loser turnover, spread variation, market impact, capacity, short-stock
borrow fees, rebates, cash yield, margin and forced liquidation. Even constant
factor exposure trades underlying stocks. These results are conditional cost
sensitivities and cannot establish implementable net alpha; unmanaged costs are
particularly understated. Real turnover requires aligned security-level holdings
and pre-trade drift-adjusted weights. Existing stock-level research is preserved
for that future extension.

Financing must not be interpreted as the full cost of funding the two legs.
A 1x factor exposure already has 2x gross notional. Change the financing model
explicitly if a broker's margin or borrow convention is required.

Gross and net metrics use the existing zero-risk-free-rate implementation.
Returns at or below -100% leave arithmetic statistics available but invalidate
wealth metrics and the entire corresponding wealth column. There is no account
or liquidation simulator. Fixed historical parameters are an in-sample scenario,
not an out-of-sample trading result or an exact net-of-cost paper replication.

`--raw-deciles` uses `data.clean_momentum` to convert percent-unit ten-decile
tables to decimal P10-P1. Without it, files must already contain decimal `mom`.
The older `01_momentum_*` caches are not the validated Notebook 02 input;
do not infer factor identity from their generic column names.

## Validated local run

On the cached Notebook 02 deciles, May 1927–December 2011 (1,016 months),
12% target and no leverage cap, gross unmanaged annual mean/Sharpe are
14.8597%/0.541876 and gross managed are 16.6949%/0.995810, agreeing with
the existing replication snapshot. At 10 bps per traded side and 100 bps
annual incremental financing, managed net mean is 16.4176%, volatility
16.7533%, Sharpe 0.979963 and maximum drawdown -43.8782%.
Unmanaged net mean is 14.8573% and Sharpe 0.541793; its near-zero ongoing
cost is a limitation of the proxy, not evidence that momentum is cheap to trade.
The input fingerprints and detailed ledger are in the new
`outputs/04_backtest/` directory.
