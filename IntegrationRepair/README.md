# Integration repair

A standalone Python tool restores missing and outdated LIFT records from KN Oracle delta integrations. Run the normal integration first, then keep integrations writing the target table stopped through prepare, review, and apply. Configuration stays fixed. Run the normal integration later to refresh map caches.

## Run

The existing `.venv` is ready. For a new checkout, create it and install `requirements.txt`. Configure `.env` from `.env.example` with PostgreSQL metadata/data connections and KN Oracle credentials. Apply needs a write-capable account.

Use a fresh SQLite file for this two-table version:

```sh
cd IntegrationRepair
.venv/bin/python repair.py --store ev-test.sqlite prepare INTEGRATION_UUID
.venv/bin/python repair.py --store ev-test.sqlite apply REPAIR_UUID
```

Prepare prints a repair UUID. Review that run before apply:

```sql
SELECT created_at, attribute_table_name, cutoff,
       oracle_count, lift_count, insert_count, update_count,
       expected_needed_deletions, warnings, prepared, applied
FROM integration_transfer WHERE id='REPAIR_UUID';

SELECT * FROM upsert_diff WHERE run_id='REPAIR_UUID';
```

Both row counts use `change_time <= cutoff`. Oracle is counted from the integration query's eligible result. Insert/update counts describe planned actions:

```text
expected_needed_deletions = lift_count + insert_count - oracle_count
```

The estimate stays signed; negative values produce a warning. It provides visibility into expected surplus rows without identifying or changing them. All counts remain preparation totals, even if apply skips entries.

## Roles

| File / function | Owns |
| --- | --- |
| `repair.py`: prepare/apply | Sequence, one-page prefetch, comparison loop, source rechecks |
| `definition.py`: IntegrationDefinition | LIFT metadata and supported configuration |
| `source.py`: OracleSource | Saved SQL, streamed pairs, payload reads, driver values |
| `store.py`: classify | Pure missing/older/equal/newer decision |
| `store.py`: RepairStore | Two SQLite tables, counts, pending entries, progress |
| `target.py`: map_row | FMP mapping, NULL omission, WKT, row metadata |
| `target.py`: LiftTarget | Scoped count, page lookup, upserts, commits, completion |

Prepare compares each 10,000-row source page directly with LIFT and stores only differences. One Oracle worker fetches at most one page ahead while the main thread uses PostgreSQL and SQLite. Every source key/date pair still crosses the network; only difference records are saved locally.

Apply fetches full payloads only for pending upserts, using Oracle IN groups of 1,000. Source-pair changes, missing rows, and newer LIFT dates are terminal warnings. Commit PostgreSQL before SQLite progress; rerun the same apply command after failure. The first apply time is persisted for replay. Completion fills point sampling fields and refreshes direct materialized views.

Text keys retain leading zeroes; integer keys remain integers. Timestamps retain wall-clock fields without offset conversion, using PostgreSQL's six-digit precision. Source timestamps with nonzero precision beyond microseconds are unsupported. Set `APP_TIMEZONE` to the backend value (default UTC).

**Performance:** source sorting and per-row upserts can be slow for millions of records. PostgreSQL needs a key index for efficient page lookups. Memory is bounded by the current/next source pages and current lookup/diff data; apply holds one payload page, which can be substantial for large WKT values.

## Tests and debugger

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_source.py::test_inventory --trace -s
```

Each production file has a matching test file with a simple example per function/method. Broader checks are in `tests/test_regressions.py`. Examples use real in-memory SQLite and small fixed SQL stand-ins; no credentials are needed.

In the debugger, `s` steps into calls, `n` advances a line, and `c` continues. You can also put a breakpoint in a production function and debug its pytest example in PyCharm or VS Code.

Current tests cover counts, signed warnings, page overlap, empty pages, reader failure, mapping, terminal skips, commit-before-progress replay, and completion restart. Earlier read-only checks verified FMP metadata, PostGIS WKT/timestamp expressions, and generated upsert statement preparation. The new page lookup/prefetch flow has been checked locally; live Oracle execution and PostgreSQL writes have not been run for this revision.
