import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env,connect_oracle
cfg=dotenv_values(ROOT/'.env')
sql="""SELECT json_build_object(
'rt_rows',(SELECT json_agg(t) FROM (SELECT fv.id,fv.vrednost_enacba,p1.pogoj AS size_condition,p2.pogoj AS year_condition,p3.pogoj AS level_condition,p1.sek_razreda AS size_class,p2.sek_razreda AS year_class,p3.sek_razreda AS level_class
FROM public.md_faktor_vrednost fv
JOIN public.md_razredi_podr p1 ON p1.id=fv.id_rel_razred_podr1
JOIN public.md_razredi r1 ON r1.id=p1.id_rel_razredi
JOIN public.md_razredi_podr p2 ON p2.id=fv.id_rel_razred_podr2
JOIN public.md_razredi_podr p3 ON p3.id=fv.id_rel_razred_podr3
WHERE r1.id_rel_faktor='f1281084-5934-4352-8fee-597f64f49097' AND p1.sek_razreda=1 AND p2.sek_razreda=1 LIMIT 8)t),
'variable_columns',(SELECT json_agg(column_name) FROM information_schema.columns WHERE table_schema='public' AND table_name='md_spremenljivke_podatki'),
'relations',(SELECT json_agg(t) FROM (SELECT model,verzija,relacijska,osnova,m2 FROM public.primoz_gv_relacijske WHERE model='IND' AND verzija=66 AND relacijska=26 LIMIT 2)t));"""
r=query(pg_env(cfg),sql)[0]
Path(__file__).with_name('model-values.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'rt_rows':r['rt_rows'],'variable_columns':r['variable_columns']},indent=2))
with connect_oracle(cfg) as conn:
 try:
  with conn.cursor() as cur:
   cur.execute('SET TRANSACTION READ ONLY')
   cur.execute('SELECT xml FROM EV.MODELI_XML WHERE id_model_ver=:id',{'id':1173})
   row=cur.fetchone()
   for name,lob in zip(['runtime'],row):
    text=lob.read() if hasattr(lob,'read') else lob
    assert len(text)<150000
    Path(__file__).with_name('ev-ind-1173-'+name+'.xml').write_text(text)
    print(name,'XML characters',len(text))
 finally:conn.rollback()
