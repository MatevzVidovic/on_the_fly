from db import connect, sql, TABLE

with connect() as db:
    result = db.execute(sql.SQL("""
        UPDATE {table}
        SET date_change_utc =
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
        WHERE date_change_utc IS NULL AND date_change IS NOT NULL
    """).format(table=TABLE))
    print(f"Updated {result.rowcount} rows", flush=True)
print("Done", flush=True)
