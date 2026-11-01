import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.stock_reconstruction import (
    price_gap_exclusions, reconstruct_stock_wml, attach_delisting_evidence,
    portfolio_returns, scenario_returns,
)


def monthly_panel():
    records=[]
    for stock in range(1,21):
        for month in pd.period_range('1999-01','2000-03',freq='M'):
            records.append(dict(permno=stock,mthcaldt=month.end_time.date(),
                mthcap=float(stock),mthprc=10.,mthret=.001*stock,mthretx=.001*stock,
                mthdelflg='N',mthretflg='CR',mthprcflg='TR',
                legacy_shrcd=10,legacy_exchcd=1))
    return pd.DataFrame(records)


def test_historical_codes_exclude_foreign_and_off_exchange():
    m=monthly_panel()
    m.loc[m.permno.eq(20),'legacy_shrcd']=12
    m.loc[m.permno.eq(19),'legacy_exchcd']=-1
    h,_,_=reconstruct_stock_wml(m,start='2000-02',end='2000-03')
    assert not h.permno.isin([19,20]).any()
    np.testing.assert_allclose(h.groupby(['month','momentum_decile']).leg_weight.sum(),1)


def test_holding_returns_do_not_change_current_targets_or_remove_delisted_stock():
    m=monthly_panel()
    first,_,_=reconstruct_stock_wml(m,start='2000-02',end='2000-03')
    mask=m.permno.eq(1)&pd.to_datetime(m.mthcaldt).dt.to_period('M').eq(pd.Period('2000-02'))
    m.loc[mask,'mthret']=-.7
    m.loc[mask,'mthdelflg']='A'
    second,_,_=reconstruct_stock_wml(m,start='2000-02',end='2000-03')
    a=first[first.month.eq(pd.Period('2000-02'))].set_index('permno')
    b=second[second.month.eq(pd.Period('2000-02'))].set_index('permno')
    pd.testing.assert_series_equal(a.leg_weight,b.leg_weight)
    assert b.loc[1,'mthret']==-.7
    assert b.loc[1,'payoff_complete']
    assert not ((second.month==pd.Period('2000-03'))&(second.permno==1)).any()


def test_exact_200_boundary_and_reopening():
    calendar=pd.bdate_range('2000-01-01',periods=205)
    intervals=pd.DataFrame({'permno':[1],'exclusion_start_date':[calendar[201]],'exclusion_end_exclusive':[calendar[204]]})
    points=pd.DataFrame({'permno':[1,1,1,2],'date':[calendar[200],calendar[201],calendar[204],calendar[202]]})
    assert price_gap_exclusions(points,intervals).tolist()==[False,True,False,False]


def test_excluded_recorded_payoff_added_once_included_payoff_untouched():
    h=pd.DataFrame({'permno':[1,2,3,4], 'month':pd.PeriodIndex(['2000-01']*4,freq='M'),
       'mthret':[-.2,-.5,-.2,-.2],'mthdelflg':['G','A','M','V'],
       'numeric_return_available':[True]*4,'return_strict':[np.nan,-.5,np.nan,np.nan],
       'payoff_complete':[False,True,False,False],'return_resolution':['incomplete','complete','incomplete','partial']})
    d=pd.DataFrame({'permno':[1,2,3,4], 'delistingdt':pd.to_datetime(['2000-01-20']*4),
       'delret':[-.5,-.5,np.nan,-.3]})
    x=attach_delisting_evidence(h,d)
    assert x.loc[0,'return_strict']==pytest.approx(-.6)
    assert x.loc[1,'return_strict']==-.5
    assert x.loc[2:,'return_strict'].isna().all()
    assert x.loc[2:,'unresolved_final_payoff'].all()


def test_missing_stock_not_dropped_from_denominator_and_sensitivity_explicit():
    m=monthly_panel();mask=m.permno.eq(1)&pd.to_datetime(m.mthcaldt).dt.to_period('M').eq(pd.Period('2000-02'))
    m.loc[mask,'mthret']=np.nan
    h,_,_=reconstruct_stock_wml(m,start='2000-02',end='2000-03')
    w,_=portfolio_returns(h)
    assert pd.isna(w.loc['2000-02','P1'])
    assert h.loc[h.month.eq(pd.Period('2000-02'))&h.permno.eq(1),'leg_weight'].iloc[0]>0
    s=scenario_returns(h,0)
    assert s.scenario_imputed.sum()==1
    assert portfolio_returns(s,'return_scenario')[0].loc['2000-02','P1']>0


def test_ciz_fallback_is_tagged_and_only_used_after_2024():
    m=monthly_panel()
    m['mthcaldt']=pd.to_datetime(m.mthcaldt)+pd.DateOffset(years=25)
    m['securitytype']='EQTY';m['securitysubtype']='COM';m['sharetype']='NS'
    m['usincflg']='Y';m['issuertype']='CORP';m['primaryexch']='N'
    m['conditionaltype']='RW';m['tradingstatusflg']='A'
    # February 2025 holdings use January formation classification.
    formation=pd.to_datetime(m.mthcaldt).dt.to_period('M').eq(pd.Period('2025-01'))
    m.loc[formation,['legacy_shrcd','legacy_exchcd']]=np.nan
    m.loc[formation&m.permno.eq(20),'tradingstatusflg']='S'
    original=m[['legacy_shrcd','legacy_exchcd']].copy()
    h,_,audit=reconstruct_stock_wml(m,start='2025-02',end='2025-03')
    feb=h[h.month.eq(pd.Period('2025-02'))]
    assert not feb.permno.eq(20).any()
    assert feb.eligibility_source.str.startswith('CIZ').all()
    assert audit['ciz_fallback_eligible_stock_months']==19
    pd.testing.assert_frame_equal(original,m[['legacy_shrcd','legacy_exchcd']])
