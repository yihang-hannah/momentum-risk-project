"""Current stock-level WML construction API for research and cost backtests.

No network calls. Input selection, valuation policies and source fingerprints are
explicit. Full-day coverage must match the formed stock-month universe.
"""
from dataclasses import dataclass,field
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from .ciz_quality import screen_formation_values
from .stock_reconstruction import reconstruct_stock_wml,attach_delisting_evidence,portfolio_returns
from .daily_portfolio import daily_wml_from_holdings
from .stock_backtest import simulate_stock_account

SCHEMA_VERSION=2
MONTHLY_COLUMNS=['permno','mthcaldt','mthret','mthretx','mthprc','mthprcdt','mthcap',
 'mthretflg','mthdelflg','mthprcflg','legacy_shrcd','legacy_exchcd','securitytype',
 'securitysubtype','sharetype','usincflg','issuertype','primaryexch','conditionaltype',
 'tradingstatusflg','mthdtflg','mthcompsubflg']


def file_sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def membership_digest(holdings):
    x=holdings.loc[holdings.momentum_decile.isin([1,10]),['permno','month']].copy()
    m=pd.PeriodIndex(x.month,freq='M')
    x['yyyymm']=m.year*100+m.month
    a=x[['permno','yyyymm']].drop_duplicates().sort_values(['permno','yyyymm']).to_numpy(dtype='<i8')
    return hashlib.sha256(a.tobytes()).hexdigest()


def estimate_risk(daily_wml,months,*,annual_target=.12,window=126,trading_days_per_month=21):
    """Monthly-unit sigma and next-month weight; missing stays NaN, never cash."""
    if not isinstance(daily_wml.index,pd.DatetimeIndex) or not daily_wml.index.is_unique or not daily_wml.index.is_monotonic_increasing:
        raise ValueError('Daily WML needs unique sorted DatetimeIndex')
    if not np.isfinite(annual_target) or annual_target<=0 or window<1 or trading_days_per_month<1:
        raise ValueError('Invalid risk parameters')
    if np.isinf(daily_wml).any():raise ValueError('Infinite returns are invalid')
    sigma=np.sqrt(trading_days_per_month*daily_wml.pow(2).rolling(window,min_periods=window).mean())
    sigma=sigma.groupby(sigma.index.to_period('M')).agg(lambda s:s.iloc[-1]);sigma.index+=1
    sigma=sigma.reindex(pd.PeriodIndex(months,freq='M'))
    available=np.isfinite(sigma)&sigma.gt(0)
    return pd.DataFrame({'previous_month_sigma':sigma,'forecast_available':available,
        'weight':(annual_target/np.sqrt(12)/sigma).where(available)})


@dataclass
class WMLBuild:
    holdings:pd.DataFrame
    breakpoints:pd.DataFrame
    monthly_dm:pd.DataFrame
    monthly_reference:pd.DataFrame
    audit:dict=field(default_factory=dict)
    provenance:dict=field(default_factory=dict)
    daily:pd.DataFrame|None=None
    daily_reconstructed:pd.DataFrame|None=None

    @property
    def monthly_reconstructed(self):
        return portfolio_returns(self.holdings,"return_reconstructed")[0]

    def account_holdings(self,return_policy):
        """Explicit valuation selection; never quietly substitute the reference."""
        if return_policy not in {'dm','published_reference','reconstructed_zero_missing'}:
            raise ValueError('Choose dm, published_reference or reconstructed_zero_missing explicitly')
        h=self.holdings.copy()
        column={'dm':'return_dm','published_reference':'return_reference','reconstructed_zero_missing':'return_reconstructed'}[return_policy]
        h['account_return']=h[column]
        h['scenario_imputed']=h['dm_imputed' if return_policy=='dm' else 'reconstructed_imputed' if return_policy=='reconstructed_zero_missing' else 'reference_imputed']
        return h

    def targets(self,weights):
        h=self.holdings.loc[self.holdings.momentum_decile.isin([1,10]) & self.holdings.month.isin(weights.index),['month','permno','momentum_decile','leg_weight']].copy()
        h['factor_weight']=h.month.map(weights)
        h['signed_weight']=h.leg_weight*np.where(h.momentum_decile.eq(10),1.,-1.)*h.factor_weight
        return h

    def backtest(self,weights,*,return_policy,transaction_cost_bps=0.,financing_cost_bps=0.):
        """Stock-level drift/entries/exits/fees via the existing funded account.

        Return account and stock trades. Unknown DM valuations stop the account;
        missing factor weights raise rather than creating zero exposure.
        Known delistings settle once. Reference results remain conditional.
        """
        if not isinstance(weights.index,pd.PeriodIndex) or weights.index.freqstr!='M' or not weights.index.is_unique or not weights.index.is_monotonic_increasing:
            raise ValueError('Weights need a unique sorted monthly PeriodIndex')
        if weights.empty or not weights.index.equals(pd.period_range(weights.index[0],weights.index[-1],freq='M')):
            raise ValueError('Requested backtest months must be consecutive')
        h=self.account_holdings(return_policy)
        h=h.loc[h.month.isin(weights.index)]
        if not pd.PeriodIndex(sorted(h.month.unique()),freq='M').equals(weights.index):
            raise ValueError('Requested weights extend beyond constructed holdings')
        return simulate_stock_account(h,weights,return_column='account_return',
            transaction_cost_bps=transaction_cost_bps,financing_cost_bps=financing_cost_bps)


