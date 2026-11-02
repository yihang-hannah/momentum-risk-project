# Momentum Risk Management

Replication and extension of Barroso and Santa-Clara (2015), *Momentum Has Its Moments*, Journal of Financial Economics. [Paper](https://doi.org/10.1016/j.jfineco.2014.11.010) · [Repository and team](https://github.com/yihang-hannah/momentum-risk-project) · [Contributors](https://github.com/yihang-hannah/momentum-risk-project/graphs/contributors).

## Current status and scientific scope

The repository now follows the course hierarchy: reusable logic in `src`, four thin ordered scripts, centralized configuration, separate intermediate/final data, rebuildable results and exploratory notebooks. See Git history for the published revision of this course-aligned layout. Historical notebooks and audits are preserved privately; no licensed observations are committed.

- **01:** explore the canonical KF daily/monthly decile-return inputs and validate their packaged loader.
- **02:** independently derive/check the paper equations and regressions against script-generated results; it is no longer the only source of reported FF3/FF4/timing results.
- **03:** document all data sources, field/flag rules and assumptions; inspect the package-built stock WML and script-generated KF comparisons. The complete processing specification and official links remain at its beginning.
- **04:** unpack the factor-scaling cost proxy for teaching and check the reusable engine/script report.
- **05:** display script-generated stock-cost results and validate short stock-account/API examples.
- **Frontend MVP (2026-11-01):** completed the English Streamlit research desk with sample/source/cost switching, interactive performance and trading charts, coverage explanations and CSV/JSON exports. Saved scenarios are verified against their own generated ledgers; primary strategies now use independent daily-risk sources. See [startup instructions](#research-frontend-mvp).

**Independent risk sources:** the rebuilt strategy now estimates risk only from
`daily_reconstructed.WML`, and KF estimates risk only from KF daily WML. There is
no KF-to-rebuilt fallback. Both use the same evaluation calendar and a 126-session
prior-month forecast, 21-session monthly scaling and 12% annual target.

**Missing-value scenario:** fill missing stock return components with zero, retain
published numeric components, and include recorded terminal components once. The
primary monthly return prefers known DM-reconciled payoffs before the published
aggregate. Unknown terminal *increments* are explicitly assumed zero; that does
not mean a zero liquidation value or an observed final payoff. Multi-session
numeric returns are booked once at their source endpoint, with unavailable
intervening observations zero. Strict unresolved-value diagnostics remain parallel.
No already-aggregated WML gaps, missing forecasts or non-existent prehistory are
filled with cash/zeros to force coverage.

The common historical comparison is **1927-07–2011-12**, not the former KF-only
May start. Reconstructed daily portfolios begin January 1927 and have only 124
sessions through May; June provides the first complete month-end forecast for
July. A read-only WRDS query confirms no monthly stock observations before
1925-12-31, so earlier full-rule holdings cannot be fabricated. The independent
KF benchmark is restricted to identical July-start dates. The 1951–2010 paper
turnover check and 2012–2025 extension are unchanged.

At 10bp per dollar traded, the updated independently managed rebuilt strategy
has historical annual mean **15.33%**, Sharpe **0.893**, and worst month **−29.09%**,
versus unmanaged **12.98%**, **0.472**, **−78.26%**. In 2012–2025 the corresponding
annual means are **3.27% vs 2.84%**, Sharpe **0.262 vs 0.105**, and worst month
**−12.23% vs −29.66%**. Risk mitigation persists while extension profits remain weak.
Old shared-KF-risk reports are preserved privately under
`data/interim/shared_kf_before_own_risk_20261101` and are not current primary results.

## Repository structure

```text
momentum-risk-project/
├── README.md
├── pyproject.toml / uv.lock
├── Makefile / run_all.py
├── configs/config.yaml
├── data/                         # Entire directory ignored; local licensed caches
│   ├── raw/                      # Unmodified provider downloads/query extracts
│   ├── interim/                  # Selected/validated fields, audit history, backups
│   └── processed/                # Final WML build and analysis-ready study datasets
├── src/momentum_risk_project/
│   ├── paths.py / config.py
│   ├── data.py / features.py
│   ├── models.py / evaluation.py / plotting.py
│   ├── pipeline.py / study.py
│   └── ...                       # Detailed existing WML, risk and account modules
├── scripts/
│   ├── 01_get_data.py
│   ├── 02_build_dataset.py
│   ├── 03_replicate.py
│   ├── 04_extend.py
│   ├── run_stock_cost_study.py    # Thin compatibility wrapper
│   └── validate_notebooks.py     # Optional display/API verification
├── app/streamlit_app.py           # Read-only research frontend
├── .streamlit/config.toml         # Local UI theme/server settings
├── notebooks/                    # Exploration/validation; never required for results
├── results/                      # Entirely generated/ignored; may be deleted/rebuilt
│   ├── replication/{tables,figures}/
│   └── extension/{tables,figures}/
├── tests/
└── report/                       # Write-up/slides sources and data-access notes
```

The template's `project-name`/`src/project` are placeholders. The importable package keeps its existing name `momentum_risk_project`; detailed tested modules remain separated instead of being collapsed into large files.

## Install once

Use Python 3.12 or a compatible version supported by the locked dependencies. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Or use the checked lockfile with uv:

```bash
uv sync --frozen --extra dev
```

`.[dev]` is a real pip optional-dependency extra; uv development groups remain supported. The setuptools backend supports editable installation. Do not install research dependencies globally or commit `.env`, credentials, virtual environments or licensed data.

## Reproduce all reported results

With the configured frozen inputs available locally:

```bash
python run_all.py
# Equivalent after installation:
make all
# Or:
momentum-risk-project --stage all --config configs/config.yaml
```

These commands execute the four stages without running notebooks:

```bash
python scripts/01_get_data.py
python scripts/02_build_dataset.py
python scripts/03_replicate.py
python scripts/04_extend.py
```

1. **Get data:** verify existing public/authorized provider extracts and recorded hashes. Existing raw files are never silently refreshed.
2. **Build dataset:** select/validate required stock fields into `data/interim/stock_inputs`, reconstruct monthly/daily WML and save the final fingerprinted `data/processed/wml_current` build. A changed build is archived before replacement. An unchanged valid build can be reused.
3. **Replicate:** generate gross KF strategies, FF3 OLS, FF4/timing HAC tests, reconstruction comparisons, the teaching factor-proxy scenario and stock-cost results for the historical windows.
4. **Extend:** generate the disjoint extension with the same scientific conventions and continuous stock-account history. The fixed-leverage comparison is calibrated on the historical common window and frozen for the extension; it is an ex-post historical attribution benchmark, not a predictive signal.

To rebuild the final WML dataset directly from frozen raw inputs:

```bash
python run_all.py --force-build
```

All source paths/periods/universe/risk/cost settings and the random seed are in [configs/config.yaml](configs/config.yaml). Configured paths are relative to the project and cannot escape it. `--config` supports a separate validated settings file; `--root` or `MOMENTUM_PROJECT_ROOT` supports an explicit repository location. Unsupported universe/valuation changes fail rather than pretending to implement them. The current cutoff study requires the existing 10bp baseline and zero stock financing. Record scientific changes as new research experiments and compare on matched dates.

### Data access and first acquisition

Public KF deciles and FF3 are separate from licensed WRDS CRSP stock extracts. A fresh Git clone does **not** contain those data or generated results. See [report/data_sources.md](report/data_sources.md), [WML_PIPELINE.md](WML_PIPELINE.md), and [CIZ_FLAGS.md](CIZ_FLAGS.md).

Offline commands fail clearly on missing data. For initial public and authorized WRDS acquisition, explicitly opt in:

```bash
python scripts/01_get_data.py --download
```

WRDS requires an existing account, annual CRSP access and local login configuration. No credentials are embedded in files or manifests. Provider revisions can produce different results from the frozen snapshot; acquisition records and membership fingerprints must match before daily-return filling. Do not replace a partial universe with artificial zero returns.

### Optional external CRSP cache

By default, CRSP data are cached inside the project directory using the
paths defined in `configs/config.yaml`.

To store large CRSP extracts outside the repository (for example, to
avoid cloud-synced folders), set the `MOMENTUM_CRSP_CACHE` environment
variable before running the pipeline.

**Windows PowerShell:**

```powershell
$env:MOMENTUM_CRSP_CACHE = "C:\Columbia_Data\momentum-risk-project\crsp_cache"
```

**macOS/Linux:**

```bash
export MOMENTUM_CRSP_CACHE="$HOME/momentum-crsp-cache"
```

The override applies to both `raw_cache` and `daily_cache`, which share
the same CRSP extraction. All other paths remain relative to the
repository.

The environment variable must be set in each new terminal session.
Do not commit downloaded CRSP data or WRDS credentials to Git.

After configuring the cache, run:

```bash
python scripts/01_get_data.py --download
python run_all.py
```

`data/raw` stores the original downloaded/query-extract bytes, including their provider/extraction manifests. Query-joined provider rows are retained as originally downloaded; the validated field-selected working dataset is in `data/interim`. All original raw bytes are preserved during this refactor. Old `outputs` reports, diagnostic inputs and notebook snapshots are retained under `data/interim/research_history`, `data/interim/reference`, and `data/interim/refactor_baseline_20261101`. They are optional audit evidence, **not inputs required to regenerate current reported results**. Original provenance is retained, not rewritten to impersonate a new provider snapshot.

## Results map

The output tree can be removed and regenerated with `python run_all.py`. Only final data/caches under `data` may accelerate the run; previous result CSVs/plots and notebook execution are never required.

- `results/replication/tables/paper_available_common/`: gross four-strategy metrics/returns/weights, monthly sigma, FF3/FF4/timing tests, factor coverage, reconstructed/KF comparisons, construction audit, factor-proxy ledger/summary and run manifest.
- `results/replication/tables/paper_turnover_test/`: the same baseline diagnostics on the paper's distinct turnover window.
- `results/extension/tables/extension_disjoint/`: the disjoint extension's baseline/factor/reconstruction reports.
- `results/{replication,extension}/tables/stock_costs/`: scope-filtered stock-account/cost metrics, turnover, significance cutoffs, coverage, monthly ledger and directional observations. Their manifest links the continuous analysis-ready study and input/code fingerprints.
- `results/{replication,extension}/figures/`: gross strategy wealth/drawdown and KF/rebuilt stock-study wealth, drawdown and cost sensitivity.
- `data/processed/stock_study/`: final continuous study returns/metrics, strict account/own-risk coverage and fingerprints. Licensed PERMNO-level transitions/trades are under its `stock_trades/` subdirectory. These are private final analysis-ready data, not publication assets.

The accepted windows are **1927-07–2011-12**, **1951-03–2010-12** (separate paper turnover check), and **2012-01–2025-12**. March–June 1927 lack complete reconstructed daily warm-up. The extension is post-sample, not wholly post-publication. No removed auxiliary windows are restored.

## Research frontend MVP

**Status: implemented and browser-tested.** The app uses real verified study data, not demo values. Desktop and narrow-screen layouts, scenario switching and an actual CSV download were checked.

After installing the project, activate its environment and start the interface from the repository root:

```bash
source .venv/bin/activate
python -m streamlit run app/streamlit_app.py
# Equivalent from the repository root:
make app
```

Open `http://127.0.0.1:8501`. The server binds to localhost. The frontend reads
verified saved study scenarios and does not acquire data, fit models, send
orders or change source/config/result files. Generate the configured dataset
with `python run_all.py` first; a fresh clone without local results shows clear
setup instructions rather than mock performance. You do not need to rerun the pipeline for each UI change: once the saved study exists, switching views is read-only and immediate. Stop the local server with Ctrl+C in its terminal. This launch is local; pushing the code to GitHub does not host a public website.

Select the historical, paper-turnover-test or extension window, rebuilt versus
KF WML, gross/net returns, an exact saved one-way fee scenario, starting capital
and funded/paper-style accounting. Explore interactive wealth, drawdown, monthly
returns, actual stock turnover, fee drag, applied weights and cost sensitivity.
Export the selected monthly series and scenario/provenance JSON. Starting capital
only rebases displayed wealth; source returns and the continuous historical
stock-account history are preserved.

KF is explicitly gross-only because it has no constituent stock-cost ledger.
Rebuilt results now use their own daily risk and the explicit stock-component-zero scenario; the coverage tab shows the separate strict diagnostics.
No interpolated fees, invented returns or automatic cash substitution are used.
The app exposes the current realized-volatility baseline; EWMA/GARCH selectors
will be added after those research modules are integrated.

The frontend and risk-source tests verify independent risk, no KF fallback, component-zero handling, point-in-time weights and scenario consistency.

Presentation lives in `app/streamlit_app.py`; read-only scenario selection,
provenance checks and metrics delegation are in `dashboard.py`, with interactive
charts in `dashboard_charts.py`. No existing research engine is modified.

```bash
python -m pytest tests/test_dashboard.py -q
```

## Package API and modules

- `paths.py`, `config.py`: root-relative locations, settings validation and config digest.
- `data.py`: public loaders/cleaning and the acquisition facade; `features.py` exposes the current construction API. Detailed ranking, quality, stock reconstruction and daily valuation logic stays in its existing modules.
- `models.paper_strategies`: four-strategy gross comparison, lagged risk weights and historical fixed-leverage reference.
- `evaluation.factor_tests`, `evaluation.describe`: independent reported factor/timing statistics and performance; `plotting.py` generates all official figures.
- `wml_pipeline.load_build`, `estimate_risk`, `WMLBuild.targets/backtest`: the current stock-construction artifact, already lagged holding-month risk weights, signed targets and explicit-policy stock accounts.
- `study.run_study`: complete stock-cost study as a package function; `pipeline.py` owns the four-stage orchestration.
- `backtest.run_backtest`: the factor-scaling cost proxy used by the Notebook 04 teaching scenario. It does not observe constituent turnover.
- `paper_turnover.py`, `stock_backtest.py`: separate normalized-leg turnover/cutoff diagnostics and actual self-funded stock fees. The latter uses price/ex-distribution drift and monthly distribution cash.

```python
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.paths import project_root
from momentum_risk_project.wml_pipeline import load_build
import pandas as pd

root = project_root()
config = load_config(root=root)
build = load_build(configured_path(config, "build", root))
months = pd.period_range("2012-01", "2025-12", freq="M")
weights = pd.Series(1.0, index=months)  # +1 long / -1 short; a new account episode
ledger, trades = build.backtest(
    weights, return_policy="reconstructed_zero_missing", transaction_cost_bps=10,
    financing_cost_bps=0,
)
```

Each call starts a new account. For continuous comparisons, run once over the full consecutive calendar, then slice. `reconstructed_zero_missing` is the explicit complete primary scenario; `dm` stops on unknown valuations and `published_reference` is a legacy diagnostic. `estimate_risk` already returns holding-month weights, while `strategies.volatility_managed_momentum` accepts origin-month sigma and shifts once internally. Never apply both lags.

## Validation

```bash
python -m pytest -p no:cacheprovider tests/ -q
python -m pytest tests/test_pipeline.py -q
make notebooks
```

The tests use synthetic/local fixtures, not live WRDS queries. Notebook checks are optional, require generated results and validate presentation/independent derivations; they are not the production pipeline. Every notebook ends with focused module tests and the full-suite command. The repository refactor passed **103 tests**; frontend tests additionally cover scenario selection, integrity/missing-data states, exports, initial drawdown and UI control behavior. All existing 93 behavioral tests are retained, with 10 additional refactor tests for paths/config, immutable-cache verification, missing inputs, packaged equations/regressions and orchestration.

The refactor is checked against original numerical baselines for monthly/daily WML, risk weights, gross strategies, stock fees/ledgers, cutoff/turnover metrics and independently calculated regressions. Raw-byte fingerprints and original manifests are preserved. See [report/reproducibility.md](report/reproducibility.md) for the final validation evidence and how to repeat it. Missing economic values remain unresolved even when software tests pass.

## Team plan: frontend MVP, EWMA and GARCH

The current maintainer has implemented the first Streamlit research frontend MVP in `app/streamlit_app.py`, calling package presentation services rather than executing notebooks. It exposes verified saved scenarios and interactive results with explicit valuation/risk coverage. Live model recomputation, broker connections and order execution are outside this MVP.

The two collaborators can choose one extension each, working on their own named branches:

- **EWMA:** proposed `src/momentum_risk_project/ewma.py`, `tests/test_ewma.py`, and Notebook 06. Use a zero-mean squared-return recursion, configurable decay (initial research setting 0.94), documented seed and warm-up. Return a forecast-origin-month schema with monthly sigma, availability and reason. A proposed 126-session warm-up is an experiment setting, not a paper rule. [Pandas EWM reference](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.ewm.html).
- **GARCH:** proposed `garch.py`, `tests/test_garch.py`, and Notebook 07. Start with zero-mean Gaussian GARCH(1,1), rolling monthly refits using only available history; proposed 252–1,260-session training bounds. Fit percent returns, sum 21 daily forecast residual variances, convert back by 100², then take the square root. Record convergence/coverage failures, rather than substituting cash. [arch forecasting reference](https://arch.readthedocs.io/en/latest/univariate/forecasting.html).

Both proposed modules should expose `forecast_month_end(daily_returns, origin_months, **parameters)` returning `monthly_sigma`, `forecast_available`, `reason`, indexed by the **forecast-origin month**. Convert to following holding-month weights once. For the rebuilt strategy, every model must consume reconstructed daily WML and apply its own weights to reconstructed holdings. KF may be a separate benchmark using KF daily inputs; do not inject KF risk into a rebuilt strategy. A KF-only preliminary model comparison must remain separately labelled. Keep valuation, costs, dates and target fixed; do not tune on 2012–2025 performance. Use exact common contiguous months, state any shorter GARCH warm-up sample, and do not drop internal gaps to stitch wealth.

The maintainer will integrate the shared interface into a future `risk_models.py` adapter/extension runner. These proposed modules/options do not exist yet; current production configuration supports only the validated baseline. New model logic must live in `src`, experiments in notebooks, and official extension results be regenerated through scripts. Keep model results in separate configured locations and review changes before merging.

## Collaboration

The remote alias is `ieor4576`; the repository name is `momentum-risk-project`. Work on a personal named branch, fetch before integrating, and do not use `git add .` over licensed/local data. No raw data, generated results or credentials belong in Git. Review code/config changes together with tests and regenerated result manifests. See the detailed methodology guides for remaining economic assumptions; software refactoring does not resolve provider-vintage or terminal-payoff uncertainty.

### Independent-risk verification

Run `python -m momentum_risk_project.own_risk_validation` after `python run_all.py`
to reconcile source-derived weights, gross returns, funded-account identities and
all saved frontend scenarios. `pytest -q` covers component-zero handling, known
delisting exactly once, lagged risk, independent inputs and rejection of old
shared-KF-risk manifests. `validation.py` is only the historical layout-migration
audit; its old numerical-equality baseline is not the current scientific policy.
