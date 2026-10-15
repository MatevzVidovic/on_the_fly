"""Bounded read-only baseline; optional budget catches slow page reads/fetches."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from uuid import UUID
from dotenv import dotenv_values
import psycopg
import oracledb
from backfill import ROOT
from benchmark_oracle_lookup import fetch_models

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--budget',type=float)
a=p.parse_args()
cfg=dotenv_values(ROOT/'IntegrationRepair/.env');src=dotenv_values(ROOT/'IntegrationRepair_full_export/.env')
assert cfg['PG_HOST']==dotenv_values(ROOT/'KN_deltas_reason/reconciliation/.env')['STAG_HOST']
if src.get('KN_ORACLE_CLIENT_LIB_DIR'):oracledb.init_oracle_client(lib_dir=src['KN_ORACLE_CLIENT_LIB_DIR'])
r={}
with psycopg.connect(host=cfg['PG_HOST'],port=cfg['PG_PORT'],user=cfg['PG_USER'],password=cfg['PG_PASSWORD'],dbname=cfg['PG_DATABASE_DATA'],autocommit=True,options='-c default_transaction_read_only=on -c statement_timeout=30000') as pg, oracledb.connect(user=src['KN_ORACLE_USER'],password=src['KN_ORACLE_PASSWORD'],dsn=src['KN_ORACLE_DSN']) as ora:
 ora.call_timeout=30000
 with ora.cursor() as c:c.execute('SET TRANSACTION READ ONLY')
 start=perf_counter()
 rows=pg.execute('''SELECT id,jn_del_st_enota_pk,id_model_ver FROM public.ev_del_stavbe_enota_h_2020_2024
  WHERE id>%s ORDER BY id LIMIT 10000''',(UUID('0938aa00-28f5-4af9-a107-101123f856f1'),)).fetchall()
 r['lift_read_seconds']=round(perf_counter()-start,3)
 keys=[tuple(map(int,k.rsplit('-',1))) for _,k,_ in rows]
 start=perf_counter();models=fetch_models(ora,keys)
 r['oracle_fetch_seconds']=round(perf_counter()-start,3)
 r['rows']=len(rows);r['missing']=len(set(keys)-models.keys())
 r['read_fetch_seconds']=r['lift_read_seconds']+r['oracle_fetch_seconds']
 ora.rollback()
Path(__file__).with_name('benchmark_baseline.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2),flush=True)
if a.budget is not None:assert r['read_fetch_seconds']<=a.budget, 'Read/fetch alone exceeds page budget'
