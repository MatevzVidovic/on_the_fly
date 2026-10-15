"""Read-only check of current staging SFC wiring."""
import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
cfg=dotenv_values(ROOT/'.env');env=pg_env(cfg);env['PGDATABASE']=cfg['PG_DATABASE_SYSTEM']
q="""SELECT COALESCE(json_agg(t),'[]') FROM (SELECT s.sfc_item_id,s.title,s.description,
a.name AS table_name,p.position_key,p.layer_id,p."order" AS menu_order,
s.js IS NOT NULL AS inline_js_present,s.button_js IS NOT NULL AS inline_button_js_present
FROM public.sfc_items s JOIN public.sfc_item_attribute_table p ON p.sfc_item_id=s.sfc_item_id
LEFT JOIN public.attribute_tables a ON a.id=p.attribute_table_id
WHERE a.name='pripis_presecni_datum' ORDER BY p."order",s.title LIMIT 15)t;"""
r=query(env,q)[0]
(ROOT/'pilot/pripis-sfc-wiring.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
q="""SELECT json_build_object('dates',(SELECT json_agg(t) FROM (SELECT id,datum FROM public.pripis_presecni_datum ORDER BY datum LIMIT 15)t),
'ind_models',(SELECT json_agg(t) FROM (SELECT id,model,verzija,datum_modela,pripisna FROM public.md_verzije_modeli WHERE model='IND' AND verzija IN (51,66))t),
'ind_configs',(SELECT json_agg(t) FROM (SELECT x.id,x.id_rel_pr_datum,x.id_rel_verzije_modeli,vm.verzija,pd.datum FROM public.pripis_vm_x_pd x JOIN public.md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli JOIN public.pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum WHERE vm.model='IND' LIMIT 10)t));"""
r=query(pg_env(cfg),q)[0]
(ROOT/'pilot/pripis-ind-run-state.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
