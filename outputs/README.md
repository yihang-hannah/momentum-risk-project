# Current notebook outputs

- Notebook 01: plots remain inline; data caches are under `data/processed/`.
- Notebook 02: `02_momentum_replication_metrics.parquet` (fixed main-branch path).
- Notebook 03: `03_wml/report/` is the current src API report. `validation/` holds
  its frozen monthly/daily comparison targets and plots; `diagnostics/` holds the
  August 1935 investigation and field dictionary. Historical path names in source
  manifests are provenance, resolved by `03_wml/relocation_map.json`.
- Notebook 04: `04_backtest/` retains its verified factor-cost engine output;
  notebook plots and calculations remain inline.

Only current results and required validation assets are retained. Superseded
outputs and data were moved to a dedicated macOS Trash folder, not permanently
removed. The cleanup inventory is recorded in that folder's cleanup_manifest.json.

Recovery folder: `momentum-risk-project-cleanup-20261101_002535` in macOS Trash. Original paths are recorded in cleanup_manifest.json inside it.

## Notebook 05

`05_stock_backtest/` contains the current reconstructed-WML stock-cost study:
complete conditional KF/rebuilt gross comparisons, funded-account and Appendix B
cost sensitivities, strict coverage, significance cutoffs, plots and run manifest.
The paper's distinct 1951-03 to 2010-12 turnover test is evaluated separately.
Regenerate offline with `python scripts/run_stock_cost_study.py`.
