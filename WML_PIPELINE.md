# Current WML construction API

The authoritative implementation of Notebook 03's current method is
`momentum_risk_project.wml_pipeline`. Notebook 05 should use this API or its
fingerprinted artifacts, rather than copy cells or call a historical experiment.
Notebook 02 remains unchanged on GitHub main.

## Build once, use in Notebook 05

```python
from pathlib import Path
import pandas as pd
from momentum_risk_project.wml_pipeline import (
    build_from_cache, rebuild_daily, estimate_risk, save_build, load_build,
)

build = build_from_cache(
    Path('data/raw/03_stock_full_20261031'), start='1927-01', end='2025-12',
)
rebuild_daily(build, Path('data/raw/03_quality_daily_20261031'))
save_build(build, Path('data/processed/wml_new'))  # New path; no overwrites.

# Notebook 05:
build = load_build(Path('data/processed/wml_current_v1_20261031'))
months = pd.period_range('2012-01', '2025-12', freq='M')
weights = pd.Series(1.0, index=months)  # Unmanaged example.
ledger, trades = build.backtest(
    weights, return_policy='dm', transaction_cost_bps=10, financing_cost_bps=0,
)
stock_targets = build.targets(weights)
```

The strict DM account stops at an unknown valuation. It does not restart or fill
unknowns with cash. For the explicitly conditional complete published-return
reference, choose `return_policy='published_reference'`. The policy argument is
required; there is no automatic fallback. Complete gross/reference comparisons
must use the same calendar and the same chosen risk weights for both WML series.
A factor weight of one means +1 winner and -1 loser notional, gross two.

`build.backtest` returns the existing funded stock-account calculation, including
entries, exits, drifted prior positions, proportional fees and delisting settlement.
`trades` includes PERMNO, month, pretrade and post-fee target weights, signed trade
weight and absolute traded notional. Fees are paid from NAV; target holdings are
scaled after costs. Financing defaults to zero; the optional incremental
above-one factor-weight spread remains a simplified scenario, not brokerage terms.

Each call starts at NAV one with no positions. To retain continuity across study
windows, run once over a consecutive full calendar and then evaluate ledger
subperiods. Monthly weights must be sorted, unique, consecutive, nonnegative and
finite. Missing weights raise; they never silently become zero exposure.

## Returned data

`WMLBuild` contains:

- `holdings`: all monthly deciles; PERMNO, formation and holding months, formation
  capitalization, momentum rank, decile, normalized leg weight, observed total
  and ex-distribution returns, source flags, delisting evidence, valuation columns
  and explicit imputation masks. Treat this as read-only; rebuild after changing
  formation policy. `account_holdings(policy)` returns a separate policy-specific
  copy suitable for account evaluation.
- `breakpoints`: NYSE monthly decile boundaries.
- `monthly_dm`: P1–P10 and WML under ordinary-zero / known-payoff-once policy;
  unknown terminal values remain NaN.
- `monthly_reference`: published numeric returns with numeric monthly gaps zero;
  unconfirmed terminal values remain a material qualification.
- `daily`: optional checked daily leg returns/WML and unknown/imputation counts.
- `audit`, `provenance`: policy, coverage-universe digest, parameters and input/code
  fingerprints. Source credentials are never included.

`estimate_risk(build.daily.WML, months)` returns previous-month monthly-unit sigma,
forecast availability and the next-month weight. It uses 126 squared daily simple
returns, 21 sessions per month, 12% annual target, no demeaning and no cash fill.
Input must follow the complete trading calendar, with unknown observations NaN.

Artifacts use schema version 1: holdings, breakpoints, monthly DM/reference,
optional daily Parquets and `manifest.json`. `load_build` checks file fingerprints,
schema and membership. Keep licensed holdings/trades under ignored `data/` paths.

## Current construction rules

The builder composes `ciz_quality`, `ranking`, `stock_reconstruction` and
`daily_portfolio`; the account composes `stock_backtest`.

- Formation-date common-stock/exchange eligibility, historical codes and labelled
  post-2024 CIZ mapping; no opening already-delisted issues.
- Usable period-end TR/BA price and market equity, including t-13 price validation;
  NS only when its actual price date is period-end. No blanket red/yellow deletion.
- t-12..t-2 momentum, skip t-1, NYSE cutoffs, value weighting. The CIZ missing-price
  ranking adapter retains its documented legacy-code-equivalence limitation.
- Ordinary missing returns zero under the selected convention; known recorded
  delisting payoff once; unknown/partial terminal information stays unknown.
- Checked daily mode additionally protects special missing corporate values and
  multi-session P1–P9 returns; one-session weekend/holiday codes remain valid.
- Known late payoff attribution is research event accounting, not proof of
  point-in-time cash receipt. Monthly distribution/price-drift timing is approximate.

Full flag definitions and policy are in `CIZ_FLAGS.md`.

## Rebuild and cache safety

```bash
uv run python -m momentum_risk_project.wml_pipeline \
  --cache-dir data/raw/03_stock_full_20261031 \
  --daily-cache-dir data/raw/03_quality_daily_20261031 \
  --output-dir data/processed/wml_new
uv run pytest tests/ -q
```

Omit `--daily-cache-dir` for a monthly-only artifact. Daily rebuilding requires a
complete cache with a matching requested-universe digest, either in its extraction
manifest or a verified `membership_manifest.json`. Actual missing provider records
are different from stock-months never requested. Old selected caches are refused
when coverage differs; absent rows are not automatically legitimized as zeros.
Build the full attested universe once, then select backtest windows through weights.

New WRDS extractions use this same construction API to select daily memberships,
record their digest and default to December 1925–December 2025. Existing historical
complete caches remain fingerprint-verifiable without being rewritten. A legacy
partial extraction without attested membership cannot be mixed into a new run.

`stock_cli.run_research` and the earlier `aligned_comparison` experiment remain
historical code for reproducing archived outputs; they are not the current WML
construction API. The latest formation-quality script delegates construction,
valuation and stock costs to `wml_pipeline`; the DM daily script also reuses its
valuation and risk functions. No Notebook 05 has been created by this refactor.

## Notebook 05 stock-cost study

`notebooks/05_reconstructed_wml_stock_cost_backtest.ipynb` loads the current
fingerprinted build without reconstructing or changing Notebook 03. Run
`python scripts/run_stock_cost_study.py --cost-bps 0 5 10 25 50` offline.

`paper_turnover.appendix_b_turnover` implements Appendix B's normalized-leg
total-return drift and half absolute weight changes. It includes old/new stock
unions and leg switches. The local manuscript prints inverse L in managed
equation 10, inconsistent with multiplied-L return exposure. Both literal
inverse-L and scaled-position diagnostics are explicit; neither is silently
claimed to be the author's verified implementation. The actual funded account
retains common-NAV/ex-distribution drift and self-funded fees.

One-way per-dollar costs are twice as large when quoted as roundtrip rates.
The study includes the paper's distinct 1951-03 to 2010-12 turnover-test window,
plus the accepted historical and disjoint extension windows. Full accounts run
continuously; subperiods do not introduce new entry fees. The significance
cutoff uses a labeled IID Student-t test, not an asserted paper-exact SE method.

Complete results remain published-return references using shared KF risk.
Unknown strict monthly/daily valuations are preserved, and missing own-risk
forecasts are never interpreted as cash. Licensed stock transition and trade
files stay under ignored `data/processed/05_stock_backtest`; figures and monthly
results are in `outputs/05_stock_backtest`.
