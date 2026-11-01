"""Validated shared settings; unsupported scientific changes fail explicitly."""
from pathlib import Path
import copy, hashlib, json, os
import numpy as np
import pandas as pd
import yaml
from .paths import project_root,project_path


def load_config(path=None, *, root=None):
    base=project_root(root)
    path=Path(path) if path is not None else base/"configs/config.yaml"
    if not path.is_absolute(): path=base/path
    with path.open() as f: c=yaml.safe_load(f)
    if not isinstance(c,dict):raise ValueError("Configuration must be a mapping")
    required={"seed","paths","periods","windows","universe","risk","costs","valuation"}
    if required-set(c):raise ValueError("Missing configuration sections")
    for value in c["paths"].values():project_path(value,base)
    for key in ["raw_cache","daily_cache","stock_inputs","build","study","results","kf_daily","kf_monthly","ff3"]:
        if key not in c["paths"]:raise ValueError("Missing configured path: "+key)
    r=c["risk"];cost=c["costs"]
    if r.get("rebuilt_source")!="reconstructed_daily" or r.get("benchmark_source")!="KF_daily":raise ValueError("Rebuilt risk must use reconstructed daily WML; KF fallback is forbidden")
    if not np.isfinite(r["annual_target"]) or r["annual_target"]<=0 or not isinstance(r["window"],int) or r["window"]<1 or r["trading_days_per_month"]<1:
        raise ValueError("Invalid risk settings")
    if not np.isfinite(r["leverage_cap"]) or r["leverage_cap"]!=2.0:raise ValueError("The named managed_cap_2x baseline requires a 2.0 leverage cap")
    rates=cost["transaction_cost_bps"]
    if not rates or len(set(rates))!=len(rates) or not all(np.isfinite(x) and x>=0 for x in rates) or cost["baseline_bps"] not in rates or 0 not in rates:
        raise ValueError("Costs need unique nonnegative rates including zero and baseline")
    if cost["baseline_bps"]!=10 or cost["financing_cost_bps"]!=0:raise ValueError("Current reported study requires 10bp baseline and zero financing")
    expected={"share_codes":[10,11],"exchange_codes":[1,2,3],"ranking":"12-2","weighting":"value","formation_price_policy":"period_end_TR_BA"}
    if c["universe"]!=expected:raise ValueError("Unsupported universe change; implement and validate before configuring")
    if c["valuation"]!={"ordinary_missing":"zero","terminal":"known_once_unknown_preserved","complete_reference":"reconstructed_zero_missing","primary_unknown_terminal_increment":"zero","daily_multisession":"book_on_observed_endpoint"}:
        raise ValueError("Unsupported valuation policy")
    start=pd.Period(c["periods"]["study_start"],freq="M");end=pd.Period(c["periods"]["end"],freq="M")
    if pd.Period(c["periods"]["build_start"],freq="M")>start or start>end:raise ValueError("Invalid build/study dates")
    if set(c["windows"])!={"paper_available_common","paper_turnover_test","extension_disjoint"}:raise ValueError("Three explicit study windows are required")
    for name,(a,b) in c["windows"].items():
        a,b=pd.Period(a,freq="M"),pd.Period(b,freq="M")
        if a>b or a<start or b>end:raise ValueError("Window outside study: "+name)
    if pd.Period(c["windows"]["extension_disjoint"][0],freq="M")<=pd.Period(c["windows"]["paper_available_common"][1],freq="M"):
        raise ValueError("Extension must be disjoint")
    if not isinstance(c["seed"],int):raise ValueError("Seed must be integer")
    return c


def config_digest(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()


def configured_path(config, key, root=None):
    if key in ("raw_cache", "daily_cache"):
        external_cache = os.environ.get("MOMENTUM_CRSP_CACHE")

        if external_cache:
            return Path(external_cache).expanduser().resolve()

    return project_path(config["paths"][key], root)