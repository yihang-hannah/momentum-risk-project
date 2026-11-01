# Momentum Risk Management — Project README

## Current progress

**Updated 2026-11-01 — local working-tree status.** Notebooks 03–05 and their reusable modules are implemented and executed locally; this does not imply that they have been committed, pushed, or merged. Notebook 02 remains identical to the checked GitHub-main baseline (`1437301c19cbffb787c253a5f3b9a7727eca3dae`). The latest full test run passed **93 tests**.

- **Notebook 03 — Stock-level WML construction:** current CRSP formation/price-quality screens, missing-return and delisting policies, monthly/daily reconstruction, KF comparisons, source audits and a fingerprinted reusable build are implemented. Ordinary missing stock returns use the accepted zero assumption; unknown terminal payoffs remain unresolved in the strict policy.
- **Notebook 04 — Cost-aware backtest lab:** the factor-level backtest is unpacked into explanatory cells and reconciled against the reusable engine. Its turnover is a factor-scaling proxy, not constituent-stock turnover.
- **Notebook 05 — Reconstructed WML with stock costs:** stock entries, exits, drift, Appendix B turnover diagnostics, funded-account fees, cost sensitivity, KF comparisons and historical/extension results are implemented. Complete performance uses published-return stock-reference valuations and **shared KF risk weights**; it is not a complete independent stock-risk replication.

**Current finding:** At 10bp per dollar traded, the historical common-window funded-account Sharpe rises from **0.474 to 0.900** after risk management; in 2012–2025 it rises from **0.105 to 0.270**. Tail-risk improvement persists, but extension profitability is weak. Strict own-stock daily gaps currently leave no complete month-end 126-session risk forecasts; missing forecasts are never replaced by cash.

**Separate gross KF replication snapshot (Notebook 02):** unmanaged annualized mean **14.86%**, volatility **27.42%**, Sharpe **0.5419**; managed mean **16.69%**, volatility **16.77%**, Sharpe **0.9958**. These gross benchmark results must not be confused with Notebook 05's net stock-reference results.

## 1. Project overview

We replicate the volatility-management approach in **Barroso and Santa-Clara (2015), _Momentum Has Its Moments_**. Momentum WML is the difference between value-weighted winner (P10) and loser (P1) portfolio returns. The central question is whether scaling momentum exposure using previously observed volatility improves risk-adjusted performance.

