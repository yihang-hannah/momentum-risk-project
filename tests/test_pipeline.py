import copy,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from momentum_risk_project.paths import project_path,project_root
from momentum_risk_project.config import load_config,config_digest
from momentum_risk_project.pipeline import verify_cache,get_data,stock_reports
from momentum_risk_project.models import paper_strategies
from momentum_risk_project.evaluation import factor_tests
from momentum_risk_project.wml_pipeline import file_sha256


def test_paths_are_root_relative_and_reject_escape(tmp_path):
    assert project_path("data/raw/x",tmp_path)==tmp_path/"data/raw/x"
    for p in ["../x","/tmp/x"]:
        with pytest.raises(ValueError):project_path(p,tmp_path)
    (tmp_path/"escape").symlink_to(tmp_path.parent,target_is_directory=True)
    with pytest.raises(ValueError):project_path("escape/leak",tmp_path)


def test_config_rejects_unsupported_universe_and_overlap(tmp_path):
    import yaml
    c=load_config();p=tmp_path/"bad.yaml"
    for key in ["universe","windows"]:
        bad=copy.deepcopy(c)
        if key=="universe":bad[key]["share_codes"]=[10]
        else:bad[key]["extension_disjoint"][0]="2011-01"
        p.write_text(yaml.safe_dump(bad))
        with pytest.raises(ValueError):load_config(p,root=tmp_path)
    assert config_digest(c)==config_digest(copy.deepcopy(c))


def test_offline_get_data_missing_input_does_not_download_or_create_raw(tmp_path):
    c=load_config()
    with pytest.raises(FileNotFoundError,match="--download"):get_data(c,tmp_path)
    assert not (tmp_path/"data").exists()


def test_raw_verifier_detects_mutation_and_never_repairs_it(tmp_path):
    p=tmp_path/"calendar.parquet";p.write_bytes(b"immutable")
    (tmp_path/"cache_manifest.json").write_text(json.dumps({"status":"complete","files":{"calendar":{"sha256":file_sha256(p)}}}))
    verify_cache(tmp_path);p.write_bytes(b"bad")
    with pytest.raises(ValueError,match="fingerprint"):verify_cache(tmp_path)
    assert p.read_bytes()==b"bad"


def test_packaged_four_strategy_equations_and_gap_rejection():
    rng=np.random.default_rng(4576)
    d=pd.Series(rng.normal(0,.01,700),index=pd.bdate_range("1999-01-01",periods=700))
    m=pd.Series(.02,index=pd.period_range("1999-01","2001-06",freq="M"))
    r,w,s,average=paper_strategies(d,m,start="2000-01",end="2000-12")
    np.testing.assert_allclose(r.managed,w*m.reindex(w.index))
    np.testing.assert_allclose(r.fixed_leverage,average*m.reindex(w.index))
    np.testing.assert_allclose(r.managed_cap_2x,w.clip(upper=2)*m.reindex(w.index))
    changed=d.copy();changed.loc['2000-06-01':]=.7
    _,w2,_,_=paper_strategies(changed,m,start="2000-01",end="2000-12")
    np.testing.assert_allclose(w.loc[:'2000-06'],w2.loc[:'2000-06'])
    m.loc['2000-03']=np.nan
    with pytest.raises(ValueError,match="finite|complete"):paper_strategies(d,m,start="2000-01",end="2000-12")


