"""Read-only field audit of the applied EV parcela run and older control rows."""
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
RUN = '03ff3376-0110-4c42-a617-07662100d1bf'
cfg = dotenv_values(ROOT / '.env')
with sqlite3.connect((ROOT / 'full-ev-parcela.sqlite').as_uri() + '?mode=ro', uri=True) as saved:
    saved.row_factory = sqlite3.Row
    run = dict(saved.execute('SELECT * FROM integration_transfer WHERE id=?', (RUN,)).fetchone())
    repaired = [(json.loads(r['key']), r['date']) for r in saved.execute(
        'SELECT key,date FROM addition_diff WHERE run_id=? AND processed=1 ORDER BY key', (RUN,))]
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=20000')
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
report = dict(at=datetime.now(timezone.utc).isoformat(), run=run, cohorts={})
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
    d = IntegrationDefinition.load(metadata, run['integration_id'])
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA'], autocommit=True, row_factory=dict_row) as target:
        types = {r['attname']: r['type'] for r in target.execute('''SELECT attname,
            format_type(atttypid,atttypmod) AS type FROM pg_attribute
            WHERE attrelid='ev_parcela_h'::regclass AND attnum>0 AND NOT attisdropped''')}
        report['postgres_types'] = types
        controls = [(r['jn_parcela_pk'], wall_time(r['date_change'])) for r in target.execute('''
            SELECT jn_parcela_pk,date_change FROM ev_parcela_h TABLESAMPLE SYSTEM (0.02) REPEATABLE (17)
            WHERE created_at IS DISTINCT FROM %s::timestamp LIMIT 100''', (run['max_date'],))]
        columns = [f['target'] for f in d.fields]
        declarations = sql.SQL(',').join(sql.SQL('{} {}').format(sql.Identifier(c), sql.SQL(types[c])) for c in columns)
        checks = sql.SQL(',').join(sql.SQL('e.{} IS NOT NULL AND e.{} IS DISTINCT FROM t.{} AS {}').format(
            sql.Identifier(c), sql.Identifier(c), sql.Identifier(c), sql.Identifier('m_' + c)) for c in columns)
        nulls = sql.SQL(',').join(sql.SQL('e.{} IS NULL AND t.{} IS NOT NULL AS {}').format(
            sql.Identifier(c), sql.Identifier(c), sql.Identifier('n_' + c)) for c in columns)
        query = sql.SQL('''WITH expected AS (SELECT * FROM jsonb_to_recordset(%s) AS e({}))
            SELECT e.jn_parcela_pk AS expected_key,t.id,t.created_by,t.updated_by,t.created_at,t.updated_at,
            t.date_change,t.geom IS NOT NULL AS has_geom,{},{} FROM expected e
            LEFT JOIN ev_parcela_h t ON t.jn_parcela_pk=e.jn_parcela_pk''').format(declarations, checks, nulls)
        with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN']) as oracle:
            oracle.call_timeout = 15000
            source = OracleSource(oracle, d)
            with oracle.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            for name, entries in [('repaired', repaired), ('older_controls', controls)]:
                counts = Counter(); mismatches = Counter(); retained = Counter(); actors = Counter(); versions = Counter()
                examples = []; raw_types = {}; expected_dates = dict(entries)
                for start in range(0, len(entries), 1000):
                    keys = [k for k, _ in entries[start:start + 1000]]
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
                    for row in target.execute(query, (Jsonb(expected),)):
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
                report['cohorts'][name] = dict(requested=len(entries), counts=dict(counts),
                    mismatched_fields=dict(mismatches), nonnull_target_when_source_null=dict(retained),
                    actors=[dict(created_by=k[0], updated_by=k[1], count=v) for k, v in actors.items()],
                    uuid_versions=dict(versions), oracle_python_types=raw_types, mismatch_examples=examples)
                (ROOT / 'diagnostics/ev_parcela_value_audit.json').write_text(json.dumps(report, indent=2) + '\n')
                print(name, json.dumps(report['cohorts'][name]), flush=True)
            oracle.rollback()
