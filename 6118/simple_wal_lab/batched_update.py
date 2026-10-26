from db import connect, sql, TABLE
import time

with connect() as db:
    while True:
        result = db.execute(sql.SQL("""
            WITH batch AS (
                SELECT ctid FROM {table}
                WHERE date_change_utc IS NULL AND date_change IS NOT NULL
                LIMIT 500
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
print("Done", flush=True)
