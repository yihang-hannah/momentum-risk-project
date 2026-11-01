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

def test_download_cache_accepts_empty_directory(tmp_path, monkeypatch):
    from momentum_risk_project.wrds_stock import download_cache

    cache = tmp_path / "crsp_cache"
    cache.mkdir()

    class StopBeforeConnection(Exception):
        pass

    def fake_connect():
        raise StopBeforeConnection()

    monkeypatch.setattr(
        "momentum_risk_project.wrds_stock.connect_readonly",
        fake_connect,
    )

    with pytest.raises(StopBeforeConnection):
        download_cache(cache, resume=True)

    assert (cache / "cache_manifest.json").exists()

def test_daily_year_resumes_verified_months(tmp_path, monkeypatch):
    import hashlib

    daily_dir = tmp_path / "held_daily"
    group = pd.DataFrame({
        "permno": [10001, 10002],
        "yyyymm": [200101, 200102],
    })

    calls = []

    def fake_extract(connection, sql, path, cursor_name):
        calls.append(cursor_name)

        if cursor_name == "daily_200102" and len(calls) == 2:
            raise ConnectionError("Simulated WRDS interruption")

        pd.DataFrame({
            "permno": [10001],
            "dlycaldt": [pd.Timestamp("2001-01-15")],
            "dlyret": [0.01],
        }).to_parquet(path, index=False)

        return 1

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def mogrify(self, template, values):
            return (
                f"({values[0]},{values[1]})"
            ).encode()

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(source, "_extract", fake_extract)

    with pytest.raises(ConnectionError, match="interruption"):
        source._extract_daily_year(
            FakeConnection(),
            group,
            2001,
            daily_dir,
            progress=lambda _: None,
        )

    january = daily_dir / "_monthly" / "2001" / "200101.parquet"
    assert january.exists()

    source._extract_daily_year(
        FakeConnection(),
        group,
        2001,
        daily_dir,
        progress=lambda _: None,
    )

    assert calls == [
        "daily_200101",
        "daily_200102",
        "daily_200102",
    ]

    yearly = pd.read_parquet(daily_dir / "2001.parquet")
    assert len(yearly) == 2

def test_extract_empty_daily_month(tmp_path):
    import pyarrow.parquet as pq

    class FakeCursor:
        description = [
            (name,) for name in [
                "permno", "dlycaldt", "dlydelflg",
                "dlyret", "dlyretx", "dlyprc",
                "dlyprcflg", "dlyretmissflg",
                "dlyretdurflg", "dlyprevdt",
                "dlycumfacpr",
            ]
        ]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            pass

        def fetchmany(self, size):
            return []

    class FakeConnection:
        def __init__(self):
            self.committed = False

        def cursor(self, name=None):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            pass

    connection = FakeConnection()
    path = tmp_path / "empty_month.parquet"

    rows = source._extract(
        connection,
        "SELECT ...",
        path,
        "daily_200101",
    )

    assert rows == 0
    assert connection.committed
    assert path.exists()
    assert pq.read_table(path).num_rows == 0
    assert len(pq.read_table(path).column_names) == 11    