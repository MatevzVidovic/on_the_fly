# Simple WAL lab (PostgreSQL 15 staging)

Four independent update scripts. No tracking inside them. Only `db_tracker.py`
prints metrics and saves samples to SQLite. `db.py` just opens the connection.

```bash
python3 -m pip install 'psycopg[binary]'
```

Configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` (or `.pgpass`)
for your **staging** database. The programs use those standard connection settings.

Before **each** experiment, recreate the same small disposable copy:

```bash
psql -X -v ON_ERROR_STOP=1 -f 6118/simple_wal_lab/setup.sql
```

The source is `public.ev_posebna_enota_h`. Both timestamp columns must already
exist. The scripts only update `simple_wal_lab.test_table`. Setup copies indexes,
but no triggers, defaults or foreign keys. Stop source writers while comparing.
Setup itself generates WAL; wait for Barman retention/disk activity to settle
before measuring the update. Start tracking before setup if you want to see it too.

In another terminal, leave the tracker running:

```bash
python3 6118/simple_wal_lab/db_tracker.py full.sqlite
```

Run **one** experiment:

```bash
python3 6118/simple_wal_lab/full_update.py
python3 6118/simple_wal_lab/full_unlogged_update.py
python3 6118/simple_wal_lab/batched_update.py
python3 6118/simple_wal_lab/batched_unlogged_update.py
```

Re-run setup before the next one and use a different SQLite filename per test.
Ctrl+C stops tracking; every sample is committed immediately. Leave it running
after the update finishes to observe Barman catching up. Batch size is 500 with
one second between batches; edit those two values directly in the batch scripts.
Connections use autocommit: each UPDATE/batch/ALTER is its own transaction.
If an unlogged experiment fails before SET LOGGED, its copy remains unlogged.
Running setup again replaces that copy.

Tracker stores one row per sample in `samples`, including generated WAL, actual
WAL-directory size if permitted, Barman slot retention, database/table sizes,
sessions, reads/hits, temporary bytes, and checkpoint counters/timings. Additional
statistics and replication details are in `details_json`. `?` means unavailable.
Metrics are cumulative or cluster-wide; compare differences. No statistics are reset.
Host CPU/RAM/filesystem free space and Barman archive disk usage require your host
graphs. Database bytes exclude pg_wal; retained WAL is not Barman archive size.

These intentionally simple scripts have no automatic size/retention stop guards.
Use only the small staging copy and watch your existing disk/load graphs. They do
not force checkpoints; checkpoint timing can affect comparisons. Keep the tracker
and graph timestamps aligned (the tracker timestamp includes its UTC offset).
