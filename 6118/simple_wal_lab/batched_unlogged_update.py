from db import connect
import time

with connect() as db:
    db.execute("ALTER TABLE simple_wal_lab.test_table SET UNLOGGED")
    while True:
        result = db.execute("""
            WITH batch AS (
                SELECT ctid FROM simple_wal_lab.test_table
                WHERE date_change_utc IS NULL AND date_change IS NOT NULL
                LIMIT 500
            )
            UPDATE simple_wal_lab.test_table t
            SET date_change_utc =
                (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
            FROM batch b WHERE t.ctid = b.ctid
        """)
        print(f"Updated {result.rowcount} rows", flush=True)
        if result.rowcount == 0:
            break
        time.sleep(1)
    print("Setting table back to logged...", flush=True)
    db.execute("ALTER TABLE simple_wal_lab.test_table SET LOGGED")
print("Done", flush=True)
