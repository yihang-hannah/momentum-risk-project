"""Audit current independent-risk results against source series and saved ledgers.

Run: python -m momentum_risk_project.own_risk_validation
The older validation.py audits only the historical architecture migration.
"""
import json
import numpy as np
import pandas as pd
from .config import configured_path
from .dashboard import load_snapshot, STRATEGIES, METHOD_LABELS
from .data import clean_momentum
from .risk_inputs import independent_risk
from .wml_pipeline import load_build, file_sha256


def audit_own_risk(root=None):
    snapshot = load_snapshot(root)
    root, config = snapshot.root, snapshot.config
    build = load_build(configured_path(config, "build", root))
    gross = snapshot.frames["gross_reference_returns"]
    months = gross.index
    kf_daily = clean_momentum(pd.read_parquet(configured_path(config, "kf_daily", root)), "daily").mom
    own, kf = independent_risk(build, kf_daily, months, config["risk"])
    folder = configured_path(config, "study", root)
    for filename, expected in [("own_risk_coverage", own), ("KF_risk_weights", kf)]:
        actual = pd.read_csv(folder / (filename + ".csv"), index_col=0)
        actual.index = pd.PeriodIndex(actual.index, freq="M")
        np.testing.assert_allclose(actual.weight, expected.weight, atol=1e-12)
        assert actual.forecast_available.all()
    monthly = build.monthly_reconstructed.WML.reindex(months)
    kf_monthly = clean_momentum(pd.read_parquet(configured_path(config, "kf_monthly", root)), "monthly").mom.reindex(months)
    for column, expected in [("Rebuilt unmanaged", monthly), ("Rebuilt managed", monthly * own.weight),
                             ("KF unmanaged", kf_monthly), ("KF managed", kf_monthly * kf.weight)]:
        np.testing.assert_allclose(gross[column], expected, atol=1e-12)
    funded = snapshot.frames["funded_monthly"]
    for strategy, weight in [("unmanaged", pd.Series(1., index=months)), ("managed_own_risk", own.weight)]:
        for cost in snapshot.costs:
            ledger = funded.loc[funded.strategy.eq(strategy) & funded.cost_bps_per_dollar.eq(cost)].set_index("month").reindex(months)
            assert ledger.state.eq("ok").all()
            np.testing.assert_allclose(ledger.factor_weight, weight, atol=1e-12)
            np.testing.assert_allclose(ledger.gross_factor_return, monthly * weight, atol=1e-12)
            np.testing.assert_allclose(ledger.transaction_cost, ledger.turnover * cost / 10000, atol=1e-12)
            np.testing.assert_allclose(ledger.net_return, ledger.postcost_nav / ledger.pretrade_nav * (1 + ledger.gross_factor_return) - 1, atol=1e-12)
    checks = 0
    metrics = snapshot.frames["metrics"]
    for window in config["windows"]:
        for method in METHOD_LABELS:
            for cost in snapshot.costs:
                view = snapshot.select(window, method=method, cost=cost)
                for strategy, label in STRATEGIES.items():
                    expected = metrics.loc[metrics.window.eq(window) & metrics.method.eq(method) & metrics.strategy.eq(strategy) & metrics.cost_bps_per_dollar.eq(cost)].iloc[0]
                    for key, value in view.metrics.loc[label].items():
                        np.testing.assert_allclose(value, expected[key], atol=1e-12)
                checks += 1
    baseline = root / "data/interim/refactor_baseline_20261101/raw_sha256.json"
    raw_count = 0
    if baseline.exists():
        for name, digest in json.loads(baseline.read_text()).items():
            if name.endswith(".gitkeep"):
                continue
            assert file_sha256(root / name) == digest, name
            raw_count += 1
    result = {"risk_source": "independent per strategy; no KF fallback", "months": len(months),
              "complete_daily_observations": int(build.daily_reconstructed.WML.notna().sum()),
              "verified_dashboard_scenarios": checks, "unchanged_raw_files": raw_count,
              "checks": "source weights, gross returns, funded fee/NAV identities, saved dashboard metrics"}
    output = configured_path(config, "results", root) / "replication/tables/own_risk_validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit_own_risk(), indent=2))
