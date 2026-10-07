"""Full key/date inventories for the 16 named integrations; STAGING ONLY."""
import argparse
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from dotenv import dotenv_values
import psycopg
from psycopg import sql
from reconcile import HERE, SCHEMA, utc_text

TABLES = [
    'kn_nep_hisne_stevilke_h', 'kn_nep_etaze_h', 'kn_nep_prostori_h', 'kn_nep_deli_stavb_h',
    'ev_posebna_enota_h', 'ev_pe_parc_h', 'ev_pe_dst_h',
    'ev_dst_pripis_podatki_h', 'ev_del_stavbe_enota_h_2025_danes',
    'ev_parc_pripis_podatki_h', 'ev_del_stavbe_h', 'ev_parc_del_h',
    'ev_prostor_h', 'ev_stavba_h', 'ev_parc_enota_h_2025_danes', 'ev_parcela_h',
]
METADATA = (HERE / 'metadata.sql').read_text().split('WHERE i.id =')[0].replace('i.is_full_sync,', 'i.is_full_sync, i.integration_type,')
UTC = timezone.utc


def metadata(connection, table):
    cursor = connection.execute(METADATA + 'WHERE t.name = %s', (table,))
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise ValueError(f'{table}: expected exactly one integration, found {len(rows)}')
    return dict(zip([column.name for column in cursor.description], rows[0]))


