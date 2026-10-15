import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
cfg=dotenv_values(ROOT/'.env');env=pg_env(cfg);env['PGDATABASE']=cfg['PG_DATABASE_SYSTEM']
q="""SELECT COALESCE(json_agg(t),'[]') FROM (SELECT i.id AS integration_id,i.name AS integration_name,a.id AS table_id,a.name AS target_table,i.processing_status,
(SELECT json_agg(json_build_object('id',f.id,'name',f.name,'type',f.type,'virtual',f.virtual,'type_params',f.type_params)) FROM public.attribute_fields f WHERE f.attribute_table_id=a.id) AS fields
FROM public.attribute_table_integrations i JOIN public.attribute_tables a ON a.id=i.attribute_table_id
WHERE i.url ILIKE '%EV.MODELI_XML%' LIMIT 5)t;"""
r=query(env,q)[0]
(ROOT/'model-mapping/failed-integration-fields.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
if r:
 names=[x['target_table'] for x in r]
 assert all(__import__('re').fullmatch('[a-zA-Z0-9_]+',x) for x in names)
 sql="SELECT COALESCE(json_agg(t),'[]') FROM (SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ("+','.join("'"+x+"'" for x in names)+") ORDER BY table_name,ordinal_position)t;"
 print(json.dumps(query(pg_env(cfg),sql)[0],indent=2))
