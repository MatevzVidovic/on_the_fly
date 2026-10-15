"""Read-only comparison of current decimal/MV state and saved backup."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('probe',ROOT/'assets/inspect_db.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
env=m.config('test_njihov_access')
sql="""SELECT json_build_object('checked_at',now(),'column',(SELECT row_to_json(x) FROM (SELECT data_type,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema='public' AND table_name='pripis_vmxpd_x_enote' AND column_name='vrednost_izr')x),'mv',(SELECT row_to_json(x) FROM (SELECT schemaname,matviewname,matviewowner,ispopulated,definition FROM pg_matviews WHERE schemaname='public' AND matviewname='pripis_standardne_statistike_napak')x),'acl',(SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_class c CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid=to_regclass('public.pripis_standardne_statistike_napak'))x),'columns',(SELECT json_agg(x ORDER BY ordinal_position) FROM (SELECT a.attname AS column_name,format_type(a.atttypid,a.atttypmod) AS data_type,a.attnum AS ordinal_position FROM pg_attribute a WHERE a.attrelid=to_regclass('public.pripis_standardne_statistike_napak') AND a.attnum>0 AND NOT a.attisdropped)x),'indexes',(SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='pripis_standardne_statistike_napak')x));"""
data=m.query(env,sql)[0]
if data['mv'] and data['mv']['ispopulated']:
 data['mv_sample']=m.query(env,"SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT refreshed_at FROM public.pripis_standardne_statistike_napak LIMIT 1)x;")[0]
backup=json.loads((ROOT/'mv-backup/pripis_standardne_statistike_napak.metadata.json').read_text())
acl=lambda rs:{(r['grantee'],r['privilege_type'],r['is_grantable']) for r in rs}
data['backup_checks']={'owner_matches':bool(data['mv'] and data['mv']['matviewowner']==backup['view']['owner']),'grants_match':acl(data['acl'])==acl(backup['acl']),'indexes_match':data['indexes']==backup['indexes']}
(ROOT/'mv-backup/staging-after-refresh.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:v for k,v in data.items() if k not in ['acl','columns','indexes','mv']},indent=2));print('MV populated:',data['mv']['ispopulated'] if data['mv'] else None)
values={}
for line in (ROOT.parent/'symlinks/test_njihov_access/.env').read_text().splitlines():
 if '=' in line and not line.lstrip().startswith('#'):
  k,v=line.split('=',1);values[k.strip()]=v.strip().strip('\"').strip("'")
env['PGDATABASE']=values['PG_DATABASE_SYSTEM']
meta=m.query(env,"SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') AND table_name IN ('attribute_fields','attribute_tables'))x;")[0]
(ROOT/'reference/lift-metadata-column-discovery.json').write_text(json.dumps(meta,indent=2)+'\n')
for table in sorted({r['table_name'] for r in meta}):print(table,[(r['column_name'],r['data_type']) for r in meta if r['table_name']==table])
