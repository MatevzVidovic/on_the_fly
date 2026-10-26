# UTC backfill: WAL strategy research

2026-10-23. Documentation findings; no database writes performed for this note. The deployed PostgreSQL/Barman versions must still be recorded before testing.

## Decision

Keep the integration table **LOGGED**. Test the unchanged original UPDATE against a separate, identical small staging copy, then test **paced, independently committed batches**. Measure WAL generation, peak retained WAL, table growth, and real filesystem headroom separately. Batching can limit the production rate and peak backlog; it does **not** make the update WAL-free or guarantee lower total WAL.

There is no supported per-table switch that both avoids backfill WAL and subsequently makes all changed data durable and physically replicated without transmitting that data. This conclusion follows from the persistence and replication behavior below.

## Why disabling logging is not the solution

- `UNLOGGED` table data changes bypass WAL, but **the whole table is truncated after a crash or unclean shutdown**, and its contents are not replicated to standbys. Its indexes are unlogged too. This is a change to durability, not merely a performance setting. [PostgreSQL CREATE TABLE](https://www.postgresql.org/docs/current/sql-createtable.html#SQL-CREATETABLE-UNLOGGED)
- **`ALTER TABLE ... SET LOGGED` writes the table contents to WAL**, creating the postponed replication spike. PostgreSQL's project documentation explicitly warns about this; PostgreSQL 17 source also marks both persistence changes as table rewrites. These operations can therefore need substantial additional relation storage as well as WAL. Do not promise zero total WAL based only on measuring the unlogged UPDATE. [PostgreSQL 9.5 feature notes](https://wiki.postgresql.org/wiki/What's_new_in_PostgreSQL_9.5#ALTER_TABLE_..._SET_LOGGED_.2F_UNLOGGED), [PostgreSQL 17 implementation](https://github.com/postgres/postgres/blob/REL_17_STABLE/src/backend/commands/tablecmds.c)
- The server-wide bulk-load optimization uses `wal_level=minimal`, `archive_mode=off`, and `max_wal_senders=0`, needs server restarts, prevents continuous archiving/streaming, invalidates the previous base-backup recovery chain, and requires a **fresh base backup** afterward. It is not a session-level UPDATE optimization. It is unsuitable for this cutover while preserving the existing Barman recovery chain. [PostgreSQL bulk loading guidance](https://www.postgresql.org/docs/current/populate.html#POPULATE-PITR), [WAL configuration](https://www.postgresql.org/docs/current/runtime-config-wal.html#GUC-WAL-LEVEL)

## Recommended comparison and safeguards

- PostgreSQL recommends smaller batches for large UPDATEs because of bloat, replica lag, and locking. Select bounded rows and update them using a CTE/self-join; commit **each** batch and wait outside its transaction. A loop around updates inside one outer transaction is not independently committed batching. [PostgreSQL UPDATE](https://www.postgresql.org/docs/17/sql-update.html)
- Preserve table identity, keys, mappings, indexes, and logging mode; update only null UTC values with non-null local timestamps. Inspect triggers before benchmarking so the copies reproduce the relevant write behavior. The UTC expression remains `(date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'`.
- Start conservatively, one writer. Advance only while slot backlog and actual disk measurements remain below agreed limits; pause when the receiver stalls or backlog grows beyond the budget. Derive the production batch rate from the measured receiver throughput with headroom for ordinary traffic. This is an operational recommendation, not an automatic property of batching.
- `restart_lsn` is the oldest WAL a slot might still require. `active=true` does not establish that it is caught up. Retained WAL from LSN differences is **not** actual `pg_wal` directory size or free filesystem space. Physical slots are cluster-wide, so simultaneous activity in other databases matters. [PostgreSQL replication slot view](https://www.postgresql.org/docs/current/view-pg-replication-slots.html)
- Barman streaming uses PostgreSQL's WAL stream and replication slots; keeping that stream intact retains normal backup/recovery semantics. Compare Barman's streaming progress throughout the test; do not drop/advance its slot or stop its receiver to reduce the measured backlog. [Barman WAL architecture](https://docs.pgbarman.org/release/3.5.0/#the-barman-wal-archive), [Barman streaming status](https://docs.pgbarman.org/release/3.16.1/user_guide/wal_archiving.html#synchronous-wal-streaming)
- `EXPLAIN (ANALYZE, WAL, BUFFERS)` can report WAL produced by an UPDATE, but **executes it**. Rolling it back still generates WAL. Use it only on the bounded staging comparison objects, not as a harmless production preview. [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html)
- Check whether UTC is indexed: HOT updates can avoid new index entries only if the updated columns are not referenced by ordinary indexes and the old page has enough free space. Do not remove indexes or rewrite fillfactor merely to improve the benchmark; those changes need their own space/WAL budget. [PostgreSQL HOT](https://www.postgresql.org/docs/16/storage-hot.html)

## What would actually avoid the historic UPDATE

Leaving historical UTC values derived at read time could avoid rewriting those rows, but would change the application/schema contract. It needs separate Lift/downstream compatibility checks and is **not established as safe here**. A stored generated column or a table rewrite is not a free substitute. The approved staging comparison should first establish whether paced logged updates keep backlog and storage comfortably bounded.
