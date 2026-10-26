# Small staging WAL experiment

Run manually on **staging**, using standard libpq `PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, `PGPASSWORD` (or `.pgpass`). Requires Python 3 and `psql`; no Python packages.
Do not put passwords in commands or result files. No remote experiment has been run by this tooling's author.

Default source: `public.ev_posebna_enota_h` (previous comparison DB estimate: 35,768 rows,
39 MB; rechecked by the script). This is different from `ev_posebna_enota`.
Both `date_change` and `date_change_utc` must already exist as timestamp without time zone.
Stop source integration/writers during the comparison so each copy gets the same source data.
Use an otherwise quiet staging database and verify adequate filesystem/Barman free space first.

```bash
python3 6118/wal_lab_full.py --expected-database "$PGDATABASE"
python3 6118/wal_lab_unlogged_full.py --expected-database "$PGDATABASE"
python3 6118/wal_lab_batched.py --expected-database "$PGDATABASE"
python3 6118/wal_lab_unlogged_batched.py --expected-database "$PGDATABASE"
```

The database name argument prevents connecting to an unexpected database; **it does
not identify staging by itself**. Check your host and database configuration first.

Each script creates its own table in schema `wal6118_lab` and refuses to overwrite
an existing table. Run the four commands separately, in order. Each gets its own results directory. Original data and previous SQL files remain unchanged.
Copies include source indexes but omit defaults, triggers and foreign keys.
All begin logged, with `date_change_utc` cleared. Source limit: 50,000 rows / 128 MB.

In order:

1. `full`: one logged UPDATE.
2. `unlogged_full`: SET UNLOGGED, one UPDATE, SET LOGGED.
3. `batched`: logged UPDATEs of 500 rows, each separately committed, 1 second pauses.
4. `unlogged_batched`: SET UNLOGGED, the same batches, SET LOGGED.

The conversion is `(date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'`.
The copy phase, SET UNLOGGED, UPDATE and SET LOGGED are measured separately.
Validation checks row counts, every converted timestamp, and final logged state.
Each SQL call has a 5 second lock timeout and 120 second statement timeout.
There is a 30 second monitored cooldown after setup and after each variant.
No forced CHECKPOINT or VACUUM: checkpoint timing and cache state can affect results.
For stronger comparisons, repeat experiments at similar checkpoint/load conditions.

Options: `--source NAME`, `--batch-size 500`, `--pause 1`, `--cooldown 30`,
`--max-retained-mb 64`, `--output DIRECTORY`. Retention is checked between statements;
64 MB is a stop threshold, **not an instantaneous disk cap**. Other cluster traffic
can trigger it. Failures leave copies for inspection; an interrupted unlogged variant
may remain unlogged. Do not repurpose these copies as integration tables.

## Results

Each run produces:

- `phases.csv`: duration and cluster-wide generated WAL bytes per phase/batch.
  For batched runs, sum batch WAL bytes; wall-clock duration including pauses comes
  from the first batch start to the final batch end in events.jsonl.
  For unlogged runs, include both logging transitions in the comparison.
- `events.jsonl`: UTC timestamps, phase boundaries, batch counts and validation.
- `samples.jsonl`: approximately one sample/second, including during cooldowns.
- `config.json`, `settings.json`: source bounds and effective checkpoint/WAL settings.

Samples record WAL insertion position, WAL counters/full-page images, slot retention
(including Barman), database and copy sizes, checkpoint counters/times, database
read/hit/temp/transaction counters, and session states/waits. Counters are cumulative;
compare differences between samples, watching for resets. WAL is cluster-wide, not
exclusive to this process. Reported session details can be limited by permissions.

WAL directory bytes are collected only if the account has permission, otherwise null.
Database size is **not filesystem usage**; it excludes pg_wal. Barman slot retention is
**not Barman's own archive disk usage**, nor a network throughput measurement. CPU,
RAM, filesystem free space, disk latency/IOPS, and Barman server load need your
existing host monitoring graphs. Align those graphs using the UTC timestamps.

The monitor can also run by itself, stopping with Ctrl+C:

```bash
python3 6118/wal_lab_monitor.py --output overnight.jsonl --interval 5
```

These are observations, not proof that backfill is safe at production scale. SET
LOGGED is expected to generate WAL; batching unlogged updates cannot remove that cost.
The runner never deletes the copies automatically. After inspection, manually run
`DROP SCHEMA wal6118_lab CASCADE;` on the same staging database to remove only this lab.

The four experiment files contain the actual SQL steps. `wal_lab_common.py` handles
shared setup, guardrails, validation and recording; `wal_lab_db.py` handles psql.
`wal_lab_run.py` remains an optional launcher for all four commands.
