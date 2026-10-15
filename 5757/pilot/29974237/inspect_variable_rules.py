import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
sql="""SELECT json_agg(t) FROM (SELECT s.spremenljivka,p.id,p.opis,p.pogoj,p.vrednost_enacba
FROM public.md_spremenljivke s JOIN public.md_spremenljivke_podatki p ON p.id_rel_spremenljivka=s.id
WHERE s.id_rel_verzije_modeli='5f52e4a5-af0a-4ce7-9854-d14a6ce7cb40'
AND s.spremenljivka IN ('velikost','leto_obn') LIMIT 12)t;"""
r=query(pg_env(dotenv_values(ROOT/'.env')),sql)[0]
Path(__file__).with_name('variable-rules.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
