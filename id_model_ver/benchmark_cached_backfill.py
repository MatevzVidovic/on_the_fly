"""Read-only live page comparison using a temporary local cache of matching keys."""
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import UUID
from dotenv import dotenv_values
import psycopg
import oracledb
from backfill import ROOT, transfer
from benchmark_oracle_lookup import fetch_models

cfg=dotenv_values(ROOT/'IntegrationRepair/.env');src=dotenv_values(ROOT/'IntegrationRepair_full_export/.env')
assert cfg['PG_HOST']==dotenv_values(ROOT/'KN_deltas_reason/reconciliation/.env')['STAG_HOST']
if src.get('KN_ORACLE_CLIENT_LIB_DIR'):oracledb.init_oracle_client(lib_dir=src['KN_ORACLE_CLIENT_LIB_DIR'])
after=UUID('0938aa00-28f5-4af9-a107-101123f856f1')
result={}
with psycopg.connect(host=cfg['PG_HOST'],port=cfg['PG_PORT'],user=cfg['PG_USER'],password=cfg['PG_PASSWORD'],dbname=cfg['PG_DATABASE_DATA'],autocommit=True,options='-c default_transaction_read_only=on -c statement_timeout=30000') as target, oracledb.connect(user=src['KN_ORACLE_USER'],password=src['KN_ORACLE_PASSWORD'],dsn=src['KN_ORACLE_DSN']) as ora, TemporaryDirectory() as tmp:
 ora.call_timeout=30000
 with ora.cursor() as cur:cur.execute('SET TRANSACTION READ ONLY')
 keys=[tuple(map(int,key.rsplit('-',1))) for key, in target.execute('''SELECT jn_del_st_enota_pk
 FROM public.ev_del_stavbe_enota_h_2020_2024 WHERE id>%s ORDER BY id LIMIT 10000''',(after,))]
 start=perf_counter();models=fetch_models(ora,keys)
 result['old_oracle_fetch_seconds']=round(perf_counter()-start,3)
 assert len(models)==len(set(keys))
 with sqlite3.connect(Path(tmp)/'sample.sqlite') as cache:
  start=perf_counter()
  cache.execute('CREATE TABLE models (sid INTEGER,revision INTEGER,model INTEGER,PRIMARY KEY(sid,revision)) WITHOUT ROWID')
  cache.executemany('INSERT INTO models VALUES (?,?,?)',[(sid,rev,model) for (sid,rev),model in models.items()]);cache.commit()
  result['sample_cache_write_seconds']=round(perf_counter()-start,3)
  result['cached_page_seconds']={}
  for n in [1000,10000]:
   start=perf_counter()
   transfer(target,cache,'ev_del_stavbe_enota_h_2020_2024',after=after,page_size=n,pages=1)
   result['cached_page_seconds'][str(n)]=round(perf_counter()-start,3)
 ora.rollback()
Path(__file__).with_name('benchmark_cached_backfill.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
assert result['cached_page_seconds']['10000']<2, 'Cached read/compare exceeds page budget'
