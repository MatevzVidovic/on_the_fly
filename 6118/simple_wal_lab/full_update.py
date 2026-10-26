from db import connect

with connect() as db:
    result = db.execute("""
        UPDATE simple_wal_lab.test_table
        SET date_change_utc =
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
        WHERE date_change_utc IS NULL AND date_change IS NOT NULL
    """)
    print(f"Updated {result.rowcount} rows", flush=True)
print("Done", flush=True)
