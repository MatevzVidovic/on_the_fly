# Integration repair

A standalone Python tool for the agreed KN Oracle delta repair. Run the regular integration first, then keep integrations writing the target table stopped through prepare, review and apply. Configuration must stay unchanged. Run the regular integration again later to clear map caches.

```sh
cd IntegrationRepair
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Fill in credentials: PostgreSQL system metadata and data DB, KN Oracle.
.venv/bin/python repair.py prepare INTEGRATION_UUID
sqlite3 repair.sqlite
.venv/bin/python repair.py apply REPAIR_UUID
```

Use `--env /path/to/.env` and `--store /path/to/repair.sqlite` before the command to override paths. Applying writes PostgreSQL. The provided test account is read-only and cannot apply repairs.

Review the run's cutoff, additions and removals before apply:

```sql
SELECT * FROM integration_transfer;
SELECT * FROM addition_diff WHERE run_id='REPAIR_UUID';
SELECT * FROM removal_diff WHERE run_id='REPAIR_UUID';
```

All warnings are printed with the business key. Apply warnings also remain on addition entries. Skips are terminal for this run. Rerun the same apply command after an execution failure; committed but unmarked batches safely replay. Failed prepare runs remain unprepared: start a fresh prepare instead.

## Where each role lives

| File / unit | Responsibility |
| --- | --- |
| `repair.py`: prepare/apply | The complete sequence, rechecks and commit-before-progress order |
| `store.py`: classify | The five comparison rules; no database access |
| `definition.py`: IntegrationDefinition | Read and interpret LIFT metadata |
| `source.py`: OracleSource | Wrap saved Oracle SQL, stream pairs, fetch payload pages |
| `store.py`: RepairStore | Four SQLite tables, local diff construction and durable run progress |
| `target.py`: map_row | FMP field mapping, NULL omission, WKT SQL and row metadata |
| `target.py`: LiftTarget | PostgreSQL inventory, writes, sampling fill and direct view refresh |

No framework, repository interfaces, audit writes, locks or normal integration metadata updates. Unknown custom hooks/decorators and non-WKT transforms are rejected. This tool assumes the inspected FMP global event/decorator configs remain empty; it cannot discover PHP config from PostgreSQL.

Both inventories scan keys/dates and filter by cutoff in Python. This lets NULL and duplicate values fail visibly rather than disappearing behind SQL filtering. Inventories stream 10,000 rows at a time; apply fetches 10,000 payloads, using Oracle IN groups of 1,000. Source names use exact configured casing, like FMP payload access: all 583 inspected enabled KN mappings were uppercase, matching Oracle unquoted result names. Text keys stay text (including leading zeroes); bigint keys stay integers. Timestamps use source wall-clock fields, with six fractional digits matching PostgreSQL; no offset conversion. The first apply timestamp uses APP_TIMEZONE (default UTC), matching the backend. Source timestamps with nonzero precision beyond microseconds are unsupported.

**Performance:** sorting full inventories and per-row SQLite lookups/PostgreSQL upserts favor clear code. Millions of repairs will be slow, especially over a network. Improve these specific loops with bulk joins/writes later if needed. Payload memory is bounded by one 10,000-row page, but large WKT values can make that page substantial.

## Verification

```sh
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

Each production file has a matching `tests/test_<file>.py`, with one simple example for each declared function or method. `tests/test_regressions.py` retains the broader regression checks. The examples use real in-memory SQLite and tiny fixed Oracle/PostgreSQL stand-ins, so no credentials or servers are needed.

Run a single file or step through one example:

```sh
.venv/bin/python -m pytest tests/test_source.py -q
.venv/bin/python -m pytest tests/test_source.py::test_inventory --trace -s
```

In the debugger, `s` steps into a call, `n` runs the next line, and `c` continues. Set a breakpoint inside the production method to skip fixture setup. You can also debug an individual pytest test from your IDE.

Tests cover comparison, mapping, actual generated SQL, stored progress, terminal skips, replay after commit and completion restart. Read-only test metadata was checked against real KN definitions: bigint/text keys, date-time values, WKT mappings, point layers and direct materialized subscriptions. Oracle was unavailable during development, so source SQL/driver execution has not been checked live. The read-only data DB successfully evaluated the configured PostGIS WKT expression and timestamp binding; generated INSERT/UPDATE/DELETE statements were PREPAREd and DEALLOCATEd without executing them. PostgreSQL writes and materialized refresh were not executed against the read-only test database. Verify those on a writable disposable copy before production use.
