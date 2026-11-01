# Repository refactor validation

Validated locally on 2026-11-01. This is a record of completed software/reproduction
checks, not a claim of identical provider vintages or resolved terminal payoffs.
The checks describe the recorded local execution; the published source revision is identified in Git history.

## Implemented course layout

- Central relative paths: `src/momentum_risk_project/paths.py`; validated scientific
  settings, universe, windows, costs and seed: `configs/config.yaml` / `config.py`.
- Untouched provider/query extracts remain in `data/raw`; selected/validated
  working fields and historical audits are in `data/interim`; final stock build
  and continuous study datasets are in `data/processed`.
- Official estimation/evaluation/figures are in `models.py`, `evaluation.py`,
  `plotting.py`, `study.py` and existing detailed WML/account modules. Thin scripts
  01–04 and `pipeline.py` orchestrate them; `run_all.py` / Makefile rebuild all.
- Reported output assets are separated into replication/extension tables/figures.
  Notebooks only explore, display and independently/API-check scripted results.
- Pip editable dev extras, setuptools and frozen uv installation work. All data,
  generated results and secrets are ignored; documentation moved out of data.
- Original notebooks/research scripts, reports and manifests remain recoverable
  in private intermediate history. No original provider byte was rewritten.

## Completed tests and execution checks

1. **103 tests passed**, retaining all 93 previous behavioral tests and adding
   10 tests for paths/config, cache integrity, missing-input behavior, four-strategy
   equations/information boundaries, regressions, staging/signature reuse,
   study invalidation, orchestration and scope-specific export.
2. Actual `python -m pip install -e ".[dev]"` completed, including editable build.
   `uv sync --frozen --extra dev` and lock validation completed without changing
   scientific dependency versions.
3. CLI help for all four ordered scripts, `run_all.py` and the installed console
   command completed. Makefile command expansion covers every target; its exact
   underlying commands were run in full pipeline/notebook/test verification.
4. **Cold rebuild:** isolated the generated results and final stock-study cache,
   then ran `python run_all.py --force-build`. This reconstructed the stock build
   from frozen raw inputs and all formal historical/extension assets, with no
   notebook execution or previous generated result input.
5. All five active notebooks executed successfully against the new structure.
   Notebook 02's independent equations and FF3/FF4 regressions match formal package
   reports. Notebook 04's unpacked factor account matches both its engine and the
   scripted scenario. Notebook 05's stock-account/trade prefix matches the full
   continuous study.
6. Original preserved FF3/FF4 display tables agree at their retained four-decimal
   precision; independent full-precision regression/API checks also passed.
7. Figures were visually inspected for readable legends/titles/axes, complete
   scope separation and preserved conditional interpretations. Local links,
   English API/test instructions and saved notebook outputs were checked.

## Numerical and provenance audit

`python -m momentum_risk_project.validation` performs the optional migration audit
when the private original baseline and dated artifact are present. It is **not**
a production dependency. Its result is written to
`results/replication/tables/refactor_validation.json` and can be reproduced after
any normal results rebuild.

The audit verified **18 objects/categories**: metrics, turnover, cutoffs, coverage,
observations, full funded monthly ledger, Appendix B monthly returns,
gross-reference returns, own-risk coverage, strict account, both strategy turnover
ledgers, strict/reference monthly WML, checked daily WML, common original holding
fields, original paper strategy returns and applied weights. Numeric CSV
round-trips match within `1e-12`; WML artifacts/holding fields match exactly.
The historical original index's missing name is normalized to `month`; this is
label metadata, not a return/weight change.

**288 actual raw input files** match their pre-refactor SHA-256 inventory.
Removed zero-byte `.gitkeep` directory scaffolding is not a provider download and
is explicitly excluded from that raw-data count. Original source manifests and
old reports are retained with their original content under private history.
New signatures bind staged/processed inputs, config and scientific code. They
never rewrite an old provider release as if it were a fresh observation.

## Repeat the public workflow

```bash
python run_all.py
python -m pytest -p no:cacheprovider tests/ -q
python scripts/validate_notebooks.py
```

For the stronger raw-input reconstruction, use `python run_all.py --force-build`;
prior final builds are archived under `data/interim/superseded_builds`. Existing
raw files are only verified. Initial acquisition requires explicit `--download`
and licensed WRDS permissions. A fresh clone without licensed inputs will fail
with actionable missing-input instructions, never invent substitute observations.

## Scientific limitations preserved

The complete reference uses published monthly stock aggregates and shared KF
risk; ordinary missing returns use the accepted zero assumption. Strict terminal
values and own-stock risk gaps remain unknown. Neither software tests nor moving
files makes the strict independent-stock managed strategy complete. The paper's
inverse-L turnover ambiguity, early risk warm-up, post-sample versus
post-publication distinction and cost/funding omissions remain documented in
Notebook 03/05 and the methodology guides. EWMA/GARCH and the frontend remain
planned work, outside this completed layout refactor.
