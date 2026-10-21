
from pathlib import Path

import numpy as np
import pandas as pd
from pandas_datareader import data as web


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DATASET_NAMES = {
    "daily": "10_Portfolios_Prior_12_2_Daily",
    "monthly": "10_Portfolios_Prior_12_2",
}


def validate_frequency(frequency: str) -> None:
    """Validate the requested data frequency."""
    if frequency not in DATASET_NAMES:
        raise ValueError("frequency must be 'daily' or 'monthly'")


def download_momentum(frequency: str) -> pd.DataFrame:
    """Download raw momentum returns from Kenneth French."""
    validate_frequency(frequency)

    result = web.DataReader(
        DATASET_NAMES[frequency],
        "famafrench",
        start="1926-01-01",
    )

    return result[0]


def clean_momentum(
    df: pd.DataFrame,
    frequency: str,
) -> pd.DataFrame:
    """Clean and standardize raw momentum returns."""
    validate_frequency(frequency)

    if df.shape[1] != 10:
        raise ValueError("Expected exactly ten momentum decile columns")

    # Kenneth French table 0: value-weighted deciles, low to high.
    loser = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    winner = pd.to_numeric(df.iloc[:, -1], errors="coerce")
    if loser.isna().any() or winner.isna().any():
        raise ValueError("Non-numeric or missing decile returns detected")
    if (loser <= -90).any() or (winner <= -90).any():
        raise ValueError("Missing-return sentinel detected in momentum deciles")
    cleaned = ((winner - loser) / 100.0).to_frame(name="mom")

    if frequency == "daily":
        if isinstance(cleaned.index, pd.PeriodIndex):
            cleaned.index = cleaned.index.to_timestamp()
        elif not isinstance(cleaned.index, pd.DatetimeIndex):
            raise TypeError("Daily data must have a date index")

        cleaned.index.name = "date"

    else:
        if isinstance(cleaned.index, pd.DatetimeIndex):
            cleaned.index = cleaned.index.to_period("M")
        elif not isinstance(cleaned.index, pd.PeriodIndex):
            raise TypeError("Monthly data must have a date index")

        if cleaned.index.freqstr != "M":
            cleaned.index = cleaned.index.asfreq("M")

        cleaned.index.name = "month"

    cleaned = cleaned.sort_index()
    validate_cleaned_data(cleaned, frequency)

    return cleaned


def validate_cleaned_data(
    df: pd.DataFrame,
    frequency: str,
) -> None:
    """Validate the schema and values of cleaned data."""
    validate_frequency(frequency)

    if df.columns.tolist() != ["mom"]:
        raise ValueError("Expected exactly one column: mom")

    expected_index_type = (
        pd.DatetimeIndex
        if frequency == "daily"
        else pd.PeriodIndex
    )

    if not isinstance(df.index, expected_index_type):
        raise TypeError("Unexpected index type")

    if frequency == "monthly" and df.index.freqstr != "M":
        raise ValueError("Expected monthly PeriodIndex")

    if not df.index.is_unique:
        raise ValueError("Duplicate dates detected")

    if not df.index.is_monotonic_increasing:
        raise ValueError("Dates must be sorted")

    if df.empty:
        raise ValueError("DataFrame is empty")

    if not pd.api.types.is_numeric_dtype(df["mom"]):
        raise TypeError("Momentum returns must be numeric")

    if not np.isfinite(df["mom"].to_numpy()).all():
        raise ValueError("Missing or non-finite returns detected")


def raw_path(frequency: str) -> Path:
    """Return the raw CSV file path."""
    validate_frequency(frequency)
    return RAW_DIR / f"kf_deciles_{frequency}_vw.csv"


def processed_path(frequency: str) -> Path:
    """Return the processed Parquet file path."""
    validate_frequency(frequency)
    return PROCESSED_DIR / f"kf_wml_deciles_{frequency}_vw.parquet"


def save_raw_data(
    df: pd.DataFrame,
    frequency: str,
) -> Path:
    """Save raw source data to CSV."""
    path = raw_path(frequency)
    path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(path)
    return path


def save_processed_data(
    df: pd.DataFrame,
    frequency: str,
) -> Path:
    """Save validated returns to Parquet."""
    validate_cleaned_data(df, frequency)

    path = processed_path(frequency)
    path.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(
        path,
        engine="pyarrow",
        compression="snappy",
    )

    return path


def read_processed_data(
    frequency: str,
) -> pd.DataFrame:
    """Load and validate cached Parquet returns."""
    path = processed_path(frequency)

    df = pd.read_parquet(
        path,
        engine="pyarrow",
    )

    validate_cleaned_data(df, frequency)
    return df


def load_momentum_returns(
    refresh: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load daily and monthly KF value-weighted decile P10-P1 returns."""
    datasets = {}

    for frequency in ("daily", "monthly"):
        path = processed_path(frequency)

        if path.exists() and not refresh:
            cleaned = read_processed_data(frequency)

        else:
            raw = download_momentum(frequency)
            save_raw_data(raw, frequency)

            cleaned = clean_momentum(raw, frequency)
            save_processed_data(cleaned, frequency)

        datasets[frequency] = cleaned

    return datasets["daily"], datasets["monthly"]


def load_wml_decile_returns(refresh: bool = False) -> tuple[pd.Series, pd.Series]:
    """Return daily and monthly KF value-weighted P10-P1 as `wml` Series."""
    daily, monthly = load_momentum_returns(refresh=refresh)
    return daily["mom"].rename("wml"), monthly["mom"].rename("wml")
