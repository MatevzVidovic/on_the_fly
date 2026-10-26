from db import connect, sql, TABLE

with connect() as db:
    db.execute(sql.SQL("ALTER TABLE {table} SET UNLOGGED").format(table=TABLE))
    result = db.execute(sql.SQL("""
        UPDATE {table}
        SET date_change_utc =
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
        WHERE date_change_utc IS NULL AND date_change IS NOT NULL
    """).format(table=TABLE))
    print(f"Updated {result.rowcount} rows", flush=True)
    print("Setting table back to logged...", flush=True)
    db.execute(sql.SQL("ALTER TABLE {table} SET LOGGED").format(table=TABLE))
print("Done", flush=True)
