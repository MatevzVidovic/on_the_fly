from db import connect, sql, TABLE

from run_log import run_log

with run_log(__file__) as run:
    with connect() as db:
        run["phase"] = "set_unlogged"
        db.execute(sql.SQL("ALTER TABLE {table} SET UNLOGGED").format(table=TABLE))
        run["phase"] = "backfill"
        result = db.execute(sql.SQL("""
            UPDATE {table}
            SET date_change_utc =
                (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
            WHERE date_change_utc IS NULL AND date_change IS NOT NULL
        """).format(table=TABLE))
        print(f"Updated {result.rowcount} rows", flush=True)
        print("Setting table back to logged...", flush=True)
        run["phase"] = "set_logged"
        db.execute(sql.SQL("ALTER TABLE {table} SET LOGGED").format(table=TABLE))
        run["logging_restored"] = True
    print("Done", flush=True)
    run["phase"] = "done"
