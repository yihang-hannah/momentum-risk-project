"""Historical research entry; current construction API: wml_pipeline.

Offline, reproducible stock-level WML research and cost scenarios.

python -m momentum_risk_project.stock_cli --cache-dir ... --output-dir ...
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

from .daily_portfolio import daily_wml_from_holdings
from .metrics import performance_metrics
from .stock_backtest import simulate_stock_account
from .stock_reconstruction import reconstruct_stock_wml,attach_delisting_evidence,portfolio_returns,scenario_returns


def sha256_file(path):
    value=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def run_research(cache_dir,output_dir,*,start='1963-01',end='2011-12',transaction_cost_bps=10.,
                 financing_cost_bps=0.,target_volatility=.12,leverage_cap=None,
                 private_artifacts_dir=None,kf_monthly=None,dm_monthly=None,progress=print):
    cache_dir,output_dir=Path(cache_dir),Path(output_dir)
    private=Path(private_artifacts_dir) if private_artifacts_dir else None
    if output_dir.exists() or (private is not None and private.exists()):
        raise FileExistsError('Choose new output and private-artifact directories')
    for value in (transaction_cost_bps,financing_cost_bps):
        if not np.isfinite(value) or value<0:raise ValueError('Cost parameters must be finite and nonnegative')
    if not np.isfinite(target_volatility) or target_volatility<=0:raise ValueError('Invalid target volatility')
    if leverage_cap is not None and (not np.isfinite(leverage_cap) or leverage_cap<=0):raise ValueError('Invalid leverage cap')
    start,end=pd.Period(start,freq='M'),pd.Period(end,freq='M')
    if end<start:raise ValueError('End precedes start')
    monthly=pd.read_parquet(cache_dir/'monthly_enriched.parquet')
    calendar=pd.read_parquet(cache_dir/'calendar.parquet')
    delists=pd.read_parquet(cache_dir/'delists.parquet')
    gaps=pd.read_parquet(cache_dir/'price_gap_intervals.parquet')
    first_month=pd.to_datetime(monthly.mthcaldt).dt.to_period('M').min()
    warm_start=max(start-12,first_month+13)
    holdings,breakpoints,audit=reconstruct_stock_wml(monthly,start=str(warm_start),end=str(end),price_intervals=gaps)
    holdings=attach_delisting_evidence(holdings,delists)
    holdings['return_best_available']=holdings.return_strict.combine_first(holdings.return_as_published)
    portfolio_frames={}
    for label,column in [('strict','return_strict'),('as_published','return_as_published'),('best_available','return_best_available')]:
        portfolio_frames[label]=portfolio_returns(holdings,column)[0].loc[start:end]
    dates=pd.DatetimeIndex(pd.to_datetime(calendar.loc[calendar.tradingflg.eq('Y')&calendar.exchangegroup.eq('CIZ'),'caldt'])).sort_values().unique()
    daily_frames={'strict':[],'carry_prices':[]}
    for year in range(warm_start.year,end.year+1):
        path=cache_dir/'held_daily'/f'{year}.parquet'
        if not path.exists():raise FileNotFoundError(f'Required daily cache missing for {year}')
        daily=pd.read_parquet(path)
        positions=holdings.loc[holdings.month.dt.year.eq(year)&holdings.momentum_decile.isin([1,10])]
        if positions.empty:continue
        for mode in daily_frames:
            daily_frames[mode].append(daily_wml_from_holdings(positions,daily,dates,mode=mode))
        progress(f'Reconstructed daily portfolios: {year}')
    daily_frames={mode:pd.concat(frames).sort_index() for mode,frames in daily_frames.items()}
    risk_input=daily_frames['carry_prices'].WML
    sigma_daily=np.sqrt(21*risk_input.pow(2).rolling(126,min_periods=126).mean())
    sigma_monthly=sigma_daily.groupby(sigma_daily.index.to_period('M')).agg(lambda s:s.iloc[-1])
    sigma_monthly.index=sigma_monthly.index+1
    months=pd.period_range(start,end,freq='M')
    forecast=sigma_monthly.reindex(months)
    valid=np.isfinite(forecast)&forecast.gt(0)
    managed=((target_volatility/np.sqrt(12))/forecast).where(valid,0.)
    if leverage_cap is not None:managed=managed.clip(upper=leverage_cap)
    weight_frame=pd.DataFrame({'previous_month_sigma':forecast,'forecast_available':valid,
         'unmanaged':1.,'managed':managed},index=months)
    sample=holdings.loc[holdings.month.between(start,end)].copy()
    wml_sample=sample.loc[sample.momentum_decile.isin([1,10])]
    scenarios={'strict':None,'unresolved_total_minus_100pct':-1.,
               'unresolved_total_minus_50pct':-.5,'unresolved_total_zero':0.,'unresolved_total_plus_50pct':.5}
    summary_rows=[];ledgers={};private_trades={}
    for scenario,value in scenarios.items():
        scenario_holdings=sample if value is None else scenario_returns(sample,value)
        return_column='return_strict' if value is None else 'return_scenario'
        for strategy in ['unmanaged','managed']:
            for cost_case,bps,fbps in [('gross',0.,0.),('net',transaction_cost_bps,financing_cost_bps)]:
                ledger,trades=simulate_stock_account(scenario_holdings,weight_frame[strategy],return_column=return_column,
                       transaction_cost_bps=bps,financing_cost_bps=fbps)
                key=f'{scenario}/{strategy}/{cost_case}'
                ledgers[key]=ledger
                row={'scenario':scenario,'strategy':strategy,'cost_case':cost_case,
                     'total_months':len(ledger),'evaluated_account_months':int(ledger.net_return.notna().sum()),
                     'full_sample_evaluable':bool(ledger.net_return.notna().all() and ledger.state.eq('ok').all()),
                     'active_months':int(weight_frame[strategy].ne(0).sum()),
                     'cash_months':int(weight_frame[strategy].eq(0).sum()),
                     'mean_monthly_turnover':ledger.turnover.mean(),
                     'annualized_mean_trading_cost':12*ledger.transaction_cost.mean(),
                     'annualized_mean_financing_cost':12*ledger.financing_cost.mean()}
                if row['full_sample_evaluable'] and len(ledger)>=2:
                    row.update(performance_metrics(ledger.net_return).to_dict())
                else:
                    for field in ('mean_monthly_turnover','annualized_mean_trading_cost','annualized_mean_financing_cost'):
                        row[field]=np.nan
                summary_rows.append(row)
                if private is not None and scenario=='unresolved_total_zero' and cost_case=='net':
                    private_trades[strategy]=trades
        progress(f'Completed cost scenario: {scenario}')
    summary=pd.DataFrame(summary_rows)
    full_ledger=pd.concat(ledgers,names=['run','month'])
    comparisons=[];pairs={}
    benchmark=None
    if kf_monthly is not None:
        k=pd.read_parquet(kf_monthly)
        k.index=pd.PeriodIndex(k.index,freq='M')
        benchmark=((k.iloc[:,-1]-k.iloc[:,0])/100).rename('KF')
        pairs['KF']=benchmark
    if dm_monthly is not None:
        d=pd.read_csv(dm_monthly,sep=r'\s+',header=None,names=['date','decile','return','market_cap','n_stocks'],dtype=str)
        for col in ['date','decile','return']:d[col]=pd.to_numeric(d[col],errors='coerce')
        d=d.dropna(subset=['date','decile','return'])
        d['month']=pd.to_datetime(d.date.astype('int64').astype(str),format='%Y%m%d').dt.to_period('M')
        p=d.pivot(index='month',columns='decile',values='return')
        pairs['DM']=p[10]-p[1]
    for source,series in pairs.items():
        for method,frame in portfolio_frames.items():
            pair=pd.concat([frame.WML.rename('reconstructed'),series.rename('benchmark')],axis=1).loc[start:end].dropna()
            if pair.empty:continue
            error=pair.reconstructed-pair.benchmark
            comparisons.append({'benchmark':source,'return_policy':method,'paired_months':len(pair),
               'correlation':pair.corr().iloc[0,1],'mean_absolute_error_bps':error.abs().mean()*10000,
               'max_absolute_error_bps':error.abs().max()*10000})
    reconciliation={}
    for mode,daily_frame in daily_frames.items():
        daily_monthly=daily_frame[['P1','P10']].groupby(daily_frame.index.to_period('M')).agg(lambda s:(1+s).prod(skipna=False)-1)
        paired=portfolio_frames['strict'][['P1','P10']].join(daily_monthly,lsuffix='_monthly',rsuffix='_daily').dropna()
        max_bps=max((paired.P1_monthly-paired.P1_daily).abs().max(),(paired.P10_monthly-paired.P10_daily).abs().max())*10000 if len(paired) else None
        reconciliation[mode]={'paired_complete_months':len(paired),'max_leg_reconciliation_error_bps':max_bps}
        if max_bps is not None and max_bps>0.1:raise ValueError('Daily/monthly leg reconciliation exceeds 0.1 bp; inspect source timing')
    uncertain=wml_sample.loc[wml_sample.return_strict.isna()].groupby(['month','momentum_decile']).leg_weight.sum().unstack(fill_value=0).reindex(index=months,columns=[1,10],fill_value=0)
    uncertain.columns=['unresolved_short_leg_weight','unresolved_long_leg_weight']
    audit.update({'daily_monthly_reconciliation':reconciliation,'research_months':len(months),'research_wml_stock_months':len(wml_sample),
       'missing_numeric_wml_stock_months':int((~wml_sample.numeric_return_available).sum()),
       'recorded_excluded_payoffs_added_once':int(wml_sample.return_resolution.eq('recorded_excluded_delisting_return_added_once').sum()),
       'unresolved_final_payoff_stock_months':int(wml_sample.unresolved_final_payoff.sum()),
       'strict_known_wml_months':int(portfolio_frames['strict'].WML.notna().sum()),
       'published_known_wml_months':int(portfolio_frames['as_published'].WML.notna().sum()),
       'cash_months_due_to_unavailable_risk':int((~valid).sum()),
       'same_holdings_daily_risk':True,'market_calendar_trading_days':len(dates),
       'status':'implementation_complete_source_uncertainty_retained',
       'limitations':['Unresolved final payoffs remain unknown; sensitivities are not observed net performance.',
         'KF legacy missing-code equivalence is not proven by the CIZ semantic adapter.',
         'Daily quote-carry/as-published terminal valuation is an explicit risk-input sensitivity.',
         'Recorded late payoff attribution is research accounting, not actual receipt-time cash settlement.',
         'Monthly total-return P&L / ex-distribution stock drift does not model intra-month reinvestment trades.',
         'Missing risk forecast moves the managed strategy to cash; no forward or stale forecast is used.']})
    inputs={str(p.relative_to(cache_dir)):sha256_file(p) for p in sorted(cache_dir.rglob('*.parquet'))}
    manifest={'parameters':{'start':str(start),'end':str(end),'transaction_cost_bps':transaction_cost_bps,
       'financing_cost_bps':financing_cost_bps,'target_volatility':target_volatility,'leverage_cap':leverage_cap},
       'cache_inputs_sha256':inputs,'source_schema':'crsp_a_stock','source_observed_coverage_end':'2025-12-31',
       'risk_policy':'same-stock monthly-formed daily WML, quote-carry sensitivity; cash when unavailable',
       'cost_policy':'post-fee target NAV, total absolute stock trades, proportional per-dollar fee',
       'sensitivity_policy':'replace entire unresolved stock-month total returns, not an estimate of actual payoff',
       'pandas_version':pd.__version__,
       'code_sha256':{p.name:sha256_file(p) for p in Path(__file__).parent.glob('*.py')},
       'benchmark_sha256':{str(p):sha256_file(Path(p)) for p in (kf_monthly,dm_monthly) if p is not None},
       'source_manifest_sha256':{p.name:sha256_file(p) for p in cache_dir.glob('*manifest.json')}}
    output_dir.mkdir(parents=True,exist_ok=False)
    summary.to_csv(output_dir/'scenario_metrics.csv',index=False)
    full_ledger.to_csv(output_dir/'monthly_accounts.csv')
    weight_frame.to_csv(output_dir/'applied_weights.csv')
    uncertain.to_csv(output_dir/'unresolved_exposure.csv')
    pd.DataFrame(comparisons).to_csv(output_dir/'benchmark_comparison.csv',index=False)
    pd.concat(portfolio_frames,names=['return_policy','month']).to_csv(output_dir/'decile_returns.csv')
    for mode,frame in daily_frames.items():frame.to_parquet(output_dir/f'daily_wml_{mode}.parquet')
    (output_dir/'quality_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (output_dir/'run.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if private is not None:
        private.mkdir(parents=True,exist_ok=False)
        holdings.to_parquet(private/'holdings.parquet',index=False)
        breakpoints.to_parquet(private/'breakpoints.parquet')
        for name,frame in private_trades.items():frame.to_parquet(private/f'{name}_zero_sensitivity_trades.parquet',index=False)
        wml_sample.loc[wml_sample.return_strict.isna()].to_parquet(private/'unresolved_stock_months.parquet',index=False)
    return summary,audit,weight_frame


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--private-artifacts-dir',type=Path)
    p.add_argument('--start',default='1963-01');p.add_argument('--end',default='2011-12')
    p.add_argument('--transaction-cost-bps',type=float,default=10.)
    p.add_argument('--financing-cost-bps',type=float,default=0.)
    p.add_argument('--target-volatility',type=float,default=.12)
    p.add_argument('--leverage-cap',type=float)
    p.add_argument('--kf-monthly',type=Path);p.add_argument('--dm-monthly',type=Path)
    a=p.parse_args(argv)
    summary,audit,_=run_research(**vars(a))
    print(summary.to_string(index=False))
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
