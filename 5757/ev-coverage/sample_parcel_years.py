import json,sys
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
report={}
for year in range(2020,2025):
 table=f'ev_parc_enota_h_{year}'
 sql=f"""SELECT COALESCE(json_agg(t),'[]') FROM (
 SELECT id_model,id_model_ver,count(*) AS sampled_rows,
 min(valid_from) AS first_sampled_start,max(valid_from) AS last_sampled_start,
 min(valid_to) AS first_sampled_end,max(valid_to) AS last_sampled_end,
 count(*) FILTER(WHERE valid_from IS NULL) AS missing_start,
 count(*) FILTER(WHERE valid_to IS NOT NULL AND valid_to<valid_from) AS reversed_intervals
 FROM (SELECT id_model,id_model_ver,valid_from,valid_to FROM public.{table}
 TABLESAMPLE SYSTEM(0.002) REPEATABLE(5757) LIMIT 500)s
 GROUP BY id_model,id_model_ver ORDER BY id_model)t;"""
 report[table]=query(pg_env(dotenv_values(ROOT/'.env')),sql)[0]
 print(table,sum(x['sampled_rows'] for x in report[table]),'sample rows',flush=True)
(ROOT/'ev-coverage/staging-yearly-parcel-samples.json').write_text(json.dumps(report,indent=2)+'\n')
