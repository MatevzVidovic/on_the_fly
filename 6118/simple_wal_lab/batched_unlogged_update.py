from db import connect, sql, TABLE
import time

from run_log import run_log
from barman import wait_for_barman

with run_log(__file__) as run:
    with connect() as db:
        wait_for_barman(db)
        run["phase"] = "set_unlogged"
        db.execute(sql.SQL("ALTER TABLE {table} SET UNLOGGED").format(table=TABLE))
        run["phase"] = "backfill"
        last_id = None
        while True:
            wait_for_barman(db)
            batch_started = time.perf_counter()
            after = sql.SQL('') if last_id is None else sql.SQL('AND id > %s')
            rows = db.execute(sql.SQL("""
                SELECT id FROM {table}
                WHERE date_change_utc IS NULL AND date_change IS NOT NULL
                {after}
                ORDER BY id
                LIMIT 50000
            """).format(table=TABLE, after=after),
                () if last_id is None else (last_id,)).fetchall()
            select_seconds = time.perf_counter() - batch_started
            if not rows:
                break
            ids = [row[0] for row in rows]
            update_started = time.perf_counter()
            result = db.execute(sql.SQL("""
                UPDATE {table} t
                SET date_change_utc =
                    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
                WHERE t.id = ANY(%s)
                  AND t.date_change_utc IS NULL AND t.date_change IS NOT NULL
            """).format(table=TABLE), (ids,))
            update_seconds = time.perf_counter() - update_started
            batch_seconds = time.perf_counter() - batch_started
            print(f"Updated {result.rowcount} rows | select {select_seconds:.2f}s"
                  f" | update {update_seconds:.2f}s | batch {batch_seconds:.2f}s"
                  f" | {result.rowcount / batch_seconds:.0f} rows/s", flush=True)
            last_id = ids[-1]
            wait_for_barman(db)
            time.sleep(1)
        wait_for_barman(db)
        print("Setting table back to logged...", flush=True)
        run["phase"] = "set_logged"
        db.execute(sql.SQL("ALTER TABLE {table} SET LOGGED").format(table=TABLE))
        run["logging_restored"] = True
        wait_for_barman(db)
    print("Done", flush=True)
    run["phase"] = "done"
