import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml
from momentum_risk_project.config import load_config,config_digest
from momentum_risk_project.dashboard import load_snapshot,DashboardDataError,STRATEGIES
from momentum_risk_project.evaluation import describe
from momentum_risk_project.wml_pipeline import file_sha256


@pytest.fixture
def dashboard_root(tmp_path):
    c=load_config();c['periods'].update(build_start='2000-01',study_start='2000-01',end='2000-06')
    c['windows']={'paper_available_common':['2000-01','2000-03'],'paper_turnover_test':['2000-02','2000-03'],'extension_disjoint':['2000-04','2000-06']}
    (tmp_path/'configs').mkdir();(tmp_path/'configs/config.yaml').write_text(yaml.safe_dump(c))
    folder=tmp_path/c['paths']['study'];folder.mkdir(parents=True)
    months=pd.period_range('2000-01',periods=6,freq='M',name='month')
    u=np.array([-.02,.01,.03,.015,-.01,.02]);m=.6*u+.005
    gross=pd.DataFrame({'KF unmanaged':u+.001,'Rebuilt reference unmanaged':u,'KF managed':m+.001,'Rebuilt reference managed':m},index=months)
    gross.to_csv(folder/'gross_reference_returns.csv')
    ledgers=[];appendix=[];metric_rows=[]
    for name,r,weight in [('unmanaged',u,1.),('managed_shared_KF_risk',m,.6)]:
        for cost in c['costs']['transaction_cost_bps']:
            x=1/(1+2*cost/10000);net=x*(1+r)-1;ends=np.cumprod(1+net)
            f=pd.DataFrame({'month':months,'factor_weight':weight,'state':'ok','gross_factor_return':r,'net_return':net,
                'turnover':2*x,'transaction_cost':2*x*cost/10000,'financing_cost':0.,'end_nav':ends,
                'strategy':name,'cost_bps_per_dollar':float(cost)})
            ledgers.append(f)
            methods={'funded_account':net,'appendix_scaled_positions':r-2*cost/10000,'appendix_literal_eq10':r-3*cost/10000}
            for method,n in methods.items():
                if method!='funded_account':appendix.append(pd.DataFrame({'month':months,'strategy':name,'method':method,'cost_bps_per_dollar':float(cost),'gross_return':r,'net_return':n,'half_turnover':1. if method.endswith('positions') else 1.5}))
                for window,(a,z) in c['windows'].items():
                    ser=pd.Series(n,index=months).loc[a:z]
                    metric_rows.append({'window':window,'strategy':name,'method':method,'cost_bps_per_dollar':float(cost),**describe(ser)})
    pd.concat(ledgers).to_csv(folder/'funded_monthly.csv',index=False)
    pd.concat(appendix).to_csv(folder/'appendix_monthly.csv',index=False)
    pd.DataFrame(metric_rows).to_csv(folder/'metrics.csv',index=False)
    coverage=pd.DataFrame([{'window':w,'months':len(pd.period_range(a,z,freq='M')),'own_stock_risk_forecasts':0,
        'strict_DM_monthly_returns':1,'strict_continuous_account_known_months':0,'cash_fill_used':False} for w,(a,z) in c['windows'].items()])
    coverage.to_csv(folder/'coverage.csv',index=False)
    pd.DataFrame({'window':list(c['windows']),'value':[1.,1.,1.]}).to_csv(folder/'turnover.csv',index=False)
    pd.DataFrame({'window':list(c['windows']),'value':[1.,1.,1.]}).to_csv(folder/'cutoffs.csv',index=False)
    (tmp_path/'source.txt').write_text('frozen source evidence')
    (tmp_path/'code.txt').write_text('fixed synthetic study code')
    manifest={'config_digest':config_digest(c),'cost_bps_per_dollar':c['costs']['transaction_cost_bps'],'risk':c['risk'],
        'input_sha256':{'source.txt':file_sha256(tmp_path/'source.txt')},'code_sha256':{'code.txt':file_sha256(tmp_path/'code.txt')},
        'output_sha256':{str(p.relative_to(tmp_path)):file_sha256(p) for p in folder.glob('*.csv')}}
    (folder/'run.json').write_text(json.dumps(manifest))
    return tmp_path


