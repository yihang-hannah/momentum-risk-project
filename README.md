# Momentum Risk Management — Project README

## Current progress

**Latest completed commit:** `ff8eca5` — `feat: complete KF momentum data pipeline and paper replication` (on the former `feature/data-pipeline` branch; rename/push status should be checked on GitHub). This commit contains **Notebook 01, Notebook 02, five Python source modules, and four test files**.

**Work Completed So Far:** momentum data exploration; replication of Barroso and Santa-Clara (2015) using Kenneth French **value-weighted momentum decile P10 − P1**; a 126-trading-day squared-return volatility estimator; lagged volatility-managed exposure; unmanaged/fixed-leverage/managed comparisons; factor regressions; performance reporting; and automated unit tests.

**Key replication results (historical paper-era sample):** unmanaged WML annualized mean **14.86%**, volatility **27.42%**, Sharpe **0.5419**; volatility-managed WML annualized mean **16.69%**, volatility **16.77%**, Sharpe **0.9958**. These are gross historical research outputs, not live trading results.

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
├── pyproject.toml              
├── uv.lock                     
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   └── 02_paper_replication.ipynb
├── src/
│   └── momentum_risk_project/
│       ├── data.py
│       ├── wml.py
│       ├── volatility.py
│       ├── strategies.py
│       └── metrics.py
└── tests/
    ├── test_data.py
    ├── test_metrics.py
    ├── test_strategies.py
    └── test_volatility.py
```

`wml.py` is committed as a reusable stock-level momentum utility, but **it is not required to run the validated Notebook 02 replication**. See the module reference below. Local raw data, generated caches, and figures are not guaranteed to be present in the repository.

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

## 6. Automated tests

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

**Repository:** [yihang-hannah/momentum-risk-project](https://github.com/yihang-hannah/momentum-risk-project). **Published research covered by this README: Notebook 01 and Notebook 02.**
