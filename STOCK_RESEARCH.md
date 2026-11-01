# Current stock-level WML research

## Production path

`configs/config.yaml` → ordered scripts 01–04 → `pipeline.py` → current
`wml_pipeline.py` construction and `study.py` accounts/evaluation → scope-separated
`results/replication` and `results/extension`. Notebooks are documentation,
exploration and independent/API checks; no reported result requires running one.
The definitive processing specification and official links are at the beginning
of Notebook 03. See WML_PIPELINE.md for the artifact API and CIZ_FLAGS.md for
field-specific definitions (774 frozen values across 62 types).

## Sources and classification

Frozen authorized annual CRSP/WRDS extracts contain monthly observations,
historical name classifications, daily selected-universe components, delisting
events and the independent exchange calendar. Provider extraction bytes and their
original manifests stay in data/raw. Validated required fields are staged in
data/interim/stock_inputs, and final holdings/returns live in the configured
processed build. Public KF monthly/daily value-weighted deciles and FF3 remain
separate independent inputs. Provider vintages are not proven identical to KF
or the paper merely because both use CIZ.

Use historical share 10/11 and exchange 1/2/3 at formation. After 2024, explicitly
label the qualified CIZ common-share/active/exchange adapter where historical
codes are unavailable. It is not silently substituted for observed historical
classifications. Reject already-delisted formation records but retain
holding-month delistings for valuation.

## Ranking and endpoint quality

Rank on t-12 through t-2, skip t-1, require the t-13 endpoint price and good t-2
return, and allow only the specified intermediate missing-price case. The CIZ
NT/MP/missing-price/N adapter is not proven equivalent to the legacy -99 code.
NYSE decile cutoffs use explicit pandas interpolation and lower-side tie handling.
Weights use positive t-1 market equity. WML is +1 P10 and -1 P1, gross two.

Formation and t-13 prices must satisfy actual period-end date equality, positive
finite prices and TR/BA price types. NS is accepted only on the actual period-end;
LA/stale or other substitute prices do not establish an endpoint. Red/yellow
completeness alone does not delete all observations. Screening formation prices
does not rewrite holding-month returns.

## Returns and uncertainty

The strict DM-aligned policy sets ordinary active/no-event numeric gaps to zero
under the accepted research assumption, includes recoverable known terminal
payoffs once, and preserves partial/unknown terminal values. A/P aggregate
terminal components are not added again; G/M components are recovered only when
recorded/valid; V remains partial. Known later payoffs attributed to the event
month are research attribution, not proof of contemporaneous cash settlement.

The complete published-return reference retains numeric provider aggregates and
fills numeric gaps with zero. It is explicitly conditional on unconfirmed
terminal values and is not an automatic fallback. Unknown weighted stocks
invalidate a strict leg; surviving weights are not renormalized. Monthly WML is
monthly P10 minus P1, not compounded daily long-short returns or price-only ratios.

Checked daily reconstruction fixes monthly membership, aligns real CRSP sessions,
separately combines regular/Y components and protects multi-session/corporate-action
or unknown terminal cases. Its ordinary-zero rule is not an official universal
missing-return rule. Post-settlement proceeds stay in cash within the month.
The >200-session price-gap audit uses an independent calendar and restores
eligibility at the quoted reopening boundary; it adds no otherwise-eligible
monthly exclusions in the current sample. KF's daily deciles instead reform daily.

## Risk, costs and conclusions

Risk is sqrt(21 times the last 126 daily squared WML returns' mean), without
demeaning. The prior month's final session determines the next holding-month
weight targeting 12% annual volatility. Missing forecasts are unknown, not cash.
Strict own-stock diagnostics remain incomplete. The complete primary component-zero series supplies its own risk; missing forecasts never fall back to KF or cash.

Complete primary comparisons use independently reconstructed daily risk and the explicit component-zero/known-payoff scenario. KF is independently risk-managed from its own daily series.
Actual stock fees apply to entries/exits/drift with after-fee NAV targets;
Appendix B half-turnover is a separate leg-normalized diagnostic. Keep the
literal inverse-L and economically scaled-position conventions distinct. Stock
financing is zero; the factor-level Notebook 04 lab's illustrative financing
spread is a separate scenario. Borrow/rebates, capacity and actual delayed cash
availability are not identified.

Historical common evaluation is 1927-07–2011-12; the paper's distinct turnover
check is 1951-03–2010-12; extension is 2012-01–2025-12. Extension risk mitigation
persists, but profitability is weak. Unknown payoffs, early warm-up and source
vintage limitations survive a successful software refactor.

## Preserved diagnostics

August 1935's stale American Express formation quote motivated the general
endpoint screen: current rebuilt WML is about -18.323% versus KF -18.320%.
Historical reference MAE is about 13.91bp; extension about 47.43bp. Original
attribution, flags, version comparisons, experiment scripts and notebook snapshots
remain under private data/interim history or Git history. They are optional audit
evidence rather than prerequisites for rebuilding current results.

## Primary policy update

The complete primary scenario fills missing stock components and unknown terminal
increments with zero, with explicit diagnostic counts; it does not declare
unknown final values observed. Known terminal components are included once.
Multi-session numeric components are booked once on their observed endpoint.
Both KF and rebuilt strategies now use separate own-source risk estimates. The
old shared-risk study is archived privately and is no longer the primary result.