def test_exact_saved_scenarios_and_no_kf_cost_inference(dashboard_root):
    s=load_snapshot(dashboard_root)
    a=s.select('paper_available_common',cost=0)
    b=s.select('paper_available_common',cost=50)
    assert (a.returns>b.returns).all().all()
    assert a.metrics.loc['Risk managed','Annualized Mean Return']>b.metrics.loc['Risk managed','Annualized Mean Return']
    with pytest.raises(DashboardDataError,match='KF'):s.select('extension_disjoint',source='KF',basis='net')
    with pytest.raises(DashboardDataError,match='not been computed'):s.select('extension_disjoint',cost=12.5)
    gross=s.select('extension_disjoint',source='KF',basis='gross')
    assert gross.account.empty and gross.cost==0
    assert gross.metadata(s,10000)['accounting']=='gross benchmark only'


def test_rebased_capital_and_initial_drawdown_are_correct(dashboard_root):
    v=load_snapshot(dashboard_root).select('paper_available_common',cost=0)
    w,d=v.curves(10000);w2,_=v.curves(5000)
    assert w.iloc[0].eq(10000).all() and d.iloc[0].eq(0).all()
    assert d.iloc[1].lt(0).all()  # First negative month is a real drawdown from initial capital.
    np.testing.assert_allclose(w2,w/2)
    from io import BytesIO
    export=pd.read_csv(BytesIO(v.download(10000)))
    assert len(export)==3
    np.testing.assert_allclose(export['Unmanaged return'],v.returns.Unmanaged)
    for invalid in [0,-1,float('inf')]:
        with pytest.raises(ValueError):v.curves(invalid)


def test_tampering_and_missing_results_fail_without_writing(dashboard_root,tmp_path):
    s=load_snapshot(dashboard_root);p=dashboard_root/s.config['paths']['study']/'gross_reference_returns.csv'
    p.write_text('corrupt')
    with pytest.raises(DashboardDataError,match='changed'):load_snapshot(dashboard_root)
    empty=tmp_path/'empty';(empty/'configs').mkdir(parents=True)
    (empty/'configs/config.yaml').write_text((dashboard_root/'configs/config.yaml').read_text())
    with pytest.raises(DashboardDataError,match='not available'):load_snapshot(empty)
    assert not (empty/'data').exists()


def test_internal_gap_is_not_compounded_or_replaced_with_cash(dashboard_root):
    s=load_snapshot(dashboard_root)
    frame=s.frames['funded_monthly']
    s.frames['funded_monthly']=frame.loc[~(frame.month.eq(pd.Period('2000-02')) & frame.strategy.eq('unmanaged'))]
    with pytest.raises(DashboardDataError,match='unresolved'):s.select('paper_available_common')


def test_frontend_switches_scenarios_and_explains_missing_data(dashboard_root,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('MOMENTUM_PROJECT_ROOT',str(dashboard_root))
    app=Path(__file__).resolve().parents[1]/'app/streamlit_app.py'
    at=AppTest.from_file(str(app)).run(timeout=25)
    assert not at.exception
    initial=at.metric[0].value
    at.select_slider(key='fee').set_value(50.).run()
    assert not at.exception and at.metric[0].value!=initial
    at.selectbox(key='window').select('extension_disjoint').run()
    assert not at.exception
    at.selectbox(key='method').select('appendix_literal_eq10').run()
    assert not at.exception
    at.selectbox(key='source').select('KF WML · gross benchmark').run()
    assert not at.exception
    assert at.radio(key='basis').value=='Gross before costs'
    assert at.radio(key='basis').disabled
    assert any('unavailable' in x.value.lower() for x in at.info)
    at.selectbox(key='source').select('Rebuilt WML · stock reference').run()
    at.radio(key='basis').set_value('Net of trading costs').run()
    assert not at.exception


def test_frontend_empty_state_is_actionable(dashboard_root,tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    root=tmp_path/'missing';(root/'configs').mkdir(parents=True)
    (root/'configs/config.yaml').write_text((dashboard_root/'configs/config.yaml').read_text())
    monkeypatch.setenv('MOMENTUM_PROJECT_ROOT',str(root))
    app=Path(__file__).resolve().parents[1]/'app/streamlit_app.py'
    at=AppTest.from_file(str(app)).run(timeout=20)
    assert not at.exception
    assert any('not available' in x.value for x in at.info)
    assert any('python run_all.py' in x.value for x in at.code)


def test_invalid_settings_have_an_actionable_frontend_error(dashboard_root):
    p=dashboard_root/'configs/config.yaml';c=yaml.safe_load(p.read_text());c['universe']['share_codes']=[10]
    p.write_text(yaml.safe_dump(c))
    with pytest.raises(DashboardDataError,match='settings'):load_snapshot(dashboard_root)