- **Paper:** Barroso, P. and Santa-Clara, P. (2015), *Momentum Has Its Moments*, *Journal of Financial Economics*.
- **Public data:** [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
- **Repository:** https://github.com/yihang-hannah/momentum-risk-project
- **Git remote alias on the maintainer's computer:** `ieor4576` (this is a local alias, **not** the GitHub repository name). Each teammate can configure the same alias for consistency.

## 2. What is in the repository

```text
momentum-risk-project/
├── README.md
├── pyproject.toml / uv.lock
├── WML_PIPELINE.md / CIZ_FLAGS.md / STOCK_RESEARCH.md / BACKTEST.md
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_paper_replication.ipynb
│   ├── 03_wml_construction.ipynb
│   ├── 04_cost_aware_backtest_lab.ipynb
│   └── 05_reconstructed_wml_stock_cost_backtest.ipynb
├── src/momentum_risk_project/
│   ├── data.py / wml.py / volatility.py / strategies.py / metrics.py
│   ├── backtest.py / cli.py
│   ├── wml_pipeline.py / ranking.py / ciz_quality.py
│   ├── stock_reconstruction.py / daily_portfolio.py / wrds_stock.py
│   └── stock_backtest.py / stock_turnover.py / paper_turnover.py
├── scripts/run_stock_cost_study.py
├── tests/
├── data/                       # Licensed raw data and reusable local artifacts
└── outputs/                    # Latest notebook reports; see outputs/README.md
```

This is the current local layout, including work not yet published to GitHub. `wml.py` is the earlier stock-level utility; **`wml_pipeline.py` is the authoritative Notebook 03 construction API used by Notebook 05**. Licensed raw data and processed stock artifacts are Git-ignored and are not supplied by a fresh clone. Read [data/README.md](data/README.md) and [outputs/README.md](outputs/README.md) before regenerating or cleaning files.

## 3. Required software and first-time setup

Every teammate should install these three tools **before** opening the project:

| Tool | Why it is needed | Installation |
| --- | --- | --- |
| **Visual Studio Code (VS Code)** | Edit Python, inspect notebooks, run terminals and tests | https://code.visualstudio.com/ |
| **Git** | Clone, branch, commit, synchronize, and collaborate | https://git-scm.com/downloads |
| **uv** | Manage Python versions, virtual environments, dependencies, and reproducible commands | https://docs.astral.sh/uv/getting-started/installation/ |

Also install the **Python** and **Jupyter** extensions inside VS Code. Python 3.12 is the development target; `uv` can install/manage a compatible Python interpreter.

Verify installations in the VS Code terminal:

```bash
git --version
uv --version
code --version
```

Clone the project and configure the same remote alias used by the maintainer:

```bash
git clone -o ieor4576 https://github.com/yihang-hannah/momentum-risk-project.git
cd momentum-risk-project
git remote -v
```

Install project dependencies and run tests:

```bash
uv sync
uv run python --version
uv run pytest tests/ -v
```

**Important:** `uv sync` requires a valid `pyproject.toml` in the repository. If it is not committed yet, ask the maintainer for the project's dependency specification rather than guessing packages or installing them globally. The source-code commit summary alone does not establish that this file was pushed. When `uv.lock` is committed, use `uv sync --frozen` to follow its resolved versions.

To run a notebook, open the repository folder in VS Code, open the `.ipynb` file, choose the project's `.venv` Python interpreter as the kernel, and execute cells in order. The Kenneth French datasets require network access on first download. Never commit credentials, `.env`, licensed market-data extracts, `.venv/`, or large generated datasets.

## 4. Notebook guide

### Notebook 01 — Data exploration

**Purpose:** Establish the momentum-return data pipeline and inspect the statistical properties of momentum returns before implementing a strategy.

Typical workflow: load daily and monthly momentum returns; check date coverage, units, duplicates, missing values, and alignment; explore return distributions and volatility; cache cleaned data locally for reproducible reruns. Review its actual cells for the authoritative list of figures and tables.

**Important distinction:** The project baseline uses the Kenneth French **value-weighted P10 − P1 decile WML**, not the separately published 2×3 `Mom` factor. Use `load_wml_decile_returns()` where available; confirm the shared data-loader changes have been committed before relying on that API in a fresh clone.

### Notebook 02 — Paper replication (validated core)

**Research/implementation separation:** This notebook independently implements the paper equations for experimentation, diagnostics, and replication. It does **not** need to call `strategies.py`. After the notebook logic is validated, the equivalent production-facing calculations are encapsulated separately in `src/momentum_risk_project/strategies.py`, with unit tests in `tests/test_strategies.py`. The two implementations should agree numerically for identical inputs.

**Purpose:** Reproduce the central result of Barroso and Santa-Clara (2015) using the **value-weighted** P10 − P1 spread from Kenneth French's `10_Portfolios_Prior_12_2` (monthly) and `10_Portfolios_Prior_12_2_Daily` (daily) datasets. Use the corrected decile-WML notebook, not an older draft using the standard `Mom` factor.

**Implemented analysis:**

1. Download and validate the monthly and daily momentum decile data; compute `WML = P10 - P1` in decimal returns.
2. Estimate monthly risk from the **last 126 trading-day squared daily WML returns** (21-day monthly scaling).
3. Compute a **12% annualized volatility-target** exposure and apply the **previous month-end** weight to the current month's return; do not shift the daily estimator and then shift monthly weights a second time.
4. Compare unmanaged WML, constant-leverage WML, uncapped volatility-managed WML, and a 2× capped sensitivity.
5. Evaluate annualized arithmetic return, volatility, Sharpe, CAGR, maximum drawdown, and terminal wealth on a **common evaluation sample**.
6. Estimate Fama–French three-factor and four-factor (FF3 + WML) regressions, including HAC inference, and perform leverage and alignment checks.
7. Export aligned returns and summary outputs as specified by the notebook.

**Risk estimator:**

\[
\widehat{\sigma}_{WML,t}^{2}=\frac{21}{126}\sum_{j=0}^{125}r_{WML,d_{t-1}-j}^{2},
\]

where \(d_{t-1}\) is the final trading day of the preceding month. The estimated volatility is in **monthly** units. The weight chosen at the end of month \(t-1\) is applied to month \(t\):

\[
w_{t-1}=\frac{0.12/\sqrt{12}}{\widehat{\sigma}_{WML,t-1}},
\qquad R_{managed,t}=w_{t-1}R_{WML,t}.
\]

**Validated replication snapshot (paper-era sample, from the corrected notebook):**

| Strategy | Annualized mean | Annualized volatility | Sharpe (rf = 0) |
| --- | ---: | ---: | ---: |
| Unmanaged WML | 14.86% | 27.42% | 0.5419 |
| Fixed leverage | 13.33% | 24.59% | 0.5419 |
| Volatility managed | 16.69% | 16.77% | 0.9958 |
| Managed, 2× cap | 16.69% | 16.76% | 0.9956 |

The uncapped leverage reached approximately 2.094× and exceeded 2× in only two months. These are historical replication outputs, **not** out-of-sample performance or evidence of a tradable net-of-cost strategy. Data-library updates can change exact values.

### Notebook 03 — Stock-level WML construction and KF reconciliation

[Open Notebook 03](notebooks/03_wml_construction.ipynb). **Status:** implemented and executed; the strict valuation and independent daily-risk gaps below remain unresolved.

- Reconstruct monthly value-weighted deciles from WRDS CRSP CIZ data using historical ordinary-share/exchange eligibility, NYSE momentum breakpoints and prior-month capitalization. Apply the current period-end price/date quality screens at formation and t-13; stale last-available quotes are not treated as observed month-end prices.
- Use the documented KF 12-2 ranking screen, with the CIZ/legacy missing-code correspondence explicitly qualified. Ordinary holding-period stock-return gaps are zero under the accepted research assumption, not claimed as a fully documented KF rule.
- Attach delisting evidence: recover known excluded payoffs once, avoid adding already included payoffs twice, and preserve unknown terminal values under the strict DM policy. Keep the complete published-return reference as a separate, explicitly conditional valuation policy.
- Reconstruct monthly-formed daily stock legs with the calendar/price-gap audit and protected special, multi-session and terminal-return cases. Compare monthly WML against KF, including the August 1935 price-quality diagnostic and source-version checks. The historical monthly reference MAE is about **13.91bp**, versus **47.43bp** in the extension; source vintages and construction details are not proven identical to KF.
- Export the fingerprinted build consumed by Notebook 05: `data/processed/wml_current_v1_20261031/`. The implementation is reusable through `load_build`, `estimate_risk`, `build.targets` and `build.backtest`, without copying notebook logic.

**Current boundary:** The strict checked daily series has no complete month-end 126-session forecasts in the evaluated windows. Unknown terminal values also interrupt the strict monthly account. Complete comparison tables therefore use the published-return reference and shared KF risk; they do not establish a full independent managed-stock backtest. Reports are in `outputs/03_wml/`. See [WML_PIPELINE.md](WML_PIPELINE.md), [CIZ_FLAGS.md](CIZ_FLAGS.md) and [STOCK_RESEARCH.md](STOCK_RESEARCH.md) for rules, source references and remaining qualifications.

### Notebook 04 — Cost-aware backtest, step-by-step lab

[Open Notebook 04](notebooks/04_cost_aware_backtest_lab.ipynb). **Status:** implemented, executed and reconciled against `backtest.py`.

The notebook exposes the calculation before calling the packaged engine: existing KF deciles → WML → squared-return risk → previous-month weight → factor-scaling turnover proxy → trading/financing costs → net wealth and metrics. Intermediate tables and Markdown explain the timing and accounting. The notebook checks the complete ledger and metrics against the reusable implementation at the end.

**Scope:** this is the teaching/MVP factor-level calculation. Constant unmanaged factor weight omits ongoing stock reconstitution and therefore understates trading costs. The optional financing spread above factor weight one is a simplifying sensitivity, not a broker funding model; its illustrative lab default is distinct from Notebook 05's zero-financing study. Use Notebook 05 for constituent-stock costs. Executed lab outputs are embedded in the notebook; separate CLI exports are documented in [BACKTEST.md](BACKTEST.md) and currently retained under `outputs/04_backtest/`.

### Notebook 05 — Reconstructed WML, stock turnover and net performance

[Open Notebook 05](notebooks/05_reconstructed_wml_stock_cost_backtest.ipynb). **Status:** implemented and fully executed, including cost sensitivities and qualitative paper comparisons.

**Evaluation windows:**

- **1927-05–2011-12:** available common historical sample. March–April 1927 are excluded because the public KF daily series lacks the full required warm-up.
- **1951-03–2010-12:** the paper's separate stock-level turnover test, used to compare turnover and significance cutoffs.
- **2012-01–2025-12:** disjoint post-sample extension. It is not entirely post-publication.

**Accounting and validation:**

- Read Notebook 03's validated artifact; compare rebuilt and KF monthly WML on identical calendars and shared lagged KF risk weights. No missing risk forecast is converted into zero exposure or cash.
- Include constituent entries, exits, leg switches and return drift. Appendix B diagnostics normalize drift within each leg and sum half absolute changes across both legs. The local manuscript's printed managed equation divides by the risk multiplier, while returns multiply by it; show both the literal inverse-multiplier diagnostic and the actual scaled-position diagnostic rather than silently resolving that ambiguity.
- Separately simulate a continuous self-funded stock account, using after-fee NAV targets, ex-distribution price drift, distribution cash and known delisting settlement. Subperiod evaluations do not introduce new entry fees. No terminal liquidation fee is charged.
- Test **0, 5, 10, 25 and 50bp per dollar traded**, with financing zero. A 10bp one-way charge corresponds to a 20bp roundtrip rate when applied to Appendix B half-turnover. Significance cutoffs use a labeled IID Student-t calculation, not an asserted replication of the authors' inference implementation.

**Results at 10bp per dollar traded, unmanaged → managed:**

- Historical common window: annual mean **13.00% → 15.07%**, Sharpe **0.474 → 0.900**, worst month **−78.26% → −24.78%**.
- Paper turnover-test window: actual scaled-position mean monthly half-turnover **71.32% → 73.40%**; IID roundtrip significance cutoff **120.4bp → 175.5bp**. This supports the paper's direction of a small turnover increase and greater cost resilience, without claiming exact replication. The literal inverse-multiplier managed turnover is **92.61%**, so that convention gives a different comparison.
- Extension: annual mean **2.84% → 3.22%**, Sharpe **0.105 → 0.270**, volatility **27.12% → 11.92%**, worst month **−29.66% → −11.58%**. Risk mitigation persists, but neither strategy's gross mean is significant in the stated IID test.

**Interpretation:** These are conditional published-return stock-reference results with shared KF risk weights. They support several qualitative paper observations, but unresolved terminal values and own-stock daily-risk gaps prevent a complete independent replication. Borrow fees, rebates, time-varying impact and intramonth settlement are not identified by the current inputs.

**Reproduce offline from the repository root**, with the retained licensed inputs present:

```bash
uv run python scripts/run_stock_cost_study.py --cost-bps 0 5 10 25 50
uv run pytest -p no:cacheprovider tests/ -q
```

Then run Notebook 05, or set its `RERUN_STUDY=True`. The notebook checks saved input/code fingerprints before displaying results. Current tables, coverage, plots and the run manifest are in `outputs/05_stock_backtest/`; licensed stock transitions and funded trades are in ignored `data/processed/05_stock_backtest/`.

## 5. Python module reference

All examples use the installed package `momentum_risk_project` and should be run in the `uv` environment. Some functions are general-purpose utilities rather than the complete Notebook 02 data-download pipeline.

### `data.py` — Data ingestion, validation, and caching

Available functions include `validate_frequency`, `download_momentum`, `clean_momentum`, `validate_cleaned_data`, `raw_path`, `processed_path`, `save_raw_data`, `save_processed_data`, `read_processed_data`, and `load_momentum_returns`.

```python
from momentum_risk_project.data import load_momentum_returns

daily_mom, monthly_mom = load_momentum_returns()
print(daily_mom.head())
print(monthly_mom.head())
```

**Data-source note:** For the paper-replication baseline, use the value-weighted decile spread **P10 − P1**. The standardized `load_wml_decile_returns()` API is intended to supply daily and monthly decile WML; verify it exists on the branch being used before running the example. The legacy `load_momentum_returns()` interface may still be present for compatibility.

```python
from momentum_risk_project.data import load_wml_decile_returns

daily_wml, monthly_wml = load_wml_decile_returns()
```

### `volatility.py` — Historical volatility estimator

`historical_volatility(daily_returns, window=126, trading_days_per_month=21)` accepts a `pd.Series` with a sorted, unique `DatetimeIndex` and returns a daily-indexed **monthly-unit** rolling volatility estimate. It uses squared returns rather than sample variance, and includes the current date in the rolling window.

```python
from momentum_risk_project.volatility import historical_volatility

# daily_wml: pd.Series with a sorted DatetimeIndex and decimal returns
sigma_daily = historical_volatility(daily_wml, window=126)
# Select each month's last observed trading-day estimate before strategy use.
```

The first 125 observations are missing by construction. The function does **not** shift dates or produce month-indexed observations automatically.

### `strategies.py` — Unmanaged and volatility-managed returns

**Role:** Reusable implementation of the strategy logic independently validated in Notebook 02, not a replacement for the notebook experiments. The module and notebook intentionally keep separate implementations; changes to the formula should be validated in the notebook first, then ported here and covered by tests.

`unmanaged_momentum(monthly_returns)` validates a complete monthly `PeriodIndex` return series and returns a copy named `unmanaged`.

`volatility_managed_momentum(monthly_returns, monthly_volatility, target_volatility=0.12)` accepts monthly `PeriodIndex` series and returns columns `mom`, `estimated_volatility`, `weight`, and `managed`. The `weight` column is the **applied previous-month weight**.

```python
from momentum_risk_project.strategies import volatility_managed_momentum

# monthly_wml: pd.Series, monthly PeriodIndex, decimal WML returns
# monthly_sigma: pd.Series, monthly PeriodIndex, month-end risk estimates
result = volatility_managed_momentum(
    monthly_returns=monthly_wml,
    monthly_volatility=monthly_sigma,
    target_volatility=0.12,
)
print(result[["weight", "managed"]].tail())
```

**Input requirements:** Both inputs must be monthly `pd.Series` with a chronologically increasing, unique `PeriodIndex` (`freq="M"`). Monthly returns must cover consecutive calendar months and contain only finite values. Volatility estimates must be in **monthly units** (not annualized), with positive finite observations; leading `NaN` values are allowed during the warm-up period. The `target_volatility` parameter is **annualized** and is converted internally by dividing by `sqrt(12)`. The weight for month `t` uses the volatility observed at the end of month `t-1` (`shift(1)` exactly once).

The module does **not** automatically cap leverage, model margin, or subtract transaction costs. Apply such rules explicitly in a separately tested extension.

### `metrics.py` — Strategy performance summary

`performance_metrics(returns, periods_per_year=12)` returns annualized arithmetic mean, annualized volatility, zero-risk-free-rate Sharpe, CAGR, maximum drawdown, and terminal wealth.

```python
from momentum_risk_project.metrics import performance_metrics

managed = result["managed"].dropna()
summary = performance_metrics(managed, periods_per_year=12)
print(summary)
```

For returns at or below −100%, arithmetic metrics remain available while CAGR, maximum drawdown, and terminal wealth return `NaN`: a normal compounded limited-liability wealth path is not defined by such a factor-return series. This is **not** a liquidation simulator. Use `periods_per_year=252` for daily observations if appropriate.

### `wml.py` — Stock-level momentum signal and portfolios

`compute_momentum_signal(crsp, lookback=12, skip=1)` requires `permno`, `month`, and `mthret`; it checks stock-month uniqueness and uses calendar-month offsets rather than assuming adjacent rows represent adjacent months.

`compute_aligned_wml(panel)` constructs value-weighted deciles and returns **(portfolio_returns, holdings)**; the input needs `permno`, `month`, `momentum_signal`, `primaryexch`, `mthcap`, and `mthret`. Check its formation/holding conventions and the notebook's additional eligibility rules before comparing against DM official portfolios.

```python
from momentum_risk_project.wml import compute_momentum_signal, compute_aligned_wml

# crsp_panel must have the documented columns and correct date/return units.
signals = compute_momentum_signal(crsp_panel)
portfolio_returns, holdings = compute_aligned_wml(signals)
```

**Research caution:** This is a reusable baseline, not a claim of exact DM replication. Formation-date CIZ screens and missing holding returns require explicit documentation and validation.

### Current stock construction and cost modules

- `wml_pipeline.py`: authoritative Notebook 03 build, explicit valuation policies, checked daily reconstruction, lagged risk estimation, fingerprinted artifacts and stock-account API. See [WML_PIPELINE.md](WML_PIPELINE.md).
- `ranking.py`, `ciz_quality.py`, `stock_reconstruction.py`, `daily_portfolio.py`: ranking eligibility, formation-price screens, monthly portfolios/delisting reconciliation and daily leg reconstruction. `wrds_stock.py` supplies resumable read-only cache acquisition.
- `backtest.py`, `cli.py`: factor-proxy cost engine and reproducible exports used by the Notebook 04 lab; see [BACKTEST.md](BACKTEST.md).
- `stock_backtest.py`: funded stock-account fees, drift and unknown-state propagation. `paper_turnover.py`: separate Appendix B leg-normalized turnover diagnostics and IID significance cutoffs used in Notebook 05. `stock_turnover.py` is an earlier gross-NAV stock-turnover diagnostic, not the Appendix B calculation.
- `scripts/run_stock_cost_study.py`: offline Notebook 05 study and result export. Historical experiment entrypoints are not the current construction API.

## 6. Automated tests

The latest local suite passed **93 tests**, including the Notebook 03 pipeline and Notebook 05 stock-turnover additions. Checks cover fingerprints and round trips, valuation/terminal-payoff policies, risk timing, stock entries/exits and leg switches, both multiplier conventions, unknown-return propagation, self-funded fees and cutoff units. Executed notebooks additionally reconcile complete result calendars, zero-cost gross returns and trade/fee aggregation.

Tests are executable checks of behavior and edge cases, not a replacement for financial/economic validation.

| Test file | Purpose |
| --- | --- |
| `test_data.py` | Daily/monthly data cleaning, duplicate/missing input rejection, Parquet round-trip, cache reuse |
| `test_volatility.py` | Squared-return estimator, 126-day warm-up, invalid window; add inclusive-last-day test if not yet merged |
| `test_strategies.py` | One-month lag: February must use January's volatility; add no-look-ahead sensitivity test if not yet merged |
| `test_metrics.py` | Normal compounded returns, ≤−100% extreme returns, non-finite input rejection |

```bash
uv run pytest tests/ -v
uv run pytest tests/test_strategies.py -v
uv run pytest tests/test_volatility.py -v
```

For any bug fix, first write a failing regression test that reproduces the issue, then implement the fix. Tests should use small synthetic inputs and **must not require WRDS credentials or live downloads**. Financial validation (KF/DM alignment, decile counts, monthly-vs-daily leg compounding) belongs in notebooks and, where feasible, deterministic fixtures.

## 7. Git collaboration: everyone uses their own name as a branch

**Team rule: each contributor should name their personal branch after their own name or GitHub username**, for example `yihangguo`. Work on your personal branch, not directly on `main`. The `main` branch is the shared stable baseline.

### A. Create a personal branch (new contributor)

```bash
# Get the latest shared code.
git switch main
git pull --ff-only ieor4576 main

# Replace <your_name> with YOUR OWN name or GitHub username.
git switch -c <your_name>

# Publish the branch and configure upstream tracking.
git push -u ieor4576 <your_name>
```

### B. Rename an existing branch to your own name

If you already created a branch under a generic name, **your commits will be preserved** when you rename it:

```bash
# First switch to the branch you want to rename.
git switch feature/my-work

# Replace <your_name> with YOUR OWN name.
git branch -m <your_name>
git push -u ieor4576 <your_name>
```

If the old remote branch exists, delete it **only after confirming the new branch was pushed successfully** and is not used by an open Pull Request or another teammate:

```bash
git push ieor4576 --delete feature/my-work
```

### C. Daily workflow: edit, test, commit, push

```bash
git switch <your_name>
git status
uv run pytest tests/ -v

git add path/to/changed_file.py tests/test_changed_file.py
git diff --cached --stat
git diff --cached --check
git commit -m "feat: describe the implemented change"
git push
```

Replace `<your_name>` and the file paths with your own. Do **not** blindly run `git add .` when local data files, notebooks, or secrets may be present. Use short, meaningful commit messages (`feat:`, `fix:`, `test:`, `docs:`).

### D. Merge completed work into main

Open a GitHub **Pull Request** with **base `main`** and **compare your personal branch**. Explain what changed, how to reproduce the result, which tests passed, and what limitations remain. Ask another teammate to review. Merge only after review and successful tests. A maintainer can merge locally if necessary, but PRs make team review and history clearer.

### E. Keep your personal branch up to date

```bash
git fetch ieor4576
git switch <your_name>
git merge ieor4576/main
uv run pytest tests/ -v
git push
```

If Git reports merge conflicts, resolve them carefully, especially notebook conflicts. Do not overwrite another person's results without review. Coordinate ownership of shared notebooks and move reusable code into tested `src/` modules.

### F. Check the current Git state

```bash
git remote -v
git branch -a
git branch --show-current
git status
git log -5 --oneline
```

Remember: `ieor4576` is the **remote alias**; `momentum-risk-project` is the **GitHub repository name**; `main` and personal names such as `yihangguo` are **branch names**.

## 8. Conventions and contribution checklist

- Write committed code, comments, notebook Markdown, plot labels, and research documentation in English.
- Use monthly `PeriodIndex` for monthly strategies and `DatetimeIndex` for daily returns.
- Check percentage-to-decimal conversions; `0.01` represents 1%.
- Do not confuse Kenneth French 2×3 `Mom` with value-weighted decile `P10 − P1`.
- Never introduce look-ahead bias: use only information available before the holding month.
- Add or update unit tests when changing a reusable function; run `uv run pytest tests/ -v`.
- Keep licensed data, personal credentials, virtual environments, and large outputs out of Git.
- Document changed inputs, assumptions, output tables, and known limitations in your PR.

---

**Repository:** [yihang-hannah/momentum-risk-project](https://github.com/yihang-hannah/momentum-risk-project). **Local research covered by this README: Notebooks 01–05.** Publication status must be checked separately; local completion does not imply a GitHub push or merge.
