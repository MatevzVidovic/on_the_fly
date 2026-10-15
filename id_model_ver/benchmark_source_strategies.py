"""Read-only, bounded comparison of scattered lookups and sequential source fetch."""
import json
from pathlib import Path
from time import perf_counter
from uuid import UUID
from dotenv import dotenv_values
import psycopg
import oracledb
from backfill import ROOT
from benchmark_oracle_lookup import fetch_models

cfg=dotenv_values(ROOT/'IntegrationRepair/.env');src=dotenv_values(ROOT/'IntegrationRepair_full_export/.env')
assert cfg['PG_HOST']==dotenv_values(ROOT/'KN_deltas_reason/reconciliation/.env')['STAG_HOST']
if src.get('KN_ORACLE_CLIENT_LIB_DIR'):oracledb.init_oracle_client(lib_dir=src['KN_ORACLE_CLIENT_LIB_DIR'])
results=[]
with psycopg.connect(host=cfg['PG_HOST'],port=cfg['PG_PORT'],user=cfg['PG_USER'],password=cfg['PG_PASSWORD'],dbname=cfg['PG_DATABASE_DATA'],autocommit=True,options='-c default_transaction_read_only=on -c statement_timeout=30000') as pg, oracledb.connect(user=src['KN_ORACLE_USER'],password=src['KN_ORACLE_PASSWORD'],dsn=src['KN_ORACLE_DSN']) as ora:
 ora.call_timeout=30000
 with ora.cursor() as c:c.execute('SET TRANSACTION READ ONLY')
 rows=pg.execute('''SELECT jn_del_st_enota_pk FROM public.ev_del_stavbe_enota_h_2020_2024
  WHERE id>%s ORDER BY id LIMIT 10000''',(UUID('0938aa00-28f5-4af9-a107-101123f856f1'),)).fetchall()
 keys=[tuple(map(int,k.rsplit('-',1))) for k, in rows]
 # Same fetch function and keys; only the cursor's prefetch setting changes.
 class PrefetchConnection:
  def cursor(self):
   c=ora.cursor();c.prefetchrows=1000
   return c
 for n in [1000,10000]:
  expected=None
  for name,connection in [('current',ora),('prefetch1000',PrefetchConnection())]:
   start=perf_counter();actual=fetch_models(connection,keys[:n]);elapsed=perf_counter()-start
   if expected is None:expected=actual
   else:assert actual==expected
   result=dict(strategy=name,rows=n,seconds=round(elapsed,3));results.append(result);print(result,flush=True)
  # This tests sequential source delivery, not the same key subset. No local export or writes.
  with ora.cursor() as c:
   c.arraysize=1000;c.prefetchrows=1000
   start=perf_counter()
   c.execute('''SELECT TO_CHAR(j.DST_SID,'TM9'),TO_CHAR(j.JN_REV_NUM,'TM9'),TO_CHAR(j.ID_MODEL_VER,'TM9')
      FROM EV.JN_DEL_STAVBE_ENOTA j JOIN EV.REVISION rf ON rf.REV_NUM=j.JN_REV_NUM
      WHERE j.JN_STATUS <> 'X' AND rf.CREATED>=TIMESTAMP '2020-01-01 00:00:00'
      AND rf.CREATED<TIMESTAMP '2025-01-01 00:00:00' AND ROWNUM<=:n''',n=n)
   count=sum(1 for row in c)
   result=dict(strategy='sequential_source_sample',rows=count,seconds=round(perf_counter()-start,3));results.append(result);print(result,flush=True)
 ora.rollback()
Path(__file__).with_name('benchmark_source_strategies.json').write_text(json.dumps(results,indent=2)+'\n')
