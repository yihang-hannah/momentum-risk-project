
import numpy as np
import pandas as pd
import pytest

from momentum_risk_project.data import (
    clean_momentum,
    read_processed_data,
    save_processed_data,
    load_momentum_returns,
)


def test_clean_daily_returns():
    """Test daily return conversion and index formatting."""

    # Arrange: create sample raw data
    raw = pd.DataFrame(
        {"Mom": [-0.53, 1.20]},
        index=pd.period_range(
            "2020-01-02",
            periods=2,
            freq="D",
        ),
    )

    # Act: execute the function under test
    cleaned = clean_momentum(raw, "daily")

    # Assert: verify expected behavior
    assert cleaned.columns.tolist() == ["mom"]
    assert isinstance(cleaned.index, pd.DatetimeIndex)
    assert cleaned.index.name == "date"
    assert cleaned["mom"].iloc[0] == -0.0053
    assert cleaned["mom"].iloc[1] == 0.012

    # Verify that the original data remains unchanged
    assert raw["Mom"].iloc[0] == -0.53

def test_clean_monthly_returns():
    """Test monthly return conversion and index formatting."""
    raw = pd.DataFrame(
        {"Mom": [2.52, -1.50]},
        index=pd.period_range(
            "2020-01",
            periods=2,
            freq="M",
        ),
    )

    cleaned = clean_momentum(raw, "monthly")

    assert isinstance(cleaned.index, pd.PeriodIndex)
    assert cleaned.index.freqstr == "M"
    assert cleaned.index.name == "month"
    assert cleaned["mom"].iloc[0] == pytest.approx(0.0252)


def test_reject_missing_values():
    """Test that missing returns are rejected."""
    raw = pd.DataFrame(
        {"Mom": [1.0, np.nan]},
        index=pd.period_range(
            "2020-01",
            periods=2,
            freq="M",
        ),
    )

    with pytest.raises(ValueError, match="non-finite"):
        clean_momentum(raw, "monthly")


def test_reject_duplicate_dates():
    """Test that duplicate dates are rejected."""
    raw = pd.DataFrame(
        {"Mom": [1.0, 2.0]},
        index=pd.PeriodIndex(
            ["2020-01", "2020-01"],
            freq="M",
        ),
    )

    with pytest.raises(ValueError, match="Duplicate"):
        clean_momentum(raw, "monthly")


def test_parquet_round_trip(tmp_path, monkeypatch):
    """Test that Parquet preserves values and index metadata."""
    import momentum_risk_project.data as data_module

    # Redirect output to a temporary test directory
    monkeypatch.setattr(
        data_module,
        "PROCESSED_DIR",
        tmp_path,
    )

    raw = pd.DataFrame(
        {"Mom": [2.52, -1.50]},
        index=pd.period_range(
            "2020-01",
            periods=2,
            freq="M",
        ),
    )

    expected = clean_momentum(raw, "monthly")

    save_processed_data(expected, "monthly")
    actual = read_processed_data("monthly")

    pd.testing.assert_frame_equal(expected, actual)


def test_cache_avoids_download(tmp_path, monkeypatch):
    """Test that cached data is loaded without downloading."""
    import momentum_risk_project.data as data_module

    monkeypatch.setattr(
        data_module,
        "PROCESSED_DIR",
        tmp_path,
    )

    # Prepare two valid cached datasets
    daily_raw = pd.DataFrame(
        {"Mom": [-0.53, 1.20]},
        index=pd.period_range(
            "2020-01-02",
            periods=2,
            freq="D",
        ),
    )

    monthly_raw = pd.DataFrame(
        {"Mom": [2.52, -1.50]},
        index=pd.period_range(
            "2020-01",
            periods=2,
            freq="M",
        ),
    )

    expected_daily = clean_momentum(daily_raw, "daily")
    expected_monthly = clean_momentum(monthly_raw, "monthly")

    save_processed_data(expected_daily, "daily")
    save_processed_data(expected_monthly, "monthly")

    # Replace the downloader with a function that always fails
    def forbidden_download(frequency):
        raise AssertionError("Download should not be called")

    monkeypatch.setattr(
        data_module,
        "download_momentum",
        forbidden_download,
    )

    # Loading must succeed using only the cached files
    daily, monthly = load_momentum_returns()

    pd.testing.assert_frame_equal(daily, expected_daily)
    pd.testing.assert_frame_equal(monthly, expected_monthly)


def test_missing_cache_downloads_and_saves(tmp_path, monkeypatch):
    """A cache miss downloads both frequencies and writes Parquet."""
    import momentum_risk_project.data as data_module

    monkeypatch.setattr(data_module, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(data_module, "RAW_DIR", tmp_path / "raw")
    requested = []

    def fake_download(frequency):
        requested.append(frequency)
        if frequency == "daily":
            return pd.DataFrame(
                {"Mom": [1.0, -2.0]},
                index=pd.period_range("2020-01-02", periods=2, freq="D"),
            )
        return pd.DataFrame(
            {"Mom": [3.0, -1.0]},
            index=pd.period_range("2020-01", periods=2, freq="M"),
        )

    monkeypatch.setattr(data_module, "download_momentum", fake_download)
    daily, monthly = load_momentum_returns()

    assert requested == ["daily", "monthly"]
    assert (tmp_path / "processed" / "01_momentum_daily.parquet").is_file()
    assert (tmp_path / "processed" / "01_momentum_monthly.parquet").is_file()
    pd.testing.assert_frame_equal(daily, read_processed_data("daily"))
    pd.testing.assert_frame_equal(monthly, read_processed_data("monthly"))


def test_partial_cache_only_downloads_missing_frequency(tmp_path, monkeypatch):
    """An existing daily cache must not be downloaded again."""
    import momentum_risk_project.data as data_module

    monkeypatch.setattr(data_module, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(data_module, "RAW_DIR", tmp_path / "raw")

    daily_raw = pd.DataFrame(
        {"Mom": [1.0, 2.0]},
        index=pd.period_range("2020-01-02", periods=2, freq="D"),
    )
    expected_daily = clean_momentum(daily_raw, "daily")
    save_processed_data(expected_daily, "daily")
    requested = []

    def fake_download(frequency):
        requested.append(frequency)
        if frequency != "monthly":
            raise AssertionError("Daily data must come from the cache")
        return pd.DataFrame(
            {"Mom": [3.0, -1.0]},
            index=pd.period_range("2020-01", periods=2, freq="M"),
        )

    monkeypatch.setattr(data_module, "download_momentum", fake_download)
    daily, monthly = load_momentum_returns()
    assert requested == ["monthly"]
    pd.testing.assert_frame_equal(daily, expected_daily)
    pd.testing.assert_frame_equal(monthly, read_processed_data("monthly"))


def test_refresh_redownloads_both_frequencies(tmp_path, monkeypatch):
    """Refresh bypasses existing cached data."""
    import momentum_risk_project.data as data_module

    monkeypatch.setattr(data_module, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(data_module, "RAW_DIR", tmp_path / "raw")
    requested = []

    def fake_download(frequency):
        requested.append(frequency)
        if frequency == "daily":
            return pd.DataFrame(
                {"Mom": [1.0]},
                index=pd.period_range("2020-01-02", periods=1, freq="D"),
            )
        return pd.DataFrame(
            {"Mom": [2.0]},
            index=pd.period_range("2020-01", periods=1, freq="M"),
        )

    monkeypatch.setattr(data_module, "download_momentum", fake_download)
    load_momentum_returns()
    load_momentum_returns(refresh=True)
    assert requested == ["daily", "monthly", "daily", "monthly"]
