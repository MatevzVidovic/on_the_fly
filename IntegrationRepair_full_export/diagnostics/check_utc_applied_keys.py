"""Read-only point checks of applied UTC diff keys and small post-cutoff samples."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import sqlite3
from datetime import datetime, timezone
from dotenv import dotenv_values
import psycopg
from psycopg import sql
from check_ev_utc_diffs import EV_RUNS, KN_RUNS
from definition import IntegrationDefinition, check_run_definition
from source import utc_time
from store import classify

cfg = dotenv_values('.env')
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=20000')
report = dict(at=datetime.now(timezone.utc).isoformat(), tables=[], post_cutoff_samples=[])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata, \
     psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA'], autocommit=True) as target:
    for file, run_id in EV_RUNS + KN_RUNS:
        with sqlite3.connect(Path(file).resolve().as_uri()+'?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            run = db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
            definition = IntegrationDefinition.load(metadata, run['integration_id'])
            check_run_definition(run, definition)
            entries = db.execute('SELECT key,date,processed,warning FROM addition_diff WHERE run_id=?', (run_id,)).fetchall()
            result = dict(table=definition.table, run_id=run_id, applied=bool(run['applied']), checked=0,
                          equal=0, missing=0, older=0, newer=0, duplicate_matches=0,
                          pending=sum(not e['processed'] for e in entries), apply_warnings=run['warnings'])
            lookup = sql.SQL('SELECT {},{} FROM {} WHERE {}=ANY(%s)').format(
                sql.Identifier(definition.key['target']), sql.Identifier(definition.date['target']),
                sql.Identifier(definition.table), sql.Identifier(definition.key['target']))
            for start in range(0,len(entries),1000):
                page = entries[start:start+1000]
                keys = [json.loads(e['key']) for e in page]
                rows = target.execute(lookup,(keys,)).fetchall()
                actual = {definition.key_value(k):utc_time(d) for k,d in rows}
                result['duplicate_matches'] += len(rows)-len(actual)
                for entry,key in zip(page,keys):
                    result['checked'] += 1
                    if key not in actual:
                        result['missing'] += 1
                    else:
                        decision = classify(entry['date'],actual[key],run['allow_one_second_ahead'],run['allow_one_second_behind'])
                        result[{'equal':'equal','upsert':'older','ahead':'newer'}[decision]] += 1
            report['tables'].append(result)
            print(result,flush=True)
            if definition.table in ('kn_nep_katastrske_obcine_h','ev_pe_dst_h'):
                samples = db.execute('SELECT key,date FROM remote_ids_and_date_changed WHERE run_id=? AND date>? LIMIT 5',
                                     (run_id,run['cutoff'])).fetchall()
                if samples:
                    actual = {definition.key_value(k):utc_time(d) for k,d in target.execute(lookup,([json.loads(e['key']) for e in samples],))}
                    for e in samples:
                        key=json.loads(e['key'])
                        report['post_cutoff_samples'].append(dict(table=definition.table,key=key,
                            cutoff=run['cutoff'],oracle_export_date=e['date'],lift_date=actual.get(key)))
Path('reports/utc_applied_key_check.json').write_text(json.dumps(report,indent=2)+'\n')
print('Totals:',{k:sum(t[k] for t in report['tables']) for k in ('checked','equal','missing','older','newer','duplicate_matches','pending','apply_warnings')},flush=True)
print('Post-cutoff samples:',report['post_cutoff_samples'],flush=True)
