"""Generate rolling GARCH forecasts for historical and extension samples."""

from pathlib import Path
import time

from momentum_risk_project.paths import project_root
from momentum_risk_project.config import load_config, configured_path
from momentum_risk_project.wml_pipeline import load_build
from momentum_risk_project.garch import garch_monthly_volatility


def main():
    root = project_root()
    config = load_config(root=root)
    build = load_build(configured_path(config, "build", root))

    daily = build.daily_reconstructed["WML"]

    output_dir = root / "outputs" / "garch"
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = {
        "historical": {
            "start": None,
            "end": "2011-11-30",
            "first_forecast": "1929-07",
            "last_forecast": "2011-11",
        },
        "extension": {
            "start": "2009-01-01",
            "end": "2025-11-30",
            "first_forecast": "2011-12",
            "last_forecast": "2025-11",
        },
    }

    for name, settings in samples.items():
        sample_daily = daily.loc[
            settings["start"]:settings["end"]
        ]

        start_time = time.perf_counter()

        forecasts = garch_monthly_volatility(
            sample_daily,
            estimation_window=756,
            forecast_horizon=21,
        ).dropna()

        forecasts = forecasts.loc[
            settings["first_forecast"]:settings["last_forecast"]
        ]

        expected = 989 if name == "historical" else 168

        if len(forecasts) != expected:
            raise RuntimeError(
                f"{name}: expected {expected} forecasts, "
                f"found {len(forecasts)}"
            )

        path = output_dir / f"{name}_garch_monthly_volatility.parquet"
        forecasts.to_frame().to_parquet(path)

        print(
            f"{name}: {len(forecasts)} forecasts, "
            f"{forecasts.index.min()} to {forecasts.index.max()}, "
            f"{time.perf_counter() - start_time:.2f} seconds"
        )
        print("Saved:", path)


if __name__ == "__main__":
    main()
