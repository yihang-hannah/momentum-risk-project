# Current independent-risk WML API

The primary method is in `wml_pipeline.py`, `daily_portfolio.py`, `risk_inputs.py`
and the package study/pipeline. Rebuilt positions use reconstructed daily WML
only; KF positions use KF daily WML only. `risk_inputs.independent_risk` requires
complete own-risk forecasts and raises on missing coverage. It has no KF/cash
fallback. Test this with `pytest tests/test_risk_inputs.py -q`.

## Build artifact and policies

Schema 2 preserves `holdings`, breakpoints, `monthly_dm`, `monthly_reference`,
`daily` (strict diagnostic), and adds `daily_reconstructed` (primary complete
zero-component scenario). `monthly_reconstructed` derives primary monthly legs
from holdings `return_reconstructed`. Old schema-1 artifacts remain readable as
diagnostics but cannot supply primary risk without rebuilding.

- Primary monthly return: prefer known DM-reconciled return; otherwise retain
  the published numeric aggregate; remaining numeric gaps are zero.
- Primary daily return: retain numeric provider components, recover recorded
  terminal components once, and fill missing stock components with zero.
- Unknown terminal *increments* are zero assumptions, not zero recovery values.
  The strict diagnostic still preserves unresolved values. Partial published
  components are retained; assumption counters remain available.
- Multi-session numeric components are booked once on the observed endpoint;
  unavailable intervening valuations are zero. This is a disclosed lumpy
  valuation approximation, not an official observed one-session return.
- Ordinary/special imputation, multi-session endpoints and uncertain terminal
  positions have separate diagnostic counts. Never fill a missing whole WML or
  substitute KF risk to make the series complete.

Formation filters, NYSE ranking, source membership attestations and raw-file
checksums are unchanged. Official rules and project assumptions are distinguished
at the beginning of Notebook 03 and in CIZ_FLAGS.md. Existing known delisting
amounts are included once; raw caches and historical metadata remain untouched.

## Reuse

```python
from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build, estimate_risk

root=project_root(); config=load_config(root=root)
build=load_build(configured_path(config,"build",root))
risk=estimate_risk(build.daily_reconstructed.WML, holding_months)
ledger,trades=build.backtest(
    risk.weight, return_policy="reconstructed_zero_missing",
    transaction_cost_bps=10, financing_cost_bps=0,
)
```

`holding_months` must be a complete consecutive monthly PeriodIndex with available
prior risk. `estimate_risk` already returns holding-month weights; no further lag.
Each account opens fresh at NAV one; run once over the full history and slice for
continuous-window evaluation. `dm` remains a strict diagnostic; `published_reference`
is the older published-aggregate diagnostic, not the primary scenario.

Rebuilt daily history starts January 1927. There are 124 sessions through May;
June is the first complete month-end 126-day estimate, applied in July. The common
historical window is July 1927–December 2011; both source strategies use exactly
those dates. The separate paper turnover test and 2012–2025 extension remain.

Run `python run_all.py --force-build` to rebuild schema-2 artifacts, then the
study and all result scopes. Unknown strict values remain diagnostics; they no
longer cause the primary strategy to borrow benchmark weights. Previous shared-KF
results are retained as a historical comparison, not advertised as own-risk.
