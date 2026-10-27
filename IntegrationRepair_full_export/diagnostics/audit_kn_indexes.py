"""Read-only catalog audit of KN integration keys and audit settings."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timezone
import json
import re
from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg.rows import dict_row
from definition import IntegrationDefinition, EXCLUDED_TABLES

cfg = dotenv_values('.env')
assert cfg['PG_HOST'] == dotenv_values('../KN_deltas_reason/reconciliation/.env')['PROD_HOST']
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=10, autocommit=True,
          options='-c default_transaction_read_only=on -c statement_timeout=30000')
report = dict(environment='production', checked_at=datetime.now(timezone.utc).isoformat(), tables=[])
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], row_factory=dict_row) as metadata, \
     psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA'], row_factory=dict_row) as lift, \
     oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN']) as oracle:
    oracle.call_timeout = 30000
    with oracle.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
    rows = metadata.execute("""SELECT i.id, i.params FROM attribute_table_integrations i
        JOIN attribute_tables t ON t.id=i.attribute_table_id
        JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id
        WHERE t.name LIKE 'kn_%' AND c.name='KN ORACLE' AND NOT i.is_full_sync
        AND i.integration_type='sql' AND NOT (t.name=ANY(%s)) ORDER BY t.name""", (list(EXCLUDED_TABLES),)).fetchall()
    for row in rows:
        d = IntegrationDefinition.load(metadata, str(row['id']))
        params = row['params'] or {}
        if isinstance(params, str):
            params = json.loads(params)
        owner, table = re.search(r'\bFROM\s+(\w+)\.(\w+)', d.query, re.I).groups()
        owner, table, key = owner.upper(), table.upper(), d.key['api_name'].upper()
        result = dict(table=d.table, integration_id=d.id, source=f'{owner}.{table}',
                      source_key=key, target_key=d.key['target'], ignore_audit=params.get('ignore_audit'),
                      ignore_audit_present='ignore_audit' in params)
        result['lift_column'] = lift.execute("""SELECT a.attnotnull AS not_null, format_type(a.atttypid,a.atttypmod) AS type
            FROM pg_attribute a WHERE a.attrelid=to_regclass(%s) AND a.attname=%s AND NOT a.attisdropped""",
            (d.table, d.key['target'])).fetchone()
        result['lift_indexes'] = lift.execute("""SELECT ic.relname AS name, am.amname AS method,
            i.indisunique AS is_unique, i.indisvalid AS valid, i.indisready AS ready,
            pg_get_expr(i.indpred,i.indrelid) AS predicate,
            pg_get_indexdef(i.indexrelid) AS definition,
            ARRAY(SELECT a.attname FROM unnest(i.indkey::smallint[]) WITH ORDINALITY k(attnum,pos)
                LEFT JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
                WHERE k.pos<=i.indnkeyatts ORDER BY k.pos) AS columns
            FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid
            JOIN pg_am am ON am.oid=ic.relam WHERE i.indrelid=to_regclass(%s)""", (d.table,)).fetchall()
        result['lift_constraints'] = lift.execute("""SELECT c.conname AS name,c.contype AS type,c.convalidated AS validated,
            pg_get_constraintdef(c.oid) AS definition,
            ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(attnum,pos)
                JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum ORDER BY k.pos) AS columns
            FROM pg_constraint c WHERE c.conrelid=to_regclass(%s) AND c.contype IN ('p','u')""", (d.table,)).fetchall()
        with oracle.cursor() as cur:
            cur.execute('SELECT data_type, nullable FROM all_tab_columns WHERE owner=:o AND table_name=:t AND column_name=:k', o=owner,t=table,k=key)
            result['oracle_column'] = dict(zip(['type','nullable'], cur.fetchone()))
            cur.execute('''SELECT c.constraint_name,c.constraint_type,c.status,c.validated,c.index_name,cc.column_name,cc.position
                FROM all_constraints c JOIN all_cons_columns cc ON cc.owner=c.owner AND cc.constraint_name=c.constraint_name
                WHERE c.owner=:o AND c.table_name=:t AND c.constraint_type IN ('P','U')
                ORDER BY c.constraint_name,cc.position''', o=owner,t=table)
            constraints = {}
            for name,typ,status,validated,index,col,pos in cur:
                item=constraints.setdefault(name,dict(name=name,type=typ,status=status,validated=validated,index=index,columns=[]))
                item['columns'].append(col)
            result['oracle_constraints']=list(constraints.values())
            cur.execute('''SELECT i.owner,i.index_name,i.uniqueness,i.status,i.index_type,i.partitioned,
                c.column_name,c.column_position
                FROM all_indexes i JOIN all_ind_columns c ON c.index_owner=i.owner AND c.index_name=i.index_name
                WHERE i.table_owner=:o AND i.table_name=:t ORDER BY i.owner,i.index_name,c.column_position''',o=owner,t=table)
            indexes={}
            for io,name,unique,status,typ,partitioned,col,pos in cur:
                item=indexes.setdefault((io,name),dict(owner=io,name=name,uniqueness=unique,status=status,type=typ,partitioned=partitioned,columns=[]))
                item['columns'].append(col)
            result['oracle_indexes']=list(indexes.values())
        report['tables'].append(result)
        print(d.table, 'ignore_audit=',result['ignore_audit'],flush=True)
    oracle.rollback()
Path('reports/kn_indexes_audit_production.json').write_text(json.dumps(report,indent=2)+'\n')
