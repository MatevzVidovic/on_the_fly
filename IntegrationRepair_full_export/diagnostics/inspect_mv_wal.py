"""Read-only MV dependency, size and refresh-trigger inventory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,sqlite3
from datetime import datetime,timezone
from dotenv import dotenv_values
import psycopg
from psycopg.rows import dict_row
from check_ev_utc_diffs import EV_RUNS,KN_RUNS
c=dotenv_values('.env');p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=30000')
tables=[]
for file,id in EV_RUNS+KN_RUNS:
 with sqlite3.connect(Path(file).resolve().as_uri()+'?mode=ro',uri=True) as s:tables.append(s.execute('SELECT attribute_table_name FROM integration_transfer WHERE id=?',(id,)).fetchone()[0])
tables.append('kn_nep_ostalo_dejanske_rabe_parcel_h')
r=dict(at=datetime.now(timezone.utc).isoformat(),base_tables=tables)
with psycopg.connect(**p,dbname=c['PG_DATABASE_DATA'],autocommit=True,row_factory=dict_row) as db:
 r['settings']=db.execute("SELECT name,setting,unit FROM pg_settings WHERE name IN ('server_version','wal_level','wal_compression','full_page_writes','checkpoint_timeout','max_wal_size')").fetchall()
 r['dependent_mvs']=db.execute('''WITH RECURSIVE deps(base,oid) AS (
 SELECT name,to_regclass('public.'||name) FROM unnest(%s::text[]) names(name)
 UNION
 SELECT deps.base,v.oid FROM deps
 JOIN pg_depend d ON d.refobjid=deps.oid AND d.refclassid='pg_class'::regclass AND d.classid='pg_rewrite'::regclass
 JOIN pg_rewrite rw ON rw.oid=d.objid
 JOIN pg_class v ON v.oid=rw.ev_class
 WHERE v.relkind IN ('m','v') AND v.oid<>deps.oid
 ) SELECT n.nspname AS schema,v.relname AS view_name,array_agg(DISTINCT deps.base ORDER BY deps.base) AS base_tables,
 v.reltuples::bigint AS estimated_rows,pg_table_size(v.oid) AS table_bytes,
 pg_indexes_size(v.oid) AS index_bytes,pg_total_relation_size(v.oid) AS total_bytes,
 EXISTS(SELECT 1 FROM pg_index i WHERE i.indrelid=v.oid AND i.indisunique AND i.indisvalid AND i.indpred IS NULL AND i.indexprs IS NULL) AS unique_index,
 pg_get_viewdef(v.oid) AS definition
 FROM deps JOIN pg_class v ON v.oid=deps.oid JOIN pg_namespace n ON n.oid=v.relnamespace
 WHERE v.relkind='m' GROUP BY v.oid,n.nspname ORDER BY pg_total_relation_size(v.oid) DESC''',(tables,)).fetchall()
 r['barman_slot']=db.execute("SELECT slot_name,active,pg_wal_lsn_diff(pg_current_wal_lsn(),restart_lsn)::bigint AS retained_bytes FROM pg_replication_slots WHERE slot_name='barman'").fetchall()
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM'],autocommit=True,row_factory=dict_row) as db:
 r['source_columns']=db.execute("SELECT column_name FROM information_schema.columns WHERE table_name='attribute_table_sources' ORDER BY ordinal_position").fetchall()
 r['fmp_sources']=db.execute('''SELECT t.name,t.type_params,s.* FROM attribute_table_sources s JOIN attribute_tables t ON t.id=s.attribute_table_id
 WHERE s.source_type IN ('sql_related_table','sql_view') AND (s.source_destination=ANY(%s) OR t.id IN (
 SELECT attribute_table_id FROM attribute_table_sources WHERE source_type='sql_related_table' AND source_destination=ANY(%s)))''',(tables,tables)).fetchall()
Path('reports/mv_wal_inventory.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
print('Settings',r['settings'])
for v in r['dependent_mvs']:print(v['view_name'],round(v['total_bytes']/1024**3,3),'GiB','unique=',v['unique_index'],'bases=',v['base_tables'])
print('Barman',r['barman_slot'])
print('FMP source rows',len(r['fmp_sources']))
