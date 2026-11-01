# Retained research data

## Raw

- `03_stock_full_20261031/`: complete frozen CRSP monthly history, calendar,
  metadata, delistings and original selected-stock daily observations.
- `03_quality_daily_20261031/`: fingerprinted new-universe daily cache and
  supplements, including its membership attestation. Cache bundles stay intact.
- `02_kf_momentum_deciles_*`: canonical KF source inputs for Notebooks 02–04.
- `02_ff3_*`: frozen FF3 source and provenance for future attribution work.
- `03_version_audit_20261030/`: original public KF snapshot evidence.
- `DM_data_2014_02.tar.gz`: original DM archive. All 12 extracted text files were
  verified byte-identical before removing the redundant extracted copy.
- `momentum_*.csv`: original small momentum source files retained as source evidence.

## Processed

- `wml_current_v1_20261031/`: current src API build for Notebook 05; schema and
  file fingerprints are validated by `load_build`.
- `01_momentum_*`, `kf_wml_deciles_*` and `02_momentum_*`: current caches for notebooks and the data module. Notebook 01 caches were regenerated from retained KF sources; the previous 1963-only caches remain recoverable in Trash.
- `reference/pre_quality/`: compact before-quality membership and reference
  series needed to reproduce diagnostics/comparisons. It is not the current build.
- `03_aug1935_audit_verified_20261031/`: retained private security-level evidence.

Licensed stock identities remain local and ignored by Git. Earlier derived
holdings and subset caches were moved to a recoverable macOS Trash directory.

Recovery folder: `momentum-risk-project-cleanup-20261101_002535` in macOS Trash. Original paths are recorded in cleanup_manifest.json inside it.

## Notebook 05 reusable stock trades

`processed/05_stock_backtest/` stores licensed PERMNO-level Appendix B stock
transitions and 10bp funded-account trades, generated from the current WML
artifact. These are useful for subsequent stock-level cost analysis and are
Git-ignored. Aggregated results live under `outputs/05_stock_backtest/`.
