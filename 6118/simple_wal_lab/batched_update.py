from db import connect, sql, TABLE
import time
from datetime import datetime, timezone

from run_log import run_log
from barman import wait_for_barman
from find_start_id import find_start_id

with run_log(__file__) as run:
    with connect() as db:
        run["phase"] = "backfill"
        init_started = time.perf_counter()
        print('Finding start by UUID bisection (assumes no gaps in completed rows)...', flush=True)
        last_id = find_start_id(db)
        print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | Start ID {last_id}"
              f" | lookup {time.perf_counter() - init_started:.2f}s", flush=True)
        comparison = sql.SQL('>=')  # Include the first unfinished row.
        while last_id is not None:
            wait_for_barman(db)
            batch_started = time.perf_counter()
            after = sql.SQL('WHERE id {comparison} %s').format(comparison=comparison)
            bound = db.execute(sql.SQL("""
                SELECT id FROM (
                    SELECT id FROM {table}
                    {after}
                    ORDER BY id
                    LIMIT 500000
                ) batch
                ORDER BY id DESC LIMIT 1
            """).format(table=TABLE, after=after),
                (last_id,)).fetchone()
            select_seconds = time.perf_counter() - batch_started
            if bound is None:
                break
            upper_id = bound[0]
            lower = sql.SQL('AND id {comparison} %s').format(comparison=comparison)
            update_started = time.perf_counter()
            result = db.execute(sql.SQL("""
                UPDATE {table}
                SET date_change_utc =
                    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
                WHERE id <= %s {lower}
                  AND date_change_utc IS NULL AND date_change IS NOT NULL
            """).format(table=TABLE, lower=lower),
                (upper_id, last_id))
            update_seconds = time.perf_counter() - update_started
            batch_seconds = time.perf_counter() - batch_started
            print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | Updated {result.rowcount} rows | select {select_seconds:.2f}s"
                  f" | update {update_seconds:.2f}s | batch {batch_seconds:.2f}s"
                  f" | {result.rowcount / batch_seconds:.0f} rows/s", flush=True)
            last_id = upper_id
            comparison = sql.SQL('>')
            wait_for_barman(db)
            time.sleep(1)
    print("Done", flush=True)
    run["phase"] = "done"