def capture(folder, table, phase, env, baseline=None):
    pg = dict(host=env['STAG_HOST'], port=env['STAG_PORT'], user=env['STAG_USER'],
              password=env['STAG_PASSWORD'], connect_timeout=10,
              options='-c default_transaction_read_only=on -c statement_timeout=120000')
    output = folder / table
    output.mkdir(parents=True, exist_ok=True)
    partial = output / 'capture.partial.sqlite3'
    if (output / 'capture.sqlite3').exists():
        print(table, 'already COMPLETE', flush=True)
        return
    with psycopg.connect(**pg, dbname=env.get('STAG_METADATA_DATABASE', 'fmp'), autocommit=True) as meta:
        meta.execute("SET TIME ZONE 'UTC'")
        live = metadata(meta, table)
        if live['integration_type'] != 'sql':
            raise ValueError('Expected SQL integration')
        keys = [m for m in live['mappings'] if m['api_id'] and not m['api_block_sync']]
        dates = [m for m in live['mappings'] if m['api_last_sync_field'] and not m['api_block_sync']]
        if len(keys) != 1 or len(dates) != 1:
            raise ValueError('Expected one business-key mapping and one delta-date mapping')
        key, date = keys[0], dates[0]
        for value in [key['api_name'], key['target_field'], date['api_name'], date['target_field']]:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', value):
                raise ValueError('Unexpected mapped identifier')
        source_sql = f'''SELECT CAST(x."{key['api_name'].upper()}" AS VARCHAR2(4000)) AS business_key,
          TO_CHAR(SYS_EXTRACT_UTC(x."{date['api_name'].upper()}"), 'YYYY-MM-DD"T"HH24:MI:SS.FF6"Z"') AS changed_at,
          TO_CHAR(x."{date['api_name'].upper()}", 'YYYY-MM-DD"T"HH24:MI:SS.FF6') AS native_changed_at
          FROM ({live['url'].strip().rstrip(';')}) x'''
        with closing(sqlite3.connect(partial, uri=True)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='capture'").fetchone():
                db.executescript(SCHEMA)
                info = dict(environment='staging', target_table=table, before=live,
                            config=dict(preflight_verified=False, target_timezone='Europe/Ljubljana', watermark_timezone=''),
                            sql=dict(source=source_sql, integration=live['url']), intervals={}, counts={},
                            sql_sha256=hashlib.sha256(live['url'].encode()).hexdigest())
                db.execute('INSERT INTO capture VALUES (?,?)', ('PARTIAL', json.dumps(info)))
                db.commit()
            info = json.loads(db.execute('SELECT metadata_json FROM capture').fetchone()[0])
            if live['url'] != info['before']['url'] or live['mappings'] != info['before']['mappings']:
                raise ValueError('SQL/mappings changed since this capture started; use a new folder')
            (output / 'source.sql').write_text(source_sql + '\n')
            if phase == 'target' and 'target' not in info['counts']:
                info['intervals']['target_start'] = datetime.now(UTC).isoformat()
                with psycopg.connect(**pg, dbname=env.get('STAG_DATABASE', 'fmp_data_gurs')) as target:
                    target.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                    target.execute("SET LOCAL TIME ZONE 'UTC'")
                    info['target_identity'] = target.execute('SELECT current_database(),inet_server_addr()::text').fetchone()
                    columns = dict(target.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,)).fetchall())
                    if columns.get(date['target_field']) != 'timestamp without time zone':
                        raise ValueError('This experiment expects a timezone-less target change field')
                    query = sql.SQL('SELECT id::text, {}::text, to_char({}, \'YYYY-MM-DD"T"HH24:MI:SS.US\'), created_at::text, updated_at::text FROM public.{}').format(
                        sql.Identifier(key['target_field']), sql.Identifier(date['target_field']), sql.Identifier(table))
                    info['sql']['target'] = query.as_string(target)
                    (output / 'target.sql').write_text(info['sql']['target'] + '\n')
                    db.execute('DELETE FROM target_rows')
                    count = 0
                    with target.cursor(name='staging_inventory') as cursor:
                        cursor.execute(query)
                        while rows := cursor.fetchmany(10000):
                            db.executemany('INSERT INTO target_rows VALUES (?,?,?,?,?,?)',
                                ((uid, k, utc_text(native, 'Europe/Ljubljana') if native else None, native, created, updated)
                                 for uid, k, native, created, updated in rows))
                            count += len(rows)
                            if count % 250000 == 0:
                                print(table, 'STAGING', f'{count:,}', flush=True)
                    db.execute('CREATE INDEX IF NOT EXISTS target_key ON target_rows(business_key)')
                    info['counts']['target'] = count
                info['intervals']['target_end'] = datetime.now(UTC).isoformat()
                info['target_metadata_after'] = metadata(meta, table)
                db.execute('UPDATE capture SET metadata_json=?', (json.dumps(info),))
                db.commit()
                print(table, 'STAGING done', f'{count:,}', flush=True)
            if phase == 'reuse-source' and 'source' not in info['counts']:
                if 'target' not in info['counts']:
                    raise ValueError('Export target first')
                previous = baseline / table / 'capture.sqlite3'
                db.execute('ATTACH DATABASE ? AS baseline', (previous.resolve().as_uri() + '?mode=ro',))
                old_status, old_raw = db.execute('SELECT status,metadata_json FROM baseline.capture').fetchone()
                old = json.loads(old_raw)
                if old_status != 'COMPLETE' or old['environment'] != 'staging':
                    raise ValueError('Expected a complete staging baseline')
                if old['before']['url'] != live['url'] or old['before']['mappings'] != live['mappings']:
                    raise ValueError('SQL/mappings changed: cannot reuse the Oracle inventory')
                db.execute('DELETE FROM source_rows')
                db.execute('INSERT INTO source_rows SELECT * FROM baseline.source_rows')
                db.execute('CREATE INDEX IF NOT EXISTS source_key ON source_rows(business_key)')
                info['counts']['source'] = old['counts']['source']
                info['source_reused_from'] = str(previous.resolve())
                info['oracle_identity'] = old['oracle_identity']
                for name in ['source_start', 'source_end']:
                    info['intervals'][name] = old['intervals'][name]
            if phase == 'source' and 'source' not in info['counts']:
                if 'target' not in info['counts']:
                    raise ValueError('Export target first')
                import oracledb
                info['intervals']['source_start'] = datetime.now(UTC).isoformat()
                with oracledb.connect(user=env['KN_ORACLE_USER'], password=env['KN_ORACLE_PASSWORD'],
                                      dsn=env['KN_ORACLE_DSN'], tcp_connect_timeout=8) as oracle:
                    oracle.call_timeout = 120000
                    with oracle.cursor() as cursor:
                        cursor.execute('ALTER SESSION SET ERROR_ON_OVERLAP_TIME = TRUE')
                        cursor.execute("ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'")
                        cursor.execute('SET TRANSACTION READ ONLY')
                        cursor.execute("SELECT SYS_CONTEXT('USERENV','SERVICE_NAME') FROM dual")
                        info['oracle_identity'] = cursor.fetchone()
                        cursor.arraysize = 10000
                        cursor.execute(source_sql)
                        db.execute('DELETE FROM source_rows')
                        count = 0
                        while rows := cursor.fetchmany(10000):
                            db.executemany('INSERT INTO source_rows VALUES (?,?,?)', rows)
                            count += len(rows)
                            if count % 250000 == 0:
                                print(table, 'ORACLE', f'{count:,}', flush=True)
                        info['counts']['source'] = count
                    oracle.rollback()
                db.execute('CREATE INDEX IF NOT EXISTS source_key ON source_rows(business_key)')
                info['intervals']['source_end'] = datetime.now(UTC).isoformat()
            if phase in ('source', 'reuse-source') and 'source' in info['counts']:
                info['after'] = metadata(meta, table)
                # Establish wall-time convention with matching source/target controls.
                controls = db.execute('SELECT s.native_changed_at,t.native_changed_at,s.changed_at=t.changed_at FROM source_rows s JOIN target_rows t USING(business_key) WHERE s.changed_at IS NOT NULL AND t.changed_at IS NOT NULL LIMIT 100').fetchall()
                info['datetime_controls'] = controls
                info['config']['preflight_verified'] = any(row[2] for row in controls)
                if not info['config']['preflight_verified']:
                    raise ValueError('No matching timezone controls; review target datetime interpretation')
                db.execute('UPDATE capture SET status=?,metadata_json=?', ('COMPLETE', json.dumps(info)))
                db.commit()
                print(table, 'ORACLE done' if phase == 'source' else 'BASELINE source reused',
                      f"{info['counts']['source']:,}", flush=True)
        if phase in ('source', 'reuse-source') and 'source' in info['counts']:
            partial.rename(output / 'capture.sqlite3')


