from pathlib import Path
import json,argparse
import pandas as pd,numpy as np
from momentum_risk_project.stock_reconstruction import reconstruct_stock_wml,portfolio_returns
from momentum_risk_project.stock_backtest import simulate_stock_account
from momentum_risk_project.metrics import performance_metrics
from momentum_risk_project.stock_cli import sha256_file
parser=argparse.ArgumentParser(description='Formation-value screened controlled WML backtest')
parser.add_argument('--output',required=True);parser.add_argument('--private-output',required=True)
args=parser.parse_args()
R=Path(__file__).resolve().parents[1];C=R/'data/raw/03_stock_full_20261031';O=Path(args.output);P=Path(args.private_output)
assert not O.exists() and not P.exists()
cols=['permno','mthcaldt','mthret','mthretx','mthprc','mthprcdt','mthcap','mthretflg','mthdelflg','mthprcflg','legacy_shrcd','legacy_exchcd','securitytype','securitysubtype','sharetype','usincflg','issuertype','primaryexch','conditionaltype','tradingstatusflg','mthdtflg','mthcompsubflg']
from momentum_risk_project.wml_pipeline import build_from_cache
build=build_from_cache(C,start='1927-01',end='2025-12')
h=build.account_holdings('published_reference')
h['reference_return']=h.account_return
bp,a=build.breakpoints,build.audit
w=build.monthly_reference
old=pd.read_parquet(R/'data/processed/reference/pre_quality/holdings_membership.parquet',columns=['permno','formation_month','month','momentum_decile','leg_weight'])
raw=pd.read_parquet(C/'monthly_enriched.parquet',columns=['permno','mthcaldt','mthdtflg','mthcompsubflg'])
raw['formation_month']=pd.to_datetime(raw.mthcaldt).dt.to_period('M')
affected=old.merge(raw[raw.mthdtflg.eq('LA')][['permno','formation_month','mthcompsubflg']],on=['permno','formation_month'],how='inner',validate='one_to_one')
ref=pd.read_csv(R/'data/processed/reference/pre_quality/aligned_monthly_returns.csv',index_col=0);ref.index=pd.PeriodIndex(ref.index,freq='M')
weights=pd.read_csv(R/'data/processed/reference/pre_quality/shared_risk_weights.csv',index_col=0).iloc[:,0];weights.index=pd.PeriodIndex(weights.index,freq='M')
returns=pd.DataFrame({'KF_unmanaged':ref.KF_unmanaged,'old_unmanaged':ref.reconstructed_unmanaged,'quality_screened_unmanaged':w.WML,
    'KF_managed_shared_risk':ref.KF_managed_shared_risk,'quality_screened_managed_shared_risk':w.WML*weights}).reindex(ref.index)
metrics=[];errors=[];accounts={};costs=[]
for label,(start,end) in {'paper_available_common':('1927-05','2011-12'),'extension_disjoint':('2012-01','2025-12')}.items():
 idx=pd.period_range(start,end,freq='M');f=returns.reindex(idx);assert f.notna().all().all()
 for col in f:metrics.append(dict(window=label,strategy=col,**performance_metrics(f[col]).to_dict()))
 for col in ['old_unmanaged','quality_screened_unmanaged']:
  e=f[col]-f.KF_unmanaged;errors.append(dict(window=label,series=col,months=len(f),correlation=f[[col,'KF_unmanaged']].corr().iloc[0,1],MAE_bps=e.abs().mean()*10000,RMSE_bps=np.sqrt(e.pow(2).mean())*10000))
 hh=h[h.month.between(idx[0],idx[-1])&h.momentum_decile.isin([1,10])]
 for strategy,ww in [('unmanaged',pd.Series(1.,index=idx)),('managed_shared_KF_risk',weights.reindex(idx))]:
  ledger,_=build.backtest(ww,return_policy='published_reference',transaction_cost_bps=10.)
  complete=bool(ledger.net_return.notna().all() and ledger.state.eq('ok').all())
  accounts[label+'/'+strategy]=ledger
  costs.append(dict(window=label,strategy=strategy,complete=complete,evaluated_months=int(ledger.net_return.notna().sum()),mean_monthly_turnover=ledger.turnover.mean() if complete else np.nan,annual_trading_cost=12*ledger.transaction_cost.mean() if complete else np.nan,**(performance_metrics(ledger.net_return).to_dict() if complete else {})))
 print('Completed',label,flush=True)
O.mkdir();P.mkdir()
returns.to_csv(O/'monthly_returns.csv');pd.DataFrame(metrics).to_csv(O/'gross_metrics.csv',index=False);pd.DataFrame(errors).to_csv(O/'reconstruction_errors.csv',index=False);pd.DataFrame(costs).to_csv(O/'net_stock_metrics.csv',index=False)
pd.concat(accounts,names=['run','month']).to_csv(O/'stock_accounts.csv')
h.to_parquet(P/'holdings.parquet',index=False);bp.to_parquet(P/'breakpoints.parquet');affected.to_parquet(P/'removed_formation_records.parquet',index=False)
counts={'all_deciles_removed_stock_months':len(affected),'WML_removed_stock_months':int(affected.momentum_decile.isin([1,10]).sum()),'WML_removed_distinct_stocks':int(affected.loc[affected.momentum_decile.isin([1,10]),'permno'].nunique()),'WML_affected_holding_months':int(affected.loc[affected.momentum_decile.isin([1,10]),'month'].nunique())}
removed=old.merge(h[['permno','month']],on=['permno','month'],how='left',indicator=True,validate='one_to_one')
removed=removed[removed._merge.eq('left_only')]
counts['all_quality_removed_stock_months']=len(removed)
counts['all_quality_removed_prior_WML_stock_months']=int(removed.momentum_decile.isin([1,10]).sum())
manifest=dict(rule='Require period-end date and TR/BA price for formation value and t-13 price; reject stale, beginning-period and unavailable values. Apply before recalculating NYSE cutoffs, memberships and weights; never delete stocks permanently or use holding-month return.',counts=counts,audit=a,risk_policy='Shared unchanged lagged KF daily risk; own-stock daily inputs must be rebuilt for changed memberships and are not reused.',return_policy='Published-return reference, numeric monthly gaps zero; unresolved terminal values not reconciled by this filter.',source_sha256={str(p.relative_to(R)):sha256_file(p) for p in [C/'monthly_enriched.parquet',C/'price_gap_intervals.parquet']})
(O/'run.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(counts));print(pd.DataFrame(errors).to_string(index=False));print('1935-08',returns.loc['1935-08'].to_dict())
