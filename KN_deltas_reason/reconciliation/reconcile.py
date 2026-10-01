"""One-table, read-only source/target inventory and local timestamp reconciliation."""

import argparse
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
UTC = timezone.utc
LOCAL = ZoneInfo('Europe/Ljubljana')
SCHEMA = """
CREATE TABLE source_rows (business_key TEXT, changed_at TEXT, native_changed_at TEXT);
CREATE TABLE target_rows (uuid TEXT NOT NULL, business_key TEXT, changed_at TEXT,
                          native_changed_at TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE capture (status TEXT, metadata_json TEXT);
"""


def utc_text(value, zone):
    """Explicit local interpretation; reject ambiguous/nonexistent naive wall times."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        tz = ZoneInfo(zone)
        candidates = {dt.replace(tzinfo=tz, fold=fold).astimezone(UTC)
                      for fold in (0, 1)
                      if dt.replace(tzinfo=tz, fold=fold).astimezone(UTC).astimezone(tz).replace(tzinfo=None) == dt}
        if len(candidates) != 1:
            raise ValueError(f'Ambiguous/nonexistent time {value}; supply an explicit offset')
        dt = candidates.pop()
    return dt.astimezone(UTC).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def metadata(connection):
    with connection.cursor() as cursor:
        cursor.execute((HERE / 'metadata.sql').read_text())
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise ValueError('Expected exactly one integration metadata row')
        return dict(zip([c.name for c in cursor.description], rows[0]))


def effective_bound(before, after, zone):
    # Current FMP full/first-sync branch and changed-date fallback. Not historical eligibility.
    if before != after or before['processing_status'] == 'PROCESSING':
        return None, 'UNKNOWN: settings changed or integration processing'
    if before['is_full_sync'] or not before['last_sync_start']:
        return None, 'NOT_DELTA: full sync or first sync'
    if not zone:
        return None, 'UNKNOWN: production worker timezone not verified'
    value = (before['last_changed_datetime'] if before['use_changed_datetime_for_delta']
             and before['last_changed_datetime'] else before['last_sync_start'])
    try:
        return utc_text(value, zone), 'Stable current effective lower bound (not historical run proof)'
    except (ValueError, TypeError):
        return None, 'UNKNOWN: uninterpretable watermark'


def export_capture(env_file, output):
    config = json.loads((HERE / 'config.json').read_text())
    if not config['preflight_verified'] or len(config['reviewed_integration_sql_sha256']) != 64:
        raise ValueError('Complete README preflight and config.json before exporting')
    ZoneInfo(config['target_timezone'])
    if config['watermark_timezone']:
        ZoneInfo(config['watermark_timezone'])
    # Drivers are deliberately absent from the offline comparison/test path.
    from dotenv import load_dotenv
    import oracledb
    import psycopg
    load_dotenv(env_file, override=False)
    if os.getenv('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=os.environ['KN_ORACLE_CLIENT_LIB_DIR'])
    pg = dict(host=os.environ['PROD_HOST'], port=os.environ['PROD_PORT'],
              user=os.environ['PROD_USER'], password=os.environ['PROD_PASSWORD'], connect_timeout=20)
    output.mkdir(parents=True, exist_ok=False)
    partial = output / 'capture.partial.sqlite3'
    info = {'config': config, 'started_at': datetime.now(UTC).isoformat(), 'sql': {}, 'intervals': {}, 'counts': {}}
    try:
        with closing(sqlite3.connect(partial)) as db, psycopg.connect(
            **pg, dbname=os.getenv('PROD_METADATA_DATABASE', 'fmp'), autocommit=True
        ) as meta:
            meta.execute('SET default_transaction_read_only = on')
            meta.execute("SET TIME ZONE 'UTC'")
            info['before'] = metadata(meta)
            before = info['before']
            if before['target_table'] != 'kn_nep_deli_stavb_h':
                raise ValueError('Live integration points at a different target')
            if hashlib.sha256(before['url'].encode()).hexdigest() != config['reviewed_integration_sql_sha256']:
                raise ValueError('Live integration SQL differs from reviewed SQL; stop and review')
            key_maps = [(m['api_name'].upper(), m['target_field']) for m in before['mappings'] if m['api_id'] and not m['api_block_sync']]
            date_maps = [(m['api_name'].upper(), m['target_field']) for m in before['mappings'] if m['api_last_sync_field'] and not m['api_block_sync']]
            if key_maps != [('DEL_STAVBE_H_ID', 'del_stavbe_h_id')] or date_maps != [('DATUM_SYS', 'datum_sys')]:
                raise ValueError('Live key/change mappings differ from this one-table experiment')
            db.executescript(SCHEMA)
            db.execute('BEGIN')
            info['sql'] = {name: (HERE / f'{name}.sql').read_text() for name in ('source', 'target', 'metadata')}
            info['endpoints'] = {'oracle_dsn': os.environ['KN_ORACLE_DSN'], 'oracle_user': os.environ['KN_ORACLE_USER'],
                                 'pg_host': pg['host'], 'pg_port': pg['port'], 'pg_user': pg['user'],
                                 'target_database': os.getenv('PROD_DATABASE', 'fmp_data_gurs'),
                                 'metadata_database': os.getenv('PROD_METADATA_DATABASE', 'fmp')}
            # One consistent Oracle stream, no pagination or retry.
            info['intervals']['source_start'] = datetime.now(UTC).isoformat()
            with oracledb.connect(user=os.environ['KN_ORACLE_USER'], password=os.environ['KN_ORACLE_PASSWORD'],
                                  dsn=os.environ['KN_ORACLE_DSN']) as oracle:
                oracle.call_timeout = 60000
                with oracle.cursor() as cursor:
                    cursor.execute('ALTER SESSION SET ERROR_ON_OVERLAP_TIME = TRUE')
                    cursor.execute('SET TRANSACTION READ ONLY')
                    cursor.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME'), SYS_CONTEXT('USERENV','SERVICE_NAME') FROM dual")
                    info['oracle_identity'] = cursor.fetchone()
                    cursor.arraysize = 5000
                    cursor.execute(info['sql']['source'])
                    count = 0
                    while rows := cursor.fetchmany(5000):
                        db.executemany('INSERT INTO source_rows VALUES (?,?,?)', rows)
                        count += len(rows)
                        print(f'Source: {count:,}', flush=True)
                    info['counts']['source'] = count
                oracle.rollback()
            info['intervals']['source_end'] = datetime.now(UTC).isoformat()
            # Independent target snapshot: this is NOT an atomic cross-database capture.
            info['intervals']['target_start'] = datetime.now(UTC).isoformat()
            with psycopg.connect(**pg, dbname=info['endpoints']['target_database']) as target:
                target.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                target.execute("SET LOCAL TIME ZONE 'UTC'")
                info['target_columns'] = target.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='kn_nep_deli_stavb_h' ORDER BY ordinal_position").fetchall()
                columns = {r[0]: r[1:] for r in info['target_columns']}
                if columns.get('datum_sys') != ('timestamp without time zone', 'YES') and columns.get('datum_sys') != ('timestamp without time zone', 'NO'):
                    raise ValueError('target.sql requires datum_sys timestamp WITHOUT time zone')
                if columns.get('id', (None, None))[1] != 'NO':
                    raise ValueError('Target UUID must be NOT NULL')
                info['target_indexes'] = target.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='kn_nep_deli_stavb_h'").fetchall()
                info['target_identity'] = target.execute('SELECT current_database(),current_user,inet_server_addr()::text,inet_server_port()').fetchone()
                with target.cursor(name='reconciliation_export') as cursor:
                    cursor.execute(info['sql']['target'])
                    count = 0
                    while rows := cursor.fetchmany(5000):
                        # Reject ambiguous/nonexistent naive target wall times, just like report bounds.
                        db.executemany('INSERT INTO target_rows VALUES (?,?,?,?,?,?)',
                                       ((uuid, key, utc_text(native, config['target_timezone']) if native else None,
                                         native, created, updated) for uuid, key, native, created, updated in rows))
                        count += len(rows)
                        print(f'Target: {count:,}', flush=True)
                    info['counts']['target'] = count
            info['intervals']['target_end'] = datetime.now(UTC).isoformat()
            info['after'] = metadata(meta)
            db.execute('CREATE INDEX source_key ON source_rows(business_key)')
            db.execute('CREATE INDEX target_key ON target_rows(business_key)')
            info['finished_at'] = datetime.now(UTC).isoformat()
            db.execute('INSERT INTO capture VALUES (?,?)', ('COMPLETE', json.dumps(info)))
            db.commit()
        partial.rename(output / 'capture.sqlite3')
    except BaseException as error:
        # No exception text/credentials in artifacts. Partial filename is never accepted.
        (output / 'FAILED.txt').write_text(f'{type(error).__name__}: export incomplete; rerun into a new directory.\n')
        raise
    print(output / 'capture.sqlite3')


def compare_capture(database, start, end, page_size=None):
    start_utc, end_utc = utc_text(start, 'Europe/Ljubljana'), utc_text(end, 'Europe/Ljubljana')
    if start_utc >= end_utc:
        raise ValueError('start must precede end')
    if database.name != 'capture.sqlite3':
        raise ValueError('Only published capture.sqlite3 files are accepted')
    if page_size is not None and page_size <= 0:
        raise ValueError('page-size must be positive')
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db, tempfile.TemporaryDirectory(prefix='.reports-', dir=database.parent) as report_dir:
        row = db.execute('SELECT status,metadata_json FROM capture').fetchall()
        if len(row) != 1 or row[0][0] != 'COMPLETE':
            raise ValueError('Capture is not complete')
        info = json.loads(row[0][1])
        if not info['config']['preflight_verified']:
            raise ValueError('Unverified date interpretation; cannot order timestamps')
        bound, bound_note = effective_bound(info['before'], info['after'], info['config']['watermark_timezone'])
        params = {'start': start_utc, 'end': end_utc, 'bound': bound}
        db.executescript('''
            CREATE TEMP TABLE source_counts AS SELECT business_key,COUNT(*) n FROM source_rows WHERE business_key IS NOT NULL GROUP BY business_key;
            CREATE UNIQUE INDEX temp.source_counts_key ON source_counts(business_key);
            CREATE TEMP TABLE target_counts AS SELECT business_key,COUNT(*) n FROM target_rows WHERE business_key IS NOT NULL GROUP BY business_key;
            CREATE UNIQUE INDEX temp.target_counts_key ON target_counts(business_key);
        ''')
        query = (HERE / 'compare.sql').read_text()
        db.execute('CREATE TEMP TABLE results AS ' + query, params)
        prefix = [start, end, start_utc, end_utc, 'Europe/Ljubljana']
        prefix_names = ['span_start_input', 'span_end_input', 'span_start_utc', 'span_end_utc', 'report_timezone']
        folder = Path(report_dir)
        # All evidence rows are streamed. No dictionary containing millions of keys.
        with (folder / 'differences.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            cursor = db.execute("SELECT * FROM results WHERE category!='EQUAL' OR target_count>1")
            writer.writerow(prefix_names + [c[0] for c in cursor.description] + ['delta_seconds'])
            for result in cursor:
                delta = None
                if result[3] and result[4]:
                    delta = (datetime.fromisoformat(result[3]) - datetime.fromisoformat(result[4])).total_seconds()
                writer.writerow(prefix + list(result) + [delta])
        # Global anomalies include duplicates OUTSIDE the chosen span and every null key/date.
        with (folder / 'global_anomalies.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(prefix_names + ['side', 'business_key', 'uuid', 'changed_at', 'native_changed_at', 'created_at', 'updated_at', 'same_side_key_count'])
            for result in db.execute('''
                SELECT 'SOURCE',s.business_key,NULL,s.changed_at,s.native_changed_at,NULL,NULL,sc.n
                FROM source_rows s LEFT JOIN source_counts sc ON sc.business_key=s.business_key
                WHERE s.business_key IS NULL OR s.changed_at IS NULL OR sc.n>1
                UNION ALL
                SELECT 'TARGET',t.business_key,t.uuid,t.changed_at,t.native_changed_at,t.created_at,t.updated_at,tc.n
                FROM target_rows t LEFT JOIN target_counts tc ON tc.business_key=t.business_key
                WHERE t.business_key IS NULL OR t.changed_at IS NULL OR tc.n>1
            '''):
                writer.writerow(prefix + list(result))
        # SQLite calls this only on locally stored UTC text, never on native ambiguous values.
        db.create_function('local_day', 1, lambda value: datetime.fromisoformat(value).astimezone(LOCAL).date().isoformat() if value else 'UNKNOWN')
        with (folder / 'daily.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(prefix_names + ['date_basis', 'day', 'category', 'relative_bound', 'distinct_keys', 'target_rows', 'duplicate_keys'])
            for basis, column in [('SOURCE', 'source_date'), ('TARGET', 'target_date')]:
                for result in db.execute(f'''SELECT local_day({column}),category,relative_bound,COUNT(DISTINCT business_key),COUNT(uuid),COUNT(DISTINCT CASE WHEN target_count>1 THEN business_key END)
                                            FROM results GROUP BY local_day({column}),category,relative_bound'''):
                    writer.writerow(prefix + [basis] + list(result))
        tie_path = folder / 'timestamp_ties.csv'
        tie_path.unlink(missing_ok=True)
        if page_size:
            with tie_path.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(prefix_names + ['source_date', 'rows_at_timestamp', 'rows_before_in_report_span', 'hypothetical_page_size', 'straddles_boundary'])
                cumulative = 0
                for value, count in db.execute('SELECT changed_at,COUNT(*) FROM source_rows WHERE changed_at>=? AND changed_at<? GROUP BY changed_at ORDER BY changed_at', (start_utc,end_utc)):
                    if count > 1:
                        writer.writerow(prefix + [value, count, cumulative, page_size, cumulative // page_size != (cumulative + count - 1) // page_size])
                    cumulative += count
        summary = ['# KN reconciliation', '', f'Span: `{start}` to `{end}` (exclusive end), Europe/Ljubljana.',
                   f'UTC: `{start_utc}` to `{end_utc}`.', '', f'Effective lower bound: `{bound}`. {bound_note}.',
                   '', f'Capture intervals: `{json.dumps(info["intervals"])}`.', '',
                   '| Scope | Category | Distinct keys | Target rows |', '|---|---|---:|---:|']
        for scope, category, keys, targets in db.execute('SELECT scope,category,COUNT(DISTINCT business_key),COUNT(uuid) FROM results GROUP BY scope,category ORDER BY scope,category'):
            summary.append(f'| {scope} | {category} | {keys} | {targets} |')
        summary += ['', 'Global inventory:', '']
        for table in ('source_rows', 'target_rows'):
            total, null_keys, null_dates = db.execute(f'SELECT COUNT(*),COUNT(*)-COUNT(business_key),COUNT(*)-COUNT(changed_at) FROM {table}').fetchone()
            duplicates = db.execute(f'SELECT COUNT(*) FROM {table.split("_")[0]}_counts WHERE n>1').fetchone()[0]
            summary.append(f'- {table}: {total:,} rows; {null_keys:,} null keys; {null_dates:,} null dates; {duplicates:,} duplicate keys.')
        summary += ['', 'Source duplicate keys are excluded from classifications and retained in global_anomalies.csv.',
                    'UNKNOWN_DATE is a global cohort, not silently assigned to the requested span.',
                    'Key categories can overlap when different target UUIDs disagree; do not sum distinct-key categories.',
                    'Separate source/target snapshots can race with writes. Same timestamps do not prove equal business payload.',
                    'Target created_at may be overwritten by UPSERT; it is not proof of insertion time.',
                    'BELOW means ordinary unchanged deltas exclude this row. AT is inclusive; ABOVE may simply be pending.',
                    'Current settings do not reconstruct historical runs. Unobserved intervening runs remain possible.',
                    'Timestamp ties use today\'s inventory and this report span, not a verified historical run. Boundary flags are hypothetical, not proof of skipped rows.',
                    'Tie ordinals reset at report start; historical boundaries require the actual run bounds and identical membership, neither established by this report.',
                    f'Page-size assumption: {page_size or "not supplied; no tie report"}.',
                    f'Comparison SQL SHA256: {hashlib.sha256(query.encode()).hexdigest()}.', '']
        (folder / 'summary.md').write_text('\n'.join(summary))
        # Stage first, invalidate old completion marker, publish summary last.
        # An interrupted publication has no summary claiming the mixed set is complete.
        (database.parent / 'summary.md').unlink(missing_ok=True)
        (database.parent / 'timestamp_ties.csv').unlink(missing_ok=True)
        for path in folder.glob('*.csv'):
            path.replace(database.parent / path.name)
        (folder / 'summary.md').replace(database.parent / 'summary.md')
    print(database.parent / 'summary.md')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    export.add_argument('--env', type=Path, default=HERE / '.env')
    export.add_argument('--output', type=Path, default=HERE / 'captures' / datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    compare = commands.add_parser('compare')
    compare.add_argument('database', type=Path)
    compare.add_argument('--start', required=True)
    compare.add_argument('--end', required=True)
    compare.add_argument('--page-size', type=int, help='Optional hypothetical old OFFSET page-boundary analysis')
    args = parser.parse_args()
    if args.command == 'export':
        export_capture(args.env, args.output)
    else:
        compare_capture(args.database, args.start, args.end, args.page_size)
