import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.stock_backtest import simulate_stock_account


def inputs():
    h=pd.DataFrame({'permno':[1,2,1,2], 'month':pd.PeriodIndex(['2020-01','2020-01','2020-02','2020-02'],freq='M'),
      'momentum_decile':[10,1,10,1],'leg_weight':[1.]*4,
      'return_strict':[.1,-.1,0.,0.],'mthretx':[.1,-.1,0.,0.],
      'delistingdt':[pd.NaT]*4})
    w=pd.Series(1.,index=pd.period_range('2020-01',periods=2,freq='M'))
    return h,w


def test_zero_cost_account_matches_compounded_factor_returns():
    h,w=inputs();m,_=simulate_stock_account(h,w)
    assert m.iloc[0].end_nav==pytest.approx(1.2)
    assert m.iloc[1].end_nav==pytest.approx(1.2)
    assert m.iloc[1].turnover==pytest.approx(abs(1-1.1/1.2)+abs(-1+.9/1.2))


def test_initial_fees_self_funded_and_trade_ledger_reconciles():
    h,w=inputs();m,t=simulate_stock_account(h,w,transaction_cost_bps=10)
    x=1/(1+.002)
    assert m.iloc[0].postcost_nav==pytest.approx(x)
    assert m.iloc[0].transaction_cost==pytest.approx(1-x)
    assert m.iloc[0].net_return==pytest.approx(x*1.2-1)
    np.testing.assert_allclose(t.groupby('month').absolute_trade.sum(),m.turnover)


def test_unknown_return_stops_account_not_reset():
    h,w=inputs();h.loc[0,'return_strict']=np.nan
    m,_=simulate_stock_account(h,w)
    assert m.net_return.isna().all()
    assert m.iloc[0].state=='unresolved_price_or_payoff'
    assert m.iloc[1].state=='account_not_evaluable_after_gap'


def test_cash_position_needs_no_stock_returns():
    h,w=inputs();w[:]=0;h.return_strict=np.nan;h.mthretx=np.nan
    m,_=simulate_stock_account(h,w)
    np.testing.assert_allclose(m.net_return,0)


def test_current_return_cannot_change_current_trade():
    h,w=inputs();a,_=simulate_stock_account(h,w,transaction_cost_bps=10)
    h.loc[:1,'return_strict']=[-.2,.1]
    b,_=simulate_stock_account(h,w,transaction_cost_bps=10)
    assert a.iloc[0].turnover==b.iloc[0].turnover
