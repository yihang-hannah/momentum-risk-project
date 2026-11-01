"""Explicit read-only WRDS extraction for configurable stock research windows.

Requires an existing WRDS .pgpass entry and annual CRSP access. Credentials are
never written to manifests or printed. Raw CRSP data must remain local/ignored.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import pandas as pd
import psycopg2
import pyarrow as pa
import pyarrow.parquet as pq
from .wml_pipeline import build_wml, membership_digest

QUERIES = {'calendar': "SELECT * FROM crsp_a_stock.metaexchangecalendar WHERE caldt BETWEEN '1961-01-01' AND '2011-12-31' ORDER BY caldt", 'delists': "SELECT * FROM crsp_a_stock.stkdelists WHERE delistingdt BETWEEN '1961-01-01' AND '2012-12-31' ORDER BY permno,delistingdt", 'security_history': "SELECT permno,secinfostartdt,secinfoenddt,securitybegdt,securityenddt,primaryexch,conditionaltype,tradingstatusflg,securitynm,usincflg,issuertype,securitytype,securitysubtype,sharetype,securityactiveflg FROM crsp_a_stock.stksecurityinfohist WHERE secinfostartdt<='2011-12-31' AND secinfoenddt>='1961-01-01' ORDER BY permno,secinfostartdt", 'monthly_enriched': "SELECT m.permno,m.mthcaldt,m.mthret,m.mthretx,m.mthprc,m.mthprcflg,m.mthprcdt,m.mthdtflg,m.mthprevprc,m.mthprevdt,m.mthcap,m.mthprevcap,m.mthretflg,m.mthdelflg,m.mthcompflg,m.mthcompsubflg,m.mthdiscnt,m.mthprcvolmisscnt,m.securitytype,m.securitysubtype,m.sharetype,m.conditionaltype,m.primaryexch,m.tradingstatusflg,m.usincflg,m.issuertype,m.ticker,m.issuernm,n.shrcd AS legacy_shrcd,n.exchcd AS legacy_exchcd\n FROM crsp_a_stock.msf_v2 m LEFT JOIN crsp_a_stock.msenames n ON m.permno=n.permno AND m.mthcaldt BETWEEN n.namedt AND n.nameendt\n WHERE m.mthcaldt BETWEEN '1961-01-01' AND '2011-12-31' ORDER BY m.permno,m.mthcaldt", 'legacy_monthly': "SELECT permno,date,ret,retx,prc,shrout FROM crsp_a_stock.msf WHERE date BETWEEN '1961-01-01' AND '2011-12-31' ORDER BY permno,date", 'flags': 'SELECT flagtype,flagvalue,flagtypedesc,flagdesc,flagdef FROM crsp_a_stock.metaflaginfo ORDER BY flagtype,flagvalue'}

PRICE_GAP_SQL = "WITH calendar AS (\n SELECT caldt,row_number() OVER (ORDER BY caldt) AS day_number\n FROM crsp_a_stock.metaexchangecalendar WHERE tradingflg='Y' AND exchangegroup='CIZ' AND caldt BETWEEN '1961-01-01' AND '2011-12-31'\n), prices AS (\n SELECT DISTINCT permno,dlycaldt AS price_date FROM crsp_a_stock.dsf_v2\n WHERE dlycaldt BETWEEN '1961-01-01' AND '2011-12-31' AND dlyprc>0 AND dlyprcflg IN ('TR','BA')\n), sequence AS (\n SELECT permno,price_date,lead(price_date) OVER (PARTITION BY permno ORDER BY price_date) AS next_price_date FROM prices\n)\nSELECT s.permno,s.price_date AS previous_price_date,s.next_price_date,\n c.day_number AS previous_price_number,COALESCE(n.day_number,(SELECT max(day_number)+1 FROM calendar)) AS next_price_number,\n g.caldt AS exclusion_start_date,\n COALESCE(n.caldt,DATE '2012-01-01') AS exclusion_end_exclusive\nFROM sequence s JOIN calendar c ON s.price_date=c.caldt\nLEFT JOIN calendar n ON s.next_price_date=n.caldt\nJOIN calendar g ON g.day_number=c.day_number+201\nWHERE COALESCE(n.day_number,(SELECT max(day_number)+1 FROM calendar))-c.day_number>201\nORDER BY s.permno,s.price_date\n"


def connect_readonly():
    """Connect to WRDS using existing PostgreSQL credentials."""
    import os

    home = Path.home()

    credential_paths = []

    # Respect an explicitly configured PostgreSQL password file.
    if os.environ.get("PGPASSFILE"):
        credential_paths.append(Path(os.environ["PGPASSFILE"]))

    # Standard PostgreSQL credential locations.
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            credential_paths.append(
                Path(appdata) / "postgresql" / "pgpass.conf"
            )

    credential_paths.append(home / ".pgpass")

    for path in credential_paths:
        if not path.is_file():
            continue

        for line in path.read_text().splitlines():
            if not line or line.startswith("#"):
                continue

            fields = line.split(":", 4)

            if len(fields) != 5:
                continue

            host, port, database, username, _ = fields

            if "wrds" not in host.lower():
                continue

            return psycopg2.connect(
                host=host,
                port=port if port != "*" else "9737",
                dbname=database if database != "*" else "wrds",
                user=username,
                connect_timeout=20,
                application_name="momentum_research_readonly",
                options=(
                    "-c default_transaction_read_only=on "
                    "-c statement_timeout=600000"
                ),
                passfile=str(path),
            )

    raise RuntimeError(
        "WRDS credentials not found. Configure PostgreSQL "
        ".pgpass (Unix) or pgpass.conf (Windows), or set PGPASSFILE."
    )


def _hash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def _extract(connection,sql,path,cursor_name):
    partial=path.with_suffix('.partial.parquet')
    writer=None;count=0
    try:
        with connection.cursor(name=cursor_name) as cursor:
            cursor.itersize=100000;cursor.execute(sql)
            while True:
                rows=cursor.fetchmany(100000)
                if not rows:break
                data=pd.DataFrame(rows,columns=[c[0] for c in cursor.description])
                for col in data:
                    if any(isinstance(v,__import__('decimal').Decimal) for v in data[col].head(200).dropna()):
                        data[col]=pd.to_numeric(data[col]).astype(float)
                table=pa.Table.from_pandas(data,preserve_index=False)
                if writer is None:writer=pq.ParquetWriter(partial,table.schema,compression='zstd')
                if table.schema!=writer.schema:table=table.cast(writer.schema)
                writer.write_table(table);count+=len(data)
        if writer:writer.close();writer=None
        if count == 0:
            if not cursor_name.startswith("daily_"):
                raise RuntimeError(
                    "Extraction returned no rows; refusing an empty cache"
             )

            # A monthly holdings query can legitimately return no records.
            # Preserve the expected daily-data schema.
            empty = pd.DataFrame({
                "permno": pd.Series(dtype="int64"),
                "dlycaldt": pd.Series(dtype="datetime64[ns]"),
                "dlydelflg": pd.Series(dtype="object"),
                "dlyret": pd.Series(dtype="float64"),
                "dlyretx": pd.Series(dtype="float64"),
                "dlyprc": pd.Series(dtype="float64"),
                "dlyprcflg": pd.Series(dtype="object"),
                "dlyretmissflg": pd.Series(dtype="object"),
                "dlyretdurflg": pd.Series(dtype="object"),
                "dlyprevdt": pd.Series(dtype="datetime64[ns]"),
                "dlycumfacpr": pd.Series(dtype="float64"),
            })

            pq.write_table(
                pa.Table.from_pandas(empty, preserve_index=False),
                partial,
                compression="zstd",
            )
        connection.commit()
        partial.rename(path)
        return count
    except Exception:
        try:
            if writer is not None:
                writer.close()
        finally:
            try:
                if not connection.closed:
                    connection.rollback()
            finally:
                partial.unlink(missing_ok=True)
        raise


def extraction_queries(start, end):
    """Expand the frozen template dates without altering old cache defaults."""
    start = str(pd.Timestamp(start).date())
    end_date = pd.Timestamp(end)
    end = str(end_date.date())
    if pd.Timestamp(start) >= end_date:
        raise ValueError('Extraction end must follow start')
    next_end = str((end_date + pd.DateOffset(years=1)).date())
    exclusive = str((end_date + pd.Timedelta(days=1)).date())
    def expand(sql):
        return (sql.replace('1961-01-01', start).replace('2011-12-31', end)
                .replace('2012-12-31', next_end).replace('2012-01-01', exclusive))
    return {name:expand(sql) for name,sql in {**QUERIES,'price_gap_intervals':PRICE_GAP_SQL}.items()}

def _extract_daily_year(connection, group, year, daily_dir, progress=print):
    """Download selected daily holdings by month and assemble a yearly file.

    Completed monthly files are verified and reused after interruption.
    """
    year = int(year)
    year_dir = daily_dir / "_monthly" / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    monthly_paths = []

    for month, month_group in group.groupby("yyyymm", sort=True):
        month = int(month)
        path = year_dir / f"{month}.parquet"
        fingerprint_path = year_dir / f"{month}.sha256"

        if path.exists():
            if not fingerprint_path.exists():
                raise RuntimeError(
                    f"Monthly cache lacks fingerprint: {path}"
                )
            if _hash(path) != fingerprint_path.read_text().strip():
                raise RuntimeError(
                    f"Monthly cache fingerprint mismatch: {path}"
                )
            monthly_paths.append(path)
            continue

        if fingerprint_path.exists():
            raise RuntimeError(
                f"Monthly fingerprint exists without data: {path}"
            )

        with connection.cursor() as cursor:
            values = ",".join(
                cursor.mogrify(
                    "(%s,%s)",
                    (int(permno), int(yyyymm))
                ).decode()
                for permno, yyyymm in month_group[
                    ["permno", "yyyymm"]
                ].itertuples(index=False, name=None)
            )

        month_start = pd.Period(str(month), freq="M").start_time.date()
        month_end = (
            pd.Period(str(month), freq="M") + 1
        ).start_time.date()

        sql = f"""
            WITH requested(permno, yyyymm) AS (VALUES {values})
            SELECT
                d.permno,
                d.dlycaldt,
                d.dlydelflg,
                d.dlyret::float8,
                d.dlyretx::float8,
                d.dlyprc::float8,
                d.dlyprcflg,
                d.dlyretmissflg,
                d.dlyretdurflg,
                d.dlyprevdt,
                d.dlycumfacpr::float8
            FROM crsp_a_stock.dsf_v2 d
            JOIN requested r
              ON d.permno = r.permno
             AND (d.yyyymmdd / 100) = r.yyyymm
            WHERE d.dlycaldt >= DATE '{month_start}'
              AND d.dlycaldt < DATE '{month_end}'
            ORDER BY d.dlycaldt, d.permno, d.dlydelflg
        """

        rows = _extract(
            connection,
            sql,
            path,
            f"daily_{month}"
        )

        fingerprint_path.write_text(_hash(path) + "\n")
        monthly_paths.append(path)
        progress(f"Saved daily holdings {month}: {rows:,} rows")

    yearly_path = daily_dir / f"{year}.parquet"
    partial_path = daily_dir / f"{year}.partial.parquet"

    writer = None
    total_rows = 0

    try:
        for month_path in monthly_paths:
            parquet = pq.ParquetFile(month_path)

            for batch in parquet.iter_batches(batch_size=100000):
                table = pa.Table.from_batches([batch])

                if writer is None:
                    writer = pq.ParquetWriter(
                        partial_path,
                        table.schema,
                        compression="zstd"
                    )

                if table.schema != writer.schema:
                    table = table.cast(writer.schema)

                writer.write_table(table)
                total_rows += table.num_rows

        if writer is None:
            raise RuntimeError(
                f"No daily observations extracted for {year}"
            )

        writer.close()
        writer = None

        partial_path.replace(yearly_path)
        return total_rows

    except Exception:
        if writer is not None:
            writer.close()
        partial_path.unlink(missing_ok=True)
        raise

def download_cache(
    cache_dir,
    *,
    resume=False,
    start='1925-12-01',
    end='2025-12-31',
    progress=print,
):
    root = Path(cache_dir)
    manifest_path = root / 'cache_manifest.json'

    # ---------------------------------------------------------
    # 1. Validate the existing cache directory
    # ---------------------------------------------------------
    if root.exists():
        if not root.is_dir():
            raise FileExistsError(
                f"Cache path exists but is not a directory: {root}"
            )

        if not manifest_path.exists():
            if any(root.iterdir()):
                raise FileExistsError(
                    "Cache directory contains files but has no manifest; "
                    "use a new directory rather than mixing unverified data"
                )
        elif not resume:
            raise FileExistsError(
                "Existing cache requires --resume"
            )

    root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # 2. Load or initialize the extraction manifest
    # ---------------------------------------------------------
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {
            'source_schema': 'crsp_a_stock',
            'requested_start': start,
            'requested_end': end,
            'extraction_started_utc': datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            'connection_mode': 'read-only',
            'files': {},
            'status': 'in_progress',
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + '\n'
        )

    def save():
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + '\n'
        )

    # ---------------------------------------------------------
    # 3. Verify an already completed cache without WRDS access
    # ---------------------------------------------------------
    if resume and manifest.get('status') == 'complete':
        for key, entry in manifest['files'].items():
            relative = (
                Path(key)
                if str(key).endswith('.parquet')
                else Path(str(key) + '.parquet')
            )

            file_path = root / relative

            if (
                not file_path.exists()
                or _hash(file_path) != entry['sha256']
            ):
                raise RuntimeError(
                    'Completed cache failed fingerprint verification'
                )

        progress(
            'Completed cache verified; no network request required'
        )
        return manifest

    # ---------------------------------------------------------
    # 4. Check extraction dates before resuming
    # ---------------------------------------------------------
    if (
        manifest.get('requested_start', start) != start
        or manifest.get('requested_end', end) != end
    ):
        raise ValueError(
            'Resume dates must match the original extraction'
        )

    # ---------------------------------------------------------
    # 5. Connect to WRDS
    # ---------------------------------------------------------
    connection = connect_readonly()

    try:
        # Verify that the source database coverage has not changed.
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT min(mthcaldt), max(mthcaldt) '
                'FROM crsp_a_stock.msf_v2'
            )
            lo, hi = cursor.fetchone()

        observed = {
            'first': str(lo),
            'last': str(hi),
        }

        if (
            'source_observed_coverage' in manifest
            and manifest['source_observed_coverage'] != observed
        ):
            raise RuntimeError(
                'Source coverage changed; use a new directory '
                'rather than mixing snapshots'
            )

        manifest['source_observed_coverage'] = observed
        save()
        connection.commit()

        # -----------------------------------------------------
        # 6. Download or verify the seven core CRSP datasets
        # -----------------------------------------------------
        queries = extraction_queries(start, end)

        for name, sql in queries.items():
            path = root / f'{name}.parquet'

            if path.exists():
                if (
                    manifest['files'].get(name, {}).get('sha256')
                    != _hash(path)
                ):
                    raise RuntimeError(
                        'Existing cache fingerprint mismatch'
                    )

                progress(f'Validated existing cache: {name}')
                continue

            rows = _extract(
                connection,
                sql,
                path,
                'extract_' + name,
            )

            manifest['files'][name] = {
                'rows': rows,
                'sha256': _hash(path),
                'sql': sql,
                'completed_utc': datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }

            save()
            progress(f'Saved {name}: {rows:,} rows')

        # -----------------------------------------------------
        # 7. Reconstruct momentum portfolio membership
        # -----------------------------------------------------
        monthly = pd.read_parquet(
            root / 'monthly_enriched.parquet'
        )

        gaps = pd.read_parquet(
            root / 'price_gap_intervals.parquet'
        )

        first = (
            pd.to_datetime(monthly.mthcaldt)
            .min()
            .to_period('M')
        )

        built = build_wml(
            monthly,
            pd.read_parquet(root / 'delists.parquet'),
            start=str(first + 13),
            end=str(pd.Period(end, freq='M')),
            price_intervals=gaps,
        )

        holdings = built.holdings
        digest = membership_digest(holdings)

        if manifest.get('membership_digest') not in (
            None,
            digest,
        ):
            raise RuntimeError(
                'Formation universe changed; use a new cache'
            )

        if (
            manifest.get('membership_digest') is None
            and any(
                str(key).startswith('held_daily/')
                for key in manifest['files']
            )
        ):
            raise RuntimeError(
                'Legacy partial daily selection is unverified; '
                'use a new cache'
            )

        manifest['membership_digest'] = digest
        manifest['formation_policy'] = (
            built.audit['formation_policy']
        )
        save()

        # Only the loser and winner deciles are required.
        holdings = holdings.loc[
            holdings.momentum_decile.isin([1, 10])
        ].copy()

        holdings['year'] = holdings.month.dt.year

        holdings['yyyymm'] = (
            holdings.month.dt.year * 100
            + holdings.month.dt.month
        )

        # -----------------------------------------------------
        # 8. Download daily holdings in resumable monthly batches
        # -----------------------------------------------------
        daily_dir = root / 'held_daily'
        daily_dir.mkdir(exist_ok=True)

        for year, group in holdings.groupby('year'):
            year = int(year)
            path = daily_dir / f'{year}.parquet'
            key = f'held_daily/{year}'

            # Already completed and recorded in the manifest.
            if path.exists() and key in manifest['files']:
                if (
                    manifest['files'][key].get('sha256')
                    != _hash(path)
                ):
                    raise RuntimeError(
                        f'Daily fingerprint mismatch: {year}'
                    )

                progress(
                    f'Validated existing daily holdings: {year}'
                )
                continue

            # A year may have been assembled just before an
            # interruption, but not yet recorded in the manifest.
            # Reassemble it from verified monthly intermediates
            # rather than trusting an unrecorded yearly file.
            if path.exists() and key not in manifest['files']:
                progress(
                    f'Unrecorded yearly file found for {year}; '
                    'verifying monthly intermediates and reassembling'
                )

            rows = _extract_daily_year(
                connection,
                group,
                year,
                daily_dir,
                progress=progress,
            )

            manifest['files'][key] = {
                'rows': rows,
                'sha256': _hash(path),
                'selection': (
                    'formed P1/P10 stock-months; '
                    'no holding-month security filter'
                ),
                'requested_stock_months': len(group),
                'completed_utc': datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }

            save()
            progress(
                f'Saved daily holdings {year}: {rows:,} rows'
            )

        # -----------------------------------------------------
        # 9. Mark the full cache complete
        # -----------------------------------------------------
        manifest['status'] = 'complete'
        save()

    finally:
        connection.close()

    return manifest

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir',type=Path,required=True)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--start',default='1925-12-01')
    p.add_argument('--end',default='2025-12-31')
    a=p.parse_args(argv)
    download_cache(a.cache_dir,resume=a.resume,start=a.start,end=a.end)


if __name__=='__main__':main()
