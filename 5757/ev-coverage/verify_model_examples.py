"""Indexed source-history lookups for one observed unit per valuation model."""
import json,sys
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env,connect_oracle,read_oracle
cfg=dotenv_values(ROOT/'.env')
q="""SELECT COALESCE(json_agg(t),'[]') FROM (
SELECT id_model,min(dst_sid) AS unit FROM (
 SELECT id_model,dst_sid FROM public.ev_del_stavbe_enota_h_2025_danes
 TABLESAMPLE SYSTEM (0.02) REPEATABLE(5757) LIMIT 3000)s
WHERE id_model<>'NAPAKA' GROUP BY id_model ORDER BY id_model)t;"""
units=query(pg_env(cfg),q)[0]
report={'building_examples':{},'parcel_examples':{}}
observed=json.loads((ROOT/'ev-coverage/observed-coverage.json').read_text())
with connect_oracle(cfg) as conn:
 for unit in units:
  rows=read_oracle(conn,"""SELECT j.dst_sid,j.id_model,j.id_model_ver,j.jn_rev_num,j.jn_rev_num_to,j.jn_status,
      rf.created AS valid_from,rt.created AS valid_to
      FROM EV.JN_DEL_STAVBE_ENOTA j
      LEFT JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
      LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
      WHERE j.dst_sid=:unit AND j.id_model=:model AND j.jn_status<>'X'
      ORDER BY j.jn_rev_num FETCH FIRST 31 ROWS ONLY""",{'unit':unit['unit'],'model':unit['id_model']},limit=30)
  report['building_examples'][unit['id_model']]=rows
  print('building',unit['id_model'],unit['unit'],[(x['id_model_ver'],str(x['valid_from'])) for x in rows],flush=True)
 for unit in observed['oracle']['PARC_ENOTA']:
  if unit['id_model']=='ZPS':continue
  rows=read_oracle(conn,"""SELECT j.id_parc_enota,j.pc_mid,j.id_model,j.id_model_ver,j.jn_rev_num,j.jn_rev_num_to,j.jn_status,
      rf.created AS valid_from,rt.created AS valid_to
      FROM EV.JN_PARC_ENOTA j
      LEFT JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
      LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
      WHERE j.id_parc_enota=:unit AND j.id_model=:model AND j.jn_status<>'X'
      ORDER BY j.jn_rev_num FETCH FIRST 31 ROWS ONLY""",{'unit':unit['example_unit'],'model':unit['id_model']},limit=30)
  report['parcel_examples'][unit['id_model']]=rows
  print('parcel',unit['id_model'],len(rows),'rows',flush=True)
(ROOT/'ev-coverage/verified-model-examples.json').write_text(json.dumps(report,default=str,indent=2)+'\n')
