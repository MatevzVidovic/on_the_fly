"""Read-only scheduled integration -> configured MV routes and current footprints."""
import json
from pathlib import Path
from datetime import datetime, timezone
import psycopg
from psycopg.rows import dict_row
from dotenv import dotenv_values
c=dotenv_values('.env')
p=dict(host=c['PG_HOST'],port=c['PG_PORT'],user=c['PG_USER'],password=c['PG_PASSWORD'],connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=15000',autocommit=True,row_factory=dict_row)
with psycopg.connect(**p,dbname=c['PG_DATABASE_SYSTEM']) as db:
 integrations=db.execute('''SELECT i.id AS integration_id,t.name,i.sync_schedule,i.scheduled_task_id,i.last_sync_start,i.last_sync_end
 FROM attribute_table_integrations i JOIN attribute_tables t ON t.id=i.attribute_table_id
 WHERE i.sync_schedule IS NOT NULL AND i.sync_schedule <> 'none' AND i.sync_schedule <> '' ORDER BY i.sync_schedule,t.name''').fetchall()
 links=db.execute("SELECT attribute_table_id,source_type,source_destination FROM attribute_table_sources WHERE source_type IN ('sql_related_table','sql_view') AND NOT is_archived").fetchall()
with psycopg.connect(**p,dbname=c['PG_DATABASE_DATA']) as db:
 mvs={v['name']:v for v in db.execute("SELECT relname AS name,pg_total_relation_size(oid) AS total_bytes,position('uuid_generate_v4()' in pg_get_viewdef(oid))>0 AS random_uuid FROM pg_class WHERE relkind='m' AND relnamespace='public'::regnamespace").fetchall()}
for i in integrations:
 owners={s['attribute_table_id'] for s in links if s['source_type']=='sql_related_table' and s['source_destination']==i['name']}
 names=sorted({s['source_destination'] for s in links if s['source_type']=='sql_view' and s['attribute_table_id'] in owners})
 i['mvs']=[mvs.get(n,{'name':n,'not_found':True}) for n in names]
 print(i['sync_schedule'],i['name'],'->',', '.join(f"{v['name']} ({v.get('total_bytes',0)/2**30:.3f} GiB; random UUID={v.get('random_uuid','unknown')})" for v in i['mvs']) or 'no direct MV route')
out={'at':datetime.now(timezone.utc).isoformat(),'note':'Configured schedules, not proof of enabled Temporal schedules or actual executions. Cron timezone must be checked separately. All cron expressions retained for review, not automatically classified as nightly.','integrations':integrations}
Path('reports/scheduled_mv_refreshes.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print('Saved reports/scheduled_mv_refreshes.json')
