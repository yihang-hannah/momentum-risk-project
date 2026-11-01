# Current stock-level WML workflow

## Authoritative implementation and Notebook 05 contract

Current construction is packaged in `src/momentum_risk_project/wml_pipeline.py`.
Notebook 03 now calls `build_from_cache`, `rebuild_daily` and `estimate_risk`, then
validates the full monthly/daily series against the verified reconstruction.
Notebook 05 can load `data/processed/wml_current_v1_20261031/` with `load_build` and
call `build.backtest` to get monthly accounts plus actual stock trades. Return
policy (`dm` or `published_reference`) is mandatory. Unknowns never become cash.
See `WML_PIPELINE.md` for schema, CLI and examples.

Current API-based reference account results are in
`outputs/03_wml/report/`. These accounts use attached delisting
evidence for settlement; earlier reference fee ledgers without that evidence
are retained as historical results rather than reused as the current costs.
The source monthly WML and checked daily WML remain numerically validated.
WRDS new extraction selects daily membership through the same current builder;
old partial caches without attested membership are not mixed into new runs.

## Frozen construction and prior verification details

`notebooks/03_wml_construction.ipynb` is the English construction and backtest
report. It opens with the processing steps, source tables, documented rules,
selected valuation conventions and limits. Notebook 02 is byte-identical to
verified GitHub `main` commit `1437301c19cbffb787c253a5f3b9a7727eca3dae`.
Previous notebooks, local Notebook 02 edits and research notes are archived under
`notebooks/archive/`. Notebook 04 and the original factor-level engine are preserved.

## Frozen inputs and process

1. Use the authorized WRDS annual CRSP cache at
   `data/raw/03_stock_full_20261031/`. It contains 5,240,606 monthly observations,
   22,463,849 selected-stock daily observations, the CRSP calendar, historical
   classifications, delisting records and 106 fingerprinted Parquet files.
   Queries are read-only. Credentials are never copied into the cache.
2. Form monthly common-stock deciles using formation-date share codes 10/11,
   exchange codes 1/2/3, t-13 price, good t-2 return, positive t-1 market equity,
   t-12 through t-2 momentum and NYSE cutoffs. Stocks are value weighted within
   each leg. Current CIZ fields map post-2024 classifications; source labels remain.
3. Ordinary missing daily/monthly returns are zero under the selected convention.
   Known delisting returns are included once. Unknown or partial terminal values
   remain unknown. The zero convention is not attributed to KF or DM.
4. Rebuild daily returns separately for each monthly-formed leg, then subtract.
   Monthly WML is the difference of the monthly leg returns, not compounded daily
   WML. Forecast monthly volatility as sqrt(21 * mean(last 126 squared daily WML
   returns)); use the 12% annual target and next-calendar-month execution.
5. Evaluate the fully available common window May 1927-December 2011 and the
   disjoint extension January 2012-December 2025. The paper's March-April 1927 risk forecasts lack the
   available public early daily warmup; no zeros or shorter windows manufacture it.

## Result scopes

- **Complete published-return reference:**
  `data/processed/reference/pre_quality/`. Numeric monthly gaps are zero; published
  numeric values are retained even where final payoffs are unconfirmed. KF and
  reconstructed monthly returns share KF daily risk weights. This controlled
  monthly comparison is not a fully reconciled independent stock-risk backtest.
- **Current DM-aligned calculation:** `outputs/03_dm_zero_daily_20261031/`.
  Ordinary daily components are zero-filled; known terminal payoffs are retained
  once; unresolved terminal values remain missing. Missing risk is never cash.
  Full-window independent metrics are withheld. Paper-era risk availability is
  247/1016 months; extension availability is 21/168 months.
- **Current notebook report:** `outputs/03_current_report_audited_20261031/`.
  Recomputed complete reference metrics, current paired-month error diagnostics,
  coverage, stock costs/turnover and input fingerprints. Paired error diagnostics
  do not imply a compounded performance path over missing months.

