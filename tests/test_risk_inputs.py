import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.risk_inputs import independent_risk
from momentum_risk_project.wml_pipeline import estimate_risk
from momentum_risk_project.daily_portfolio import daily_wml_from_holdings
from test_daily_portfolio import inputs
from test_wml_pipeline import bundle


def risk_fixture():
    b=bundle();idx=pd.bdate_range('1999-01-01','2000-03-31')
    b.daily_reconstructed=pd.DataFrame({'WML':.01+np.sin(np.arange(len(idx)))*.002},index=idx)
    kf=pd.Series(.03,index=idx)
    months=pd.period_range('2000-01','2000-03',freq='M')
    params={'annual_target':.12,'window':126,'trading_days_per_month':21}
    return b,kf,months,params


def test_kf_changes_cannot_change_rebuilt_positions():
    b,kf,months,params=risk_fixture()
    own,k=independent_risk(b,kf,months,params)
    changed=kf*9
    own2,k2=independent_risk(b,changed,months,params)
    pd.testing.assert_frame_equal(own,own2)
    assert not np.allclose(k.weight,k2.weight)
    expected=estimate_risk(b.daily_reconstructed.WML,months)
    pd.testing.assert_frame_equal(own,expected)


def test_own_future_returns_only_change_later_holding_months():
    b,kf,months,params=risk_fixture();own,k=independent_risk(b,kf,months,params)
    b.daily_reconstructed.loc['2000-02-01':,'WML']*=5
    changed,k2=independent_risk(b,kf,months,params)
    pd.testing.assert_frame_equal(own.loc[:'2000-02'],changed.loc[:'2000-02'])
    assert own.loc['2000-03','weight']!=changed.loc['2000-03','weight']
    pd.testing.assert_frame_equal(k,k2)


def test_no_kf_or_cash_fallback_for_missing_own_series_or_warmup():
    b,kf,months,params=risk_fixture()
    b.daily_reconstructed=None
    with pytest.raises(ValueError,match='fallback is forbidden'):independent_risk(b,kf,months,params)
    b,kf,months,params=risk_fixture()
    b.daily_reconstructed.loc['2000-01-31','WML']=np.nan
    with pytest.raises(ValueError,match='do not substitute KF or cash'):independent_risk(b,kf,months,params)


def test_component_zero_preserves_other_leg_not_zero_whole_wml():
    h,d,c=inputs();d.loc[0,'dlyret']=np.nan
    primary=daily_wml_from_holdings(h,d,c,mode='zero_missing_reconstructed')
    assert primary.iloc[0].P10==0
    assert primary.iloc[0].WML==pytest.approx(.1)


def test_unknown_terminal_zero_increment_is_explicit_and_strict_remains_unknown():
    h,d,c=inputs()
    h.loc[0,['mthdelflg','delistingdt','payoff_complete']]=['M',pd.Timestamp('2020-02-03'),False]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-03')],
        'dlydelflg':['Y'],'dlyret':[np.nan],'dlyprc':[np.nan]})],ignore_index=True)
    strict=daily_wml_from_holdings(h,d,c,mode='zero_regular_dm_checked')
    primary=daily_wml_from_holdings(h,d,c,mode='zero_missing_reconstructed')
    assert strict.WML.isna().all()
    assert primary.WML.notna().all()
    assert primary.iloc[0].P10==pytest.approx(.1)
    assert primary.iloc[0].P10_assumed_terminal_positions==1


def test_known_delisting_is_included_once_under_zero_scenario():
    h,d,c=inputs();h.loc[0,['mthdelflg','delistingdt','delret']]=['A',pd.Timestamp('2020-02-03'),-.5]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-03')],
        'dlydelflg':['Y'],'dlyret':[-.5],'dlyprc':[np.nan]})],ignore_index=True)
    primary=daily_wml_from_holdings(h,d,c,mode='zero_missing_reconstructed')
    assert primary.iloc[0].P10==pytest.approx(1.1*.5-1)
    assert primary.iloc[1].P10==0


def test_multisession_is_booked_once_at_observed_endpoint_and_flagged():
    h,d,c=inputs();d['dlyretdurflg']='D1';d.loc[0,'dlyretdurflg']='P1'
    p=daily_wml_from_holdings(h,d,c,mode='zero_missing_reconstructed')
    assert p.iloc[0].P10==pytest.approx(.1)
    assert p.iloc[0].P10_multisession_endpoint_components==1
    assert (1+p.P10).prod()-1==pytest.approx(.21)


def test_primary_monthly_keeps_known_dm_payoffs_and_explicitly_fills_residuals():
    from momentum_risk_project.wml_pipeline import value_holdings
    h=pd.DataFrame({'return_strict':[-.45,np.nan,np.nan], 'return_as_published':[.1,.1,np.nan],
      'mthdelflg':['G','M','M'],'delistingdt':pd.to_datetime(['2000-01-31']*3),
      'delret':[-.5,np.nan,np.nan],'payoff_complete':[True,False,False]})
    v=value_holdings(h)
    np.testing.assert_allclose(v.return_reconstructed,[-.45,.1,0.])
    assert v.return_dm.iloc[1:].isna().all()
    assert v.terminal_increment_assumed_zero.tolist()==[False,True,True]
