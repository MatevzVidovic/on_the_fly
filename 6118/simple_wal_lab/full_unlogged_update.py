from db import connect

with connect() as db:
    db.execute("ALTER TABLE simple_wal_lab.test_table SET UNLOGGED")
    result = db.execute("""
        UPDATE simple_wal_lab.test_table
        SET date_change_utc =
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
        WHERE date_change_utc IS NULL AND date_change IS NOT NULL
    """)
    print(f"Updated {result.rowcount} rows", flush=True)
    print("Setting table back to logged...", flush=True)
    db.execute("ALTER TABLE simple_wal_lab.test_table SET LOGGED")
print("Done", flush=True)
