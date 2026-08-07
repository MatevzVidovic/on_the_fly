# KN integration delta audit

`kn-delta-audit` is a read-only command-line audit for FMP integrations whose
metadata connection is named `KN ORACLE`.  It never reconstructs an Oracle
source table: source data always comes from the integration's saved SQL.

Copy `.env.example` to `.env` and fill credentials.  `TEST` is the default
profile; use `--environment stag` when appropriate.

## Read-only boundary

The CLI itself sends only:

- PostgreSQL: `SET TRANSACTION READ ONLY`, `SET TIME ZONE`, and `SELECT`.
- Oracle: `ALTER SESSION SET TIME_ZONE`, `SET TRANSACTION READ ONLY`, and
  the saved integration `SELECT`.

It contains no DML/DDL or integration-run command. The stored integration SQL
is checked to be one `SELECT`/`WITH` statement before it is run.

For a true operational guarantee, use dedicated **read-only database roles**
for `TEST_*`, `STAG_*`, and `KN_*`: grant only `CONNECT` and the necessary
`SELECT` privileges; grant no DML/DDL, procedure-execution, or integration-run
privileges. A `SELECT` can theoretically call a privileged side-effecting
function, so database permissions—not application validation alone—are the
final safeguard.

## 1. Discover the candidate table set

Run discovery first. It queries only the FMP metadata database; it does not
open a KN Oracle connection or execute any integration SQL.

```sh
.venv/bin/kn-delta-audit discover --environment test --output-dir artifacts
```

The printed artifact directory contains `inventory.md` and `inventory.jsonl`.
The inventory lists every FMP integration whose SQL connection is `KN ORACLE`,
including table name, integration UUID, stored SQL, SQL hash, high-water mark,
and duplicate-integration warning.

Review that inventory and create a deliberately small `selected_tables.json`.
The audit never selects all discovered tables automatically. Explicit mappings
avoid guessing keys or aliases:

```json
{"tables":[{"name":"example","integration_id":"UUID-FROM-INVENTORY","target_table":"example",
"target_schema":"public","keys":[{"source":"ID_A","target":"id_a"},
{"source":"ID_B","target":"id_b"}],"source_date":"DATE_CHANGED",
"target_date":"date_changed","source_temporal_mode":"oracle_native_local"}]}
```

`source_temporal_mode` is required: use `oracle_native_local` for Oracle
`DATE`/`TIMESTAMP` columns (naive values mean `Europe/Ljubljana`), or
`iso8601_text` only for offset-bearing ISO-8601 text. Target values use the
documented `postgres_timestamp` contract. Composite keys are deliberately
limited to finite integer/`Decimal` values: text/UUID keys are rejected rather
than risking an invalid cross-database merge under different collations.

## 2. Audit the selected tables

```sh
.venv/bin/kn-delta-audit audit --environment test \
  --selection selected_tables.json \
  --as-of '2026-08-07T10:00:00+02:00' \
  --limit 20 --output-dir artifacts
```

`audit` requires an offset-bearing `--as-of`, and compares only
`DATE_CHANGED < as_of`.  It writes an ignored directory containing an audit
manifest, report, and bounded (default 20) JSONL samples. `--limit` changes
only samples. `--export` writes full rows only if every requested category is
at most 1,000 rows; use `--allow-large-export` to intentionally exceed that
guard.

## Repeated runs and database impact

- There is **no data cache**. A repeat intentionally reads live data again,
  because a cached delta result could be stale.
- Each normal audit executes exactly one saved KN integration key/date stream
  and one PostgreSQL target key/date stream per selected table. Both streams
  include all rows, are ordered by the numeric composite key, and are merged
  locally; this globally validates null/duplicate/order problems and classifies
  `DATE_CHANGED < as_of` without extra post-cutoff lookups.
- `discover` is cheap relative to audit: one metadata query, no KN access.
- The audit streams rows in batches of 1,000 and initially fetches only the
  composite key and date. It does not use `OFFSET`, load whole key sets into
  memory, or fetch full payloads unless `--export` is explicit.
- `--limit` reduces artifact examples, **not** source scan workload.
- `--export` is the heavy mode: only after exact delta counts are known and
  under the cap, it re-runs bounded per-key reads for the actual delta keys.
  It never streams full-table payloads or writes a table spool. Evidence is a
  later re-read (its timestamp is recorded), so it is not a global snapshot.

Recommended repeat workflow:

1. Run `discover` once to build/review the table inventory.
2. Keep `selected_tables.json` small; add tables gradually.
3. Reuse a deliberate `--as-of` only when reproducing one investigation.
4. Save the generated `manifest.json` and report instead of rerunning merely
   to inspect old results.
5. Use a new cutoff for a new live audit, and run the no-export audit before a
   full export.
