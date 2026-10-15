"""Count the proposed Oracle 2020–2024 slice and its staging target, read-only."""
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
cfg = dotenv_values(ROOT / 'IntegrationRepair/.env')
assert cfg['PG_HOST'] == dotenv_values(ROOT / 'KN_deltas_reason/reconciliation/.env')['STAG_HOST']
# Use the Oracle credentials already used by the repair diagnostics.
source = dotenv_values(ROOT / 'IntegrationRepair_full_export/.env')
r = dict(environment='staging', started_at=datetime.now(timezone.utc).isoformat(),
         definition='2020 <= starting revision date < 2025; JN_STATUS <> X; same joins as 2025 integration')
if source.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=source['KN_ORACLE_CLIENT_LIB_DIR'])
with oracledb.connect(user=source['KN_ORACLE_USER'], password=source['KN_ORACLE_PASSWORD'], dsn=source['KN_ORACLE_DSN']) as oracle:
    oracle.call_timeout = 300000
    with oracle.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        r['oracle_indexes'] = []
        for table in ['JN_DEL_STAVBE_ENOTA', 'REVISION']:
            cur.execute('''SELECT i.index_name,i.uniqueness,i.status,c.column_name,c.column_position
                FROM all_indexes i JOIN all_ind_columns c ON c.index_owner=i.owner AND c.index_name=i.index_name
                WHERE i.table_owner='EV' AND i.table_name=:t ORDER BY i.index_name,c.column_position''',t=table)
            r['oracle_indexes'].append(dict(table=table, columns=[list(x) for x in cur]))
        print('Counting Oracle 2020–2024 ...', flush=True)
        start = perf_counter()
        cur.execute((HERE / 'oracle_2020_2024_count.sql').read_text())
        n, nonnull, lo, hi = cur.fetchone()
        r.update(oracle_count=int(n), oracle_model_version_non_null=int(nonnull),
                 oracle_model_version_null=int(n-nonnull), min_model_version=lo,max_model_version=hi,
                 oracle_seconds=round(perf_counter()-start,3))
        print(f'Oracle: {n:,} rows; {n-nonnull:,} null model versions',flush=True)
    oracle.rollback()
(HERE / 'counts_2020_2024.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
with psycopg.connect(host=cfg['PG_HOST'],port=cfg['PG_PORT'],user=cfg['PG_USER'],password=cfg['PG_PASSWORD'],
                     dbname=cfg['PG_DATABASE_DATA'],connect_timeout=10,
                     options='-c default_transaction_read_only=on -c statement_timeout=300000',row_factory=dict_row) as target:
    target.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
    print('Counting staging 2020–2024 ...',flush=True)
    start=perf_counter()
    r['staging'] = target.execute('''SELECT count(*) AS row_count,
        min(valid_from) AS min_valid_from,max(valid_from) AS max_valid_from,
        count(*) FILTER (WHERE valid_from < TIMESTAMP '2020-01-01' OR valid_from >= TIMESTAMP '2025-01-01') AS outside_start_date_window,
        count(*) FILTER (WHERE valid_from IS NULL) AS null_valid_from,
        count(*) FILTER (WHERE jn_status='X') AS status_x,
        count(*) FILTER (WHERE jn_del_st_enota_pk IS NULL) AS null_business_key
        FROM public.ev_del_stavbe_enota_h_2020_2024''').fetchone()
    r['staging_seconds']=round(perf_counter()-start,3)
    target.rollback()
r['oracle_minus_staging']=r['oracle_count']-r['staging']['row_count']
r['finished_at']=datetime.now(timezone.utc).isoformat()
(HERE / 'counts_2020_2024.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='oracle_indexes'},indent=2,default=str),flush=True)