def test_factor_tests_match_independent_ols_and_hac():
    import statsmodels.api as sm
    rng=np.random.default_rng(4);idx=pd.period_range('2000-01',periods=100,freq='M')
    ff=pd.DataFrame(rng.normal(0,.03,(100,4)),index=idx,columns=['Mkt-RF','SMB','HML','RF'])
    r=pd.DataFrame(rng.normal(.01,.04,(100,4)),index=idx,columns=['unmanaged','fixed_leverage','managed','managed_cap_2x'])
    tables=factor_tests(r,ff)
    independent=sm.OLS(r.managed,sm.add_constant(ff[['Mkt-RF','SMB','HML']])).fit()
    assert tables['ff3_regressions'].loc['managed','Alpha (monthly)']==pytest.approx(independent.params['const'])
    timing=sm.OLS(r.managed-r.fixed_leverage,pd.DataFrame({'const':1.},index=idx)).fit(cov_type='HAC',cov_kwds={'maxlags':6})
    assert tables['timing_HAC'].iloc[0].HAC_t==pytest.approx(timing.tvalues['const'])
    ff.iloc[0,0]=np.nan
    assert factor_tests(r,ff)['factor_coverage'].iloc[0].excluded_months==1


def test_dataset_staging_and_signature_reuse_without_raw_edits(tmp_path,monkeypatch):
    monkeypatch.delenv("MOMENTUM_CRSP_CACHE", raising=False)
    from momentum_risk_project import pipeline
    from momentum_risk_project.wml_pipeline import MONTHLY_COLUMNS
    from test_wml_pipeline import bundle
    c=load_config();raw=tmp_path/c['paths']['raw_cache'];raw.mkdir(parents=True)
    m=pd.DataFrame({name:[0] for name in MONTHLY_COLUMNS})
    m['permno']=1;m['mthcaldt']=pd.to_datetime(['2000-01-31'])
    m.to_parquet(raw/'monthly_enriched.parquet',index=False)
    pd.DataFrame({'permno':[1]}).to_parquet(raw/'delists.parquet',index=False)
    pd.DataFrame({'permno':[1]}).to_parquet(raw/'price_gap_intervals.parquet',index=False)
    fingerprints={p.name:file_sha256(p) for p in raw.glob('*.parquet')}
    daily=tmp_path/c['paths']['daily_cache'];daily.mkdir(parents=True, exist_ok=True)
    (daily/'cache_manifest.json').write_text('{}')
    for key,freq in [('kf_daily','daily'),('kf_monthly','monthly')]:
        f=pd.DataFrame(1.,index=pd.bdate_range('2000-01-01',periods=2) if freq=='daily' else pd.period_range('2000-01',periods=2,freq='M'),columns=range(10))
        f.to_parquet(tmp_path/c['paths'][key])
    (tmp_path/'data/processed').mkdir()
    calls=[]
    monkeypatch.setattr(pipeline,'build_from_cache',lambda *a,**k:(calls.append('build') or bundle()))
    monkeypatch.setattr(pipeline,'rebuild_daily',lambda *a,**k:calls.append('daily'))
    pipeline.build_dataset(c,tmp_path);pipeline.build_dataset(c,tmp_path)
    assert calls==['build','daily']
    assert all(file_sha256(raw/name)==digest for name,digest in fingerprints.items())
    staged=tmp_path/c['paths']['stock_inputs']
    assert (staged/'staging_manifest.json').exists()
    (staged/'monthly_enriched.parquet').write_bytes(b'corrupt derived input')
    pipeline.build_dataset(c,tmp_path)
    assert calls==['build','daily']  # Restoring identical staging bytes retains the valid build.


def test_stock_cache_detects_changed_config_and_output(tmp_path,monkeypatch):
    from momentum_risk_project import pipeline
    c=load_config();private=tmp_path/c['paths']['study'];private.mkdir(parents=True)
    calls=[]
    monkeypatch.setattr(pipeline.study,'run_study',lambda *a,**k:calls.append(k['scopes']))
    # A stale manifest must trigger package recomputation, not use previous results.
    (private/'run.json').write_text(json.dumps({'config_digest':'stale'}))
    pipeline.stock_reports(c,tmp_path,'replication')
    assert calls==[('replication',)]


