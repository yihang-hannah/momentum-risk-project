"""Historical research entry; current construction API: wml_pipeline.

Same-window stock/KF comparison; never turn missing risk into cash.

The primary controlled comparison applies the SAME lagged KF daily-decile risk
weights to both monthly WML series. This isolates monthly reconstruction error;
it is not an independently estimated own-stock risk replication. Own-stock risk
coverage is reported separately. No daily missing return is imputed implicitly.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .data import clean_momentum
from .volatility import historical_volatility
from .strategies import volatility_managed_momentum
from .metrics import performance_metrics
from .stock_reconstruction import reconstruct_stock_wml, attach_delisting_evidence, portfolio_returns
from .stock_backtest import simulate_stock_account
from .stock_cli import sha256_file

WINDOWS = {
    'paper_available_common': ('1927-05','2011-12'),
    'extension_disjoint': ('2012-01','2025-12'),
}


def aligned_metrics(frame, windows=WINDOWS):
    """Withhold a whole window if any series is missing; never drop gap months."""
    rows=[]
    for label,(start,end) in windows.items():
        idx=pd.period_range(start,end,freq='M')
        block=frame.reindex(idx)
        complete=bool(np.isfinite(block.to_numpy()).all())
        for name in block:
            row=dict(window=label,start=start,end=end,months=len(idx),series=name,
                complete_comparison=complete,missing_months=int(block[name].isna().sum()))
            if complete:row.update(performance_metrics(block[name]).to_dict())
            rows.append(row)
    return pd.DataFrame(rows)


def run(cache_dir,output_dir,*,kf_monthly,kf_daily,private_dir=None,transaction_cost_bps=10.,progress=print):
    cache=Path(cache_dir);out=Path(output_dir)
    private=Path(private_dir) if private_dir else None
    if out.exists() or (private and private.exists()):raise FileExistsError('Use new output paths')
    # Do not load source company-name/classification strings that formation does
    # not use; this keeps a century of reconstruction within local memory.
    columns=['permno','mthcaldt','mthret','mthretx','mthprc','mthprcdt','mthcap',
        'mthretflg','mthdelflg','mthprcflg','legacy_shrcd','legacy_exchcd',
        'securitytype','securitysubtype','sharetype','usincflg','issuertype',
        'primaryexch','conditionaltype','tradingstatusflg']
    monthly=pd.read_parquet(cache/'monthly_enriched.parquet',columns=columns)
    gaps=pd.read_parquet(cache/'price_gap_intervals.parquet')
    h,bp,audit=reconstruct_stock_wml(monthly,start='1927-01',end='2025-12',price_intervals=gaps)
    del monthly
    h=attach_delisting_evidence(h,pd.read_parquet(cache/'delists.parquet'))
    # User-selected convention: numeric holding-month gaps only are zero.
    # Preserve published numbers (including incomplete numeric payoffs) as in
    # the earlier calibration; incompleteness remains in source-quality audit.
    h['return_zero_numeric']=h.return_as_published.fillna(0.)
    h['scenario_imputed']=h.return_as_published.isna()
    own=portfolio_returns(h,'return_zero_numeric')[0].WML.rename('reconstructed_unmanaged')
    kf=clean_momentum(pd.read_parquet(kf_monthly),'monthly').mom.rename('KF_unmanaged')
    kd=clean_momentum(pd.read_parquet(kf_daily),'daily').mom
    vd=historical_volatility(kd)
    vm=vd.groupby(vd.index.to_period('M')).agg(lambda s:s.iloc[-1])
    managed=volatility_managed_momentum(kf,vm)
    weights=managed.weight.rename('shared_KF_risk_weight')
    idx=pd.period_range('1927-01','2025-12',freq='M')
    frame=pd.DataFrame({'KF_unmanaged':kf,'reconstructed_unmanaged':own,
        'KF_managed_shared_risk':managed.managed,
        'reconstructed_managed_shared_risk':own*weights}).reindex(idx)
    summary=aligned_metrics(frame)
    errors=[]
    for label,(start,end) in WINDOWS.items():
        pair=frame.loc[start:end,['KF_unmanaged','reconstructed_unmanaged']]
        error=pair.reconstructed_unmanaged-pair.KF_unmanaged
        errors.append(dict(window=label,months=len(pair),missing_months=int(pair.isna().any(axis=1).sum()),
            correlation=pair.corr().iloc[0,1],mae_bps=error.abs().mean()*10000,
            rmse_bps=np.sqrt(error.pow(2).mean())*10000))
    # Stock costs use the stock ledger; KF has no underlying holdings here, so
    # no factor-scaling proxy is presented as a comparable KF stock cost.
    accounts={};cost_rows=[]
    for label in ['paper_available_common','extension_disjoint']:
        start,end=WINDOWS[label];months=pd.period_range(start,end,freq='M')
        selected=h.loc[h.month.between(months[0],months[-1])&h.momentum_decile.isin([1,10])]
        for strategy,w in [('unmanaged',pd.Series(1.,index=months)),('managed_shared_KF_risk',weights.reindex(months))]:
            for case,bps in [('gross',0.),('net',transaction_cost_bps)]:
                account,_=simulate_stock_account(selected,w,return_column='return_zero_numeric',transaction_cost_bps=bps)
                accounts[f'{label}/{strategy}/{case}']=account
                complete=bool(account.net_return.notna().all() and account.state.eq('ok').all())
                row=dict(window=label,strategy=strategy,cost_case=case,complete=complete,
                    months=len(account),evaluated_months=int(account.net_return.notna().sum()))
                if complete:row.update(performance_metrics(account.net_return).to_dict())
                cost_rows.append(row)
        progress(f'Compared identical months: {label}')
    out.mkdir(parents=True,exist_ok=False)
    frame.to_csv(out/'aligned_monthly_returns.csv')
    weights.reindex(idx).to_csv(out/'shared_risk_weights.csv')
    summary.to_csv(out/'gross_metrics.csv',index=False)
    pd.DataFrame(errors).to_csv(out/'reconstruction_errors.csv',index=False)
    pd.DataFrame(cost_rows).to_csv(out/'stock_cost_metrics.csv',index=False)
    pd.concat(accounts,names=['run','month']).to_csv(out/'stock_accounts.csv')
    audit.update(numeric_missing_filled_zero=int((h.momentum_decile.isin([1,10])&h.scenario_imputed).sum()),
        terminal_uncertainty_retained=int((h.momentum_decile.isin([1,10])&h.unresolved_final_payoff).sum()),
        primary_risk_policy='Shared KF daily-decile risk weights; missing risk remains NaN, never cash',
        paper_window='1927-03 through 2011-12',available_primary_window='1927-05 through 2011-12',
        early_paper_gap='March/April 1927 unavailable with public KF daily-decile 126-day warmup',
        extension_policy='2012-2025 disjoint extension',
        ciz_2025_caveat='CIZ post-2024 eligibility screen is not proven exactly equivalent to legacy codes')
    (out/'quality_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    manifest=dict(windows=WINDOWS,transaction_cost_bps=transaction_cost_bps,financing_cost_bps=0.,
        monthly_missing_policy='numeric missing only = 0; observed numbers retained',
        risk_source='KF daily deciles; shared for controlled monthly return comparison',
        selection_policy='0 assumption fixed before extension; no retuning on 2012-2025',
        source_hashes={str(p):sha256_file(Path(p)) for p in [kf_monthly,kf_daily,cache/'monthly_enriched.parquet',cache/'delists.parquet',cache/'price_gap_intervals.parquet']},
        code_hashes={p.name:sha256_file(p) for p in Path(__file__).parent.glob('*.py')})
    (out/'run.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if private:
        private.mkdir(parents=True,exist_ok=False)
        h.to_parquet(private/'holdings.parquet',index=False);bp.to_parquet(private/'breakpoints.parquet')
    return summary


def audit_own_risk(cache_dir, output_dir, private_dir, progress=print):
    """Rebuild own daily risk with explicit unavailable observations, never cash."""
    from .daily_portfolio import daily_wml_from_holdings
    cache, out = Path(cache_dir), Path(output_dir)
    if (out/'own_risk_coverage.csv').exists():
        raise FileExistsError('Own risk audit already exists')
    h=pd.read_parquet(Path(private_dir)/'holdings.parquet')
    h=h[h.momentum_decile.isin([1,10])]
    c=pd.read_parquet(cache/'calendar.parquet')
    dates=pd.DatetimeIndex(pd.to_datetime(c.loc[c.tradingflg.eq('Y')&c.exchangegroup.eq('CIZ'),'caldt']))
    frames=[]
    for year,g in h.groupby(h.month.dt.year):
     d=pd.read_parquet(cache/f'held_daily/{year}.parquet')
     frames.append(daily_wml_from_holdings(g,d,dates,mode='carry_prices'))
     progress(f'Audited own-stock daily risk: {year}')
    x=pd.concat(frames).sort_index();x.to_parquet(out/'own_daily_carry_prices.parquet')
    sig=np.sqrt(21*x.WML.pow(2).rolling(126,min_periods=126).mean())
    sig=sig.groupby(sig.index.to_period('M')).agg(lambda s:s.iloc[-1]);sig.index+=1
    f=pd.read_csv(out/'aligned_monthly_returns.csv',index_col=0);f.index=pd.PeriodIndex(f.index,freq='M')
    w=(.12/np.sqrt(12)/sig).reindex(f.index)
    w=w.where(np.isfinite(w)&w.gt(0))
    f['own_risk_weight']=w
    f['reconstructed_managed_own_risk_available_only']=w*f.reconstructed_unmanaged
    f['KF_managed_own_risk_available_only']=w*f.KF_unmanaged
    f.to_csv(out/'own_risk_diagnostic_returns.csv')
    rows=[]
    for name,(a,b) in WINDOWS.items():
     b=f.loc[a:b];rows.append(dict(window=name,months=len(b),risk_available=int(b.own_risk_weight.notna().sum()),risk_unavailable=int(b.own_risk_weight.isna().sum()),cash_imputation=False))
    pd.DataFrame(rows).to_csv(out/'own_risk_coverage.csv',index=False)
    (out/'own_risk_policy.json').write_text(json.dumps({'missing_risk':'NaN, never zero exposure; no compounded wealth or full metrics over gapped own-risk samples','primary_comparison':'shared KF risk, explicitly controlled, not independent own-risk replication'},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--private-dir');p.add_argument('--kf-monthly',required=True);p.add_argument('--kf-daily',required=True)
    p.add_argument('--transaction-cost-bps',type=float,default=10.)
    p.add_argument('--audit-own-risk',action='store_true')
    p.add_argument('--audit-only',action='store_true')
    args=vars(p.parse_args())
    audit=args.pop('audit_own_risk');only=args.pop('audit_only')
    if not only:print(run(**args).to_string(index=False))
    if audit or only:
        if not args['private_dir']:raise ValueError('Own-risk audit requires --private-dir')
        audit_own_risk(args['cache_dir'],args['output_dir'],args['private_dir'])

if __name__=='__main__':main()
