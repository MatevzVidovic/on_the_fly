"""Catalog-only audit of KN/EV integration keys; no property table scans."""
import sys,json,re
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env,connect_oracle,read_oracle
cfg=dotenv_values(ROOT/'.env');env=pg_env(cfg);env['PGDATABASE']=cfg['PG_DATABASE_SYSTEM']
q="""SELECT COALESCE(json_agg(t),'[]') FROM (
SELECT i.id,t.name AS target_table,c.name AS connection_name,i.url AS source_sql,
(SELECT json_agg(json_build_object('target',f.name,'source',m.api_name,'is_key',m.api_id,'is_change_time',m.api_last_sync_field))
 FROM attribute_field_integrations m JOIN attribute_fields f ON f.id=m.attribute_field_id
 WHERE m.attribute_table_integration_id=i.id AND (m.api_id OR m.api_last_sync_field)
 AND NOT COALESCE(m.api_block_sync,false)) AS key_fields
FROM attribute_table_integrations i JOIN attribute_tables t ON t.id=i.attribute_table_id
JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id
WHERE i.integration_type='sql' AND (t.name LIKE 'kn\\_%' ESCAPE '\\' OR t.name LIKE 'ev\\_%' ESCAPE '\\')
ORDER BY t.name LIMIT 201)t;"""
integrations=query(env,q)[0]
assert len(integrations)<=200
folder=Path(__file__).resolve().parent
(folder/'integrations.json').write_text(json.dumps(integrations,indent=2)+'\n')
print('Integrations:',len(integrations))
tables=sorted({i['target_table'] for i in integrations})
assert all(re.fullmatch(r'[a-zA-Z0-9_]+',t) for t in tables)
names=','.join("'"+t+"'" for t in tables)
q=f"""SELECT json_build_object('indexes',(SELECT json_agg(t) FROM (
 SELECT tbl.relname AS table_name,idx.relname AS index_name,ix.indisunique,ix.indisprimary,ix.indisvalid,ix.indisready,
 ix.indpred IS NOT NULL AS partial,pg_get_indexdef(ix.indexrelid) AS definition,
 (SELECT json_agg(a.attname ORDER BY k.n) FROM unnest(ix.indkey) WITH ORDINALITY k(attnum,n)
 LEFT JOIN pg_attribute a ON a.attrelid=tbl.oid AND a.attnum=k.attnum WHERE k.n<=ix.indnkeyatts) AS key_columns
 FROM pg_index ix JOIN pg_class tbl ON tbl.oid=ix.indrelid
 JOIN pg_class idx ON idx.oid=ix.indexrelid JOIN pg_namespace ns ON ns.oid=tbl.relnamespace
 WHERE ns.nspname='public' AND tbl.relname IN ({names}))t),
 'constraints',(SELECT json_agg(t) FROM (SELECT tbl.relname AS table_name,c.conname,c.contype,c.convalidated,
 pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_class tbl ON tbl.oid=c.conrelid
 JOIN pg_namespace ns ON ns.oid=tbl.relnamespace WHERE ns.nspname='public' AND tbl.relname IN ({names}) AND c.contype IN ('p','u'))t));"""
pg=query(pg_env(cfg),q)[0]
(folder/'postgres-catalog.json').write_text(json.dumps(pg,indent=2)+'\n')
source_tables=set()
for i in integrations:
 for owner,table in re.findall(r'\b(?:FROM|JOIN)\s+"?([A-Za-z0-9_]+)"?\."?([A-Za-z0-9_]+)"?',i['source_sql'] or '',re.I):
  source_tables.add((owner.upper(),table.upper()))
(folder/'oracle-source-tables.json').write_text(json.dumps(sorted(source_tables),indent=2)+'\n')
print('Oracle source tables:',len(source_tables))
with connect_oracle(cfg) as conn:
 oracle_indexes=[];oracle_constraints=[]
 # Keep each dictionary query scoped to <=20 table names, sequentially.
 pairs=sorted(source_tables)
 for offset in range(0,len(pairs),20):
  chunk=pairs[offset:offset+20]
  clause=' OR '.join(f'(table_owner=:o{n} AND table_name=:t{n})' for n in range(len(chunk)))
  params={k:v for n,(o,t) in enumerate(chunk) for k,v in [(f'o{n}',o),(f't{n}',t)]}
  rows=read_oracle(conn,f"""SELECT c.table_owner,c.table_name,c.index_owner,c.index_name,c.column_name,c.column_position,
     i.uniqueness,i.status,i.index_type,i.partitioned
     FROM all_ind_columns c JOIN all_indexes i ON i.owner=c.index_owner AND i.index_name=c.index_name
     WHERE {' OR '.join(f'(c.table_owner=:o{n} AND c.table_name=:t{n})' for n in range(len(chunk)))}
     ORDER BY c.table_owner,c.table_name,c.index_name,c.column_position FETCH FIRST 501 ROWS ONLY""",params,limit=500)
  oracle_indexes+=rows
  rows=read_oracle(conn,f"""SELECT c.owner,c.table_name,c.constraint_name,c.constraint_type,c.status,c.validated,
     k.column_name,k.position
     FROM all_constraints c JOIN all_cons_columns k ON k.owner=c.owner AND k.constraint_name=c.constraint_name
     WHERE c.constraint_type IN ('P','U') AND
     ({' OR '.join(f'(c.owner=:o{n} AND c.table_name=:t{n})' for n in range(len(chunk)))})
     ORDER BY c.owner,c.table_name,c.constraint_name,k.position FETCH FIRST 501 ROWS ONLY""",params,limit=500)
  oracle_constraints+=rows
(folder/'oracle-catalog.json').write_text(json.dumps({'indexes':oracle_indexes,'constraints':oracle_constraints},indent=2)+'\n')
print('Postgres indexes:',len(pg['indexes'] or []),'Oracle indexed columns:',len(oracle_indexes))
