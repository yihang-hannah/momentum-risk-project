"""Four ordered reproducible stages; results never depend on notebook execution."""
from pathlib import Path
import argparse, hashlib, json, shutil
import numpy as np
import pandas as pd
from .paths import project_root
from .config import load_config,configured_path,config_digest
from .data import clean_momentum,save_processed_data,validate_cleaned_data
from .wml_pipeline import build_from_cache,rebuild_daily,save_build,load_build,file_sha256,MONTHLY_COLUMNS,estimate_risk
from .models import paper_strategies
from .evaluation import describe,factor_tests,reconstruction_errors
from .plotting import replication_figures
from .backtest import run_backtest
from . import study
from .risk_inputs import independent_risk


def verify_cache(cache,manifest_name="cache_manifest.json"):
    cache=Path(cache);path=cache/manifest_name
    if not path.exists():raise FileNotFoundError(f"Missing licensed cache manifest: {path}; provide licensed data or explicitly acquire it")
    m=json.loads(path.read_text())
    if m.get("status")!="complete":raise ValueError("Incomplete cache: "+str(cache))
    for key,item in m["files"].items():
        p=cache/key
        if not p.is_file():p=cache/(key+".parquet")
        if not p.is_file() or file_sha256(p)!=item["sha256"]:raise ValueError("Raw cache fingerprint mismatch: "+str(p))
    return m



