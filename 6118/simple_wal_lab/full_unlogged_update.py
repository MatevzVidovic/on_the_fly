from db import connect, sql, TABLE, DATE_COLUMN, SOURCE_DATE_COLUMN

from run_log import run_log

with run_log(__file__) as run:
    with connect() as db:
        run["phase"] = "set_unlogged"
        db.execute(sql.SQL("ALTER TABLE {table} SET UNLOGGED").format(table=TABLE, date_column=DATE_COLUMN, source_date_column=SOURCE_DATE_COLUMN))
        run["phase"] = "backfill"
        result = db.execute(sql.SQL("""
            UPDATE {table}
            SET {date_column} =
                ({source_date_column} AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
            WHERE {date_column} IS NULL AND {source_date_column} IS NOT NULL
        """).format(table=TABLE, date_column=DATE_COLUMN, source_date_column=SOURCE_DATE_COLUMN))
        print(f"Updated {result.rowcount} rows", flush=True)
        print("Setting table back to logged...", flush=True)
        run["phase"] = "set_logged"
        db.execute(sql.SQL("ALTER TABLE {table} SET LOGGED").format(table=TABLE, date_column=DATE_COLUMN, source_date_column=SOURCE_DATE_COLUMN))
        run["logging_restored"] = True
    print("Done", flush=True)
    run["phase"] = "done"
