"""Backfill an isolated staging copy: unlogged full."""
from wal_lab_common import experiment


with experiment("unlogged_full") as run:
    table = run.table
    run.phase("set_unlogged", f"ALTER TABLE {table} SET UNLOGGED;")
    run.phase('update', f"""
        UPDATE {table}
        SET date_change_utc =
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
        WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
    """)
    run.phase("set_logged", f"ALTER TABLE {table} SET LOGGED;")