def value_holdings(holdings):
    """Current monthly DM/reference policies, after delisting evidence attachment."""
    h=holdings.copy()
    h['return_dm']=h.return_strict
    ordinary=h.return_as_published.isna()&h.mthdelflg.eq('N')&h.delistingdt.isna()
    recorded=h.return_as_published.isna()&h.delistingdt.notna()&np.isfinite(h.delret)&h.delret.ge(-1)&~h.mthdelflg.eq('V')
    h.loc[ordinary,'return_dm']=0.
    h.loc[recorded,'return_dm']=h.loc[recorded,'delret']
    h['dm_imputed']=ordinary|recorded
    h['return_reference']=h.return_as_published.fillna(0.)
    h['reference_imputed']=h.return_as_published.isna()
    h['return_reconstructed']=h.return_dm.combine_first(h.return_reference)
    h['reconstructed_imputed']=h.return_as_published.isna()
    h['terminal_increment_assumed_zero']=~h.payoff_complete.fillna(False).astype(bool)
    return h


def build_wml(monthly,delistings,*,start,end,price_intervals=None):
    """Notebook03's current monthly construction; all inputs remain unmodified."""
    required={'mthdtflg','mthprcdt','mthprcflg'}
    if required-set(monthly):raise ValueError('Current builder requires price/date quality fields')
    prepared=screen_formation_values(monthly)
    h,bp,a=reconstruct_stock_wml(prepared,start=start,end=end,price_intervals=price_intervals)
    # Formation screen does not rewrite the observed holding-month price.
    observed=monthly[['permno','mthcaldt','mthprc']].copy()
    observed['month']=pd.to_datetime(observed.mthcaldt).dt.to_period('M')
    observed=observed.rename(columns={'mthprc':'observed_mthprc'})
    h=h.merge(observed[['permno','month','observed_mthprc']],on=['permno','month'],how='left',validate='one_to_one')
    h['mthprc']=h.pop('observed_mthprc')
    h=attach_delisting_evidence(h,delistings)
    h=value_holdings(h)
    a.update({'formation_policy':'period-end TR/BA; NS only on actual period-end; same screen for t-13',
        'monthly_policy':'ordinary gaps zero; known DM payoff once; unknown terminal retained',
        'reference_policy':'published numeric monthly returns, numeric gaps zero; unconfirmed terminal values retained',
        'start':str(pd.Period(start,freq='M')),'end':str(pd.Period(end,freq='M'))})
    a['membership_digest']=membership_digest(h)
    return WMLBuild(h,bp,portfolio_returns(h,'return_dm')[0],portfolio_returns(h,'return_reference')[0],a)


def build_from_cache(cache_dir,*,start='1927-01',end='2025-12'):
    root=Path(cache_dir)
    paths=[root/'monthly_enriched.parquet',root/'delists.parquet',root/'price_gap_intervals.parquet']
    b=build_wml(pd.read_parquet(paths[0],columns=MONTHLY_COLUMNS),pd.read_parquet(paths[1]),
        start=start,end=end,price_intervals=pd.read_parquet(paths[2]))
    b.provenance={'source_sha256':{str(p):file_sha256(p) for p in paths},
        'code_sha256':{p.name:file_sha256(p) for p in Path(__file__).parent.glob('*.py')}}
    return b


