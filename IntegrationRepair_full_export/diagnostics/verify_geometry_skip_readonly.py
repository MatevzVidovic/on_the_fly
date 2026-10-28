"""Exercise skip recovery using real PostGIS parse errors and SELECTs only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from types import SimpleNamespace
from dotenv import dotenv_values
import psycopg
from target import LiftTarget
from store import RepairStore
c=dotenv_values('.env')
p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=15000')
bad=json.loads(Path('reports/huge_invalid_geometry.json').read_text())['bad'][0]
class ParseOnlyTarget(LiftTarget):
 def _upsert_batch(self,writes,max_date):
  with self.db.pipeline(),self.db.cursor() as cur:
   for key,payload in writes:cur.execute('SELECT ST_GeomFromText(%s,3794)',(payload['GEOM'],))
  self.db.commit()
  return [(key,None) for key,payload in writes]
with psycopg.connect(**p,dbname=c['PG_DATABASE_DATA']) as db:
 target=ParseOnlyTarget(db,None,SimpleNamespace(table='unused',key={'target':'key'},date={'target':'date'}))
 writes=[('1',{'GEOM':'POINT (1 1)'}),(str(bad['key']),{'GEOM':bad['wkt']}),('3',{'GEOM':'POINT (2 2)'})]
 outcomes=target.upsert_batch(writes,None)
 assert outcomes==[('1',None),(str(bad['key']),'Skipped row: Oracle geometry cannot be parsed by PostGIS'),('3',None)]
 store=RepairStore(':memory:');run=store.create_run('example','2026-10-28 00:00:00.000000','unused')
 store.save_source(run,[(1,'2026-10-28 00:00:00.000000'),(bad['key'],'2026-10-28 00:00:00.000000'),(3,'2026-10-28 00:00:00.000000')]);store.finish_preparation(run)
 store.finish_additions(run,outcomes)
 assert store.require_prepared_run(run)['warnings']==1
 assert store.db.execute('SELECT count(*) FROM addition_diff WHERE processed=1').fetchone()[0]==3
 print('PASS: real PostGIS error isolated; valid rows continue; skipped key and warning saved. No remote writes.')
 store.db.close()
