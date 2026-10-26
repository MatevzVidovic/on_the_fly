"""Backfill an isolated staging copy: unlogged batched."""
import time
from wal_lab_common import experiment


with experiment("unlogged_batched") as run:
    table = run.table
    run.phase("set_unlogged", f"ALTER TABLE {table} SET UNLOGGED;")
    while True:
        result = run.phase('batch', f"""
            WITH picked AS (
                SELECT ctid FROM {table}
                WHERE date_change_utc IS NULL AND date_change IS NOT NULL
                LIMIT {run.args.batch_size} FOR UPDATE
            ), changed AS (
                UPDATE {table} t
                SET date_change_utc =
                    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
                FROM picked p WHERE t.ctid = p.ctid
                RETURNING 1
            )
            SELECT json_build_object('rows', count(*)) FROM changed;
        """)
        if result[0]['rows'] == 0:
            break
        time.sleep(run.args.pause)
    run.phase("set_logged", f"ALTER TABLE {table} SET LOGGED;")
