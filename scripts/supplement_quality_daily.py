from pathlib import Path
import shutil,json,datetime
import pandas as pd
from momentum_risk_project.wrds_stock import connect_readonly,_extract,_hash
R=Path(__file__).resolve().parents[1];old=R/'data/raw/03_stock_full_20261031';out=R/'data/raw/03_quality_daily_20261031'
assert not out.exists();out.mkdir();(out/'held_daily').mkdir()
manifest={'status':'in_progress','kind':'immutable annual source plus selected-membership supplement','files':{},'source_manifest_sha256':_hash(old/'cache_manifest.json'),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
def save():(out/'cache_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for p in old.glob('*.parquet'):
 shutil.copy2(p,out/p.name);manifest['files'][p.stem]={'sha256':_hash(out/p.name),'source':'unchanged original frozen cache'}
save()
h=pd.read_parquet(R/'data/processed/wml_current_v1_20261031/holdings.parquet',columns=['permno','month','momentum_decile']);h=h[h.momentum_decile.isin([1,10])];h['yyyymm']=h.month.dt.year*100+h.month.dt.month
prior=pd.read_parquet(R/'data/processed/reference/pre_quality/holdings_membership.parquet',columns=['permno','month','momentum_decile']);prior=prior[prior.momentum_decile.isin([1,10])];prior['yyyymm']=prior.month.dt.year*100+prior.month.dt.month
keys=prior[['permno','yyyymm']]
c=connect_readonly();total_new=0
try:
 for year,g in h.groupby(h.month.dt.year):
  request=g[['permno','yyyymm']].drop_duplicates()
  missing=request.merge(keys,on=['permno','yyyymm'],how='left',indicator=True);missing=missing[missing._merge.eq('left_only')]
  d=pd.read_parquet(old/f'held_daily/{year}.parquet')
  if len(missing):
   with c.cursor() as q:values=','.join(q.mogrify('(%s,%s)',(int(s),int(m))).decode() for s,m in missing[['permno','yyyymm']].itertuples(index=False,name=None))
   sql=f'''WITH requested(permno,yyyymm) AS (VALUES {values}) SELECT d.permno,d.dlycaldt,d.dlydelflg,d.dlyret::float8,d.dlyretx::float8,d.dlyprc::float8,d.dlyprcflg,d.dlyretmissflg,d.dlyretdurflg,d.dlyprevdt,d.dlycumfacpr::float8 FROM crsp_a_stock.dsf_v2 d JOIN requested r ON d.permno=r.permno AND d.yyyymmdd/100=r.yyyymm ORDER BY d.dlycaldt,d.permno,d.dlydelflg'''
   path=out/f'added_{year}.parquet';_extract(c,sql,path,'supplement_'+str(year));extra=pd.read_parquet(path);total_new+=len(extra);d=pd.concat([d,extra],ignore_index=True)
   manifest['files'][f'added_{year}']={'sha256':_hash(path),'rows':len(extra),'requested_stock_months':len(missing),'sql':sql}
  dt=pd.to_datetime(d.dlycaldt);d['yyyymm']=dt.dt.year*100+dt.dt.month
  d=d.merge(request,on=['permno','yyyymm'],how='inner',validate='many_to_one').drop(columns='yyyymm')
  assert not d.duplicated(['permno','dlycaldt','dlydelflg']).any()
  path=out/f'held_daily/{year}.parquet';d.to_parquet(path,index=False)
  manifest['files'][f'held_daily/{year}']={'sha256':_hash(path),'rows':len(d)};save()
  print('Validated new daily membership',year,'added',len(missing),'stock-months',flush=True)
finally:c.close()
manifest['status']='complete';manifest['supplementary_daily_rows']=total_new;save();print('Supplement complete',total_new,flush=True)
