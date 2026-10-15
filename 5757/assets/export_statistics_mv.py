"""Export one materialized view using bounded, read-only catalog queries."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('probe',ROOT/'assets/inspect_db.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sql="""SELECT json_build_object(
 'view',(SELECT row_to_json(x) FROM (SELECT n.nspname AS schema,c.relname AS name,pg_get_userbyid(c.relowner) AS owner,c.relispopulated AS populated,c.reloptions,ts.spcname AS tablespace,am.amname AS access_method,obj_description(c.oid,'pg_class') AS comment,pg_get_viewdef(c.oid,false) AS definition FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_tablespace ts ON ts.oid=c.reltablespace LEFT JOIN pg_am am ON am.oid=c.relam WHERE n.nspname='public' AND c.relname='pripis_standardne_statistike_napak' AND c.relkind='m')x),
 'columns',(SELECT COALESCE(json_agg(x ORDER BY attnum),'[]'::json) FROM (SELECT a.attnum,a.attname,format_type(a.atttypid,a.atttypmod) AS type,col_description(a.attrelid,a.attnum) AS comment FROM pg_attribute a WHERE a.attrelid='public.pripis_standardne_statistike_napak'::regclass AND a.attnum>0 AND NOT a.attisdropped)x),
 'acl',(SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,pg_get_userbyid(a.grantor) AS grantor,a.privilege_type,a.is_grantable FROM pg_class c CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid='public.pripis_standardne_statistike_napak'::regclass)x),
 'column_acl',(SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT at.attname,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,pg_get_userbyid(a.grantor) AS grantor,a.privilege_type,a.is_grantable FROM pg_attribute at CROSS JOIN LATERAL aclexplode(at.attacl) a WHERE at.attrelid='public.pripis_standardne_statistike_napak'::regclass AND at.attnum>0 AND NOT at.attisdropped)x),
 'indexes',(SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='pripis_standardne_statistike_napak')x)
);"""
data=m.query(m.config('test_njihov_access'),sql)[0]
assert data['view'],'Materialized view not found'
out=ROOT/'mv-backup';out.mkdir(exist_ok=True)
(out/'pripis_standardne_statistike_napak.metadata.json').write_text(json.dumps(data,indent=2)+'\n')
def ident(s):return '"'+s.replace('"','""')+'"'
def literal(s):return "'"+s.replace("'","''")+"'"
v=data['view'];qualified=ident(v['schema'])+'.'+ident(v['name'])
create='CREATE MATERIALIZED VIEW '+qualified+' (\n    '+',\n    '.join(ident(c['attname']) for c in data['columns'])+'\n)'
if v['access_method']:create+='\nUSING '+ident(v['access_method'])
if v['reloptions']:create+='\nWITH ('+', '.join(v['reloptions'])+')'
if v['tablespace']:create+='\nTABLESPACE '+ident(v['tablespace'])
create+='\nAS\n'+v['definition'].rstrip().rstrip(';')+'\nWITH NO DATA;\n'
lines=['-- Exported from staging; this file was generated, NOT executed.', '-- Run only after the old MV is absent. This file does not drop anything.', '-- Data is not backed up: REFRESH at the end recalculates statistics.', '-- Original ACL grantors are recorded in metadata; effective grants are restored below.', 'BEGIN;', "SET LOCAL search_path = pg_catalog, public;",create, 'ALTER MATERIALIZED VIEW '+qualified+' OWNER TO '+ident(v['owner'])+';']
# Remove grants inherited from default privileges so explicit captured grants determine access.
lines += [f'DO $restore_acl$\nDECLARE recipient record;\nBEGIN\n  FOR recipient IN SELECT DISTINCT x.grantee FROM pg_class c CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault(\'r\',c.relowner))) x WHERE c.oid={literal(qualified)}::regclass AND x.grantee<>c.relowner\n  LOOP\n    EXECUTE format(\'REVOKE ALL PRIVILEGES ON TABLE %s FROM %s\', {literal(qualified)}, CASE WHEN recipient.grantee=0 THEN \'PUBLIC\' ELSE quote_ident(pg_get_userbyid(recipient.grantee)) END);\n  END LOOP;\nEND;\n$restore_acl$;']
for a in data['acl']:
 if a['grantee']==v['owner']:continue
 recipient='PUBLIC' if a['grantee']=='PUBLIC' else ident(a['grantee'])
 lines.append(f"GRANT {a['privilege_type']} ON TABLE {qualified} TO {recipient}"+(' WITH GRANT OPTION' if a['is_grantable'] else '')+';')
for a in data['column_acl']:
 recipient='PUBLIC' if a['grantee']=='PUBLIC' else ident(a['grantee'])
 lines.append(f"GRANT {a['privilege_type']} ({ident(a['attname'])}) ON TABLE {qualified} TO {recipient}"+(' WITH GRANT OPTION' if a['is_grantable'] else '')+';')
for idx in data['indexes']:lines.append(idx['indexdef'].rstrip(';')+';')
if v['comment'] is not None:lines.append('COMMENT ON MATERIALIZED VIEW '+qualified+' IS '+literal(v['comment'])+';')
for c in data['columns']:
 if c['comment'] is not None:lines.append('COMMENT ON COLUMN '+qualified+'.'+ident(c['attname'])+' IS '+literal(c['comment'])+';')
lines+=['-- Original view was '+('populated' if v['populated'] else 'unpopulated')+'.', '-- Refresh may be expensive; schedule it appropriately.', 'REFRESH MATERIALIZED VIEW '+qualified+';' if v['populated'] else '-- Leave unpopulated to match original state.', 'COMMIT;']
(out/'recreate_pripis_standardne_statistike_napak.sql').write_text('\n\n'.join(lines)+'\n')
(out/'pripis_standardne_statistike_napak.select.sql').write_text(v['definition'].rstrip().rstrip(';')+';\n')
print(json.dumps({'saved_to':str(out),'columns':len(data['columns']),'indexes':len(data['indexes']),'acl_entries':len(data['acl']),'column_acl_entries':len(data['column_acl']),'populated':v['populated'],'database_changed':False}))
