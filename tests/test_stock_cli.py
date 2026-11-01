import pandas as pd
import numpy as np
import pytest
from momentum_risk_project.stock_cli import run_research


def test_offline_pipeline_no_overwrite_and_one_month_lag(tmp_path):
    cache=tmp_path/'cache';cache.mkdir();(cache/'held_daily').mkdir()
    months=pd.period_range('1999-01','2001-02',freq='M')
    records=[]
    for stock in range(1,21):
        for month in months:
            records.append(dict(permno=stock,mthcaldt=month.end_time.date(),mthprcdt=month.end_time.date(),
                mthcap=float(stock),mthprc=10.,
                mthret=(1+.0001*stock)**len(pd.bdate_range(month.start_time,month.end_time))-1,
                mthretx=(1+.0001*stock)**len(pd.bdate_range(month.start_time,month.end_time))-1,
                mthdelflg='N',mthretflg='CR',mthprcflg='TR',legacy_shrcd=10,legacy_exchcd=1))
    pd.DataFrame(records).to_parquet(cache/'monthly_enriched.parquet',index=False)
    pd.DataFrame({'permno':pd.Series(dtype=int),'delistingdt':pd.Series(dtype='datetime64[ns]'),
        'delret':pd.Series(dtype=float)}).to_parquet(cache/'delists.parquet',index=False)
    pd.DataFrame({'permno':pd.Series(dtype=int),'exclusion_start_date':pd.Series(dtype='datetime64[ns]'),
        'exclusion_end_exclusive':pd.Series(dtype='datetime64[ns]')}).to_parquet(cache/'price_gap_intervals.parquet',index=False)
    dates=pd.bdate_range('1999-01-01','2001-02-28')
    pd.DataFrame({'caldt':dates,'tradingflg':'Y','exchangegroup':'CIZ'}).to_parquet(cache/'calendar.parquet',index=False)
    for year in [2000,2001]:
        daily=[]
        for date in dates[dates.year==year]:
            for stock in range(1,21):
                daily.append(dict(permno=stock,dlycaldt=date,dlydelflg='N',dlyret=.0001*stock,
                                  dlyretx=.0001*stock,dlyprc=10.,dlyprcflg='TR'))
        pd.DataFrame(daily).to_parquet(cache/'held_daily'/f'{year}.parquet',index=False)
    result=tmp_path/'result'
    summary,audit,weights=run_research(cache,result,start='2001-01',end='2001-02',progress=lambda _:None)
    assert len(summary)==20
    assert weights.forecast_available.all()
    assert audit['same_holdings_daily_risk']
    assert (result/'run.json').exists()
    daily_path=cache/'held_daily/2001.parquet'
    changed=pd.read_parquet(daily_path)
    changed.loc[pd.to_datetime(changed.dlycaldt).dt.month.eq(1),'dlyret']*=2
    changed.to_parquet(daily_path,index=False)
    changed_monthly=pd.read_parquet(cache/'monthly_enriched.parquet')
    jan=pd.to_datetime(changed_monthly.mthcaldt).dt.to_period('M').eq(pd.Period('2001-01'))
    count=len(pd.bdate_range('2001-01-01','2001-01-31'))
    changed_monthly.loc[jan,'mthret']=(1+.0002*changed_monthly.loc[jan,'permno'])**count-1
    changed_monthly.loc[jan,'mthretx']=changed_monthly.loc[jan,'mthret']
    changed_monthly.to_parquet(cache/'monthly_enriched.parquet',index=False)
    _,_,changed_weights=run_research(cache,tmp_path/'second',start='2001-01',end='2001-02',progress=lambda _:None)
    assert changed_weights.iloc[0].managed==weights.iloc[0].managed
    assert changed_weights.iloc[1].managed<weights.iloc[1].managed
    with pytest.raises(FileExistsError):run_research(cache,result,start='2001-01',end='2001-02')
