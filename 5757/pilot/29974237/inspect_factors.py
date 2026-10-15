import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
sql="""SELECT json_build_object('columns',(SELECT json_agg(t) FROM (
SELECT table_name,column_name,data_type,numeric_precision,numeric_scale FROM information_schema.columns
WHERE table_schema='public' AND table_name IN ('md_faktor_vrednost','md_razredi','md_razredi_podr','md_spremenljivke_enacbe','md_spremenljivke_sql') ORDER BY table_name,ordinal_position)t),
'factor_ids',(SELECT json_agg(t) FROM (SELECT id,faktor FROM public.md_faktorji WHERE id_rel_verzije_modeli='5f52e4a5-af0a-4ce7-9854-d14a6ce7cb40')t),
'other_tables',(SELECT json_agg(table_name) FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE 'md_spremenljivke%' OR table_name LIKE 'md_faktorji%')));"""
r=query(pg_env(dotenv_values(ROOT/'.env')),sql)[0]
Path(__file__).with_name('factor-schema.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
