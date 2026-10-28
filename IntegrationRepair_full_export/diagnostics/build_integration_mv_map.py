"""Read-only FMP refresh routing and PostgreSQL MV definitions/indexes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from datetime import datetime,timezone
from dotenv import dotenv_values
import psycopg
from psycopg.rows import dict_row
c=dotenv_values('.env');p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=30000')
base=json.loads(Path('reports/mv_wal_inventory.json').read_text())['base_tables']
r=dict(at=datetime.now(timezone.utc).isoformat())
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM'],autocommit=True,row_factory=dict_row) as db:
 r['integrations']=db.execute('''SELECT i.id AS integration_id,t.id AS table_id,t.name,t.type_params,i.params,i.is_full_sync
 FROM attribute_table_integrations i JOIN attribute_tables t ON t.id=i.attribute_table_id
 JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id
 WHERE c.name='KN ORACLE' AND i.integration_type='sql' AND t.name=ANY(%s) ORDER BY t.name''',(base,)).fetchall()
 r['tables']=db.execute('SELECT id,name,type_params FROM attribute_tables').fetchall()
 r['sources']=db.execute("SELECT attribute_table_id,source_type,source_destination,status_key,is_archived FROM attribute_table_sources WHERE source_type IN ('sql_related_table','sql_view') AND NOT is_archived").fetchall()
with psycopg.connect(**p,dbname=c['PG_DATABASE_DATA'],autocommit=True,row_factory=dict_row) as db:
 r['mvs']=db.execute('''SELECT v.oid,n.nspname AS schema,v.relname AS name,v.relispopulated,
 v.reltuples::bigint AS estimated_rows,pg_table_size(v.oid) AS table_bytes,pg_indexes_size(v.oid) AS index_bytes,
 pg_get_viewdef(v.oid) AS sql FROM pg_class v JOIN pg_namespace n ON n.oid=v.relnamespace WHERE v.relkind='m' AND n.nspname='public' ORDER BY v.relname''').fetchall()
 for v in r['mvs']:
  v['indexes']=db.execute('''SELECT ci.relname,pg_get_indexdef(i.indexrelid) AS sql,i.indisunique,i.indisvalid,
 i.indimmediate,i.indpred IS NULL AS non_partial,i.indexprs IS NULL AS no_expressions,am.amname
 FROM pg_index i JOIN pg_class ci ON ci.oid=i.indexrelid JOIN pg_am am ON am.oid=ci.relam WHERE i.indrelid=%s''',(v['oid'],)).fetchall()
  v['random_uuid']='uuid_generate_v4()' in v['sql']
Path('reports/integration_mv_refresh_map.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
print('Integrations',len(r['integrations']),'metadata tables',len(r['tables']),'source links',len(r['sources']),'MVs',len(r['mvs']))
for i in r['integrations']:
 events=(i['type_params'] or {}).get('events',{})
 print(i['name'],'prevent=',(i['type_params'] or {}).get('prevent_materialized_view_refresh',False),'events=',json.dumps(events))
