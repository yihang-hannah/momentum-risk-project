import json

import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.backtest import run_backtest
from momentum_risk_project.cli import main


@pytest.fixture
def inputs():
    dates = pd.bdate_range("2019-12-01", "2020-06-30")
    daily = pd.Series(0.01, index=dates)
    monthly = pd.Series([0.01, -0.02, 0.03, 0.04, -0.01, 0.02],
                        index=pd.period_range("2020-01", periods=6, freq="M"))
    return daily, monthly


def test_cost_accounting_and_initial_entry(inputs):
    ledger, _ = run_backtest(*inputs, window=2, transaction_cost_bps=10,
                            financing_cost_bps=120, target_volatility=0.6)
    managed = ledger.loc["managed"]
    weight = (0.6 / np.sqrt(12)) / (np.sqrt(21) * 0.01)
    assert managed.iloc[0].weight == pytest.approx(weight)
    assert managed.iloc[0].transaction_cost == pytest.approx(2 * weight * 0.001)
    assert managed.iloc[1].transaction_cost == pytest.approx(0)
    assert managed.iloc[0].financing_cost == pytest.approx((weight - 1) * 0.012 / 12)
    np.testing.assert_allclose(managed.net_return,
                               managed.gross_return - managed.transaction_cost - managed.financing_cost)
    assert ledger.loc["unmanaged"].iloc[0].transaction_cost == pytest.approx(0.002)


def test_zero_cost_cap_and_common_sample(inputs):
    ledger, summary = run_backtest(*inputs, window=2, leverage_cap=0.5)
    managed = ledger.loc["managed"]
    assert managed.weight.max() == 0.5
    pd.testing.assert_series_equal(managed.net_return, managed.gross_return, check_names=False)
    assert ledger.loc["unmanaged"].index.equals(managed.index)
    assert len(summary) == 4


def test_lag_no_lookahead_and_changed_exposure(inputs):
    daily, monthly = inputs
    changed = daily.copy()
    changed.loc["2020-03":] *= 2
    first, _ = run_backtest(daily, monthly, window=2, transaction_cost_bps=10)
    second, _ = run_backtest(changed, monthly, window=2, transaction_cost_bps=10)
    a, b = first.loc["managed"], second.loc["managed"]
    assert a.loc["2020-03", "weight"] == b.loc["2020-03", "weight"]
    assert b.loc["2020-04", "weight"] == pytest.approx(a.loc["2020-04", "weight"] / 2)
    assert b.loc["2020-04", "turnover_proxy"] == pytest.approx(
        2 * abs(b.loc["2020-04", "weight"] - b.loc["2020-03", "weight"]))


@pytest.mark.parametrize("kwargs", [
    {"transaction_cost_bps": -1}, {"financing_cost_bps": np.nan},
    {"leverage_cap": 0}, {"start": "2030-01"},
])
def test_bad_parameters(inputs, kwargs):
    with pytest.raises(ValueError):
        run_backtest(*inputs, window=2, **kwargs)


def test_missing_risk_month_rejected(inputs):
    daily, monthly = inputs
    daily = daily[daily.index.month != 3]
    with pytest.raises(ValueError, match="Missing lagged"):
        run_backtest(daily, monthly, window=2)


def test_cli_reproducible_and_no_overwrite(inputs, tmp_path):
    daily, monthly = inputs
    paths = [tmp_path / "daily.parquet", tmp_path / "monthly.parquet"]
    for series, path in zip((daily, monthly), paths):
        series.rename("mom").to_frame().to_parquet(path)
    args = ["--daily", str(paths[0]), "--monthly", str(paths[1]),
            "--window", "2", "--transaction-cost-bps", "10", "--output-dir"]
    first, second = tmp_path / "first", tmp_path / "second"
    main(args + [str(first)])
    main(args + [str(second)])
    for name in ("monthly_ledger.csv", "summary.csv", "run.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert json.loads((first / "run.json").read_text())["transaction_cost_bps"] == 10
    with pytest.raises(SystemExit):
        main(args + [str(first)])


def test_cli_raw_deciles(inputs, tmp_path):
    daily, monthly = inputs
    paths = [tmp_path / "daily.parquet", tmp_path / "monthly.parquet"]
    for series, path in zip((daily, monthly), paths):
        table = pd.DataFrame(0.0, index=series.index, columns=range(10))
        table[9] = series * 100
        table.to_parquet(path)
    output = tmp_path / "raw_run"
    main(["--daily", str(paths[0]), "--monthly", str(paths[1]),
          "--raw-deciles", "--window", "2", "--output-dir", str(output)])
    ledger = pd.read_csv(output / "monthly_ledger.csv")
    unmanaged = ledger.loc[ledger.strategy == "unmanaged"]
    expected = monthly.reindex(pd.PeriodIndex(unmanaged.month, freq="M"))
    np.testing.assert_allclose(unmanaged.wml, expected)
