import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
sql="""SELECT COALESCE(json_agg(t),'[]') FROM (SELECT id,id_prostora,povrsina::text FROM public.pripis_enote_prostori WHERE id_rel_prip_enote_prostori='4113d846-2f37-45c5-8573-caa160056487' LIMIT 15)t;"""
r=query(pg_env(dotenv_values(ROOT/'.env')),sql)[0]
Path(__file__).with_name('isam-rooms.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
