"""Export model-version values to SQLite once, using one Oracle SELECT/cursor."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from time import perf_counter

from dotenv import dotenv_values
import oracledb
from backfill import ROOT, TABLES


def export_models(oracle, path, table, source_id):
    # Keep the previous completed export usable until its replacement is complete.
    partial = path.with_suffix('.partial')
    path.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    start = perf_counter()
    count = 0
    period = "rf.CREATED >= TIMESTAMP '2020-01-01 00:00:00' AND rf.CREATED < TIMESTAMP '2025-01-01 00:00:00'" if table.endswith('2020_2024') else "rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'"
    with sqlite3.connect(partial) as cache:
        cache.execute('CREATE TABLE models (sid INTEGER, revision INTEGER, model INTEGER, PRIMARY KEY(sid,revision)) WITHOUT ROWID')
        cache.execute('CREATE TABLE export_info (target_table TEXT, source_id TEXT, created_at TEXT, row_count INTEGER)')
        with oracle.cursor() as cur:
            cur.arraysize = 10000
            cur.prefetchrows = 10000
            # No status filter: fill existing target identities, including historical X rows.
            cur.execute('''SELECT TO_CHAR(j.DST_SID,'TM9'),TO_CHAR(j.JN_REV_NUM,'TM9'),
                TO_CHAR(j.ID_MODEL_VER,'TM9') FROM EV.JN_DEL_STAVBE_ENOTA j
                JOIN EV.REVISION rf ON rf.REV_NUM=j.JN_REV_NUM WHERE ''' + period)
            while rows := cur.fetchmany(10000):
                cache.executemany('INSERT INTO models VALUES (?,?,?)',
                    [(int(sid),int(rev),None if model is None else int(model)) for sid,rev,model in rows])
                count += len(rows)
                if count % 100000 == 0:
                    print(f'Exported {count:,} Oracle rows; {perf_counter()-start:.1f}s',flush=True)
        cache.execute('INSERT INTO export_info VALUES (?,?,?,?)',
            (table,source_id,datetime.now(timezone.utc).isoformat(),count))
        cache.commit()
    partial.replace(path)
    print(f'Completed {path}: {count:,} rows; {perf_counter()-start:.1f}s',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('table',choices=TABLES)
    p.add_argument('--cache',type=Path)
    p.add_argument('--rebuild',action='store_true',help='replace an existing completed export')
    args=p.parse_args()
    path=args.cache or ROOT/'id_model_ver/cache'/f'{args.table}.sqlite'
    if path.exists() and not args.rebuild:
        p.error(f'{path} already exists; reuse it, or use --rebuild for fresh source values')
    cfg=dotenv_values(ROOT/'IntegrationRepair_full_export/.env')
    source_id=hashlib.sha256(cfg['KN_ORACLE_DSN'].encode()).hexdigest()
    if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
    with oracledb.connect(user=cfg['KN_ORACLE_USER'],password=cfg['KN_ORACLE_PASSWORD'],dsn=cfg['KN_ORACLE_DSN']) as oracle:
        oracle.call_timeout=300000
        with oracle.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
        export_models(oracle,path,args.table,source_id)
        oracle.rollback()


if __name__=='__main__':
    main()
