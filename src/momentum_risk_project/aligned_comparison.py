"""Aligned metrics helper; the old shared-KF-risk runner is retired.

Current independent-source construction and studies are orchestrated by run_all.py.
Legacy entrypoints fail before reading or writing data, so they cannot regenerate
obsolete shared-risk results by accident.
"""
import numpy as np
import pandas as pd
from .metrics import performance_metrics

WINDOWS = {
    "paper_available_common": ("1927-07", "2011-12"),
    "extension_disjoint": ("2012-01", "2025-12"),
}


def aligned_metrics(frame, windows=WINDOWS):
    """Withhold a whole window if any series is missing; never drop gap months."""
    rows=[]
    for label,(start,end) in windows.items():
        idx=pd.period_range(start,end,freq='M')
        block=frame.reindex(idx)
        complete=bool(np.isfinite(block.to_numpy()).all())
        for name in block:
            row=dict(window=label,start=start,end=end,months=len(idx),series=name,
                complete_comparison=complete,missing_months=int(block[name].isna().sum()))
            if complete:row.update(performance_metrics(block[name]).to_dict())
            rows.append(row)
    return pd.DataFrame(rows)



def run(*args, **kwargs):
    raise ValueError("The shared-KF-risk runner is retired. Run python run_all.py for independent reconstructed daily risk.")


def audit_own_risk(*args, **kwargs):
    raise ValueError("The legacy carry-price audit is retired. Run python -m momentum_risk_project.own_risk_validation.")


def main():
    run()


if __name__ == "__main__":
    main()