def get_data(config, root, *, download=False):
    """Reuse frozen downloads; resume incomplete authorized acquisitions."""
    root = project_root(root)

    # Public Kenneth French momentum datasets
    for key, dataset in [
        ("kf_daily", "10_Portfolios_Prior_12_2_Daily"),
        ("kf_monthly", "10_Portfolios_Prior_12_2"),
    ]:
        path = configured_path(config, key, root)

        if not path.exists():
            if not download:
                raise FileNotFoundError(
                    f"Missing {path}; run stage 01 with --download "
                    "for initial public/authorized acquisition"
                )

            from pandas_datareader import data as web

            raw = web.DataReader(
                dataset, "famafrench", start="1926-01-01"
            )[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_parquet(path)

        clean_momentum(
            pd.read_parquet(path),
            "daily" if key == "kf_daily" else "monthly",
        )

    # Public Fama-French three-factor dataset
    ff = configured_path(config, "ff3", root)

    if not ff.exists():
        if not download:
            raise FileNotFoundError(
                f"Missing frozen FF3 input: {ff}"
            )

        from pandas_datareader import data as web

        f = web.DataReader(
            "F-F_Research_Data_Factors",
            "famafrench",
            start="1926-01-01",
        )[0] / 100

        f.index = pd.PeriodIndex(f.index, freq="M")
        ff.parent.mkdir(parents=True, exist_ok=True)
        f.to_parquet(ff)

    # Licensed WRDS/CRSP caches
    processed_caches = set()

    for key in ["raw_cache", "daily_cache"]:
        cache = configured_path(config, key, root)

        # The two configuration keys may point to the same cache.
        # Avoid downloading or verifying it twice.
        if cache in processed_caches:
            continue

        processed_caches.add(cache)

        manifest_path = cache / "cache_manifest.json"

        if not manifest_path.exists():
            if download:
                from .wrds_stock import download_cache

                download_cache(
                    cache,
                    resume=cache.exists(),
                    start=config["periods"]["raw_start"],
                    end=str(
                        pd.Period(
                            config["periods"]["end"], freq="M"
                        ).end_time.date()
                    ),
                )

        elif download:
            manifest = json.loads(manifest_path.read_text())

            if manifest.get("status") != "complete":
                from .wrds_stock import download_cache

                download_cache(
                    cache,
                    resume=True,
                    start=config["periods"]["raw_start"],
                    end=str(
                        pd.Period(
                            config["periods"]["end"], freq="M"
                        ).end_time.date()
                    ),
                )

        # A complete cache must pass fingerprint verification.
        # An incomplete cache without --download is still rejected.
        verify_cache(cache)

    # Supplemental daily manifests bind the changed membership
    # and original base manifest.
    daily = configured_path(config, "daily_cache", root)

    if (daily / "membership_manifest.json").exists():
        verify_cache(daily, "membership_manifest.json")

        a = json.loads(
            (daily / "membership_manifest.json").read_text()
        )

        if (
            a["cache_manifest_sha256"]
            != file_sha256(daily / "cache_manifest.json")
        ):
            raise ValueError(
                "Daily attestation lineage mismatch"
            )

    print(
        "01: frozen public and authorized stock caches verified; "
        "no existing raw file changed"
    )


def build_dataset(config,root, *, force=False):
    root=project_root(root);raw=configured_path(config,"raw_cache",root)
    stage=configured_path(config,"stock_inputs",root);stage.mkdir(parents=True,exist_ok=True)
    source=[raw/(x+".parquet") for x in ["monthly_enriched","delists","price_gap_intervals"]]
    expected = {
    str(p.relative_to(raw)): file_sha256(p)
    for p in source
}
    staged=stage/"staging_manifest.json"
    valid=False
    if staged.exists():
        m=json.loads(staged.read_text())
        valid=m.get("source_sha256")==expected and all((stage/k).is_file() and file_sha256(stage/k)==v for k,v in m.get("files",{}).items())
    if not valid:
        monthly=pd.read_parquet(source[0],columns=MONTHLY_COLUMNS)
        if monthly.duplicated(["permno","mthcaldt"]).any():raise ValueError("Duplicate monthly stock records")
        monthly.to_parquet(stage/"monthly_enriched.parquet",index=False)
        for p in source[1:]:pd.read_parquet(p).to_parquet(stage/p.name,index=False)
        m={"source_sha256":expected,"processing":"selected required fields; validated unique stock/month rows; original downloaded bytes preserved",
           "files":{p.name:file_sha256(p) for p in stage.glob("*.parquet")}}
        staged.write_text(json.dumps(m,indent=2)+"\n")
    public={}
    for key,freq in [("kf_daily","daily"),("kf_monthly","monthly")]:
        f=clean_momentum(pd.read_parquet(configured_path(config,key,root)),freq)
        out=root/"data/processed"/f"kf_wml_deciles_{freq}_vw.parquet"
        f.to_parquet(out);public[freq]=f
    target=configured_path(config,"build",root);signature={"config_digest":config_digest(config),"staging_sha256":file_sha256(staged),
        "daily_manifest_sha256":file_sha256(configured_path(config,"daily_cache",root)/("membership_manifest.json" if (configured_path(config,"daily_cache",root)/"membership_manifest.json").exists() else "cache_manifest.json")),
        "code_sha256":{name:file_sha256(Path(__file__).parent/name) for name in ["wml_pipeline.py","ranking.py","ciz_quality.py","stock_reconstruction.py","daily_portfolio.py"]}}
    sig=target/"pipeline_signature.json"
    if not force and sig.exists() and json.loads(sig.read_text())==signature:
        load_build(target);print("02: verified analysis-ready build reused");return
    if target.exists():
        previous=root/"data/interim/superseded_builds"/file_sha256(target/"manifest.json")[:16]
        previous.parent.mkdir(parents=True,exist_ok=True)
        if previous.exists():
            stem=previous.name;number=1
            while previous.exists():
                previous=previous.with_name(stem+"_"+str(number));number+=1
        shutil.move(str(target),str(previous))
    b=build_from_cache(stage,start=config["periods"]["build_start"],end=config["periods"]["end"])
    rebuild_daily(b,configured_path(config,"daily_cache",root))
    b.provenance["raw_staging_manifest_sha256"]=file_sha256(staged)
    save_build(b,target);sig.write_text(json.dumps(signature,indent=2)+"\n")
    print("02: monthly/daily WML, holdings, flags and provenance built from raw inputs")


def baseline_reports(config,root,scope):
    """Report gross KF strategies/regressions and the rebuilt/KF difference."""
    root=project_root(root);risk=config["risk"]
    kd=clean_momentum(pd.read_parquet(configured_path(config,"kf_daily",root)),"daily").mom
    km=clean_momentum(pd.read_parquet(configured_path(config,"kf_monthly",root)),"monthly").mom
    ff=pd.read_parquet(configured_path(config,"ff3",root));ff.index=pd.PeriodIndex(ff.index,freq="M")
    params=dict(annual_target=risk["annual_target"],window=risk["window"],trading_days_per_month=risk["trading_days_per_month"],leverage_cap=risk["leverage_cap"])
    historical=config["windows"]["paper_available_common"]
    _,_,_,fixed=paper_strategies(kd,km,start=historical[0],end=historical[1],**params)
    b=load_build(configured_path(config,"build",root))
    windows={k:v for k,v in config["windows"].items() if (k=="extension_disjoint")== (scope=="extension")}
    base=configured_path(config,"results",root)/scope
    for name,(a,z) in windows.items():
        out=base/"tables"/name;out.mkdir(parents=True,exist_ok=True)
        returns,weights,sigma,_=paper_strategies(kd,km,start=a,end=z,fixed_weight=fixed,**params)
        returns.to_csv(out/"strategy_returns.csv");weights.to_csv(out/"applied_weights.csv");sigma.to_csv(out/"month_end_sigma.csv")
        pd.DataFrame({k:describe(returns[k]) for k in returns}).T.to_csv(out/"gross_metrics.csv")
        for k,frame in factor_tests(returns,ff).items():frame.to_csv(out/(k+".csv"),index=k.startswith("ff"))
        reconstruction_errors(b.monthly_reconstructed.WML,km,{name:(a,z)}).to_csv(out/"reference_reconstruction_errors.csv",index=False)
        reconstruction_errors(b.monthly_dm.WML,km,{name:(a,z)}).to_csv(out/"strict_paired_reconstruction_errors.csv",index=False)
        own_risk,kf_risk=independent_risk(b,kd,returns.index,risk)
        reference=pd.DataFrame({"KF_unmanaged":km.reindex(returns.index),
            "rebuilt_unmanaged":b.monthly_reconstructed.WML.reindex(returns.index),
            "KF_managed":km.reindex(returns.index)*kf_risk.weight})
        reference["rebuilt_managed"]=reference.rebuilt_unmanaged*own_risk.weight
        own_risk.to_csv(out/"rebuilt_risk_weights.csv")
        kf_risk.to_csv(out/"KF_risk_weights.csv")
        reference.loc[a:z].to_csv(out/"rebuilt_KF_returns.csv")
        (out/"construction_audit.json").write_text(json.dumps(b.audit,indent=2)+"\n")
        # This is the factor-scaling teaching scenario, not stock costs.
        ledger,summary=run_backtest(kd,km,transaction_cost_bps=config["costs"]["baseline_bps"],
            financing_cost_bps=config["costs"]["lab_financing_cost_bps"],target_volatility=risk["annual_target"],window=risk["window"],start=a,end=z)
        ledger.to_csv(out/"factor_proxy_ledger.csv");summary.to_csv(out/"factor_proxy_summary.csv")
        replication_figures(returns,base/"figures"/name)
        manifest={"config_digest":config_digest(config),"window":name,"start":a,"end":z,
            "fixed_leverage":"historical common-sample mean; ex-post diagnostic in historical window, frozen in extension",
            "fixed_weight":fixed,"risk_weights":"previous month-end; no extra lag","ff3_inference":"OLS","ff4_timing_inference":"HAC 6 lags",
            "risk_inputs":{"rebuilt":"reconstructed daily WML only","KF":"KF daily WML only","fallback":False},
            "reference":"independent own-risk reconstructed strategy under explicit stock-component zero/terminal-increment scenario",
            "inputs":{key:file_sha256(configured_path(config,key,root)) for key in ["kf_daily","kf_monthly","ff3"]},
            "code":{p.name:file_sha256(p) for p in Path(__file__).parent.glob("*.py")}}
        (out/"run.json").write_text(json.dumps(manifest,indent=2)+"\n")


def stock_reports(config,root,scope, *, force=False):
    root=project_root(root);private=configured_path(config,"study",root);mp=private/"run.json"
    usable=False
    if not force and mp.exists():
        m=json.loads(mp.read_text())
        usable=m.get("config_digest")==config_digest(config) and m.get("cost_bps_per_dollar")==config["costs"]["transaction_cost_bps"]
        for group in [m.get("input_sha256",{}),m.get("code_sha256",{}),m.get("output_sha256",{})]:
            usable=usable and all((root/p).is_file() and file_sha256(root/p)==v for p,v in group.items())
    if usable:
        names=["coverage","metrics","turnover","cutoffs","funded_monthly","appendix_monthly","observations"]
        frames={name:pd.read_csv(private/(name+".csv")) for name in names}
        for frame in frames.values():
            if "month" in frame:frame["month"]=pd.PeriodIndex(frame.month,freq="M")
        gross=pd.read_csv(private/"gross_reference_returns.csv",index_col=0);gross.index=pd.PeriodIndex(gross.index,freq="M")
        study.export_study(root,config,frames,gross,{"unmanaged":None,"managed_own_risk":None},(scope,))
    else:study.run_study(root,config=config,scopes=(scope,))


def run_all(config=None, *, root=None, download=False, force_build=False):
    root=project_root(root);config=load_config(root=root) if config is None else config
    np.random.seed(config["seed"])
    get_data(config,root,download=download);build_dataset(config,root,force=force_build)
    for scope in ["replication","extension"]:
        baseline_reports(config,root,scope);stock_reports(config,root,scope)
    print("All generated results rebuilt without executing notebooks")


def main(argv=None, *, stage=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",default="configs/config.yaml");p.add_argument("--root")
    p.add_argument("--download",action="store_true",help="Explicit initial acquisition only; existing raw files are never refreshed")
    p.add_argument("--force-build",action="store_true",help="Rebuild stock dataset from raw; archive the old processed build")
    p.add_argument("--stage",choices=["all","01","02","03","04"],default=stage or "all")
    a=p.parse_args(argv);root=project_root(a.root);c=load_config(a.config,root=root)
    np.random.seed(c["seed"])
    if a.stage=="all":run_all(c,root=root,download=a.download,force_build=a.force_build)
    elif a.stage=="01":get_data(c,root,download=a.download)
    elif a.stage=="02":build_dataset(c,root,force=a.force_build)
    else:
        scope="replication" if a.stage=="03" else "extension"
        baseline_reports(c,root,scope);stock_reports(c,root,scope)

if __name__=="__main__":main()
