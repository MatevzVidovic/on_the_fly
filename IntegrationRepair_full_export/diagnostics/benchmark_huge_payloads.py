"""Small read-only huge-KN payload benchmarks; never changes source/target data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,sqlite3,time
from dataclasses import replace
from dotenv import dotenv_values
import psycopg,oracledb
from definition import IntegrationDefinition
from source import OracleSource
c=dotenv_values('.env')
p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],options='-c default_transaction_read_only=on -c statement_timeout=20000',connect_timeout=10)
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM'],autocommit=True) as m:d=IntegrationDefinition.load(m,'e0c4ee44-f34c-11ef-9c8f-02420a0001ec')
s=sqlite3.connect(Path('prod-utc-kn-dejanske-rabe-parcel.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
run=s.execute('SELECT id FROM integration_transfer ORDER BY created_at DESC,rowid DESC LIMIT 1').fetchone()[0]
keys=[json.loads(r[0]) for r in s.execute('SELECT key FROM addition_diff WHERE run_id=? AND processed=0 ORDER BY key LIMIT 1000',(run,))]
report=dict(run=run,measurements=[])
if c.get('KN_ORACLE_CLIENT_LIB_DIR'):oracledb.init_oracle_client(lib_dir=c['KN_ORACLE_CLIENT_LIB_DIR'])
with oracledb.connect(user=c['KN_ORACLE_USER'],password=c['KN_ORACLE_PASSWORD'],dsn=c['KN_ORACLE_DSN']) as o:
 o.call_timeout=30000
 src=OracleSource(o,d)
 with o.cursor() as cur:
  cur.execute('SET TRANSACTION READ ONLY')
  cur.execute("SELECT i.owner,i.index_name,i.index_type,i.uniqueness,i.status,c.column_name,c.column_position FROM all_indexes i JOIN all_ind_columns c ON c.index_owner=i.owner AND c.index_name=i.index_name WHERE i.table_owner='NEP_OSTALO' AND i.table_name='DEJANSKE_RABE_H' ORDER BY i.index_name,c.column_position")
  report['indexes']=cur.fetchall();print('INDEXES',report['indexes'],flush=True)
  cur.execute("SELECT column_name,data_type FROM all_tab_columns WHERE owner='NEP_OSTALO' AND table_name='DEJANSKE_RABE_H' AND column_name IN ('DEJANSKA_RABA_H_ID','GEOM')")
  report['types']=cur.fetchall();print('TYPES',report['types'],flush=True)
 for size in (100,1000):
  for kind in ('full','batched_clob','without_wkt'):
   src.d=d if kind!='without_wkt' else replace(d,query=d.query.replace('SDO_UTIL.TO_WKTGEOMETRY(GEOM) AS GEOM','NULL AS GEOM'))
   def handler(cursor, metadata):
    if metadata.type_code == oracledb.DB_TYPE_CLOB:
     return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
    return OracleSource.timestamp_text(cursor, metadata)
   def legacy_handler(cursor, metadata):
    if metadata.type_code == oracledb.DB_TYPE_CLOB:
     return None
    return OracleSource.timestamp_text(cursor, metadata)
   o.outputtypehandler=handler if kind=='batched_clob' else legacy_handler
   t=time.perf_counter();rows=src.fetch_payloads(keys[:size]);elapsed=time.perf_counter()-t
   item=dict(kind=kind,requested=size,rows=len(rows),seconds=round(elapsed,3),wkt_chars=sum(len(r.get('GEOM') or '') for r in rows.values()))
   if kind=='full': baseline=rows
   if kind=='batched_clob':
    assert rows==baseline, 'Payload values differ'
    item['identical_to_baseline']=True
   report['measurements'].append(item);print(item,flush=True)
   Path('reports/huge_oracle_payload_benchmark.json').write_text(json.dumps(report,indent=2,default=str))
 # Read the executed cursor plan if the account can see its own SQL plans.
 with o.cursor() as cur:
  try:
   cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL,NULL,'BASIC +PREDICATE'))")
   report['last_cursor_plan']=[r[0] for r in cur];print('PLAN',report['last_cursor_plan'],flush=True)
  except oracledb.DatabaseError as e:report['plan_error']=str(e)
 Path('reports/huge_oracle_payload_benchmark.json').write_text(json.dumps(report,indent=2,default=str))
 full=next(m for m in report['measurements'] if m['kind']=='batched_clob' and m['requested']==100)
 assert full['seconds']<1, f"Slow Oracle payload repro: {full['seconds']}s for 100 rows (budget 1s)"
