# Momentum Risk Management

Replication and extension of Barroso and Santa-Clara (2015), *Momentum Has Its Moments*, Journal of Financial Economics. [Paper](https://doi.org/10.1016/j.jfineco.2014.11.010) · [Repository and team](https://github.com/yihang-hannah/momentum-risk-project) · [Contributors](https://github.com/yihang-hannah/momentum-risk-project/graphs/contributors).

## Current status and scientific scope

The repository now follows the course hierarchy: reusable logic in `src`, four thin ordered scripts, centralized configuration, separate intermediate/final data, rebuildable results and exploratory notebooks. See Git history for the published revision of this course-aligned layout. Historical notebooks and audits are preserved privately; no licensed observations are committed.

- **01:** explore the canonical KF daily/monthly decile-return inputs and validate their packaged loader.
- **02:** independently derive/check the paper equations and regressions against script-generated results; it is no longer the only source of reported FF3/FF4/timing results.
- **03:** document all data sources, field/flag rules and assumptions; inspect the package-built stock WML and script-generated KF comparisons. The complete processing specification and official links remain at its beginning.
- **04:** unpack the factor-scaling cost proxy for teaching and check the reusable engine/script report.
- **05:** display script-generated stock-cost results and validate short stock-account/API examples.

Complete rebuilt-WML performance uses **published-reference monthly stock valuations and shared KF daily risk weights**. Ordinary missing stock returns use the accepted zero sensitivity; unresolved terminal payoffs remain unknown in the strict policy. Checked own-stock daily gaps currently leave no complete month-end 126-session risk forecasts. Missing forecasts are not cash, and these results are not a complete independent stock-risk replication.

At 10bp per dollar traded, historical common-window funded-account Sharpe improves from about **0.474 to 0.900**, and 2012–2025 from **0.105 to 0.270**. Extension profitability is weak. On the separate 1951–2010 turnover-test window, scaled-position half-turnover is about **71.32% → 73.40%**. The supplied paper prints inverse risk scaling in its managed turnover formula; the literal inverse-L diagnostic and the economically scaled-position diagnostic remain separate. Gross KF replication, factor-proxy costs and funded stock costs must not be mixed.

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

`data/raw` stores the original downloaded/query-extract bytes, including their provider/extraction manifests. Query-joined provider rows are retained as originally downloaded; the validated field-selected working dataset is in `data/interim`. All original raw bytes are preserved during this refactor. Old `outputs` reports, diagnostic inputs and notebook snapshots are retained under `data/interim/research_history`, `data/interim/reference`, and `data/interim/refactor_baseline_20261101`. They are optional audit evidence, **not inputs required to regenerate current reported results**. Original provenance is retained, not rewritten to impersonate a new provider snapshot.

## Results map

The output tree can be removed and regenerated with `python run_all.py`. Only final data/caches under `data` may accelerate the run; previous result CSVs/plots and notebook execution are never required.

- `results/replication/tables/paper_available_common/`: gross four-strategy metrics/returns/weights, monthly sigma, FF3/FF4/timing tests, factor coverage, reconstructed/KF comparisons, construction audit, factor-proxy ledger/summary and run manifest.
- `results/replication/tables/paper_turnover_test/`: the same baseline diagnostics on the paper's distinct turnover window.
- `results/extension/tables/extension_disjoint/`: the disjoint extension's baseline/factor/reconstruction reports.
- `results/{replication,extension}/tables/stock_costs/`: scope-filtered stock-account/cost metrics, turnover, significance cutoffs, coverage, monthly ledger and directional observations. Their manifest links the continuous analysis-ready study and input/code fingerprints.
- `results/{replication,extension}/figures/`: gross strategy wealth/drawdown and KF/rebuilt stock-study wealth, drawdown and cost sensitivity.
- `data/processed/stock_study/`: final continuous study returns/metrics, strict account/own-risk coverage and fingerprints. Licensed PERMNO-level transitions/trades are under its `stock_trades/` subdirectory. These are private final analysis-ready data, not publication assets.

The accepted windows are **1927-05–2011-12**, **1951-03–2010-12** (separate paper turnover check), and **2012-01–2025-12**. March–April 1927 lack the public KF daily warm-up. The extension is post-sample, not wholly post-publication. No removed auxiliary windows are restored.

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
    weights, return_policy="published_reference", transaction_cost_bps=10,
    financing_cost_bps=0,
)
```

Each call starts a new account. For continuous comparisons, run once over the full consecutive calendar, then slice. `published_reference` remains conditional; `dm` stops on unknown valuations. `estimate_risk` already returns holding-month weights, while `strategies.volatility_managed_momentum` accepts origin-month sigma and shifts once internally. Never apply both lags.

## Validation

```bash
python -m pytest -p no:cacheprovider tests/ -q
python -m pytest tests/test_pipeline.py -q
make notebooks
```

The tests use synthetic/local fixtures, not live WRDS queries. Notebook checks are optional, require generated results and validate presentation/independent derivations; they are not the production pipeline. Every notebook ends with focused module tests and the full-suite command. The complete suite currently passes **103 tests**. All existing 93 behavioral tests are retained, with 10 additional refactor tests for paths/config, immutable-cache verification, missing inputs, packaged equations/regressions and orchestration.

The refactor is checked against original numerical baselines for monthly/daily WML, risk weights, gross strategies, stock fees/ledgers, cutoff/turnover metrics and independently calculated regressions. Raw-byte fingerprints and original manifests are preserved. See [report/reproducibility.md](report/reproducibility.md) for the final validation evidence and how to repeat it. Missing economic values remain unresolved even when software tests pass.

## Team plan: frontend MVP, EWMA and GARCH

The current maintainer will first complete a Streamlit frontend MVP in a future `app/streamlit_app.py`, calling the package rather than executing notebooks. It should expose available scenarios and verified result views, with valuation/risk coverage clearly labeled. The frontend itself is **not implemented by this repository-layout refactor**.

The two collaborators can choose one extension each, working on their own named branches:

- **EWMA:** proposed `src/momentum_risk_project/ewma.py`, `tests/test_ewma.py`, and Notebook 06. Use a zero-mean squared-return recursion, configurable decay (initial research setting 0.94), documented seed and warm-up. Return a forecast-origin-month schema with monthly sigma, availability and reason. A proposed 126-session warm-up is an experiment setting, not a paper rule. [Pandas EWM reference](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.ewm.html).
- **GARCH:** proposed `garch.py`, `tests/test_garch.py`, and Notebook 07. Start with zero-mean Gaussian GARCH(1,1), rolling monthly refits using only available history; proposed 252–1,260-session training bounds. Fit percent returns, sum 21 daily forecast residual variances, convert back by 100², then take the square root. Record convergence/coverage failures, rather than substituting cash. [arch forecasting reference](https://arch.readthedocs.io/en/latest/univariate/forecasting.html).

Both proposed modules should expose `forecast_month_end(daily_returns, origin_months, **parameters)` returning `monthly_sigma`, `forecast_available`, `reason`, indexed by the **forecast-origin month**. Convert to following holding-month weights once. Start on the same public KF WML to isolate risk-model differences, then apply weights to the same reconstructed holdings via the existing stock-account API. Keep valuation, costs, dates and target fixed; do not tune on 2012–2025 performance. Use exact common contiguous months, state any shorter GARCH warm-up sample, and do not drop internal gaps to stitch wealth.

The maintainer will integrate the shared interface into a future `risk_models.py` adapter/extension runner. These proposed modules/options do not exist yet; current production configuration supports only the validated baseline. New model logic must live in `src`, experiments in notebooks, and official extension results be regenerated through scripts. Keep model results in separate configured locations and review changes before merging.

## Collaboration

The remote alias is `ieor4576`; the repository name is `momentum-risk-project`. Work on a personal named branch, fetch before integrating, and do not use `git add .` over licensed/local data. No raw data, generated results or credentials belong in Git. Review code/config changes together with tests and regenerated result manifests. See the detailed methodology guides for remaining economic assumptions; software refactoring does not resolve provider-vintage or terminal-payoff uncertainty.
