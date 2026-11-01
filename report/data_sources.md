# Data sources and local storage

CRSP is the provider and WRDS the access platform. The current annual extraction
covers December 1925–December 2025, with original query text and fingerprints in
raw-cache manifests. KF value-weighted momentum deciles and decimal FF3 are
independent frozen public inputs. Consult Notebook 03's opening specification,
CIZ_FLAGS.md and WML_PIPELINE.md for official links and field-specific rules.

- `data/raw`: immutable downloaded/query-extract bytes and original manifests.
- `data/interim/stock_inputs`: selected/validated monthly, delisting and gap inputs;
  its staging manifest binds each derived file to the original source hashes.
- `data/processed/wml_current`: final stock holdings, monthly/daily returns and
  artifact/source fingerprints. Its pipeline signature binds parameters, source
  manifests and construction code; replacements are archived, not overwritten.
- `data/processed/stock_study`: final continuous research accounts/metrics;
  `stock_trades` contains licensed identifiers and stays ignored.
- `data/interim/research_history`: preserved pre-refactor outputs/audits.
- `data/interim/reference` and `03_aug1935_audit_verified_20261031`: old optional
  diagnostic evidence; never required to generate current results.
- `data/interim/refactor_baseline_20261101`: original notebooks, reports, settings,
  scripts and raw-byte inventory used to verify this migration.

Old dated processed builds remain private until reviewed for a separate cleanup.
No files under data are committed. Access requires local licensed permissions;
missing inputs fail with acquisition instructions instead of fabricated returns.
Original manifests may contain historical extraction locations; they are retained
as evidence rather than edited to claim a different source vintage.
