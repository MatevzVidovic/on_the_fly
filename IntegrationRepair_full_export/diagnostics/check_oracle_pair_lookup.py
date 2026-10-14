"""Read-only comparison of EV parcela payload predicates; no repair writes."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import oracledb
import psycopg
from definition import IntegrationDefinition
from source import OracleSource

ROOT = Path(__file__).resolve().parents[1]
RUN = '8190f417-bbd3-41f3-b727-b00b4d3065e4'
cfg = dotenv_values(ROOT / '.env')
with sqlite3.connect((ROOT / 'full-ev-parcela.sqlite').as_uri() + '?mode=ro', uri=True) as db:
    keys = [json.loads(row[0]) for row in db.execute(
        'SELECT key FROM addition_diff WHERE run_id=? AND processed=0 LIMIT 1000', (RUN,))]
with psycopg.connect(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'],
                      password=cfg['PG_PASSWORD'], dbname=cfg['PG_DATABASE_SYSTEM'],
                      connect_timeout=5, options='-c default_transaction_read_only=on -c statement_timeout=10000') as db:
    definition = IntegrationDefinition.load(db, 'c469d91a-ae56-11f0-84be-169cd02558fe')
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
report = dict(recorded_at=datetime.now(timezone.utc).isoformat(), run_id=RUN, key_count=len(keys),
              previous_apply_seconds=528.97, previous_apply_processed=0, results={})
rows_by_method = {}
with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN']) as db:
    source = OracleSource(db, definition)
    db.call_timeout = 15000
    with db.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
    methods = ('numeric_pair', 'computed_string') if '--include-computed' in sys.argv else ('numeric_pair',)
    for method in methods:
        binds, predicates = {}, []
        for i, key in enumerate(keys):
            if method == 'numeric_pair':
                mid, revision = key.split('-')
                binds[f'm{i}'], binds[f'r{i}'] = int(mid), int(revision)
                predicates.append(f'(:m{i},:r{i})')
            else:
                binds[f'k{i}'] = key
                predicates.append(f':k{i}')
        field = '(PC_MID, JN_REV_NUM)' if method == 'numeric_pair' else '"JN_PARCELA_PK"'
        query = f'SELECT /* repair_pair_probe_{method} */ * FROM ({definition.query}) WHERE {field} IN ({",".join(predicates)})'
        started = perf_counter()
        try:
            with db.cursor() as cur:
                cur.arraysize = 1000
                cur.execute(query, binds)
                rows = cur.fetchall()
            rows_by_method[method] = {row[0]: row for row in rows}
            result = dict(seconds=round(perf_counter()-started, 3), rows=len(rows),
                          requested_keys_match=set(rows_by_method[method]) == set(keys))
        except (oracledb.DatabaseError, oracledb.InterfaceError) as error:
            result = dict(seconds=round(perf_counter()-started, 3), error=str(error))
        print(method, json.dumps(result), flush=True)
        report['results'][method] = result
        (ROOT / 'diagnostics/oracle_pair_lookup.json').write_text(json.dumps(report, indent=2) + '\n')
        if 'error' in result:
            break
        try:
            with db.cursor() as cur:
                cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL,NULL,'BASIC +PREDICATE'))")
                result['plan'] = [row[0] for row in cur]
            print('plan', '\n'.join(result['plan']), flush=True)
        except (oracledb.DatabaseError, oracledb.InterfaceError) as error:
            result['plan_error'] = str(error)
    if len(rows_by_method) == 2:
        report['payloads_identical'] = rows_by_method['numeric_pair'] == rows_by_method['computed_string']
    if db.is_healthy():
        db.rollback()
(ROOT / 'diagnostics/oracle_pair_lookup.json').write_text(json.dumps(report, indent=2) + '\n')
