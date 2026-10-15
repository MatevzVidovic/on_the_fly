import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'assets'))
sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
sql="""SELECT json_build_object(
'prepared',(SELECT json_agg(to_jsonb(e)-'geom') FROM public.pripis_enote_deli_stavb e WHERE id='4113d846-2f37-45c5-8573-caa160056487'),
'result',(SELECT json_agg(r) FROM public.pripis_vmxpd_x_enote r WHERE id='e0113d9b-8ddf-4b96-a99b-436da1f31e9e'),
'model',(SELECT json_agg(t) FROM (SELECT id,model,verzija,spremenljivke,faktorji,enacba_desna,enacba_ref_obj,datum_modela FROM public.md_verzije_modeli WHERE id='5f52e4a5-af0a-4ce7-9854-d14a6ce7cb40')t),
'indexes',(SELECT json_agg(t) FROM (SELECT tablename,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN ('ev_dst_pripis_podatki_h','md_spremenljivke','md_faktorji'))t),
'columns',(SELECT json_agg(t) FROM (SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('md_spremenljivke','md_faktorji','ev_dst_pripis_podatki_h') ORDER BY table_name,ordinal_position)t));"""
r=query(pg_env(dotenv_values(ROOT/'.env')),sql)[0]
Path(__file__).with_name('isam-sources.json').write_text(json.dumps(r,indent=2)+'\n')
for key in ('prepared','result','model','indexes'):print(key,json.dumps(r[key],indent=2))
