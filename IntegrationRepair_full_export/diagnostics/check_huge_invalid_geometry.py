"""Read-only bisection of the first pending huge-table apply batch."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,sqlite3,time
from dotenv import dotenv_values
import psycopg,oracledb
from definition import IntegrationDefinition
from source import OracleSource
c=dotenv_values('.env')
p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=30000')
with sqlite3.connect(Path('prod-utc-kn-dejanske-rabe-parcel.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as s:
 s.row_factory=sqlite3.Row
 run=s.execute('SELECT * FROM integration_transfer WHERE id=?',('eb6eef3a-e08f-4e0f-b105-94625718e188',)).fetchone()
 entries=s.execute('SELECT * FROM addition_diff WHERE run_id=? AND processed=0 LIMIT 10000',(run['id'],)).fetchall()
keys=[json.loads(e['key']) for e in entries]
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM'],autocommit=True) as m:d=IntegrationDefinition.load(m,run['integration_id'])
print('Checking',len(keys),'pending keys; geometry mapping',d.geometry,flush=True)
if c.get('KN_ORACLE_CLIENT_LIB_DIR'):oracledb.init_oracle_client(lib_dir=c['KN_ORACLE_CLIENT_LIB_DIR'])
report=dict(run=run['id'],bad=[])
with oracledb.connect(user=c['KN_ORACLE_USER'],password=c['KN_ORACLE_PASSWORD'],dsn=c['KN_ORACLE_DSN']) as o, psycopg.connect(**p,dbname=c['PG_DATABASE_DATA'],autocommit=True) as pg:
 o.call_timeout=30000
 source=OracleSource(o,d)
 with o.cursor() as cur:cur.execute('SET TRANSACTION READ ONLY')
 payloads=source.fetch_payloads(keys)
 field=d.geometry['api_name'];srid=d.geometry['api_location_transformation_srid']
 print('Fetched',len(payloads),'payloads',flush=True)
 def check(part):
  try:
   pg.execute('SELECT sum(ST_NPoints(ST_GeomFromText(wkt,%s))) FROM unnest(%s::text[]) AS t(wkt)',(srid,[payloads[k][field] for k in part])).fetchone()
   return
  except psycopg.Error as e:
   if len(part)>1:
    mid=len(part)//2;check(part[:mid]);check(part[mid:]);return
   key=part[0];text=payloads[key][field]
   print('INVALID',key,'length',len(text),'error',str(e),flush=True)
   def legacy(cursor,metadata):
    if metadata.type_code==oracledb.DB_TYPE_CLOB:return None
    return OracleSource.timestamp_text(cursor,metadata)
   o.outputtypehandler=legacy
   original=source.fetch_payloads([key])[key][field]
   o.outputtypehandler=OracleSource.timestamp_text
   item=dict(key=key,error=str(e),length=len(text),legacy_length=len(original),identical=text==original,wkt=text,legacy_wkt=original)
   report['bad'].append(item)
   print('LEGACY COMPARISON',key,'identical',item['identical'],'length',len(original),flush=True)
 check([k for k in keys if k in payloads and payloads[k].get(field) is not None])
Path('reports/huge_invalid_geometry.json').write_text(json.dumps(report,indent=2)+'\n')
print('Invalid rows:',len(report['bad']),flush=True)
