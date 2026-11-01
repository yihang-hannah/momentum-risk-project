"""Independent risk inputs for rebuilt and KF strategies; no cross-source fallback."""
from .wml_pipeline import estimate_risk


def independent_risk(build,kf_daily,months,risk):
    if build.daily_reconstructed is None:
        raise ValueError("Reconstructed daily WML is absent; rebuild the dataset. KF risk fallback is forbidden.")
    params=dict(annual_target=risk["annual_target"],window=risk["window"],trading_days_per_month=risk["trading_days_per_month"])
    own=estimate_risk(build.daily_reconstructed.WML,months,**params)
    benchmark=estimate_risk(kf_daily,months,**params)
    if not own.forecast_available.all():
        missing=own.index[~own.forecast_available]
        raise ValueError(f"Own-risk warm-up/coverage unavailable for {len(missing)} months beginning {missing[0]}; do not substitute KF or cash")
    if not benchmark.forecast_available.all():raise ValueError("KF benchmark risk unavailable on the same comparison calendar")
    return own,benchmark
