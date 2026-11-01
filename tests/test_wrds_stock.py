import json
import pandas as pd
import pytest
import momentum_risk_project.wrds_stock as source


def test_completed_cache_resume_verifies_offline(tmp_path,monkeypatch):
    data=tmp_path/'calendar.parquet';pd.DataFrame({'date':['2000-01-03']}).to_parquet(data)
    manifest={'status':'complete','files':{'calendar':{'sha256':source._hash(data)}}}
    (tmp_path/'cache_manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(source,'connect_readonly',lambda:pytest.fail('Completed cache must not connect'))
    assert source.download_cache(tmp_path,resume=True,progress=lambda _:None)==manifest


def test_completed_cache_fingerprint_failure_is_not_overwritten(tmp_path):
    data=tmp_path/'calendar.parquet';data.write_bytes(b'original')
    (tmp_path/'cache_manifest.json').write_text(json.dumps({'status':'complete','files':{'calendar.parquet':{'sha256':'wrong'}}}))
    with pytest.raises(RuntimeError,match='fingerprint'):source.download_cache(tmp_path,resume=True)
    assert data.read_bytes()==b'original'


def test_existing_directory_without_manifest_preserved(tmp_path):
    file=tmp_path/'research.txt';file.write_text('preserve')
    with pytest.raises(FileExistsError):source.download_cache(tmp_path,resume=True)
    assert file.read_text()=='preserve'


def test_configurable_extract_dates_include_formation_and_terminal_buffers():
    q=source.extraction_queries('1925-12-01','2025-12-31')
    assert "'1925-12-01'" in q['monthly_enriched']
    assert "'2025-12-31'" in q['monthly_enriched']
    assert "'2026-12-31'" in q['delists']
    assert "DATE '2026-01-01'" in q['price_gap_intervals']
    assert all('1961-01-01' not in sql for sql in q.values())
    with pytest.raises(ValueError):source.extraction_queries('2025-12-31','1925-12-01')


def test_current_extractor_default_dates(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(source,'download_cache',lambda *a,**k:calls.append(k))
    source.main(['--cache-dir',str(tmp_path/'new')])
    assert calls[0]['start']=='1925-12-01' and calls[0]['end']=='2025-12-31'
