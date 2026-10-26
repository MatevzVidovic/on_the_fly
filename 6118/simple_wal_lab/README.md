# Simple backfill experiments (PostgreSQL 15)

No setup SQL, copies, table creation, truncation, or automatic resets.
The scripts backfill the existing table configured in `.env`.
Both `date_change` and `date_change_utc` must already exist as timestamp without time zone.

```bash
cd /Users/matevzvidovic/on_the_fly/6118/simple_wal_lab
source .venv/bin/activate
# Edit .env with the staging connection and target table.
```

In a separate terminal, run the tracker:

```bash
.venv/bin/python db_tracker.py full.sqlite
```

Run one experiment:

```bash
.venv/bin/python full_update.py
.venv/bin/python full_unlogged_update.py
.venv/bin/python batched_update.py
.venv/bin/python batched_unlogged_update.py
```

Every script only backfills NULL UTC values. After one succeeds, the same rows
will be skipped by later scripts. Arrange comparable starting data manually;
these scripts never reset your data. Stop other writers during comparisons.

Unlogged variants explicitly SET UNLOGGED before the backfill and SET LOGGED
afterwards. If interrupted or failed, the table can remain unlogged. These
operations rewrite the existing table; SET LOGGED generates WAL.

Batch size is 5,000 with one second pauses, editable directly in the batch scripts.
Each UPDATE/batch/ALTER commits separately. No monitoring inside update scripts.

The tracker prints samples and commits them to SQLite `samples` every second.
Ctrl+C stops it. Use a separate filename per experiment and keep it running after
updates finish to see Barman catch up. WAL is cluster-wide. Slot retention is not
Barman archive disk usage. WAL-directory bytes are unavailable without permission.
Host CPU/RAM/filesystem free space require your existing monitoring graphs.
Checkpoint counters and timings are cumulative; compare differences.

Dependencies are installed in `.venv`; to recreate:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Tracker output also includes cumulative WAL generated since tracker start and the
sizes of databases named `fmp` and `postgres` (unknown if absent/inaccessible).
WAL lives in the cluster-wide `pg_wal` directory, not inside either database's
reported size. Existing SQLite files are extended automatically with these metrics;
older samples have NULL in the new columns. Displayed sizes use MiB (1024² bytes).

Database and table sizes refresh every 30 seconds; intervening printed/SQLite
samples repeat the last measured sizes. WAL, Barman and activity refresh each
second. The final printed columns are WAL generated and WAL disk.

Batched scripts select IDs in ascending order and remember the last ID in RAM.
They update using the indexed `id` column. Restarting starts the scan again but
skips rows whose UTC field is already filled.

The default printed line shows time, WAL rate, Barman retained, table size, WAL
generated and WAL disk. Press `t` (no Enter) to show/hide database sizes and session
counts. All metrics continue to be collected and saved regardless of display mode.
Press `r` (no Enter) to immediately refresh database and table sizes and print a
new sample. Automatic size refresh still runs every 30 seconds.

All five runnable Python programs record start/stop UTC timestamps in the `runs`
table in this directory's `full.sqlite`, with completed/interrupted/failed status.
Unlogged scripts also record whether SET LOGGED finished. The tracker defaults to
that same file; an explicit sample filename does not change the run-log location.
Ctrl+C cancels an active query or stops a pause, records the stop, and exits with
code 130 without a traceback. Previously committed batches remain committed.
Unlogged tables are not automatically switched back on interruption: this could
trigger a large unexpected rewrite. Check their state before continuing.
