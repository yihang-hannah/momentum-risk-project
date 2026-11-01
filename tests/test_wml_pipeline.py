import numpy as np,pandas as pd,pytest
from momentum_risk_project.wml_pipeline import build_wml,estimate_risk,save_build,load_build,rebuild_daily
from test_stock_reconstruction import monthly_panel


def bundle():
    m=monthly_panel();m['mthdtflg']='PE';m['mthprcdt']=m.mthcaldt
    m.loc[m.permno.eq(20)&pd.to_datetime(m.mthcaldt).dt.to_period('M').eq(pd.Period('2000-01')),['mthdtflg','mthprcdt']]=['LA',pd.Timestamp('2000-01-15')]
    d=pd.DataFrame({'permno':pd.Series(dtype=int),'delistingdt':pd.Series(dtype='datetime64[ns]'),'delret':pd.Series(dtype=float)})
    return build_wml(m,d,start='2000-02',end='2000-03')


def test_builder_filters_formation_then_allows_later_reentry_and_roundtrip(tmp_path):
    b=bundle();assert not b.holdings.loc[b.holdings.month.eq(pd.Period('2000-02'))].permno.eq(20).any()
    assert b.holdings.loc[b.holdings.month.eq(pd.Period('2000-03'))].permno.eq(20).any()
    save_build(b,tmp_path/'artifact');c=load_build(tmp_path/'artifact')
    pd.testing.assert_frame_equal(b.monthly_dm,c.monthly_dm)
    with pytest.raises(FileExistsError):save_build(b,tmp_path/'artifact')
    (tmp_path/'artifact/monthly_dm.parquet').write_bytes(b'broken')
    with pytest.raises(ValueError,match='fingerprint'):load_build(tmp_path/'artifact')


def test_targets_and_stock_fees_use_current_holdings():
    b=bundle();w=pd.Series(1.,index=b.monthly_dm.index)
    t=b.targets(w);np.testing.assert_allclose(t.groupby('month').signed_weight.sum(),0,atol=1e-12)
    np.testing.assert_allclose(t.groupby('month').signed_weight.apply(lambda s:s.abs().sum()),2)
    ledger,trades=b.backtest(w,return_policy='published_reference',transaction_cost_bps=10)
    assert ledger.state.eq('ok').all() and ledger.transaction_cost.gt(0).all()
    assert {'permno','trade_weight','absolute_trade'}.issubset(trades)
    with pytest.raises(ValueError):b.account_holdings('implicit')
    w.iloc[0]=np.nan
    with pytest.raises(ValueError):b.backtest(w,return_policy='dm')


def test_risk_uses_calendar_lag_keeps_missing_and_has_no_future_leakage():
    dates=pd.bdate_range('1999-01-01','2000-03-31');d=pd.Series(.01,index=dates)
    months=pd.period_range('1999-01','2000-03',freq='M');a=estimate_risk(d,months)
    np.testing.assert_allclose(a.previous_month_sigma.dropna(),np.sqrt(21*.0001))
    changed=d.copy();changed.loc['2000-02-01':]=.9;b=estimate_risk(changed,months)
    pd.testing.assert_frame_equal(a.loc[:'2000-02'],b.loc[:'2000-02'])
    d.loc['2000-01-31']=np.nan
    assert pd.isna(estimate_risk(d,months).loc['2000-02','weight'])


def test_daily_refuses_unverified_universe(tmp_path):
    import json
    (tmp_path/'cache_manifest.json').write_text(json.dumps({'status':'complete','membership_digest':'wrong'}))
    with pytest.raises(ValueError,match='membership'):rebuild_daily(bundle(),tmp_path)


def test_cost_backtest_can_select_an_explicit_complete_subwindow():
    b=bundle();w=pd.Series(1.,index=pd.period_range('2000-03','2000-03',freq='M'))
    ledger,_=b.backtest(w,return_policy='published_reference',transaction_cost_bps=10.)
    assert ledger.index.equals(w.index) and ledger.transaction_cost.gt(0).all()
    assert b.targets(w).month.nunique()==1


def test_unknown_terminal_never_implicitly_becomes_reference():
    m=monthly_panel();m['mthdtflg']='PE';m['mthprcdt']=m.mthcaldt
    mask=m.permno.eq(1)&pd.to_datetime(m.mthcaldt).dt.to_period('M').eq(pd.Period('2000-02'))
    m.loc[mask,'mthdelflg']='M'
    d=pd.DataFrame({'permno':[1],'delistingdt':pd.to_datetime(['2000-02-04']),'delret':[np.nan]})
    b=build_wml(m,d,start='2000-02',end='2000-03')
    assert pd.isna(b.monthly_dm.loc['2000-02','WML'])
    assert pd.notna(b.monthly_reference.loc['2000-02','WML'])
    weights=pd.Series(1.,index=b.monthly_dm.index)
    ledger,_=b.backtest(weights,return_policy='dm')
    assert ledger.net_return.isna().all()


def test_daily_roundtrip_normalizes_timestamp_units_without_changing_values(tmp_path):
    b=bundle()
    b.daily=pd.DataFrame({'P1':[.01,np.nan],'P10':[.02,.03],'WML':[.01,np.nan]},
        index=pd.DatetimeIndex(['2000-02-01','2000-02-02']).as_unit('s'))
    save_build(b,tmp_path/'build')
    restored=load_build(tmp_path/'build')
    expected=b.daily.copy();expected.index=expected.index.as_unit('ns')
    pd.testing.assert_frame_equal(restored.daily,expected)
