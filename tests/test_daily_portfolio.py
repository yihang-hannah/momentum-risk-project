import pandas as pd
import numpy as np
import pytest
from momentum_risk_project.daily_portfolio import daily_wml_from_holdings


def inputs():
    dates=pd.to_datetime(['2020-01-30','2020-01-31','2020-02-03','2020-02-04'])
    h=pd.DataFrame({'permno':[1,2],'month':pd.PeriodIndex(['2020-02']*2,freq='M'),
       'momentum_decile':[10,1],'leg_weight':[1.,1.],
       'formation_date':pd.to_datetime(['2020-01-31']*2),
       'formation_price_date':pd.to_datetime(['2020-01-31']*2),
       'mthdelflg':['N','N'],'payoff_complete':[True,True],
       'delistingdt':[pd.NaT,pd.NaT],'delret':[np.nan,np.nan]})
    d=pd.DataFrame({'permno':[1,1,2,2],'dlycaldt':pd.to_datetime(['2020-02-03','2020-02-04']*2),
       'dlydelflg':['N']*4,'dlyret':[.1,.1,-.1,0.], 'dlyprc':[11,12.1,9,9]})
    return h,d,dates


def test_daily_legs_calculated_separately():
    h,d,c=inputs();x=daily_wml_from_holdings(h,d,c)
    assert x.iloc[0].WML==pytest.approx(.2)
    assert x.iloc[1].WML==pytest.approx(.1)
    assert (1+x.P10).prod()-1==pytest.approx(.21)
    # Monthly WML is .21-(-.1)=.31, not compounded daily WML (.32).
    assert (1+x.WML).prod()-1==pytest.approx(.32)


def test_missing_price_carry_is_explicit_not_strict():
    h,d,c=inputs();d.loc[0,['dlyret','dlyprc']]=np.nan
    strict=daily_wml_from_holdings(h,d,c)
    carry=daily_wml_from_holdings(h,d,c,mode='carry_prices')
    assert strict.P10.isna().all()
    assert carry.iloc[0].P10==0
    assert carry.iloc[0].P10_carried_positions==1


def test_missing_return_with_valid_quote_not_filled():
    h,d,c=inputs();d.loc[0,'dlyret']=np.nan
    assert daily_wml_from_holdings(h,d,c,mode='carry_prices').P10.isna().all()


def test_delisting_component_not_double_counted():
    h,d,c=inputs();h.loc[0,['mthdelflg','delistingdt','delret']]=['A',pd.Timestamp('2020-02-03'),-.5]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-03')],
        'dlydelflg':['Y'],'dlyret':[-.5],'dlyprc':[np.nan]})],ignore_index=True)
    x=daily_wml_from_holdings(h,d,c)
    assert x.iloc[0].P10==pytest.approx(1.1*.5-1)
    assert x.iloc[1].P10==0


def test_next_day_delisting_component_attributed_once_before_cash_conversion():
    h,d,c=inputs();h.loc[0,['mthdelflg','delistingdt','delret']]=['A',pd.Timestamp('2020-02-03'),-.5]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-04')],
        'dlydelflg':['Y'],'dlyret':[-.5],'dlyprc':[np.nan]})],ignore_index=True)
    x=daily_wml_from_holdings(h,d,c)
    assert x.iloc[0].P10==pytest.approx(1.1*.5-1)
    assert x.iloc[1].P10==0


def test_zero_regular_gap_keeps_other_leg_actual_return():
    h,d,c=inputs();d.loc[0,'dlyret']=np.nan
    x=daily_wml_from_holdings(h,d,c,mode='zero_regular_dm')
    assert x.iloc[0].P10==0
    assert x.iloc[0].P1==pytest.approx(-.1)
    assert x.iloc[0].WML==pytest.approx(.1)
    assert x.iloc[0].P10_zero_imputed_components==1


def test_zero_regular_does_not_erase_known_delisting_component():
    h,d,c=inputs();d.loc[0,'dlyret']=np.nan
    h.loc[0,['mthdelflg','delistingdt','delret']]=['A',pd.Timestamp('2020-02-03'),-.5]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-03')],
        'dlydelflg':['Y'],'dlyret':[-.5],'dlyprc':[np.nan]})],ignore_index=True)
    x=daily_wml_from_holdings(h,d,c,mode='zero_regular_dm')
    assert x.iloc[0].P10==pytest.approx(-.5)
    assert x.iloc[1].P10==0


def test_unknown_terminal_payoff_is_not_zero_even_with_ordinary_gap_fill():
    h,d,c=inputs();h.loc[0,['mthdelflg','delistingdt','payoff_complete']]=['M',pd.Timestamp('2020-02-03'),False]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-03')],
        'dlydelflg':['Y'],'dlyret':[np.nan],'dlyprc':[np.nan]})],ignore_index=True)
    x=daily_wml_from_holdings(h,d,c,mode='zero_regular_dm')
    assert x.P10.isna().all()
    assert x.iloc[0].P10_unresolved_terminal_positions==1


def test_recorded_excluded_delisting_added_once_with_zero_ordinary_gap():
    h,d,c=inputs();d.loc[0,'dlyret']=np.nan
    h.loc[0,['mthdelflg','delistingdt','delret','payoff_complete']]=['G',pd.Timestamp('2020-02-03'),-.5,True]
    x=daily_wml_from_holdings(h,d,c,mode='zero_regular_dm')
    assert x.iloc[0].P10==pytest.approx(-.5)
    assert x.iloc[1].P10==0


def test_missing_y_recovered_from_recorded_payoff_not_zeroed():
    h,d,c=inputs();d.loc[0,'dlyret']=np.nan
    h.loc[0,['mthdelflg','delistingdt','delret','payoff_complete']]=['G',pd.Timestamp('2020-02-03'),-.7,True]
    d=pd.concat([d,pd.DataFrame({'permno':[1],'dlycaldt':[pd.Timestamp('2020-02-03')],
        'dlydelflg':['Y'],'dlyret':[np.nan],'dlyprc':[np.nan]})],ignore_index=True)
    x=daily_wml_from_holdings(h,d,c,mode='zero_regular_dm')
    assert x.iloc[0].P10==pytest.approx(-.7)
    assert x.iloc[1].P10==0


def test_missing_corporate_action_not_zero_filled():
    h,d,c=inputs();d['dlyretmissflg']='NA';d.loc[0,['dlyret','dlyretmissflg']]=[np.nan,'MV']
    assert daily_wml_from_holdings(h,d,c,mode='zero_regular_dm_checked').P10.isna().all()


def test_multisession_return_not_used_as_single_day_but_weekend_is_valid():
    h,d,c=inputs();d['dlyretdurflg']='D3'
    assert daily_wml_from_holdings(h,d,c,mode='zero_regular_dm_checked').P10.notna().all()
    d.loc[0,'dlyretdurflg']='P1'
    assert daily_wml_from_holdings(h,d,c,mode='zero_regular_dm_checked').P10.isna().all()
