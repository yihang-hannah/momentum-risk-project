"""Tests for Kenneth French value-weighted decile WML ingestion."""

import numpy as np
import pandas as pd
import pytest

import momentum_risk_project.data as data_module
from momentum_risk_project.data import (
    clean_momentum,
    load_momentum_returns,
    load_wml_decile_returns,
    read_processed_data,
    save_processed_data,
)


def sample_deciles(frequency):
    index = (
        pd.date_range("2020-01-02", periods=2, freq="B")
        if frequency == "daily"
        else pd.period_range("2020-01", periods=2, freq="M")
    )
    values = np.zeros((2, 10))
    values[:, 0] = [-2.0, 1.0]
    values[:, -1] = [3.0, 4.0]
    return pd.DataFrame(values, index=index, columns=[f"D{i}" for i in range(1, 11)])


@pytest.mark.parametrize("frequency", ["daily", "monthly"])
def test_clean_decile_wml(frequency):
    raw = sample_deciles(frequency)
    actual = clean_momentum(raw, frequency)
    assert actual.columns.tolist() == ["mom"]
    assert actual["mom"].tolist() == pytest.approx([0.05, 0.03])
    if frequency == "daily":
        assert isinstance(actual.index, pd.DatetimeIndex)
    else:
        assert isinstance(actual.index, pd.PeriodIndex)


def test_reject_wrong_number_of_deciles():
    with pytest.raises(ValueError, match="ten"):
        clean_momentum(pd.DataFrame({"Mom": [1.0]}), "monthly")


def test_reject_missing_and_sentinel():
    raw = sample_deciles("monthly")
    raw.iloc[0, -1] = np.nan
    with pytest.raises(ValueError, match="missing"):
        clean_momentum(raw, "monthly")
    raw = sample_deciles("monthly")
    raw.iloc[0, 0] = -99.99
    with pytest.raises(ValueError, match="sentinel"):
        clean_momentum(raw, "monthly")


def test_reject_duplicate_dates():
    raw = sample_deciles("monthly")
    raw.index = pd.PeriodIndex(["2020-01", "2020-01"], freq="M")
    with pytest.raises(ValueError, match="Duplicate"):
        clean_momentum(raw, "monthly")


def test_cache_reuse_and_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(data_module, "PROCESSED_DIR", tmp_path)
    daily = clean_momentum(sample_deciles("daily"), "daily")
    monthly = clean_momentum(sample_deciles("monthly"), "monthly")
    save_processed_data(daily, "daily")
    save_processed_data(monthly, "monthly")
    pd.testing.assert_frame_equal(
        read_processed_data("monthly"),
        monthly,
        check_freq=False,
    )

    def fail_download(frequency):
        raise AssertionError("Should not download cached data")

    monkeypatch.setattr(data_module, "download_momentum", fail_download)
    actual_daily, actual_monthly = load_momentum_returns()
    pd.testing.assert_frame_equal(actual_daily, daily, check_freq=False)
    pd.testing.assert_frame_equal(actual_monthly, monthly, check_freq=False)

    series_daily, series_monthly = load_wml_decile_returns()
    pd.testing.assert_series_equal(
        series_daily,
        daily["mom"].rename("wml"),
        check_freq=False,
    )

    pd.testing.assert_series_equal(
        series_monthly,
        monthly["mom"].rename("wml"),
        check_freq=False,
)