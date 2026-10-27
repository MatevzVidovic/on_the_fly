from db import connect, sql, TABLE
import time
from datetime import datetime, timezone

from run_log import run_log
from barman import wait_for_barman

with run_log(__file__) as run:
    with connect() as db:
        run["phase"] = "backfill"
        last_id = None
        while True:
            wait_for_barman(db)
            batch_started = time.perf_counter()
            after = sql.SQL('') if last_id is None else sql.SQL('WHERE id > %s')
            bound = db.execute(sql.SQL("""
                SELECT id FROM (
                    SELECT id FROM {table}
                    {after}
                    ORDER BY id
                    LIMIT 50000
                ) batch
                ORDER BY id DESC LIMIT 1
            """).format(table=TABLE, after=after),
                () if last_id is None else (last_id,)).fetchone()
            select_seconds = time.perf_counter() - batch_started
            if bound is None:
                break
            upper_id = bound[0]
            lower = sql.SQL('') if last_id is None else sql.SQL('AND id > %s')
            update_started = time.perf_counter()
            result = db.execute(sql.SQL("""
                UPDATE {table}
                SET date_change_utc =
                    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
                WHERE id <= %s {lower}
                  AND date_change_utc IS NULL AND date_change IS NOT NULL
            """).format(table=TABLE, lower=lower),
                (upper_id,) if last_id is None else (upper_id, last_id))
            update_seconds = time.perf_counter() - update_started
            batch_seconds = time.perf_counter() - batch_started
            print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | Updated {result.rowcount} rows | select {select_seconds:.2f}s"
                  f" | update {update_seconds:.2f}s | batch {batch_seconds:.2f}s"
                  f" | {result.rowcount / batch_seconds:.0f} rows/s", flush=True)
            last_id = upper_id
            wait_for_barman(db)
            time.sleep(1)
    print("Done", flush=True)
    run["phase"] = "done"
