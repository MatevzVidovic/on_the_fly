# Integration Repair

A small standalone Python tool repairs missing and outdated records from KN Oracle delta integrations in LIFT. Full-sync integrations are outside scope. Records present only in LIFT remain untouched.

## Run flow

1. Run the regular integration, then keep integrations writing this table stopped through prepare, review, and apply.
2. Prepare for an integration UUID. Capture its current `last_changed_datetime` as the fixed inclusive cutoff and create a repair UUID.
3. Review the run counts and planned inserts/updates in SQLite.
4. Apply the saved run.
5. Run the normal integration later to clear map caches.

The target otherwise stays unchanged, and integration SQL/configuration stays fixed. No locks, configuration tracking, or normal integration watermark/status updates are added.

## Prepare

Read LIFT's target table, saved Oracle SQL, and enabled field mappings. Use exactly one `api_id` mapping and one `api_last_sync_field` mapping. Preserve the business key's type; it is distinct from integration and target-row UUIDs.

Count LIFT rows with mapped change time at or before the cutoff. Stream the saved Oracle query's keys/change times, validating and counting the eligible rows as they arrive. The Oracle count is the integration query's result within the cutoff, not its underlying raw tables.

Use 10,000-row pages. One background Oracle reader fetches the next page while the main thread looks up the current page's keys in PostgreSQL and saves differences in SQLite. At most one fetch is outstanding. Empty eligible pages do not end the stream. The cursor is read and closed on its worker; PostgreSQL and SQLite remain on the main thread.

Look up LIFT pairs for the current keys within the same cutoff. Include matching NULL dates so they fail visibly.

| Pair comparison | Result |
| --- | --- |
| LIFT key missing within cutoff | Save an insert. |
| LIFT change time older | Save an update. |
| Same key/date | Correct; compare no other fields and save nothing. |
| LIFT change time newer | Warn and skip. |

Only differences are persisted. No source inventory or full target inventory is stored. Source keys/dates are checked for NULLs and duplicate keys across pages, including rows beyond the cutoff. Matching LIFT keys are checked for duplicates/NULL dates; unrelated LIFT keys are not scanned for validation.

Missing/ambiguous mappings, missing watermark, unsupported transforms, and unsupported custom hooks/decorators fail preparation. Failed preparation stays unfinished and is replaced by a fresh run rather than resumed. Reader errors propagate to the coordinator.

## Run counts

Save creation time in UTC, attribute-table name, cutoff, and these preparation totals:

- `oracle_count`: source query rows at or before cutoff.
- `lift_count`: target rows at or before cutoff.
- `insert_count`: planned missing-key inserts.
- `update_count`: planned older-row updates.
- `expected_needed_deletions = lift_count + insert_count - oracle_count`.

Keep the estimate signed. A negative value is saved, printed as a warning, and included in the warning count. The metric is diagnostic: it assumes planned inserts succeed and does not identify surplus keys or cause row changes. Counts remain the prepared totals after apply; source changes and terminal skips can make actual writes differ.

## Apply

Read pending `upsert_diff` entries in 10,000-row batches. Fetch full source payloads using the saved SQL and require the prepared key/date pair to still match. Changed or disappeared rows are warned, marked processed, and skipped permanently for this run.

Upsert by mapped key, retaining an existing target UUID or generating UUID v1 for a new record. Check the current target date again; newer rows, including same-key rows beyond cutoff, are warned and skipped.

Commit the PostgreSQL batch before saving completion markers and warnings in SQLite. Committed-but-unmarked upserts replay safely. Stop on an execution error; rerunning apply resumes pending entries. Print record-specific warnings and the run summary.

## Match FMP

Omit NULL/missing scalar mapped values so existing values are preserved. Preserve source wall-clock timestamp fields and fractional seconds in the PostgreSQL representation; do not shift them through a session timezone. Follow the saved query's output, including explicit UTC projections.

Write no separate audit history. Set both row timestamps to the persisted first apply-start `maxDate` and both row-user fields to the NIL UUID, including updates. Use the backend's `APP_TIMEZONE` (default UTC) for that first apply time.

For WKT mappings, bind values through `ST_Transform(ST_GeomFromText(value, source_srid), target_srid)`. Wrap with `ST_Multi` for MULTI destination types.

After upserts, fill point-layer sampling fields as FMP does. Completion failures leave the run unfinished so apply can repeat completion. Materialized views and map caches are outside this tool: they may stay stale until maintained separately. Normal LIFT integration completion requests MV refreshes, but the inspected FMP path uses `CONCURRENTLY` too, so missing unique indexes can make that later refresh fail. Repair creates no view indexes and makes no promise that a later integration will refresh these views successfully.

## SQLite and roles

Use a fresh SQLite file; there is no old-schema migration.

| Table | Contents |
| --- | --- |
| `integration_transfer` | Run/integration UUIDs, table name, creation time, cutoff, preparation/application state, preparation counts, first apply time, warnings. |
| `upsert_diff` | Run UUID, encoded business key, source change time, planned action (insert/update), processed marker, warning. |

`repair.py` coordinates the flow; `definition.py` reads metadata; `source.py` reads Oracle; `target.py` maps payloads and reads/writes PostgreSQL; `store.py` owns SQLite and the pure comparison rule. Setup and debugger examples are in [README.md](../README.md).
