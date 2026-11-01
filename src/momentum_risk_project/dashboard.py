"""Read-only presentation service for the verified stock-cost study.

No acquisition, model fitting, report writes or raw holdings loads occur here.
The frontend selects exact saved scenarios; it never interpolates net returns.
"""
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
from .config import load_config, configured_path, config_digest
from .paths import project_root, project_path
from .wml_pipeline import file_sha256
from .evaluation import describe

STRATEGIES={"unmanaged":"Unmanaged", "managed_shared_KF_risk":"Risk managed"}
WINDOW_LABELS={"paper_available_common":"Historical sample", "paper_turnover_test":"Paper turnover test", "extension_disjoint":"Post-sample extension"}
METHOD_LABELS={"funded_account":"Funded stock account", "appendix_scaled_positions":"Paper-style · scaled positions", "appendix_literal_eq10":"Paper-style · printed inverse L"}


class DashboardDataError(ValueError):
    """An actionable missing/stale/invalid dataset, never silently repaired."""


def _complete(frame,index,label):
    if not frame.index.is_unique or not frame.index.equals(index):
        raise DashboardDataError(label+" has missing or duplicate months. Rebuild results.")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise DashboardDataError(label+" contains unresolved values. A continuous view is unavailable.")


@dataclass
class DashboardSnapshot:
    root: object
    config: dict
    manifest: dict
    frames: dict
    fingerprint: str

    @property
    def costs(self):
        return tuple(float(x) for x in self.manifest["cost_bps_per_dollar"])

    def select(self,window,*,source="rebuilt",basis="net",cost=10.,method="funded_account"):
        if window not in self.config["windows"]:raise DashboardDataError("Unknown study window")
        if source not in {"rebuilt","KF"} or basis not in {"gross","net"}:raise DashboardDataError("Unknown return selection")
        if method not in METHOD_LABELS:raise DashboardDataError("Unknown accounting method")
        if source=="KF" and basis!="gross":raise DashboardDataError("KF has no constituent stock-cost ledger; select gross returns")
        if cost not in self.costs:raise DashboardDataError("This cost has not been computed; choose a saved scenario")
        a,z=self.config["windows"][window];idx=pd.period_range(a,z,freq="M",name="month")
        gross=self.frames["gross_reference_returns"].reindex(idx)
        prefix="KF" if source=="KF" else "Rebuilt reference"
        returns=pd.DataFrame({"Unmanaged":gross[prefix+" unmanaged"],"Risk managed":gross[prefix+" managed"]},index=idx)
        selected=[]
        account_cost=cost if basis=="net" else 0.
        if source=="rebuilt":
            data=self.frames["funded_monthly"] if method=="funded_account" else self.frames["appendix_monthly"]
            for name,label in STRATEGIES.items():
                mask=data.strategy.eq(name)&data.cost_bps_per_dollar.eq(account_cost)
                if "method" in data:mask &= data.method.eq(method)
                f=data.loc[mask].set_index("month").reindex(idx)
                _complete(f[["net_return","gross_factor_return"]] if method=="funded_account" else f[["net_return","gross_return"]],idx,"Selected account")
                if method=="funded_account" and not f.state.eq("ok").all():raise DashboardDataError("Account was not continuously evaluable")
                if basis=="net":returns[label]=f.net_return
                selected.append(f.reset_index().assign(display_strategy=label))
        _complete(returns,idx,"Selected return series")
        metrics=pd.DataFrame({name:describe(returns[name]) for name in returns}).T
        coverage=self.frames["coverage"].loc[self.frames["coverage"].window.eq(window)].copy()
        if len(coverage)!=1:raise DashboardDataError("Missing coverage record")
        return DashboardView(window,source,basis,float(account_cost),method,returns,metrics,
                             pd.concat(selected,ignore_index=True) if selected else pd.DataFrame(),coverage,
                             self.frames["gross_reference_returns"].reindex(idx)[["KF unmanaged","KF managed"]])


