from db import connect, sql, TABLE
import time

with connect() as db:
    db.execute(sql.SQL("ALTER TABLE {table} SET UNLOGGED").format(table=TABLE))
    while True:
        result = db.execute(sql.SQL("""
            WITH batch AS (
                SELECT ctid FROM {table}
                WHERE date_change_utc IS NULL AND date_change IS NOT NULL
                LIMIT 5000
            )
            UPDATE {table} t
            SET date_change_utc =
                (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
            FROM batch b WHERE t.ctid = b.ctid
        """).format(table=TABLE))
        print(f"Updated {result.rowcount} rows", flush=True)
        if result.rowcount == 0:
            break
        time.sleep(1)
    print("Setting table back to logged...", flush=True)
    db.execute(sql.SQL("ALTER TABLE {table} SET LOGGED").format(table=TABLE))
print("Done", flush=True)
