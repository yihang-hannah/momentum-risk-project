"""Attribute the August 1935 WML residual without changing the strategy."""
import argparse,json,datetime
from pathlib import Path
import numpy as np
import pandas as pd
from momentum_risk_project.stock_cli import sha256_file
from momentum_risk_project.stock_reconstruction import reconstruct_stock_wml, portfolio_returns


def run(root,output,private_output):
    root,output,private_output=map(Path,[root,output,private_output])
    if output.exists() or private_output.exists():raise FileExistsError('Use new audit directories')
    cache=root/'data/raw/03_stock_full_20261031'
    hp=cache/'monthly_enriched.parquet'
    kp=root/'data/raw/02_kf_momentum_deciles_monthly_vw.parquet'
    old_panel=pd.read_parquet(hp,filters=[('mthcaldt','>=',datetime.date(1934,7,1)),('mthcaldt','<=',datetime.date(1935,8,31))])
    h,_,_=reconstruct_stock_wml(old_panel,start='1935-08',end='1935-08')
    h=h[h.momentum_decile.isin([1,10])].copy()
    m=pd.read_parquet(cache/'monthly_enriched.parquet',filters=[('permno','==',10284)])
    m['month']=pd.to_datetime(m.mthcaldt).dt.to_period('M')
    l=pd.read_parquet(cache/'legacy_monthly.parquet',filters=[('permno','==',10284)])
    l['month']=pd.to_datetime(l.date).dt.to_period('M')
    july=m[m.month.eq(pd.Period('1935-07'))].iloc[0]
    august=m[m.month.eq(pd.Period('1935-08'))].iloc[0]
    old_july=l[l.month.eq(pd.Period('1935-07'))].iloc[0]
    old_august=l[l.month.eq(pd.Period('1935-08'))].iloc[0]
    assert pd.isna(old_july.prc) and july.mthdtflg=='LA' and july.mthcompsubflg=='R1'
    assert pd.Timestamp(july.mthprcdt)<pd.Timestamp(july.mthcaldt)
    assert august.mthdelflg=='N'
    np.testing.assert_allclose((1+july.mthret)*(1+august.mthret)-1,old_august.ret,atol=1e-5)
    h['contribution']=h.leg_weight*h.return_as_published.fillna(0.)
    legs=h.groupby('momentum_decile').contribution.sum()
    affected=h[h.permno.eq(10284)].iloc[0]
    assert affected.momentum_decile==1
    excluded_loser=(legs[1]-affected.contribution)/(1-affected.leg_weight)
    k=pd.read_parquet(kp).loc['1935-08']
    kf_p1,kf_p10=k.iloc[0]/100,k.iloc[-1]/100
    # Test a general formation-date hypothesis for this month, recomputing all
    # NYSE cutoffs and memberships rather than hand-deleting the named security.
    panel=pd.read_parquet(cache/'monthly_enriched.parquet', filters=[
        ('mthcaldt','>=',datetime.date(1934,7,1)),('mthcaldt','<=',datetime.date(1935,8,31))])
    formation=pd.to_datetime(panel.mthcaldt).dt.to_period('M').eq(pd.Period('1935-07'))
    panel.loc[formation & ~panel.mthdtflg.eq('PE'),'mthcap']=np.nan
    screened,_,_=reconstruct_stock_wml(panel,start='1935-08',end='1935-08')
    screened['reference_return']=screened.return_as_published.fillna(0.)
    screened_legs=portfolio_returns(screened,'reference_return')[0].iloc[0]
    rows=[dict(case='Published-return reconstruction',P1=legs[1],P10=legs[10]),
          dict(case='Diagnostic: omit one stock, other memberships fixed',P1=excluded_loser,P10=legs[10]),
          dict(case='Diagnostic: period-end formation values, NYSE cutoffs recomputed',P1=screened_legs.P1,P10=screened_legs.P10),
          dict(case='KF published deciles',P1=kf_p1,P10=kf_p10)]
    table=pd.DataFrame(rows);table['WML']=table.P10-table.P1
    table['WML_minus_KF_bps']=(table.WML-(kf_p10-kf_p1))*10000
    details=dict(month='1935-08',security='American Express',permno=10284,
       formation_month='1935-07',CIZ_formation_price=float(july.mthprc),CIZ_price_date=str(july.mthprcdt),
       CIZ_period_date=str(july.mthcaldt),CIZ_formation_market_cap=float(july.mthcap),
       date_flag=str(july.mthdtflg),completeness=str(july.mthcompflg),completeness_detail=str(july.mthcompsubflg),
       legacy_formation_price_missing=bool(pd.isna(old_july.prc)),
       CIZ_july_return=float(july.mthret),CIZ_august_return=float(august.mthret),
       legacy_august_return=float(old_august.ret),
       july_august_compounded_CIZ_return=float((1+july.mthret)*(1+august.mthret)-1),
       loser_leg_weight=float(affected.leg_weight),loser_leg_contribution=float(affected.contribution),
       original_WML_error_bps=float(table.iloc[0].WML_minus_KF_bps),
       diagnostic_WML_error_bps=float(table.iloc[1].WML_minus_KF_bps),
       recomputed_screen_WML_error_bps=float(table.iloc[2].WML_minus_KF_bps),
       absolute_error_reduction=float(1-abs(table.iloc[1].WML_minus_KF_bps)/abs(table.iloc[0].WML_minus_KF_bps)),
       conclusion='Formation-value eligibility/price-date mismatch dominates this month; ordinary gap filling and delisting are not its cause.',
       limitation='KF holdings/internal exact screen not observed. Omit-one-stock attribution holds other memberships fixed; the separate general-screen diagnostic recomputes cutoffs for this month only. No full-sample strategy correction is claimed.',
       required_followup='Validate a general formation-month-end price/market-equity rule, then rebuild breakpoints, memberships, daily inputs and accounts across the full sample.',
       audit_script_sha256=sha256_file(Path(__file__)),
       source_urls=['https://www.crsp.org/wp-content/uploads/appendix/FlagType_AG.html','https://www.crsp.org/wp-content/uploads/appendix/FlagType_CF.html','https://www.crsp.org/wp-content/uploads/appendix/FlagType_CG.html'],
       input_sha256={str(p.relative_to(root)):sha256_file(p) for p in [cache/'monthly_enriched.parquet',cache/'legacy_monthly.parquet',hp,kp]})
    output.mkdir(parents=True);private_output.mkdir(parents=True)
    table.to_csv(output/'reconciliation.csv',index=False)
    (output/'summary.json').write_text(json.dumps(details,indent=2)+'\n')
    m[m.month.between(pd.Period('1935-05'),pd.Period('1935-09'))].to_parquet(private_output/'CIZ_security_months.parquet',index=False)
    l[l.month.between(pd.Period('1935-05'),pd.Period('1935-09'))].to_parquet(private_output/'legacy_security_months.parquet',index=False)
    h.to_parquet(private_output/'P1_P10_holdings.parquet',index=False)
    print(table.to_string(index=False));print(json.dumps({k:details[k] for k in ['loser_leg_weight','CIZ_july_return','CIZ_august_return','legacy_august_return','absolute_error_reduction']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    p.add_argument('--output',required=True);p.add_argument('--private-output',required=True)
    run(**vars(p.parse_args()))