def load_snapshot(root=None):
    try:
        root=project_root(root);c=load_config(root=root)
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise DashboardDataError("Project settings are invalid. Check configs/config.yaml before rebuilding results.") from error
    folder=configured_path(c,"study",root)
    path=folder/"run.json"
    if not path.exists():raise DashboardDataError("Saved study results are not available. Run python run_all.py from the repository root.")
    try:
        m=json.loads(path.read_text())
        if m.get("config_digest")!=config_digest(c):raise DashboardDataError("Saved results use different settings. Rebuild with python run_all.py.")
        for group in ["input_sha256","code_sha256","output_sha256"]:
            if not m.get(group):raise DashboardDataError("Missing provenance records. Rebuild the study.")
            for name,digest in m[group].items():
                p=project_path(name,root)
                if not p.is_file() or file_sha256(p)!=digest:raise DashboardDataError("Saved inputs or results have changed. Rebuild with python run_all.py.")
        frames={name:pd.read_csv(folder/(name+".csv")) for name in ["metrics","funded_monthly","appendix_monthly","coverage","turnover","cutoffs"]}
        for name in ["funded_monthly","appendix_monthly"]:
            frames[name]["month"]=pd.PeriodIndex(frames[name].month,freq="M")
            keys=["month","strategy","cost_bps_per_dollar"]+(["method"] if name=="appendix_monthly" else [])
            if frames[name].duplicated(keys).any():raise DashboardDataError("Duplicate saved account observations. Rebuild results.")
        gross=pd.read_csv(folder/"gross_reference_returns.csv",index_col=0)
        gross.index=pd.PeriodIndex(gross.index,freq="M",name="month")
        months=pd.period_range(c["periods"]["study_start"],c["periods"]["end"],freq="M",name="month")
        _complete(gross,months,"Gross reference")
        frames["gross_reference_returns"]=gross
        return DashboardSnapshot(root,c,m,frames,file_sha256(path))
    except DashboardDataError:raise
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise DashboardDataError("Study files are missing or invalid. Rebuild with python run_all.py.") from error


@dataclass
class DashboardView:
    window:str
    source:str
    basis:str
    cost:float
    method:str
    returns:pd.DataFrame
    metrics:pd.DataFrame
    account:pd.DataFrame
    coverage:pd.DataFrame
    kf_gross:pd.DataFrame

    def curves(self,capital=10000.):
        if not np.isfinite(capital) or capital<=0:raise ValueError("Starting capital must be positive and finite")
        if self.returns.le(-1).any().any():raise DashboardDataError("A standard positive wealth path is undefined after a return at or below -100%")
        initial=self.returns.index[0].to_timestamp(how="start")
        wealth=(1+self.returns).cumprod();wealth.index=self.returns.index.to_timestamp("M")
        wealth=pd.concat([pd.DataFrame(1.,index=[initial],columns=wealth.columns),wealth])
        drawdown=wealth/wealth.cummax()-1
        return wealth*capital,drawdown

    def download(self,capital=10000.):
        wealth,dd=self.curves(capital)
        out=pd.DataFrame(index=self.returns.index.astype(str))
        out.index.name="month"
        for name in self.returns:
            out[name+" return"]=self.returns[name].to_numpy()
            out[name+" wealth"]=wealth[name].iloc[1:].to_numpy()
            out[name+" drawdown"]=dd[name].iloc[1:].to_numpy()
        return out.to_csv().encode()

    def metadata(self,snapshot,capital):
        return {"window":self.window,"start":str(self.returns.index[0]),"end":str(self.returns.index[-1]),
            "months":len(self.returns),"source":self.source,"basis":self.basis,"one_way_cost_bps":self.cost,
            "accounting":self.method if self.source=="rebuilt" else "gross benchmark only",
            "starting_capital":capital,"risk":snapshot.manifest["risk"],"financing_cost_bps":0,
            "risk_source":"KF daily deciles, shared between monthly return series",
            "valuation":"published reference, conditional terminal values" if self.source=="rebuilt" else "published KF deciles",
            "account_continuity":"full-study account retained, wealth rebased only for display",
            "study_fingerprint":snapshot.fingerprint}