def report(folder, table):
    output = folder / table
    path = output / 'capture.sqlite3'
    if not path.exists():
        return dict(table=table, status='INCOMPLETE')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        status, raw = db.execute('SELECT status,metadata_json FROM capture').fetchone()
        info = json.loads(raw)
        if status != 'COMPLETE':
            raise ValueError('Incomplete inventory')
        result = dict(table=table, status='COMPLETE', **info['counts'])
        result['source_reused_from'] = info.get('source_reused_from')
        result['snapshot_intervals'] = info.get('intervals', {})
        result['last_sync_end'] = info['after']['last_sync_end']
        result['integration_status'] = info['after']['processing_status']
        result['watermark'] = info['after']['last_changed_datetime']
        result['metadata_stable'] = info['before'] == info['target_metadata_after'] == info['after']
        for side in ['source', 'target']:
            result[side + '_duplicate_keys'] = db.execute(f'SELECT COUNT(*) FROM (SELECT business_key FROM {side}_rows GROUP BY business_key HAVING COUNT(*)>1)').fetchone()[0]
            result[side + '_null_dates'] = db.execute(f'SELECT COUNT(*) FROM {side}_rows WHERE changed_at IS NULL').fetchone()[0]
        missing = '''SELECT s.* FROM source_rows s WHERE s.business_key IS NOT NULL
                     AND NOT EXISTS(SELECT 1 FROM target_rows t WHERE t.business_key=s.business_key)'''
        db.execute('CREATE TEMP TABLE missing AS ' + missing)
        result['missing_keys'] = db.execute('SELECT COUNT(DISTINCT business_key) FROM missing').fetchone()[0]
        watermark = result['watermark']
        correct = utc_text(watermark, 'Europe/Ljubljana') if watermark else None
        shifted = utc_text(watermark, 'UTC') if watermark else None
        result['missing_at_or_before_watermark'] = db.execute('SELECT COUNT(DISTINCT business_key) FROM missing WHERE changed_at<=?', (correct,)).fetchone()[0]
        result['missing_after_watermark'] = db.execute('SELECT COUNT(DISTINCT business_key) FROM missing WHERE changed_at>?', (correct,)).fetchone()[0]
        result['missing_in_next_shifted_window'] = db.execute('SELECT COUNT(DISTINCT business_key) FROM missing WHERE changed_at>=? AND changed_at<?', (correct, shifted)).fetchone()[0]
        result['stale_keys'] = db.execute('SELECT COUNT(DISTINCT s.business_key) FROM source_rows s JOIN target_rows t USING(business_key) WHERE s.changed_at>t.changed_at').fetchone()[0]
        result['stale_at_or_before_watermark'] = db.execute('SELECT COUNT(DISTINCT s.business_key) FROM source_rows s JOIN target_rows t USING(business_key) WHERE s.changed_at>t.changed_at AND s.changed_at<=?', (correct,)).fetchone()[0]
        result['target_only_keys'] = db.execute('SELECT COUNT(DISTINCT t.business_key) FROM target_rows t WHERE NOT EXISTS(SELECT 1 FROM source_rows s WHERE s.business_key=t.business_key)').fetchone()[0]
        with (output / 'missing.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['business_key', 'changed_at_utc', 'changed_at_ljubljana'])
            writer.writerows(db.execute('SELECT * FROM missing ORDER BY changed_at,business_key'))
        with (output / 'missing_days.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['day_ljubljana', 'missing_keys', 'earliest', 'latest'])
            writer.writerows(db.execute('SELECT substr(native_changed_at,1,10), COUNT(DISTINCT business_key), MIN(native_changed_at),MAX(native_changed_at) FROM missing GROUP BY 1 ORDER BY 1'))
        # Audit cohort maxima are clues to old outgoing watermarks, not immutable logs.
        # Current FMP overwrites created_at on UPSERT; later repairs can change dates.
        db.execute('CREATE INDEX temp.missing_date ON missing(changed_at)')
        db.execute('CREATE TEMP TABLE window_candidates (business_key TEXT, run_stamp TEXT, inferred_watermark TEXT)')
        windows = []
        if result['missing_at_or_before_watermark']:
            cohorts = db.execute("SELECT created_at,MAX(native_changed_at) FROM target_rows WHERE created_at >= '2025-01-01' AND native_changed_at IS NOT NULL GROUP BY created_at").fetchall()
            for run, maximum in cohorts:
                start = utc_text(maximum, 'Europe/Ljubljana')
                end = utc_text(maximum, 'UTC')
                # Keep only plausible run cohorts: imported max cannot exceed run upper bound.
                if start > utc_text(run, 'UTC'):
                    continue
                hits = db.execute('SELECT business_key,native_changed_at FROM missing WHERE changed_at>=? AND changed_at<? AND changed_at<=?', (start,end,correct)).fetchall()
                if hits:
                    windows.append([run, maximum, start, end, len({row[0] for row in hits}), min(row[1] for row in hits), max(row[1] for row in hits)])
                    db.executemany('INSERT INTO window_candidates VALUES (?,?,?)', ((key,run,maximum) for key,_ in hits))
        result['historical_missing_in_inferred_windows'] = db.execute('SELECT COUNT(DISTINCT business_key) FROM window_candidates').fetchone()[0]
        with (output / 'inferred_windows.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['target_created_at_assumed_utc', 'inferred_max_ljubljana', 'correct_bound_utc', 'shifted_bound_utc', 'historical_missing_keys', 'earliest_missing_ljubljana', 'latest_missing_ljubljana'])
            writer.writerows(windows)
        with (output / 'missing_window_candidates.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['business_key', 'run_stamp', 'inferred_watermark'])
            writer.writerows(db.execute('SELECT * FROM window_candidates ORDER BY business_key,run_stamp'))
        (output / 'summary.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['target', 'source', 'reuse-source', 'report'])
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, help='Existing capture folder for reuse-source only')
    parser.add_argument('--tables', nargs='+', choices=TABLES, default=TABLES)
    args = parser.parse_args()
    if args.phase == 'reuse-source' and args.baseline is None:
        parser.error('reuse-source requires --baseline')
    env = dotenv_values(HERE / '.env')
    if args.phase == 'source':
        import oracledb
        oracledb.init_oracle_client(lib_dir=env['KN_ORACLE_CLIENT_LIB_DIR'])
    summaries = []
    failed = False
    for table in args.tables:
        try:
            if args.phase == 'report':
                result = report(args.folder, table)
                summaries.append(result)
                failed |= result['status'] != 'COMPLETE'
            else:
                capture(args.folder, table, args.phase, env, args.baseline)
        except Exception as error:
            failed = True
            print(table, 'FAILED', type(error).__name__, str(error).splitlines()[0][:180], flush=True)
            summaries.append(dict(table=table, status='FAILED', error_type=type(error).__name__))
    if args.phase == 'report':
        saved = {table: json.loads((args.folder / table / 'summary.json').read_text())
                 for table in TABLES if (args.folder / table / 'summary.json').exists()}
        saved.update({result['table']: result for result in summaries})
        (args.folder / 'summaries.json').write_text(json.dumps(
            [saved[table] for table in TABLES if table in saved], indent=2))
    if failed:
        raise SystemExit(1)
