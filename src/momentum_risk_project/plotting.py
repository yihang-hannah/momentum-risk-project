"""Generated figures; no display or calculation depends on notebooks."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def stock_study_figures(gross,frames,weights,windows,output):
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,len(windows),figsize=(max(10,5.4*len(windows)),8),layout="constrained",squeeze=False)
    for col,(window,(a,z)) in enumerate(windows.items()):
        idx=pd.period_range(a,z,freq="M");dates=idx.to_timestamp()
        for name in gross:
            color="#2e6eaa" if "unmanaged" in name else "#c06a25"
            axes[0,col].plot(dates,(1+gross.loc[idx,name]).cumprod(),color=color,
                linestyle=":" if name.startswith("KF") else "-",alpha=.85,label=name)
        for strategy in weights:
            q=frames['funded_monthly'].query("strategy==@strategy and cost_bps_per_dollar==10").set_index("month").loc[idx]
            r=pd.Series(q.net_return.to_numpy(),index=idx)
            wealth=pd.concat([pd.Series([1.]),(1+r).cumprod().reset_index(drop=True)],ignore_index=True)
            dd=(wealth/wealth.cummax()-1).iloc[1:]
            axes[1,col].plot(dates,100*dd.to_numpy(),label=strategy)
        axes[0,col].set(title=window+"\n"+a+" to "+z,yscale="log",ylabel="Gross wealth (start = 1, log scale)")
        axes[1,col].set(ylabel="10bp funded-account drawdown (%)")
        axes[0,col].grid(alpha=.2);axes[1,col].grid(alpha=.2)
    axes[0,0].legend(fontsize=7);axes[1,0].legend(fontsize=7)
    fig.suptitle("Conditional published-return stock reference: shared KF risk weights",fontsize=14)
    fig.savefig(output/"wealth_and_drawdown.png",dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,len(windows),figsize=(max(8,5*len(windows)),4),layout="constrained",squeeze=False)
    for ax,(window,(a,z)) in zip(axes[0],windows.items()):
        for strategy in weights:
            for method,style in [("funded_account","-"),("appendix_scaled_positions","--")]:
                q=frames['metrics'].query("window==@window and strategy==@strategy and method==@method")
                ax.plot(q.cost_bps_per_dollar,q['Sharpe (rf=0)'],style,marker='o',label=strategy+" / "+method)
        ax.set(title=window,xlabel="Cost per dollar traded (bps)",ylabel="Net Sharpe (rf = 0)");ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=6)
    fig.savefig(output/"cost_sensitivity.png",dpi=160);plt.close(fig)


def replication_figures(returns,output):
    output.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(2,1,figsize=(11,7),layout="constrained")
    wealth=(1+returns).cumprod()
    wealth.plot(ax=axes[0],logy=True,title="KF WML strategies: identical evaluation months")
    axes[0].set_ylabel("Gross wealth (start=1, log scale)")
    initial=pd.concat([pd.DataFrame(1.,index=[0],columns=wealth.columns),wealth.reset_index(drop=True)],ignore_index=True)
    dd=(initial/initial.cummax()-1).iloc[1:];dd.index=returns.index
    (100*dd).plot(ax=axes[1],title="Drawdown including initial wealth")
    axes[1].set_ylabel("Drawdown (%)")
    fig.savefig(output/"strategy_wealth_drawdown.png",dpi=160);plt.close(fig)
