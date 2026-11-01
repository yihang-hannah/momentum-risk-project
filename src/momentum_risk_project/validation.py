"""Optional migration audit; production never depends on old research outputs."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from .paths import project_root
from .config import load_config,configured_path
from .wml_pipeline import load_build,file_sha256


def audit_refactor(root=None,baseline=None):
    root=project_root(root);c=load_config(root=root)
    baseline=Path(baseline) if baseline else root/"data/interim/refactor_baseline_20261101"
    old=baseline/"outputs/05_stock_backtest";new=configured_path(c,"study",root)
    verified=[]
    for name in ["metrics","turnover","cutoffs","coverage","observations","funded_monthly","appendix_monthly","gross_reference_returns","own_risk_coverage","strict_DM_account","unmanaged_appendix_monthly","managed_shared_KF_risk_appendix_monthly"]:
        a=pd.read_csv(old/(name+".csv"));b=pd.read_csv(new/(name+".csv"))
        pd.testing.assert_frame_equal(a,b,check_dtype=False,atol=1e-12,rtol=1e-12)
        verified.append(name)
    original=load_build(root/"data/processed/wml_current_v1_20261031")
    current=load_build(configured_path(c,"build",root))
    for name in ["monthly_dm","monthly_reference","daily"]:
        pd.testing.assert_frame_equal(getattr(original,name),getattr(current,name))
        verified.append(name)
    common=[x for x in original.holdings.columns if x in current.holdings]
    pd.testing.assert_frame_equal(original.holdings[common],current.holdings[common])
    verified.append("holdings")
    old_returns=pd.read_parquet(root/"data/processed/02_momentum_strategy_returns.parquet")
    old_returns.index.name="month"
    folder=configured_path(c,"results",root)/"replication/tables/paper_available_common"
    new_returns=pd.read_csv(folder/"strategy_returns.csv",index_col=0)
    new_returns.index=pd.PeriodIndex(new_returns.index,freq="M",name="month")
    pd.testing.assert_frame_equal(old_returns,new_returns,check_freq=False,atol=1e-12,rtol=1e-12)
    old_weights=pd.read_parquet(root/"data/processed/02_momentum_weights.parquet")
    old_weights.index.name="month"
    new_weights=pd.read_csv(folder/"applied_weights.csv",index_col=0)
    new_weights.index=pd.PeriodIndex(new_weights.index,freq="M",name="month")
    pd.testing.assert_frame_equal(old_weights,new_weights,check_freq=False,atol=1e-12,rtol=1e-12)
    verified.extend(["paper_strategy_returns","paper_applied_weights"])
    raw=json.loads((baseline/"raw_sha256.json").read_text())
    # Empty Git directory placeholders are repository scaffolding, not provider downloads.
    raw={name:digest for name,digest in raw.items() if Path(name).name!=".gitkeep"}
    for name,digest in raw.items():
        assert file_sha256(root/name)==digest,name
    result={"verified_numeric_objects":verified,"unchanged_raw_files":len(raw),"tolerance":"1e-12 for CSV round trips; exact WML artifact frames", "baseline":str(baseline.relative_to(root))}
    out=configured_path(c,"results",root)/"replication/tables/refactor_validation.json"
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--baseline");p.add_argument("--root")
    a=p.parse_args();print(json.dumps(audit_refactor(a.root,a.baseline),indent=2))

if __name__=="__main__":main()
