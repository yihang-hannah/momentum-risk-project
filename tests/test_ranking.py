import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.ranking import kf_ranking_signals


def panel():
    return pd.DataFrame({
        'permno': 1, 'month': pd.period_range('2019-01', periods=15, freq='M'),
        'mthret': .01, 'mthprc': 10., 'mthprcflg': 'TR',
        'mthretflg': 'CR', 'mthdelflg': 'N',
    })


def test_complete_history_matches_product():
    x = kf_ranking_signals(panel()).set_index('month')
    assert x.loc['2020-01', 'momentum_signal'] == pytest.approx(1.01**11-1)


def test_permitted_ciz_missing_price_no_longer_requires_eleven_valid_returns():
    x = panel()
    x.loc[4, ['mthret', 'mthprc', 'mthprcflg', 'mthretflg']] = [np.nan, np.nan, 'MP', 'NT']
    row = kf_ranking_signals(x).set_index('month').loc['2020-01']
    assert row.kf_ranking_valid
    assert not row.complete_11_month_signal
    assert row.observed_ranking_returns == 10
    assert row.allowed_missing_price_months == 1
    assert row.momentum_signal == pytest.approx(1.01**10-1)
    assert pd.isna(x.loc[4, 'mthret'])


@pytest.mark.parametrize('code,allowed', [(-99., True), (-77., False), (-66., False), (np.nan, False)])
def test_only_explicit_legacy_missing_price_code_is_allowed(code, allowed):
    x = panel()
    x['legacy_return_missing_code'] = np.nan
    x.loc[4, 'mthret'] = np.nan
    x.loc[4, 'legacy_return_missing_code'] = code
    row = kf_ranking_signals(x).set_index('month').loc['2020-01']
    assert bool(row.kf_ranking_valid) == allowed


def test_recent_t_minus_two_must_be_good_even_for_missing_price():
    x = panel()
    x.loc[10, ['mthret', 'mthprc', 'mthprcflg', 'mthretflg']] = [np.nan, np.nan, 'MP', 'NT']
    assert not kf_ranking_signals(x).set_index('month').loc['2020-01', 'kf_ranking_valid']


def test_unknown_nan_and_absent_month_still_fail():
    x=panel()
    x.loc[4,'mthret']=np.nan
    assert not kf_ranking_signals(x).set_index('month').loc['2020-01', 'kf_ranking_valid']
    x=panel().drop(index=4)
    assert not kf_ranking_signals(x).set_index('month').loc['2020-01', 'kf_ranking_valid']


def test_future_returns_do_not_change_current_ranking():
    x=panel()
    baseline=kf_ranking_signals(x).set_index('month')
    x.loc[x.month >= pd.Period('2019-12'),'mthret']=.9
    changed=kf_ranking_signals(x).set_index('month')
    assert baseline.loc['2020-01','momentum_signal'] == changed.loc['2020-01','momentum_signal']


def test_total_loss_is_valid_minus_one_signal():
    x=panel();x.loc[4,'mthret']=-1
    row=kf_ranking_signals(x).set_index('month').loc['2020-01']
    assert row.kf_ranking_valid
    assert row.momentum_signal == -1


def test_duplicates_rejected():
    x=panel()
    with pytest.raises(ValueError): kf_ranking_signals(pd.concat([x,x.iloc[:1]]))
