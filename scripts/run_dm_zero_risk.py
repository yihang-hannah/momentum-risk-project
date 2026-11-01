"""Own-stock zero ordinary daily gaps + DM delisting inclusion audit.

Unknown terminal payoffs stay unknown. No cash or compounded path bridges gaps.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from momentum_risk_project.daily_portfolio import daily_wml_from_holdings
from momentum_risk_project.stock_reconstruction import portfolio_returns, attach_delisting_evidence
from momentum_risk_project.aligned_comparison import WINDOWS,aligned_metrics
from momentum_risk_project.wml_pipeline import estimate_risk, value_holdings
from momentum_risk_project.stock_cli import sha256_file


def run(cache,holdings,reference,output,daily_mode="zero_regular_dm_checked"):
    cache,holdings,reference,out=map(Path,[cache,holdings,reference,output])
    if out.exists():raise FileExistsError('Use a new result directory')
    h=pd.read_parquet(holdings)
    if "delistingdt" not in h:
        h=attach_delisting_evidence(h,pd.read_parquet(cache/"delists.parquet"))
    h=value_holdings(h)
    h['dm_monthly_return']=h.return_dm
    ordinary=h.dm_imputed & h.delistingdt.isna()
    recorded=h.dm_imputed & h.delistingdt.notna()
    monthly=portfolio_returns(h,'dm_monthly_return')[0].WML
    positions=h[h.momentum_decile.isin([1,10])]
    c=pd.read_parquet(cache/'calendar.parquet')
    dates=pd.DatetimeIndex(pd.to_datetime(c.loc[c.tradingflg.eq('Y')&c.exchangegroup.eq('CIZ'),'caldt']))
    frames=[]
    for year,g in positions.groupby(positions.month.dt.year):
        d=pd.read_parquet(cache/f'held_daily/{year}.parquet')
        frames.append(daily_wml_from_holdings(g,d,dates,mode=daily_mode))
        print('Rebuilt ordinary-zero / DM terminal daily WML:',year,flush=True)
    d=pd.concat(frames).sort_index()
    reference_file=reference/('aligned_monthly_returns.csv' if (reference/'aligned_monthly_returns.csv').exists() else 'monthly_returns.csv')
    f=pd.read_csv(reference_file,index_col=0);f.index=pd.PeriodIndex(f.index,freq='M')
    w=estimate_risk(d.WML,f.index).weight
    comparison=pd.DataFrame({'KF_unmanaged':f.KF_unmanaged,'reconstructed_DM_unmanaged':monthly,
        'KF_managed_shared_own_risk':f.KF_unmanaged*w,
        'reconstructed_DM_managed_own_risk':monthly*w}).reindex(f.index)
    rows=[]
    for name,(a,b) in WINDOWS.items():
        idx=pd.period_range(a,b,freq='M');weight=w.reindex(idx);block=comparison.reindex(idx)
        rows.append(dict(window=name,months=len(idx),risk_available=int(weight.notna().sum()),
            risk_unavailable=int(weight.isna().sum()),monthly_DM_WML_unknown=int(block.reconstructed_DM_unmanaged.isna().sum()),
            all_four_series_paired=int(block.notna().all(axis=1).sum()),cash_imputation=False))
    out.mkdir(parents=True,exist_ok=False)
    d.to_parquet(out/'daily_WML_zero_regular_DM.parquet')
    w.to_csv(out/'own_risk_weights.csv')
    comparison.to_csv(out/'monthly_comparison.csv')
    pd.DataFrame(rows).to_csv(out/'coverage.csv',index=False)
    aligned_metrics(comparison).to_csv(out/'full_window_metrics.csv',index=False)
    info=dict(daily_mode=daily_mode,ordinary_daily_gap_policy='missing ordinary N components/absent ordinary records = 0; observed returns retained',
        terminal_policy='DM includes observed/recorded delisting payoff at event once; unknown terminal payoff stays NaN',
        missing_risk_policy='NaN, never cash; no compounding after dropping gaps',
        monthly_policy='strict known payoff totals; ordinary numeric gaps zero; known recorded terminal on missing ordinary total retained',
        monthly_ordinary_stock_gaps_filled=int((ordinary&h.momentum_decile.isin([1,10])).sum()),
        monthly_missing_ordinary_with_known_terminal=int((recorded&h.momentum_decile.isin([1,10])).sum()),
        daily_zero_imputed_components=int(d.filter(like='_zero_imputed_components').to_numpy().sum()),
        source='https://www.kentdaniel.net/data/momentum/mom_data.pdf Section 2 item 6 and Section 3.1',
        attribution_limitation='late recorded payoff attributed to event for research, not as-of cash receipt',
        zero_rule_is_DM_official=False,
        input_hashes={str(p):sha256_file(p) for p in [holdings,cache/'cache_manifest.json',reference_file]},
        code_hashes={p.name:sha256_file(p) for p in Path(daily_wml_from_holdings.__code__.co_filename).parent.glob('*.py')})
    (out/'run.json').write_text(json.dumps(info,indent=2)+'\n')
    print(pd.DataFrame(rows).to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',required=True);p.add_argument('--holdings',required=True)
    p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    p.add_argument('--daily-mode',default='zero_regular_dm_checked',choices=['zero_regular_dm','zero_regular_dm_checked'])
    run(**vars(p.parse_args()))