def test_one_command_order_is_independent_of_notebooks(tmp_path,monkeypatch):
    from momentum_risk_project import pipeline
    calls=[];c=load_config()
    monkeypatch.setattr(pipeline,'get_data',lambda *a,**k:calls.append('get'))
    monkeypatch.setattr(pipeline,'build_dataset',lambda *a,**k:calls.append('build'))
    monkeypatch.setattr(pipeline,'baseline_reports',lambda c,r,s:calls.append('baseline/'+s))
    monkeypatch.setattr(pipeline,'stock_reports',lambda c,r,s:calls.append('stock/'+s))
    pipeline.run_all(c,root=tmp_path)
    assert calls==['get','build','baseline/replication','stock/replication','baseline/extension','stock/extension']
    assert not (tmp_path/'notebooks').exists()


def test_scope_export_filters_overlap_and_extension(tmp_path,monkeypatch):
    from momentum_risk_project import study
    c=load_config();private=tmp_path/c['paths']['study'];private.mkdir(parents=True)
    (private/'run.json').write_text('{}')
    monkeypatch.setattr(study,'stock_study_figures',lambda *a:None)
    frames={'metrics':pd.DataFrame({'window':list(c['windows']),'value':[1,2,3]})}
    study.export_study(tmp_path,c,frames,pd.DataFrame(),{},('replication','extension'))
    base=tmp_path/c['paths']['results']
    a=pd.read_csv(base/'replication/tables/stock_costs/metrics.csv')
    b=pd.read_csv(base/'extension/tables/stock_costs/metrics.csv')
    assert set(a.window)=={'paper_available_common','paper_turnover_test'}
    assert list(b.window)==['extension_disjoint']

def test_shared_crsp_cache_downloaded_once(tmp_path, monkeypatch):
    monkeypatch.delenv("MOMENTUM_CRSP_CACHE", raising=False)
    import json

    from momentum_risk_project import pipeline
    from momentum_risk_project.config import load_config, configured_path
    from momentum_risk_project.wml_pipeline import file_sha256

    config = load_config()
    assert config["paths"]["raw_cache"] == config["paths"]["daily_cache"]

    # Prepare valid public input files.
    from test_wml_pipeline import bundle

    for key, freq in [("kf_daily", "daily"), ("kf_monthly", "monthly")]:
        path = configured_path(config, key, tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        index = (
            pd.bdate_range("2000-01-01", periods=2)
            if freq == "daily"
            else pd.period_range("2000-01", periods=2, freq="M")
        )
        pd.DataFrame(1.0, index=index, columns=range(10)).to_parquet(path)

    ff = configured_path(config, "ff3", tmp_path)
    ff.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"Mkt-RF": [0.01], "SMB": [0.0], "HML": [0.0], "RF": [0.0]},
        index=pd.period_range("2000-01", periods=1, freq="M"),
    ).to_parquet(ff)

    calls = []

    def fake_download(cache, **kwargs):
        calls.append(cache)
        cache.mkdir(parents=True, exist_ok=True)

        file = cache / "sample.parquet"
        file.write_bytes(b"test fixture")

        manifest = {
            "status": "complete",
            "files": {
                "sample": {"sha256": file_sha256(file)}
            },
        }
        (cache / "cache_manifest.json").write_text(json.dumps(manifest))

    monkeypatch.setattr(
        "momentum_risk_project.wrds_stock.download_cache",
        fake_download,
    )

    pipeline.get_data(config, tmp_path, download=True)

    assert len(calls) == 1

def test_external_crsp_cache_override(tmp_path, monkeypatch):
    from momentum_risk_project.config import load_config, configured_path

    config = load_config()
    external = tmp_path / "external_crsp_cache"

    monkeypatch.setenv("MOMENTUM_CRSP_CACHE", str(external))

    assert configured_path(config, "raw_cache", tmp_path) == external.resolve()
    assert configured_path(config, "daily_cache", tmp_path) == external.resolve()

    # Other paths must remain inside the project.
    assert configured_path(config, "stock_inputs", tmp_path) == (
        tmp_path / config["paths"]["stock_inputs"]
    )
    assert configured_path(config, "results", tmp_path) == (
        tmp_path / config["paths"]["results"]
    )