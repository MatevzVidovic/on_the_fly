"""Replay a saved recent export through key lookups; remote reads, in-memory plan."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,sqlite3,time
from dotenv import dotenv_values
import psycopg
from definition import IntegrationDefinition,check_run_definition
from store import RepairStore
from target import LiftTarget
from repair import prepare

path=Path('prod-utc-ev-del-stavbe-catchup.sqlite')
with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as saved:
 saved.row_factory=sqlite3.Row
 run=saved.execute('SELECT * FROM integration_transfer ORDER BY created_at DESC,rowid DESC LIMIT 1').fetchone()
 pairs=[(json.loads(r['key']),r['date']) for r in saved.execute('SELECT key,date FROM remote_ids_and_date_changed WHERE run_id=?',(run['id'],))]
c=dotenv_values('.env')
p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],connect_timeout=10,
       options='-c default_transaction_read_only=on -c statement_timeout=30000')
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM'],autocommit=True) as m, psycopg.connect(**p,dbname=c['PG_DATABASE_DATA']) as pg:
 d=IntegrationDefinition.load(m,run['integration_id'])
 check_run_definition(run,d)
 store=RepairStore(':memory:')
 id=store.create_run(d.id,run['cutoff'],d.table,run['min_date'],[d.date['api_name'],d.date['target'],'UTC'],run['allow_one_second_ahead'],run['allow_one_second_behind'])
 store.save_source(id,pairs);store.finish_source(id)
 start=time.perf_counter()
 prepare(d,None,LiftTarget(pg,None,d),store,run_id=id)
 elapsed=time.perf_counter()-start
 result=dict(table=d.table,source_store=str(path),source_run=run['id'],oracle_keys=len(pairs),seconds=round(elapsed,3),
             plan=dict(store.require_prepared_run(id)),remote_read_only=True)
 print(json.dumps(result,indent=2),flush=True)
 Path('reports/catchup_key_lookup_benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
 store.db.close()