def rebuild_daily(build,cache_dir,*,progress=print):
    """Require a fingerprinted declared membership before ordinary-gap filling.

    A missing stock-month in an old selected cache must never become synthetic
    zero returns. The manifest attests requests, including legitimately empty
    provider responses; observed-row presence alone cannot prove that coverage.
    """
    root=Path(cache_dir)
    attestation=root/'membership_manifest.json'
    manifest=json.loads((attestation if attestation.exists() else root/'cache_manifest.json').read_text())
    if attestation.exists() and manifest.get('cache_manifest_sha256')!=file_sha256(root/'cache_manifest.json'):
        raise ValueError('Daily cache lineage fingerprint mismatch')
    digest=membership_digest(build.holdings)
    if manifest.get('status')!='complete' or manifest.get('membership_digest')!=digest:
        raise ValueError('Daily cache membership is unverified or differs; supplement the formed universe first')
    cal=pd.read_parquet(root/'calendar.parquet')
    dates=pd.DatetimeIndex(pd.to_datetime(cal.loc[cal.tradingflg.eq('Y')&cal.exchangegroup.eq('CIZ'),'caldt']))
    positions=build.holdings.loc[build.holdings.momentum_decile.isin([1,10])]
    frames=[];reconstructed=[]
    for year,h in positions.groupby(positions.month.dt.year):
        p=root/f'held_daily/{year}.parquet'
        if file_sha256(p)!=manifest['files'][f'held_daily/{year}']['sha256']:
            raise ValueError(f'Daily source fingerprint mismatch: {year}')
        records=pd.read_parquet(p)
        frames.append(daily_wml_from_holdings(h,records,dates,mode='zero_regular_dm_checked'))
        reconstructed.append(daily_wml_from_holdings(h,records,dates,mode='zero_missing_reconstructed'))
        progress(f'Rebuilt daily WML: {year}')
    build.daily=pd.concat(frames).sort_index()
    build.daily.index=build.daily.index.as_unit('ns')
    build.daily_reconstructed=pd.concat(reconstructed).sort_index()
    build.daily_reconstructed.index=build.daily_reconstructed.index.as_unit('ns')
    build.audit['daily_policy']='strict diagnostic: zero_regular_dm_checked; primary: zero_missing_reconstructed'
    build.audit['primary_valuation']='known terminal components once; missing stock components and unknown terminal increments zero; multisession returns at source endpoint'
    build.audit['risk_source']='reconstructed daily WML only, no KF fallback'
    build.provenance['daily_manifest_sha256']=file_sha256(root/'cache_manifest.json')
    return build.daily


def save_build(build,output_dir):
    root=Path(output_dir)
    if root.exists():raise FileExistsError('Choose a new artifact directory')
    root.mkdir(parents=True)
    frames={'holdings':build.holdings,'breakpoints':build.breakpoints,
        'monthly_dm':build.monthly_dm,'monthly_reference':build.monthly_reference}
    if build.daily is not None:frames['daily']=build.daily
    if build.daily_reconstructed is not None:frames['daily_reconstructed']=build.daily_reconstructed
    files={}
    for name,frame in frames.items():
        p=root/f'{name}.parquet';frame.to_parquet(p);files[p.name]=file_sha256(p)
    manifest={'schema_version':SCHEMA_VERSION,'audit':build.audit,'provenance':build.provenance,'files':files}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


def load_build(output_dir):
    root=Path(output_dir);m=json.loads((root/'manifest.json').read_text())
    if m['schema_version'] not in {1,SCHEMA_VERSION}:raise ValueError('Unsupported WML artifact version')
    for name,digest in m['files'].items():
        if file_sha256(root/name)!=digest:raise ValueError('WML artifact fingerprint mismatch')
    frames={name:pd.read_parquet(root/f'{name}.parquet') for name in ['holdings','breakpoints','monthly_dm','monthly_reference']}
    b=WMLBuild(**frames,audit=m['audit'],provenance=m['provenance'])
    if 'return_reconstructed' not in b.holdings:
        b.holdings['return_reconstructed']=b.holdings.return_dm.combine_first(b.holdings.return_reference)
        b.holdings['reconstructed_imputed']=b.holdings.return_as_published.isna()
        b.holdings['terminal_increment_assumed_zero']=~b.holdings.payoff_complete.fillna(False).astype(bool)
    if 'daily.parquet' in m['files']:
        b.daily=pd.read_parquet(root/'daily.parquet')
        b.daily.index=b.daily.index.as_unit('ns')
    if 'daily_reconstructed.parquet' in m['files']:
        b.daily_reconstructed=pd.read_parquet(root/'daily_reconstructed.parquet')
        b.daily_reconstructed.index=b.daily_reconstructed.index.as_unit('ns')
    if membership_digest(b.holdings)!=b.audit['membership_digest']:raise ValueError('WML membership mismatch')
    return b


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir',required=True);p.add_argument('--daily-cache-dir')
    p.add_argument('--output-dir',required=True);p.add_argument('--start',default='1927-01');p.add_argument('--end',default='2025-12')
    a=p.parse_args(argv)
    if Path(a.output_dir).exists():raise FileExistsError('Choose a new artifact directory')
    b=build_from_cache(a.cache_dir,start=a.start,end=a.end)
    if a.daily_cache_dir:rebuild_daily(b,a.daily_cache_dir)
    save_build(b,a.output_dir);print(json.dumps(b.audit,indent=2))

if __name__=='__main__':main()
