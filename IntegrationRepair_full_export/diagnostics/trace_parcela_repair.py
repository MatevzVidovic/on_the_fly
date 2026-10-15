"""Read-only key/date probe of the configured target; compare environments separately."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import psycopg
from source import wall_time

ROOT = Path(__file__).resolve().parents[1]
OLD = '03ff3376-0110-4c42-a617-07662100d1bf'
NEW = '007bbd84-c118-41b5-86f1-34e6a897abb1'
with sqlite3.connect((ROOT / 'full-ev-parcela.sqlite').as_uri()+'?mode=ro', uri=True) as db:
    before = dict(db.execute('SELECT key,date FROM addition_diff WHERE run_id=?', (OLD,)))
    after = dict(db.execute('SELECT key,date FROM addition_diff WHERE run_id=?', (NEW,)))
report = dict(at=datetime.now(timezone.utc).isoformat(), old_run=OLD, new_run=NEW,
              old_upserts=len(before), new_upserts=len(after),
              new_keys=len(after.keys()-before.keys()), dropped_keys=len(before.keys()-after.keys()),
              changed_source_dates=sum(after[k] != before[k] for k in after.keys() & before.keys()))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sample', action='store_true')
args=parser.parse_args()
cfg=dotenv_values(ROOT / '.env')
counts=Counter(); profiles=Counter(); examples=[]
keys=[json.loads(k) for k in after]; dates={json.loads(k):v for k,v in after.items()}
if args.sample:
    keys=['100000006678-2211','130311266-1354']
with psycopg.connect(host=cfg['PG_HOST'],port=cfg['PG_PORT'],user=cfg['PG_USER'],password=cfg['PG_PASSWORD'],
        dbname=cfg['PG_DATABASE_DATA'],connect_timeout=10,autocommit=True,
        options='-c default_transaction_read_only=on -c statement_timeout=15000') as db:
    report['database'] = db.execute('SELECT current_database()').fetchone()[0]
    for start in range(0,len(keys),1000):
        group=keys[start:start+1000]
        rows=db.execute('''SELECT jn_parcela_pk,id,date_change,created_at,updated_at,created_by,updated_by
            FROM ev_parcela_h WHERE jn_parcela_pk=ANY(%s)''',(group,)).fetchall()
        counts['missing']+=len(group)-len(rows)
        for key,id,date,created,updated,creator,updater in rows:
            decision='older' if wall_time(date)<dates[key] else 'equal' if wall_time(date)==dates[key] else 'ahead'
            counts[decision]+=1
            profiles[(id.version,str(creator),str(updater))]+=1
            if len(examples)<3:
                examples.append(dict(key=key,id=str(id),expected_date=dates[key],current_date=str(date),
                    created_at=str(created),updated_at=str(updated),created_by=str(creator),updated_by=str(updater)))
report['current_rows']=dict(counts)
report['profiles']=[dict(uuid_version=k[0],created_by=k[1],updated_by=k[2],count=v) for k,v in profiles.items()]
report['examples']=examples
report['passed']=counts['missing']==0 and counts['older']==0
(ROOT / ('diagnostics/parcela_repair_trace_sample.json' if args.sample else 'diagnostics/parcela_repair_trace.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if report['passed'] else 1)
