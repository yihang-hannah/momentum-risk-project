from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse
parser=argparse.ArgumentParser(description='Plot an existing aligned comparison result directory')
parser.add_argument('--output-dir',type=Path,required=True)
r=parser.parse_args().output_dir
screened=(r/'monthly_returns.csv').exists() and not (r/'aligned_monthly_returns.csv').exists()
f=pd.read_csv(r/('monthly_returns.csv' if screened else 'aligned_monthly_returns.csv'),index_col=0)
f=f.rename(columns={'quality_screened_unmanaged':'reconstructed_unmanaged','quality_screened_managed_shared_risk':'reconstructed_managed_shared_risk'})
f.index=pd.PeriodIndex(f.index,freq='M')
fig,axes=plt.subplots(2,2,figsize=(13,8),gridspec_kw={'height_ratios':[2,1]},sharex='col')
styles={'KF_unmanaged':('black','--','KF unmanaged'),'reconstructed_unmanaged':('#df8a20','-','Rebuilt unmanaged'),
 'KF_managed_shared_risk':('#275a9f','--','KF managed'),'reconstructed_managed_shared_risk':('#009b8e','-','Rebuilt managed')}
for j,(a,b,title) in enumerate([('1927-05','2011-12','Paper-era available common window: May 1927 - Dec 2011'),('2012-01','2025-12','Extension: Jan 2012 - Dec 2025')]):
 x=f.loc[a:b];assert x.notna().all().all()
 w=(1+x).cumprod();dates=x.index.to_timestamp('M')
 for col,(color,line,label) in styles.items():
  axes[0,j].plot(dates,w[col],color=color,ls=line,label=label,lw=1.4,alpha=.95)
 axes[0,j].set_yscale('log');axes[0,j].set_title(title,fontsize=10)
 axes[0,j].set_ylabel('Gross wealth, initial = 1 (log)');axes[0,j].legend(fontsize=8)
 for a,b,color,label in [('reconstructed_unmanaged','KF_unmanaged','#df8a20','Unmanaged'),('reconstructed_managed_shared_risk','KF_managed_shared_risk','#009b8e','Managed')]:
  axes[1,j].plot(dates,(w[a]/w[b]-1)*100,color=color,label=label)
 axes[1,j].axhline(0,color='gray',lw=.8);axes[1,j].set_ylabel('Rebuilt / KF wealth gap (%)');axes[1,j].legend(fontsize=8)
 for ax in axes[:,j]:ax.grid(alpha=.2)
fig.suptitle('Reconstructed vs Kenneth French decile WML — identical months and shared lagged risk weights',fontsize=12)
fig.text(.05,.025,('Period-end formation and t-13 price checks applied. ' if screened else '')+'Monthly numeric missing stock returns = 0. Gross, no fees. Managed: shared KF daily-decile risk, 126 sessions, 12% target.\nMar-Apr 1927 lack the public KF daily warmup and are not fabricated. 2025 uses documented CIZ eligibility mapping.',fontsize=9)
fig.tight_layout(rect=[0,.07,1,.95]);fig.savefig(r/'aligned_wml_comparison.png',dpi=180);fig.savefig(r/'aligned_wml_comparison.svg');plt.close(fig)
