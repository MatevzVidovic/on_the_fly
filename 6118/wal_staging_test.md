# UTC backfill: controlled staging comparison

## Decision

Keep the real table **LOGGED**. `SET UNLOGGED` skips data WAL during the UPDATE, but `SET LOGGED` writes the resulting table to WAL. It defers the burst and temporarily removes crash/physical-replication protection. [Evidence and sources](wal_strategy_research.md).

The replacement is **small, independently committed, paced batches**. It limits bursts and gives Barman time to catch up; it is not zero-WAL. A zero-WAL backfill followed by normal physical replication without transmitting the changes is not a supported per-table operation.

## Table and preparation

- Recommend **`ev_posebna_enota_h`**: approximately **35,768 rows / 39 MiB** on the reachable comparison database. Verify the actual size on `test_njihov_access` after enabling the VPN. The earlier entries in the list were much larger.
- You will run the staging test manually. No remote test has been performed by the agent. Never point these commands at production.
- Confirm staging identity, owner/CREATE privileges, healthy Barman streaming, and **at least 2 GiB actual free filesystem space**. Monitor actual disk space throughout; SQL slot lag is not a free-space measurement. The runner cannot inspect a remote filesystem.
- Pause the source integration/other writers for a consistent comparison. Record `SELECT version();`, the WAL settings, slot backlog and actual `pg_wal`/filesystem sizes. If staging has no Barman receiver, the test cannot validate Barman behavior.
- `wal_staging_setup.sql` makes three **logged isolated copies** in `wal6118_bench`, including indexes. Source values/mappings remain unchanged; copied UTC fields start null. Setup itself generates WAL. It refuses an existing test schema, >50,000 rows, >128 MiB, or unsupported source triggers/FKs/generated columns.
- The original `ev_pe_parc_utc_backfill.sql` is preserved byte-for-byte. **Do not run that whole file as-is**: its current target is the large `ev_parcela_h`, and it contains COMMIT/diagnostic statements. `wal_baseline.sql` runs the same original UPDATE on the small isolated baseline copy.

## Run baseline first, then compare

With your staging libpq connection variables configured (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`), run from the workspace root:

The runner requires the host, port and data-database name to match the stored `test_njihov_access` endpoint, as well as the explicit database argument below; matching only a database name is insufficient because production can use the same name. It reads that configuration programmatically and does not display credentials. Supply your authorized staging writer account through the PG variables.

```sh
python3 6118/wal_benchmark.py --staging \
  --expected-database YOUR_STAGING_DATABASE \
  --confirmed-free-gib 2
```

The runner creates the copies and executes these phases in order:

1. **Baseline:** original logged UPDATE in one committed transaction.
2. Wait for every slot's retained WAL to fall below 16 MiB (up to five minutes); stop on timeout.
3. **Logging experiment, clone only:** measure `SET UNLOGGED`, unlogged UPDATE and `SET LOGGED` separately. Include the final rewrite in the result; never apply this experiment to the source table.
4. Wait for slot catch-up again.
5. **Replacement:** `utc_backfill_batched.sql`, 500 rows per commit, at least 0.5 seconds between batches and additional pacing targeting 1 MiB/s average generated WAL. UUID keyset traversal avoids repeatedly scanning the already-filled prefix. No database transaction remains open during pauses.
6. Compare counts, all UTC values, original field values/IDs and final logged status. Save results to `wal_staging_results.json`, including before/after snapshots, one-second monitoring samples and per-batch measurements.

The batch runner stops **before the next batch** if slot retention exceeds the starting value by 64 MiB, and stops after a batch producing >16 MiB WAL. These are test budgets, not universal production settings or hard instantaneous limits: a committed batch cannot be undone by the guard. Earlier batches remain committed on failure. Do not wrap the runner in an outer transaction.

## Review and acceptance

- All three copies must have equal row counts, correct UTC values, unchanged original fields/keys, and `relpersistence='p'`.
- Compare **total WAL**, **largest batch WAL**, timeline/slot lag, table growth, actual WAL directory size and filesystem free space separately. LSN deltas include concurrent activity across the cluster. One-second samples can miss short spikes; operation endpoints and per-batch deltas remain necessary.
- The `UNLOGGED` variant must be judged through the end of `SET LOGGED`; a quiet UPDATE alone is not a successful result.
- The batch variant passes operationally only if real disk headroom remains comfortable and Barman catches up without sustained backlog growth. A smaller transaction alone does not prove this.
- Do not infer large-production safety from a 35k-row test. Measure bytes per row and Barman throughput, size the large-table run, and include space for dead row versions/index growth plus existing traffic. Batching can reduce peak backlog while still generating substantial total WAL.
- If interrupted, preserve the result JSON and inspect the copies. The runner refuses to overwrite an existing `wal6118_bench` schema; a failed logging experiment can leave only its isolated clone unlogged.
- After reviewing/exporting results, remove **only** the test schema with `DROP SCHEMA wal6118_bench CASCADE;`. This is cleanup of the three disposable copies, not an instruction to drop integration tables.

## Local proof and limits

`python3 6118/wal_benchmark.py --local` creates a network-isolated disposable PostgreSQL 15 container, runs the same SQL on **synthetic** winter/summer data, and removes the container and its data volume. It has no Barman receiver. See [local results](wal_local_results.json); these validate SQL mechanics, not remote staging or backup throughput.

Observed on PostgreSQL 15.19, 35,768 synthetic rows, full-page writes enabled:

| Operation | Generated WAL | Elapsed |
|---|---:|---:|
| Original logged UPDATE | 77.0 MiB | 0.38 s |
| Change clone to UNLOGGED | 0.13 MiB | 0.24 s |
| Unlogged UPDATE | 40 bytes | 0.27 s |
| Restore LOGGED | 36.0 MiB | 0.31 s |
| Paced logged batches (72 commits) | 52.8 MiB total; **4.9 MiB largest batch** | 79.8 s |

All copies had 35,768 rows, zero UTC mismatches/missing UTC values, unchanged original fields and logged persistence afterward. There were no monitoring errors. Totals include cluster activity and may vary with checkpoint/HOT behavior; the batching strategy must not depend on reproducing this particular total-WAL reduction.

Additional local guard checks are recorded in [guard results](wal_guard_test_results.json): wrong UTC type, oversized source and accidental overwrite rejection, plus independently committed/resumable batches. No remote source table was updated.

The preserved old file's SHA-256 is `23c97dee83030fecb57de20b3b9f0aefed1694dda5b6baa58f27c6543718f708`.