Stock-reference trading fees are 10bp per dollar of absolute stock trades,
financing zero. Targets use post-fee NAV; entries, exits and price drift are
included. Monthly distributions enter cash as an approximation. No terminal
liquidation fee, short-borrow/rebate model, capacity model or actual delayed cash
settlement is claimed. Late recorded payoffs retain event attribution for research.

The large August 1935 residual (about 26.9 percentage points) is attributed
primarily to a formation-value/date mismatch: a CIZ last-available July quote
was used as formation market equity despite missing legacy period-end price.
This is not a delisting or ordinary-zero-fill event. Section 6 of Notebook 03
shows both single-stock attribution and a general period-end screen with
recomputed NYSE cutoffs. These are diagnostics, not a validated full-sample
strategy correction. Extension reference MAE (about 47bp) remains material. Correlation alone is not
proof of exact replication. Current source vintage is not established to be the
same as the paper or KF's historical release.

## Reproduce offline

Run Notebook 03 from the repository or `notebooks/` directory. It reconstructs
monthly holdings from the frozen raw cache, checks a raw daily month, recomputes
risk weights and reference metrics, and validates the complete derived artifacts.
Existing identical report files are checked; differing existing files are preserved.

The full current daily reconstruction can be regenerated into a new directory:

```bash
uv run python scripts/run_dm_zero_risk.py \
  --cache data/raw/03_stock_full_20261031 \
  --holdings data/processed/reference/pre_quality/holdings_membership.parquet \
  --reference data/processed/reference/pre_quality \
  --output outputs/03_dm_zero_daily_new
uv run pytest tests/ -q
```

To rebuild the complete reference and holdings first, choose new paths:

```bash
uv run python -m momentum_risk_project.aligned_comparison \
  --cache-dir data/raw/03_stock_full_20261031 \
  --output-dir outputs/03_aligned_new \
  --private-dir data/processed/03_aligned_new \
  --kf-monthly data/raw/02_kf_momentum_deciles_monthly_vw.parquet \
  --kf-daily data/raw/02_kf_momentum_deciles_daily_vw.parquet \
  --transaction-cost-bps 10
```

Pass those new holdings/reference paths to the daily command, then update the
notebook's `REFERENCE`, `CURRENT` and `REPORT` constants. Keep licensed identities
in ignored `data/` paths. New extraction requires the existing authorized WRDS
login and annual CRSP access:

```bash
uv run python -m momentum_risk_project.wrds_stock \
  --cache-dir data/raw/03_stock_full_new \
  --start 1925-12-01 --end 2025-12-31
```

Repeat the same extraction command with `--resume` only for a documented cache.
Completed caches are fingerprint-validated offline; incompatible existing files
are refused. Use `uv sync --frozen` to restore locked dependencies.

## References

