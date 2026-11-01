import pandas as pd
import numpy as np
from momentum_risk_project.aligned_comparison import aligned_metrics


def test_common_windows_withhold_all_metrics_if_either_series_has_gap():
    months=pd.period_range('2000-01','2000-03',freq='M')
    frame=pd.DataFrame({'KF':[.01,.02,.03],'own':[.01,np.nan,.03]},index=months)
    result=aligned_metrics(frame,{'test':('2000-01','2000-03')})
    assert not result.complete_comparison.any()
    assert 'CAGR' not in result
    assert result.set_index('series').loc['own','missing_months']==1
    frame.loc[months[1],'own']=.02
    result=aligned_metrics(frame,{'test':('2000-01','2000-03')})
    assert result.complete_comparison.all()
    assert result.CAGR.notna().all()


def test_default_evaluation_uses_only_paper_and_disjoint_extension():
    from momentum_risk_project.aligned_comparison import WINDOWS
    assert set(WINDOWS)=={'paper_available_common','extension_disjoint'}
    assert WINDOWS['paper_available_common']==('1927-05','2011-12')
    assert WINDOWS['extension_disjoint']==('2012-01','2025-12')
