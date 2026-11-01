"""Offline Notebook 05 study; python scripts/run_stock_cost_study.py --help."""
from pathlib import Path
import argparse, hashlib, json, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from momentum_risk_project.wml_pipeline import load_build, estimate_risk, file_sha256
from momentum_risk_project.paper_turnover import appendix_b_turnover, cutoff_roundtrip_bps
from momentum_risk_project.data import clean_momentum
from momentum_risk_project.metrics import performance_metrics

WINDOWS={"paper_available_common":("1927-05","2011-12"),
         "paper_turnover_test":("1951-03","2010-12"),
         "extension_disjoint":("2012-01","2025-12")}


def describe(r):
    return {**performance_metrics(r).to_dict(), "Worst month":r.min(),
            "Skewness":r.skew(),"Excess kurtosis":r.kurt()}


def run_study(root=ROOT, costs=(0.,5.,10.,25.,50.), progress=print):
    root=Path(root)
    costs=tuple(float(x) for x in costs)
    if not costs or not all(np.isfinite(x) and x>=0 for x in costs) or 10. not in costs:
        raise ValueError("Supply nonnegative finite costs including the 10bp baseline")
    output=root/"outputs/05_stock_backtest"
    private=root/"data/processed/05_stock_backtest"
    output.mkdir(parents=True,exist_ok=True);private.mkdir(parents=True,exist_ok=True)
    artifact=root/"data/processed/wml_current_v1_20261031"
    b=load_build(artifact)
    months=pd.period_range("1927-05","2025-12",freq="M")
    kf_m=clean_momentum(pd.read_parquet(root/"data/raw/02_kf_momentum_deciles_monthly_vw.parquet"),"monthly").mom.reindex(months)
    kf_d=clean_momentum(pd.read_parquet(root/"data/raw/02_kf_momentum_deciles_daily_vw.parquet"),"daily").mom
    kf_w=estimate_risk(kf_d,months).weight
    own=estimate_risk(b.daily.WML,months)
    assert kf_w.notna().all()
    weights={"unmanaged":pd.Series(1.,index=months),"managed_shared_KF_risk":kf_w}
    gross=pd.DataFrame({"KF unmanaged":kf_m,"Rebuilt reference unmanaged":b.monthly_reference.WML.reindex(months),
        "KF managed":kf_m*kf_w,"Rebuilt reference managed":b.monthly_reference.WML.reindex(months)*kf_w})
    assert gross.notna().all().all()
    coverage=[]; metrics=[];turnrows=[];cutoffs=[];ledger_frames=[];net_frames=[]
    strict,_=b.backtest(weights["unmanaged"],return_policy="dm")
    for window,(a,z) in WINDOWS.items():
        idx=pd.period_range(a,z,freq="M")
        coverage.append({"window":window,"start":a,"end":z,"months":len(idx),
          "own_stock_risk_forecasts":int(own.loc[idx,"forecast_available"].sum()),
          "strict_DM_monthly_returns":int(b.monthly_dm.WML.reindex(idx).notna().sum()),
          "strict_continuous_account_known_months":int(strict.reindex(idx).net_return.notna().sum()),
          "cash_fill_used":False})
        for name in gross:
            metrics.append({"window":window,"strategy":name,"method":"gross", "cost_bps_per_dollar":0.,**describe(gross.loc[idx,name])})
    for strategy,w in weights.items():
        progress("Computing stock turnover: "+strategy)
        transitions,turn=appendix_b_turnover(b.holdings,w)
        assert turn.iloc[:,:3].notna().all().all()
        transitions.to_parquet(private/(strategy+"_appendix_stock_transitions.parquet"),index=False)
        monthly_gross=b.monthly_reference.WML.reindex(months)*w
        turnover_cols={"scaled_positions":"scaled_positions_half_trade","literal_eq10":"literal_eq10_half_trade"} if strategy!="unmanaged" else {"scaled_positions":"unmanaged_half_trade","literal_eq10":"unmanaged_half_trade"}
        for window,(a,z) in WINDOWS.items():
            idx=pd.period_range(a,z,freq="M")
            # Initial establishment is charged, but excluded from steady-state average only.
            ix=idx[~turn.loc[idx,"initial_establishment"].to_numpy()]
            row={"window":window,"strategy":strategy,"months":len(idx),"turnover_mean_months":len(ix)}
            for convention,col in turnover_cols.items():
                row[convention+"_mean_half_turnover"]=turn.loc[ix,col].mean()
                cutoffs.append({"window":window,"strategy":strategy,"convention":convention,
                    "IID_95pct_cutoff_roundtrip_bps":cutoff_roundtrip_bps(monthly_gross.loc[idx],turn.loc[idx,col])})
            turnrows.append(row)
        for cost in costs:
            # bps is one-way per actual dollar traded; roundtrip charge is 2*bps.
            for convention,col in turnover_cols.items():
                net=monthly_gross-(2*cost/10000)*turn[col]
                net_frames.append(pd.DataFrame({"month":months,"strategy":strategy,"method":"appendix_"+convention,
                    "cost_bps_per_dollar":cost,"gross_return":monthly_gross.to_numpy(),"net_return":net.to_numpy(),
                    "half_turnover":turn[col].to_numpy()}))
                for window,(a,z) in WINDOWS.items():
                    metrics.append({"window":window,"strategy":strategy,"method":"appendix_"+convention,
                      "cost_bps_per_dollar":cost,**describe(net.loc[a:z])})
            ledger,trades=b.backtest(w,return_policy="published_reference",transaction_cost_bps=cost)
            assert ledger.state.eq("ok").all() and ledger.net_return.notna().all()
            np.testing.assert_allclose(trades.groupby("month").absolute_trade.sum(),ledger.turnover,atol=1e-12)
            np.testing.assert_allclose(ledger.transaction_cost,ledger.turnover*cost/10000,atol=1e-12)
            if cost==0:np.testing.assert_allclose(ledger.net_return,monthly_gross,atol=1e-12)
            if cost==10:trades.to_parquet(private/(strategy+"_funded_trades_10bps.parquet"),index=False)
            for window,(a,z) in WINDOWS.items():
                block=ledger.loc[a:z]
                metrics.append({"window":window,"strategy":strategy,"method":"funded_account",
                  "cost_bps_per_dollar":cost,"Mean absolute traded notional":block.turnover.mean(),
                  "Annual trading cost":12*block.transaction_cost.mean(),**describe(block.net_return)})
            ledger_frames.append(ledger.reset_index().assign(strategy=strategy,cost_bps_per_dollar=cost))
        turn.to_csv(output/(strategy+"_appendix_monthly.csv"))
    frames={"coverage":pd.DataFrame(coverage),"metrics":pd.DataFrame(metrics),"turnover":pd.DataFrame(turnrows),
        "cutoffs":pd.DataFrame(cutoffs),"funded_monthly":pd.concat(ledger_frames,ignore_index=True),
        "appendix_monthly":pd.concat(net_frames,ignore_index=True)}
    gross.to_csv(output/"gross_reference_returns.csv")
    own.to_csv(output/"own_risk_coverage.csv");strict.to_csv(output/"strict_DM_account.csv")
    for name,frame in frames.items():frame.to_csv(output/(name+".csv"),index=False)
    comparison=[]
    for window in WINDOWS:
        q=frames["metrics"].query("window==@window and method=='funded_account' and cost_bps_per_dollar==10").set_index("strategy")
        u=q.loc["unmanaged"];m=q.loc["managed_shared_KF_risk"]
        comparison.append({"window":window,"managed_minus_unmanaged_mean_pp":100*(m['Annualized Mean Return']-u['Annualized Mean Return']),
         "managed_minus_unmanaged_Sharpe":m['Sharpe (rf=0)']-u['Sharpe (rf=0)'],
         "managed_volatility_lower":bool(m['Annualized Volatility']<u['Annualized Volatility']),
         "managed_worst_month_less_negative":bool(m['Worst month']>u['Worst month']),
         "managed_skewness_higher":bool(m.Skewness>u.Skewness),
         "managed_kurtosis_lower":bool(m['Excess kurtosis']<u['Excess kurtosis'])})
    frames['observations']=pd.DataFrame(comparison);frames['observations'].to_csv(output/"observations.csv",index=False)
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,3,figsize=(16,8),layout="constrained")
    for col,(window,(a,z)) in enumerate(WINDOWS.items()):
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
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout="constrained")
    for ax,(window,(a,z)) in zip(axes,WINDOWS.items()):
        for strategy in weights:
            for method,style in [("funded_account","-"),("appendix_scaled_positions","--")]:
                q=frames['metrics'].query("window==@window and strategy==@strategy and method==@method")
                ax.plot(q.cost_bps_per_dollar,q['Sharpe (rf=0)'],style,marker='o',label=strategy+" / "+method)
        ax.set(title=window,xlabel="Cost per dollar traded (bps)",ylabel="Net Sharpe (rf = 0)");ax.grid(alpha=.2)
    axes[0].legend(fontsize=6)
    fig.savefig(output/"cost_sensitivity.png",dpi=160);plt.close(fig)
    files=[artifact/"manifest.json",root/"data/raw/02_kf_momentum_deciles_daily_vw.parquet",root/"data/raw/02_kf_momentum_deciles_monthly_vw.parquet"]
    manifest={"windows":WINDOWS,"cost_bps_per_dollar":costs,"financing_cost_bps":0,
        "risk":"126 daily squared returns; 21 sessions/month; 12% annual target; previous month-end",
        "complete_scope":"published_reference valuations; shared KF risk; NOT independent stock-risk replication",
        "turnover":"leg-normalized half absolute change; literal inverse-L separately from scaled positions",
        "paper_turnover_test":"1951-03 to 2010-12; paper reports .74/.75 monthly, 127/175 roundtrip cutoff bps",
        "cutoff_test":"two-sided IID Student-t 95%; not asserted to match author's undocumented SE implementation",
        "establishment":"charged once at 1927-05; excluded only from steady-state turnover mean; no terminal liquidation",
        "continuity":"one account 1927-05 through 2025-12, sliced for metrics; wealth charts rebased per window",
        "input_sha256":{str(p.relative_to(root)):file_sha256(p) for p in files},
        "code_sha256":{str(p.relative_to(root)):file_sha256(p) for p in [Path(__file__),root/"src/momentum_risk_project/paper_turnover.py",root/"src/momentum_risk_project/stock_backtest.py",root/"src/momentum_risk_project/wml_pipeline.py"]},
        "checks":"artifact SHA; complete calendar; stock trades sum; fee identity; zero-cost gross reconciliation",
        "private_trade_files":[str(p.relative_to(root)) for p in private.glob("*.parquet")]}
    (output/"run.json").write_text(json.dumps(manifest,indent=2)+"\n")
    progress(frames['observations'].to_string(index=False))
    return frames

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cost-bps",nargs="+",type=float,default=[0,5,10,25,50],help="One-way per-dollar bps; include 10")
    a=p.parse_args();run_study(costs=a.cost_bps)
