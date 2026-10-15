"""Read-only full-field audit of an applied non-geometry EV repair run."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from definition import IntegrationDefinition
from source import OracleSource, wall_time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--store', required=True)
parser.add_argument('run_id')
args = parser.parse_args()
RUN = args.run_id
cfg = dotenv_values(ROOT / '.env')
saved = sqlite3.connect(Path(args.store).resolve().as_uri() + '?mode=ro', uri=True)
saved.row_factory = sqlite3.Row
run = dict(saved.execute('SELECT * FROM integration_transfer WHERE id=?', (RUN,)).fetchone())
assert run['applied'], 'Audit requires an applied run'
repaired_count = saved.execute('SELECT count(*) FROM addition_diff WHERE run_id=? AND processed=1', (RUN,)).fetchone()[0]
repaired = saved.execute('SELECT key,date FROM addition_diff WHERE run_id=? AND processed=1 ORDER BY key', (RUN,))
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=20000')
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
report = dict(at=datetime.now(timezone.utc).isoformat(), run=run, cohorts={})
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
    d = IntegrationDefinition.load(metadata, run['integration_id'])
    assert d.geometry is None, 'This diagnostic handles attribute fields, not WKT transforms'
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA'], autocommit=True, row_factory=dict_row) as target:
        types = {r['attname']: r['type'] for r in target.execute('''SELECT attname,
            format_type(atttypid,atttypmod) AS type FROM pg_attribute
            WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped''', (d.table,))}
        report['postgres_types'] = types
        controls = [(r['key'], wall_time(r['date'])) for r in target.execute(sql.SQL('''
            SELECT {} AS key,{} AS date FROM {} TABLESAMPLE SYSTEM (0.1) REPEATABLE (17)
            WHERE created_at IS DISTINCT FROM %s::timestamp LIMIT 100''').format(
                sql.Identifier(d.key['target']), sql.Identifier(d.date['target']), sql.Identifier(d.table)),
                (run['max_date'],))]
        columns = [f['target'] for f in d.fields]
        declarations = sql.SQL(',').join(sql.SQL('{} {}').format(sql.Identifier(c), sql.SQL(types[c])) for c in columns)
        checks = sql.SQL(',').join(sql.SQL('e.{} IS NOT NULL AND e.{} IS DISTINCT FROM t.{} AS {}').format(
            sql.Identifier(c), sql.Identifier(c), sql.Identifier(c), sql.Identifier('m_' + c)) for c in columns)
        nulls = sql.SQL(',').join(sql.SQL('e.{} IS NULL AND t.{} IS NOT NULL AS {}').format(
            sql.Identifier(c), sql.Identifier(c), sql.Identifier('n_' + c)) for c in columns)
        query = sql.SQL('''WITH expected AS (SELECT * FROM jsonb_to_recordset(%s) AS e({}))
            SELECT e.{} AS expected_key,t.id,t.created_by,t.updated_by,t.created_at,t.updated_at,
            {},{},{} FROM expected e LEFT JOIN {} t ON t.{}=e.{}''').format(declarations,
                sql.Identifier(d.key['target']),
                sql.SQL('t.geom IS NOT NULL AS has_geom') if 'geom' in types else sql.SQL('false AS has_geom'),
                checks, nulls, sql.Identifier(d.table), sql.Identifier(d.key['target']), sql.Identifier(d.key['target']))
        with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN']) as oracle:
            oracle.call_timeout = 15000
            source = OracleSource(oracle, d)
            with oracle.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            for name, count in [('repaired', repaired_count), ('older_controls', len(controls))]:
                counts = Counter(); mismatches = Counter(); retained = Counter(); actors = Counter(); versions = Counter()
                examples = []; raw_types = {}
                for start in range(0, count, 1000):
                    entries = [(json.loads(r['key']), r['date']) for r in repaired.fetchmany(1000)] if name == 'repaired' else controls[start:start + 1000]
                    expected_dates = dict(entries)
                    keys = [k for k, _ in entries]
                    payloads = source.fetch_payloads(keys)
                    counts['oracle_missing'] += len(keys) - len(payloads)
                    expected = []
                    for key, payload in payloads.items():
                        values = {}
                        for field in d.fields:
                            value = payload.get(field['api_name'])
                            raw_types[field['target']] = type(value).__name__
                            if value is not None and field['field_type'] in ('datetime', 'date-time'):
                                value = wall_time(value)
                            values[field['target']] = value
                        if values[d.date['target']] != expected_dates[key]:
                            counts['source_changed_since_snapshot'] += 1
                            continue
                        expected.append(values)
                    seen = set()
                    for row in target.execute(query, (Jsonb(expected),)):
                        counts['duplicate_target_rows'] += row['expected_key'] in seen
                        seen.add(row['expected_key'])
                        counts['compared'] += 1
                        if row['id'] is None:
                            counts['target_missing'] += 1
                            continue
                        actors[(str(row['created_by']), str(row['updated_by']))] += 1
                        versions[row['id'].version] += 1
                        counts['has_geom'] += row['has_geom']
                        counts['created_updated_equal'] += row['created_at'] == row['updated_at']
                        counts['metadata_matches_run'] += (wall_time(row['created_at']) == run['max_date']
                            and wall_time(row['updated_at']) == run['max_date']
                            and str(row['created_by']) == run['user_id'] and str(row['updated_by']) == run['user_id'])
                        bad = [c for c in columns if row['m_' + c]]
                        counts['rows_with_mismatches'] += bool(bad)
                        mismatches.update(bad)
                        retained.update(c for c in columns if row['n_' + c])
                        if bad and len(examples) < 5:
                            examples.append(dict(key=row['expected_key'], fields=bad))
                    if name == 'repaired' and (start + len(entries)) % 100000 == 0:
                        print(f'{d.table}: checked {start + len(entries):,} repaired keys', flush=True)
                report['cohorts'][name] = dict(requested=count, counts=dict(counts),
                    mismatched_fields=dict(mismatches), nonnull_target_when_source_null=dict(retained),
                    actors=[dict(created_by=k[0], updated_by=k[1], count=v) for k, v in actors.items()],
                    uuid_versions=dict(versions), oracle_python_types=raw_types, mismatch_examples=examples)
                (ROOT / f'diagnostics/{d.table}_value_audit.json').write_text(json.dumps(report, indent=2) + '\n')
                print(name, json.dumps(report['cohorts'][name]), flush=True)
            oracle.rollback()

saved.close()
