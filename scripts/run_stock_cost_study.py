"""Compatibility entrypoint; study calculations live in momentum_risk_project.study."""
import argparse
from momentum_risk_project.study import run_study
from momentum_risk_project.config import load_config
from momentum_risk_project.paths import project_root
ROOT=project_root()
WINDOWS={k:tuple(v) for k,v in load_config().get("windows").items()}
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",default="configs/config.yaml")
    p.add_argument("--cost-bps",nargs="+",type=float)
    a=p.parse_args();run_study(config=load_config(a.config),costs=a.cost_bps)
