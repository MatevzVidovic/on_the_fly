import sys,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'assets'))
from inspect_db import config,query
# Staging access file used in earlier investigations; no credentials are printed.
e=config('test_njihov_access')
sql="""SELECT json_build_object(
'gv',(SELECT json_agg(t) FROM (SELECT model,verzija,datum_na,datum_pripis,verzija_pripis,opomba FROM public.primoz_gv_verzije WHERE (model='IND' AND verzija IN (51,66)) OR (model='TUR' AND verzija IN (26,27,42)) ORDER BY model,verzija LIMIT 12)t),
'isam_models',(SELECT json_agg(t) FROM (SELECT model,verzija,datum_modela FROM public.md_verzije_modeli WHERE model IN ('IND','INP','HIS','STA','STZ','KME','GOZ','GAR','DRZ','KDS','PPL','PPP','SDP','TUR') ORDER BY model,verzija LIMIT 150)t),
'current_unit',(SELECT json_agg(t) FROM (SELECT dst_sid,id_model,id_model_ver,vrednost,posplosena_vrednost FROM public.ev_del_stavbe_enota WHERE dst_sid=29974237 AND id_model='IND' LIMIT 3)t),
'history_unit',(SELECT json_agg(t) FROM (SELECT dst_sid,id_model,vrednost,valid_from,valid_to,jn_status FROM public.ev_del_stavbe_enota_h_2025_danes WHERE dst_sid=29974237 AND id_model='IND' LIMIT 8)t),
'old_unit',(SELECT json_agg(t) FROM (SELECT dst_sid,id_model,vrednost,valid_from,valid_to,jn_status FROM public.ev_del_stavbe_enota_h_2020_2024 WHERE dst_sid=29974237 AND id_model='IND' LIMIT 8)t),
'configurations',(SELECT json_agg(t) FROM (SELECT pd.datum,vm.model,vm.verzija FROM public.pripis_vm_x_pd x JOIN public.pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum JOIN public.md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli WHERE vm.model='IND' LIMIT 10)t));"""
r=query(e,sql)[0]
Path(__file__).with_name('08-staging.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='isam_models'},indent=2))
print('ISAM model rows:',len(r['isam_models'] or []))