- [KF monthly deciles](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_10_port_form_pr_12_2.html)
- [KF daily deciles](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_10_port_form_pr_12_2_daily.html)
- [KF CIZ and data-library notes](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- [DM construction, delisting and monthly membership](https://www.kentdaniel.net/data/momentum/mom_data.pdf)
- [CRSP return-quality flags](https://www.crsp.org/wp-content/uploads/appendix/FlagType_AR.html)
- [CRSP delisting flags](https://www.crsp.org/wp-content/uploads/appendix/FlagType_DE.html)
- [CRSP share-code mapping](https://www.crsp.org/wp-content/uploads/ShareCode.html)
- [WRDS CIZtoSIZ mapping](https://wrds-www.wharton.upenn.edu/pages/wrds-research/macros/crsp-ciztosiz-macro/)
- [Barroso-Santa-Clara, Equations 5-6](https://www.sciencedirect.com/science/article/pii/S0304405X14002566)


## August 1935 attribution audit

Results: `outputs/03_wml/diagnostics/august1935/`; raw security evidence stays
under `data/processed/03_aug1935_audit_verified_20261031/`. The affected security
is American Express. Its July CIZ quote is dated July 29, with LA/R/R1 flags;
legacy July price/return are missing. It receives 36.47% of the August loser leg.
The CIZ July/August compounded return equals the legacy August return, so the
values cannot be swapped without checking return horizons.

Omitting this security while keeping other memberships fixed changes reference
WML from +8.58% to -18.28% (KF -18.32%). A general period-end formation-value
screen with recalculated NYSE cutoffs gives -18.41%. A full-sample eligibility
change would require new breakpoints, memberships, daily inputs and cost accounts;
no single-stock deletion or altered official backtest is hidden in this audit.

```bash
uv run python scripts/audit_august1935.py \
  --output outputs/03_aug1935_audit_new \
  --private-output data/processed/03_aug1935_audit_new
```

Flag sources: [CRSP aggregate dates](https://www.crsp.org/wp-content/uploads/appendix/FlagType_AG.html),
[completeness](https://www.crsp.org/wp-content/uploads/appendix/FlagType_CF.html),
[sub-flags](https://www.crsp.org/wp-content/uploads/appendix/FlagType_CG.html).


## Current CIZ quality checks (2026-10-31)

See `CIZ_FLAGS.md` for field-level definitions and policy; the complete frozen
774-label/62-type dictionary and 136 mapped pipeline definitions are in
`outputs/03_wml/diagnostics/ciz_flags/`. Current PC web additions SU/HA are recorded
in the guide and rejected as formation-price substitutes.

The `mthdtflg`, `mthcompflg`, `mthcompsubflg` fields are distinct. The current
formation/t-13 screen requires actual period-end price dates and TR/BA prices;
NS is usable only when the actual date is also period-end. It masks unusable
formation inputs without altering observed holding returns or raw source files.
The quality screen excludes 6,080 old all-decile stock-month memberships, including
2,117 previously in P1/P10 (1,361 stocks). These are month-specific exclusions.
The subset specifically attributable to LA comprises 2,987 all-decile and 1,062
P1/P10 records. Recalculated NYSE cutoffs and normalized weights are used globally.

Current monthly reference results: `outputs/03_wml/validation/formation_quality/`.
Historical MAE falls from 19.38bp to 13.91bp, correlation rises to 0.99915, and
August 1935 WML becomes -18.323% versus KF -18.320%. Extension MAE remains
47.43bp, so the screen does not resolve all reconstruction differences.

New membership daily inputs are in `data/raw/03_quality_daily_20261031/`, reusing
fingerprinted immutable source observations and adding 10,507 WRDS daily rows.
The strict `zero_regular_dm_checked` mode protects missing corporate actions,
terminal information and P1-P9 multi-session returns. D2/D3/D4/DU are one trading
session and retained. Old-cohort audit found 9,213 ordinary multi-session records
and 78 ordinary special-missing records. Current strict daily results:
`outputs/03_wml/validation/checked_daily/`; no complete month-end 126-session stock-risk
forecast is available under this treatment. Missing forecasts are not cash and
full independent managed metrics are withheld. Shared-KF-risk monthly reference
backtests remain fully reported. Earlier cache results retain their old mode.

```bash
uv run python scripts/formation_quality_backtest.py \
  --output outputs/03_formation_quality_new \
  --private-output data/processed/03_formation_quality_new
uv run python scripts/run_dm_zero_risk.py \
  --cache data/raw/03_quality_daily_20261031 \
  --holdings data/processed/wml_current_v1_20261031/holdings.parquet \
  --reference outputs/03_wml/validation/formation_quality \
  --output outputs/03_quality_DM_checked_new --daily-mode zero_regular_dm_checked
```

Notebook 02 remains identical to GitHub main. Notebook 03 records current quality
rules, new-universe reference results and strict daily limitations in English.
