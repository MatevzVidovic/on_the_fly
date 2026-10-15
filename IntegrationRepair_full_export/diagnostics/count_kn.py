"""Read-only counts and key mappings for the supported KN delta integrations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timezone
import json
from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg.rows import dict_row
from count_ev import count_table
from definition import IntegrationDefinition

cfg = dotenv_values('.env')
reference = dotenv_values('../KN_deltas_reason/reconciliation/.env')
assert cfg['PG_HOST'] == reference['PROD_HOST'], 'Expected production endpoint'
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=300000')
report = dict(environment='production', started_at=datetime.now(timezone.utc).isoformat(),
              difference='Oracle minus LIFT: net shortfall, not exact insert count', tables=[])
path = Path('reports/kn_counts_production_latest.json')
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
    with metadata.cursor(row_factory=dict_row) as cur:
        cur.execute("""SELECT i.id FROM attribute_table_integrations i
            JOIN attribute_tables t ON t.id=i.attribute_table_id
            JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id
            WHERE t.name LIKE 'kn_%' AND c.name='KN ORACLE'
            AND NOT i.is_full_sync AND i.integration_type='sql' ORDER BY t.name""")
        ids = [str(row['id']) for row in cur.fetchall()]
    definitions = [IntegrationDefinition.load(metadata, id) for id in ids]
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA']) as lift:
    lift.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
    with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN']) as oracle:
        oracle.call_timeout = 300000
        with oracle.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
        for definition in definitions:
            print(f'Counting {definition.table} (key {definition.key["api_name"]}) ...', flush=True)
            result = count_table(definition, oracle, lift)
            result.update(source_key=definition.key['api_name'], target_key=definition.key['target'],
                          key_type=definition.key['field_type'], query=definition.query,
                          net_shortfall=result['oracle_total']-result['lift_total'])
            report['tables'].append(result)
            path.write_text(json.dumps(report, indent=2)+'\n')
            print(f'Oracle={result["oracle_total"]:,} LIFT={result["lift_total"]:,} net shortfall={result["net_shortfall"]:+,}', flush=True)
        oracle.rollback()
    lift.rollback()
report['finished_at'] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(report, indent=2)+'\n')
print(f'Saved {path}', flush=True)
