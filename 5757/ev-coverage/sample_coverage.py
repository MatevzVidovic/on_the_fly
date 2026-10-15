"""Small block samples only: observed coverage, never a full-table inventory."""
import json,sys
from pathlib import Path
from datetime import datetime,timezone
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'model-mapping'));sys.path.insert(0,str(ROOT/'assets'))
from export_mapping import connect_oracle,read_oracle,pg_env
from inspect_db import query
cfg=dotenv_values(ROOT/'.env')
report={'sampled_at_utc':datetime.now(timezone.utc).isoformat(),'oracle':{},'staging':{}}
with connect_oracle(cfg) as conn:
 for table,key in [('DEL_STAVBE_ENOTA','DST_SID'),('JN_DEL_STAVBE_ENOTA','DST_SID'),('PARC_ENOTA','ID_PARC_ENOTA'),('JN_PARC_ENOTA','ID_PARC_ENOTA')]:
  history=table.startswith('JN_')
  sql=f"""SELECT s.id_model,s.id_model_ver,COUNT(*) AS sampled_rows,
      MIN(s.{key}) AS example_unit,MIN(rf.created) AS earliest_sampled_start,
      MAX(rf.created) AS latest_sampled_start,
      {'MIN(rt.created)' if history else 'CAST(NULL AS TIMESTAMP)'} AS earliest_sampled_end,
      {'MAX(rt.created)' if history else 'CAST(NULL AS TIMESTAMP)'} AS latest_sampled_end,
      {'SUM(CASE WHEN s.jn_rev_num_to IS NULL THEN 1 ELSE 0 END)' if history else 'CAST(NULL AS NUMBER)'} AS open_rows
      FROM (SELECT {key},id_model,id_model_ver,jn_rev_num{',jn_rev_num_to' if history else ''}
            FROM EV.{table} SAMPLE BLOCK (0.05) SEED (5757) FETCH FIRST 3000 ROWS ONLY)s
      LEFT JOIN EV.REVISION rf ON rf.rev_num=s.jn_rev_num
      {'LEFT JOIN EV.REVISION rt ON rt.rev_num=s.jn_rev_num_to' if history else ''}
      GROUP BY s.id_model,s.id_model_ver ORDER BY s.id_model,s.id_model_ver"""
  rows=read_oracle(conn,sql,limit=100)
  report['oracle'][table]=rows
  print(table,len(rows),'model/version groups',sum(r['sampled_rows'] for r in rows),'sampled rows',flush=True)
for table in ['ev_del_stavbe_enota','ev_del_stavbe_enota_h_2020_2024','ev_del_stavbe_enota_h_2025_danes','ev_parc_enota','ev_parc_enota_h_2020_2024','ev_parc_enota_h_2025_danes']:
 # Read only a few sampled blocks; schema lookup decides whether version IDs exist.
 columns=query(pg_env(cfg),f"SELECT COALESCE(json_agg(column_name),'[]') FROM information_schema.columns WHERE table_schema='public' AND table_name='{table}';")[0]
 if not columns:continue
 ver='id_model_ver' if 'id_model_ver' in columns else 'NULL::bigint AS id_model_ver'
 dates='valid_from,valid_to' if 'valid_from' in columns else 'NULL::timestamp AS valid_from,NULL::timestamp AS valid_to'
 sql=f"""SELECT COALESCE(json_agg(t),'[]') FROM (
 SELECT id_model,id_model_ver,count(*) AS sampled_rows,min(valid_from) AS earliest_sampled_start,
 max(valid_from) AS latest_sampled_start,min(valid_to) AS earliest_sampled_end,max(valid_to) AS latest_sampled_end,
 count(*) FILTER(WHERE valid_from IS NULL) AS missing_start_dates
 FROM (SELECT id_model,{ver},{dates} FROM public.{table} TABLESAMPLE SYSTEM (0.02) REPEATABLE(5757) LIMIT 3000)s
 GROUP BY id_model,id_model_ver ORDER BY id_model,id_model_ver)t;"""
 rows=query(pg_env(cfg),sql)[0]
 report['staging'][table]=rows
 print(table,len(rows),'groups',sum(r['sampled_rows'] for r in rows),'sampled rows',flush=True)
(ROOT/'ev-coverage/observed-coverage.json').write_text(json.dumps(report,default=str,indent=2)+'\n')
