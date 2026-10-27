"""Bounded read-only key audit; three payloads per composite integration."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import oracledb
import psycopg
from definition import IntegrationDefinition, EXCLUDED_TABLES
from source import OracleSource

ROOT = Path(__file__).resolve().parents[1]
cfg = dotenv_values(ROOT / '.env')
queries = json.loads((ROOT / 'diagnostics/current_key_queries.json').read_text())
report = {'at': datetime.now(timezone.utc).isoformat(), 'sample_size': 3, 'tables': []}
path = ROOT / 'diagnostics/oracle_key_coverage.json'
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
with psycopg.connect(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'],
                     password=cfg['PG_PASSWORD'], dbname=cfg['PG_DATABASE_SYSTEM'],
                     connect_timeout=5, autocommit=True,
                     options='-c default_transaction_read_only=on -c statement_timeout=10000') as metadata:
    with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
                          dsn=cfg['KN_ORACLE_DSN']) as db:
        db.call_timeout = 10000
        for row in queries:
            if row['name'] in EXCLUDED_TABLES or row['is_full_sync'] or row['connection_name'] != 'KN ORACLE':
                continue
            result = {'table': row['name'], 'integration_id': row['id']}
            started = perf_counter()
            try:
                definition = IntegrationDefinition.load(metadata, row['id'])
                source = OracleSource(db, definition)
                with db.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
                    owner, table = re.search(r'\bFROM\s+(\w+)\.(\w+)', definition.query, re.I).groups()
                    cur.execute('''SELECT cc.column_name FROM all_constraints c
                        JOIN all_cons_columns cc ON cc.owner=c.owner AND cc.constraint_name=c.constraint_name
                        WHERE c.owner=:owner AND c.table_name=:tab AND c.constraint_type='P'
                        ORDER BY cc.position''', owner=owner.upper(), tab=table.upper())
                    result['primary_key'] = [r[0] for r in cur]
                    result['mode'] = 'composite' if definition.oracle_key else 'direct'
                    result['key_output'] = definition.key['api_name']
                    if definition.oracle_key:
                        cur.execute(f'SELECT * FROM ({definition.query}) WHERE ROWNUM <= 3')
                        names = [c[0] for c in cur.description]
                        samples = []
                        for values in cur:
                            samples.append(dict(zip(names, (v.read() if isinstance(v, oracledb.LOB) else v
                                                            for v in values))))
                    else:
                        cur.execute(f'SELECT {source.key} FROM ({definition.query}) WHERE 1=0')
                        result['oracle_type'] = cur.description[0][1].name
                        samples = []
                if definition.oracle_key:
                    keys = [definition.key_value(r[definition.key['api_name']]) for r in samples]
                    fetch_started = perf_counter()
                    actual = source.fetch_payloads(keys)
                    result['fetch_seconds'] = round(perf_counter() - fetch_started, 6)
                    result['sample_keys'] = keys
                    assert set(actual) == set(keys), 'Requested keys differ'
                    for sample, key in zip(samples, keys):
                        assert {name: actual[key][name] for name in sample} == sample, 'Payload values differ'
                    result['payloads_equal'] = True
                result['status'] = 'checked'
            except Exception as error:
                result['status'] = 'failed'
                result['error'] = f'{type(error).__name__}: {error}'
            finally:
                db.rollback()
            result['seconds'] = round(perf_counter() - started, 6)
            report['tables'].append(result)
            path.write_text(json.dumps(report, indent=2) + '\n')
            print(result['table'], result['status'], result.get('mode'), result['seconds'],
                  result.get('error', ''), flush=True)
