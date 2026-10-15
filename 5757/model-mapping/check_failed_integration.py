import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
cfg=dotenv_values(ROOT/'.env');env=pg_env(cfg)
q="""SELECT json_build_object('columns',(SELECT json_agg(t) FROM (SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND (table_name='__i_01a13ff5_6b15_7b88_be24_2217d13d0972' OR table_name ILIKE '%model%ver%' OR table_name ILIKE '%model%xml%') ORDER BY table_name,ordinal_position)t));"""
r=query(env,q)[0];(ROOT/'model-mapping/failed-integration-data-schema.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
env['PGDATABASE']=cfg['PG_DATABASE_SYSTEM']
q="""SELECT COALESCE(json_agg(t),'[]') FROM (SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND (table_name LIKE 'attribute_table_integration%' OR table_name='attribute_fields') ORDER BY table_name,ordinal_position)t;"""
r=query(env,q)[0];(ROOT/'model-mapping/integration-metadata-schema.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
