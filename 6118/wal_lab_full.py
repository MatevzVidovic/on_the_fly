"""Backfill an isolated staging copy: full."""
from wal_lab_common import experiment


with experiment("full") as run:
    table = run.table
    run.phase('update', f"""
        UPDATE {table}
        SET date_change_utc =
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
        WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
    """)
