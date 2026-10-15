"""Read-only verification of every prepared del-stavbe-enota removal."""
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
from definition import IntegrationDefinition
from source import OracleSource, wall_time

ROOT = Path(__file__).resolve().parents[1]
RUN = '676a2dc7-00cb-4da1-85ae-6a2a8b19d121'
cfg = dotenv_values(ROOT / '.env')
with sqlite3.connect((ROOT / 'full-ev-del-stavbe-enota.sqlite').as_uri() + '?mode=ro', uri=True) as saved:
    saved.row_factory = sqlite3.Row
    run = dict(saved.execute('SELECT * FROM integration_transfer WHERE id=?', (RUN,)).fetchone())
    removals = [dict(r) for r in saved.execute('SELECT * FROM removal_diff WHERE run_id=?', (RUN,))]
    additions = [dict(r) for r in saved.execute('SELECT * FROM addition_diff WHERE run_id=?', (RUN,))]
    in_export = saved.execute('''SELECT count(*) FROM removal_diff d
        JOIN remote_ids_and_date_changed s ON s.run_id=d.run_id AND s.key=d.key
        WHERE d.run_id=?''', (RUN,)).fetchone()[0]
report = dict(at=datetime.now(timezone.utc).isoformat(), run=run, candidates=len(removals),
              removal_keys_present_in_saved_export=in_export, counts={}, examples=[], target_statuses={})
counts = Counter(); statuses = Counter(); reasons = Counter(); target_statuses = Counter()
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=15000')
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
    d = IntegrationDefinition.load(metadata, run['integration_id'])
    report['saved_query'] = d.query
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA'], autocommit=True, row_factory=dict_row) as target:
        report['referencing_foreign_keys'] = [dict(r) for r in target.execute('''
            SELECT conrelid::regclass::text AS referencing_table,conname,pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE contype='f' AND confrelid=%s::regclass''', (d.table,))]
        report['user_triggers'] = [dict(r) for r in target.execute('''
            SELECT tgname,pg_get_triggerdef(oid) AS definition FROM pg_trigger
            WHERE tgrelid=%s::regclass AND NOT tgisinternal''', (d.table,))]
        with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN']) as oracle:
            oracle.call_timeout = 15000
            source = OracleSource(oracle, d)
            with oracle.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            for start in range(0, len(removals), 1000):
                batch = removals[start:start+1000]
                keys = [json.loads(r['key']) for r in batch]
                membership = source.fetch_payloads(keys)
                counts['present_in_current_integration_result'] += len(membership)
                binds = {}; tuples = []
                for i, key in enumerate(keys):
                    a, b = key.rsplit('-', 1)
                    binds[f'a{i}'], binds[f'b{i}'] = int(a), int(b)
                    tuples.append(f'(:a{i},:b{i})')
                with oracle.cursor() as cur:
                    cur.arraysize = 1000
                    cur.execute('''SELECT TO_CHAR(j.DST_SID)||'-'||TO_CHAR(j.JN_REV_NUM),j.JN_STATUS,
                        rf.CREATED,rt.CREATED,
                        CASE WHEN j.JN_STATUS <> 'X' THEN 1 ELSE 0 END,
                        CASE WHEN rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00' THEN 1 ELSE 0 END
                        FROM EV.JN_DEL_STAVBE_ENOTA j
                        LEFT JOIN EV.REVISION rf ON rf.REV_NUM=j.JN_REV_NUM
                        LEFT JOIN EV.REVISION rt ON rt.REV_NUM=j.JN_REV_NUM_TO
                        WHERE (j.DST_SID,j.JN_REV_NUM) IN (''' + ','.join(tuples) + ')', binds)
                    raw = {r[0]: r[1:] for r in cur}
                counts['absent_from_raw_oracle_table'] += len(keys) - len(raw)
                for key in keys:
                    if key not in raw:
                        reasons['raw_row_missing'] += 1
                        continue
                    status, valid_from, valid_to, status_ok, date_ok = raw[key]
                    statuses[str(status)] += 1
                    if status == 'X':
                        reasons['excluded_by_status_X'] += 1
                    elif not int(status_ok):
                        reasons['excluded_by_null_status'] += 1
                    elif valid_from is None:
                        reasons['missing_from_revision'] += 1
                    elif not int(date_ok):
                        reasons['from_revision_before_2025'] += 1
                    else:
                        reasons['unexpected_exclusion'] += 1
                    if len(report['examples']) < 5:
                        report['examples'].append(dict(key=key,oracle_status=status,valid_from=valid_from,valid_to=valid_to))
                current = {str(r['id']): r for r in target.execute(sql.SQL('''SELECT id,{} AS key,
                    {} AS date,jn_status FROM {} WHERE id=ANY(%s::uuid[])''').format(
                        sql.Identifier(d.key['target']), sql.Identifier(d.date['target']), sql.Identifier(d.table)),
                    ([r['target_id'] for r in batch],))}
                counts['target_rows_missing'] += len(batch) - len(current)
                for planned in batch:
                    row = current.get(planned['target_id'])
                    if row is None:
                        continue
                    target_statuses[str(row['jn_status'])] += 1
                    counts['target_key_changed'] += row['key'] != json.loads(planned['key'])
                    counts['target_date_changed'] += wall_time(row['date']) != planned['date']
                    counts['target_date_above_cutoff'] += wall_time(row['date']) > run['cutoff']
                    counts['target_rows_checked'] += 1
                print(f'Checked {start+len(batch):,}/{len(removals):,} removal candidates', flush=True)
            payloads = source.fetch_payloads([json.loads(r['key']) for r in additions])
            report['upserts'] = dict(count=len(additions), source_missing=len(additions)-len(payloads),
                source_date_changed=sum(wall_time(payloads[json.loads(r['key'])][d.date['api_name']]) != r['date']
                    for r in additions if json.loads(r['key']) in payloads))
            oracle.rollback()
report['counts'] = dict(counts)
report['oracle_statuses'] = dict(statuses)
report['exclusion_reasons'] = dict(reasons)
report['target_statuses'] = dict(target_statuses)
report['consistent_with_deletion_plan'] = (in_export == 0 and counts['present_in_current_integration_result'] == 0
    and counts['target_rows_checked'] == len(removals) and counts['target_key_changed'] == 0
    and counts['target_date_changed'] == 0 and counts['target_date_above_cutoff'] == 0
    and reasons['unexpected_exclusion'] == 0)
(ROOT / 'diagnostics/enota_removal_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('saved_query','run')}, indent=2), flush=True)
