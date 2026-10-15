"""Read-only staging metadata for the building-part model-version backfill."""
from datetime import datetime, timezone
import json
from pathlib import Path
from dotenv import dotenv_values
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
cfg = dotenv_values(ROOT / 'IntegrationRepair/.env')
assert cfg['PG_HOST'] == dotenv_values(ROOT / 'KN_deltas_reason/reconciliation/.env')['STAG_HOST']
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, autocommit=True,
          options='-c default_transaction_read_only=on -c statement_timeout=30000')
names = ['ev_del_stavbe_enota', 'ev_del_stavbe_enota_h_2020_2024', 'ev_del_stavbe_enota_h_2025_danes']
r = dict(environment='staging', at=datetime.now(timezone.utc).isoformat(), tables=[])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], row_factory=dict_row) as meta, \
     psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA'], row_factory=dict_row) as data:
    for name in names:
        t = dict(table=name)
        t['metadata'] = meta.execute('SELECT id,name,type_params FROM attribute_tables WHERE name=%s',(name,)).fetchall()
        t['fields'] = meta.execute('''SELECT f.name,f.type FROM attribute_fields f JOIN attribute_tables t ON t.id=f.attribute_table_id
            WHERE t.name=%s ORDER BY f.name''',(name,)).fetchall()
        t['integrations'] = meta.execute('''SELECT i.id,i.url,i.params,i.is_full_sync,i.last_changed_datetime,c.name AS connection_name
            FROM attribute_table_integrations i JOIN attribute_tables t ON t.id=i.attribute_table_id
            JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id WHERE t.name=%s''',(name,)).fetchall()
        t['columns'] = data.execute('''SELECT a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS not_null
            FROM pg_attribute a WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum''',(name,)).fetchall()
        t['indexes'] = data.execute('''SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=%s''',(name,)).fetchall()
        t['estimate'] = data.execute('SELECT reltuples::bigint AS estimated_rows FROM pg_class WHERE oid=to_regclass(%s)',(name,)).fetchone()
        r['tables'].append(t)
        print(name,'model column:',[c for c in t['columns'] if c['name']=='id_model_ver'],'integrations:',len(t['integrations']),flush=True)
path=Path(__file__).with_name('staging_metadata.json')
path.write_text(json.dumps(r,indent=2,default=str)+'\n')
