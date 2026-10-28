"""Read-only query-size comparisons using the real huge-table payload reader."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,sqlite3,time,hashlib
from dotenv import dotenv_values
import psycopg,oracledb
from definition import IntegrationDefinition
from source import OracleSource
c=dotenv_values('.env')
p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],options='-c default_transaction_read_only=on -c statement_timeout=20000',connect_timeout=10)
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM'],autocommit=True) as m:d=IntegrationDefinition.load(m,'e0c4ee44-f34c-11ef-9c8f-02420a0001ec')
s=sqlite3.connect(Path('prod-utc-kn-dejanske-rabe-parcel.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
run=s.execute('SELECT id FROM integration_transfer ORDER BY created_at DESC,rowid DESC LIMIT 1').fetchone()[0]
keys=[json.loads(r[0]) for r in s.execute('SELECT key FROM addition_diff WHERE run_id=? AND processed=0 ORDER BY key LIMIT 10000',(run,))]
report=dict(run=run,measurements=[])
if c.get('KN_ORACLE_CLIENT_LIB_DIR'):oracledb.init_oracle_client(lib_dir=c['KN_ORACLE_CLIENT_LIB_DIR'])
with oracledb.connect(user=c['KN_ORACLE_USER'],password=c['KN_ORACLE_PASSWORD'],dsn=c['KN_ORACLE_DSN']) as o:
 o.call_timeout=30000
 source=OracleSource(o,d)
 with o.cursor() as cur:cur.execute('SET TRANSACTION READ ONLY')
 for n in (1000,10000):
  expected=None
  for chunk in (1000,100,500,1000):
   start=time.perf_counter();payloads={}
   for offset in range(0,n,chunk):payloads.update(source.fetch_payloads(keys[offset:min(offset+chunk,n)]))
   elapsed=time.perf_counter()-start
   digest=hashlib.sha256(json.dumps(payloads,sort_keys=True).encode()).hexdigest()
   if expected is None:expected=digest
   assert digest==expected,'Different payloads for different query sizes'
   item=dict(requested=n,query_size=chunk,seconds=round(elapsed,3),rows=len(payloads),wkt_chars=sum(len(p['GEOM'] or '') for p in payloads.values()),sha256=digest)
   report['measurements'].append(item);print(item,flush=True)
   Path('reports/huge_oracle_batch_sizes.json').write_text(json.dumps(report,indent=2))

 for offset in (500000,2500000):
  distant=[json.loads(r[0]) for r in s.execute('SELECT key FROM addition_diff WHERE run_id=? AND processed=0 ORDER BY key LIMIT 1000 OFFSET ?',(run,offset))]
  start=time.perf_counter();payloads=source.fetch_payloads(distant);elapsed=time.perf_counter()-start
  item=dict(offset=offset,requested=len(distant),rows=len(payloads),seconds=round(elapsed,3),key_min=min(distant),key_max=max(distant),wkt_chars=sum(len(p['GEOM'] or '') for p in payloads.values()))
  report['measurements'].append(item);print(item,flush=True)
  Path('reports/huge_oracle_batch_sizes.json').write_text(json.dumps(report,indent=2))
