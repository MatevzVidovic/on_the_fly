# Integration Repair

Build a small standalone Python tool in this directory to repair existing KN Oracle delta integrations in LIFT. Keep the implementation straightforward, read the integration definition from LIFT, and use SQLite to prepare and apply one repair run at a time. Full-sync integrations are outside scope because they do not need this repair.

## Run flow

1. Run the regular LIFT integration immediately before repair.
2. Prepare a repair run for its integration UUID. Capture the current `last_changed_datetime` as the fixed cutoff and assign the repair run its own UUID.
3. Review the prepared additions, removals, and warning counts in SQLite.
4. Apply that saved run.
5. Run the normal integration later; its completion handling will clear map caches.

Normal integrations writing this table stay stopped during preparation, review, and application. The target table otherwise remains unchanged except for this tool's writes. Other parts of the system continue working. The integration SQL, mappings, and configuration also stay unchanged throughout the run.

These are operational assumptions. Do not implement table locking, configuration-change detection, or configuration versioning. Do not change the normal integration's watermark or processing status.

## Prepare

Read the existing integration metadata as FMP does: target table, saved source SQL, and enabled field mappings. Use the mapping marked `api_id` for the source record key and the mapping marked `api_last_sync_field` for the change time. Source keys retain their defined meaning and type; they are distinct from the integration UUID and the LIFT row UUID. Column names need not literally be `id` or `date_changed`.

Execute the saved Oracle integration query and inventory its keys/change times. Inventory LIFT using the corresponding mapped fields. Upserts and LIFT inventory are bounded inclusively by `change_time <= cutoff`. Keep the complete Oracle key inventory to distinguish absent keys from existing keys newer than the cutoff.

Compare by integration key:

| Source and LIFT within the cutoff | Action |
| --- | --- |
| Same key and same change time | Correct; do nothing. Do not compare other payload fields. |
| Source key missing from LIFT | Add to `addition_diff` for upsert. |
| Same key, LIFT change time older | Add to `addition_diff` for upsert. |
| Same key, LIFT change time newer | Log, skip, and count a warning. |
| LIFT key absent from the complete Oracle query result | Add to `removal_diff`. |

A source key beyond the cutoff proves existence: leave its LIFT row alone and do not upsert it. Such rows were observed during the Deli audit, so the earlier assumption that running normal integration first prevents this case does not hold.

The cutoff defines a boundary on the current query result; it is not an Oracle historical snapshot. LIFT rows beyond the cutoff are left alone. A date mismatch on an existing key is repaired by upsert, not by independently deleting its previous pair.

Stop preparation with a clear error for missing or ambiguous key/change-time mappings, a missing watermark, duplicate keys, or NULL keys/change times. NULL values must not disappear silently through the cutoff predicate. Stop for unsupported location transformations, payload decorators, or custom hooks beyond the behavior explicitly supported or deliberately deferred here.

Inventory reads are streamed with bounded memory. Apply must refuse an unfinished preparation. Preparation resumes by explicit repair UUID. Commit each Oracle batch together with its last native key and row count; record source completion separately. Commit each LIFT comparison page together with its last eligible native key, row count, differences, seen flags, and warnings. Reuse completed source acquisition and preserve the original cutoff. Resume key-ordered scans from the checkpoint; it is accepted that restarting Oracle opens a new snapshot and will not revisit changes below the checkpoint. New preparations still create fresh runs. `--only-src` stops after Oracle export, with preparation unfinished until the LIFT stage runs.

## Apply

Use a default page size of **10,000**, defined in code.

For each pending addition, fetch the full source payload using the saved integration SQL. Require its key/change-time pair to match the prepared pair. If the row disappeared or its date changed, log and skip it, mark the entry processed, and count a warning.

Upsert by the integration's mapped key. Update an existing row in place, retaining its LIFT UUID; generate a UUID v1 for a new row, as FMP does. An existing LIFT row with a newer date is logged and skipped. This also prevents an upsert candidate from overwriting a same-key row outside the target cutoff.

Apply saved removals directly, without rechecking Oracle membership. Store the target row UUID on removal entries so deletion addresses the prepared target row.

Commit PostgreSQL batches before recording their completion in SQLite. If a destination batch committed but its completion markers were not saved, it may be replayed. Upserts and deleting an already-absent row must be safe to replay.

On an execution error, stop. Running apply again resumes the remaining entries of that run. Skipped entries are finished for the run and have no retry or reconsideration workflow. A later fresh prepare/apply run is how to reconcile again.

Print record-specific warning reasons and a final warning summary. A run may finish with warnings. Repair progress belongs to its own UUID, not the normal integration's metadata.

## Match FMP's row-write behavior

**Mappings and NULLs.** Apply enabled source-to-target mappings. Omit NULL or missing source values, preserving existing values during updates as FMP does.

**Dates.** Preserve the source query's wall-clock timestamp values exactly as FMP stores them in timezone-less target fields, including fractional seconds. Compare the source date, LIFT date, and captured cutoff in that stored representation. Do not introduce implicit Python/PostgreSQL session-timezone conversion. Follow the saved query's output; some queries explicitly return UTC, so there is no blanket conversion of all dates to Ljubljana time or UTC.

**Audit history and row metadata.** Do not write separate audit-history records, matching `ignore_audit=true`. Populate row metadata like FMP's UPSERT path: overwrite both `created_at` and `updated_at` with the run's `maxDate`, and both `created_by` and `updated_by` with the initiating LIFT user UUID hardcoded as `REPAIR_USER_ID` in `definition.py` (`955ee6d4-d98e-11f0-bd04-de28270b37c5`, mvidovic), saved in SQLite when prepare creates the run (FMP’s data manager replaces the lower-level NIL placeholder with its authenticated user), including on updates. Capture `maxDate` as the first apply-start timestamp, persist it and the user UUID in SQLite, and reuse them across batches and restarts. Reject a different user UUID on resume.

**WKT geometry.** Running the saved Oracle SQL produces the source geometry representation. Reproduce FMP's target-side WKT conversion with `ST_Transform(ST_GeomFromText(value, source_srid), target_srid)`, using the configured source and destination SRIDs. Wrap that expression in `ST_Multi` when the destination geometry type contains MULTI. Bind source values as parameters.

## Completion work

After applying entries, perform FMP's point-layer sampling fill so missing `__mod` values are populated from `gid % 1000`.

Leave materialized views alone; do not refresh them or create unique indexes. Later normal integrations perform their usual refresh work.

Do not add recursive dependency traversal. If completion work fails, keep the run unfinished; rerunning apply can repeat completion work after already-processed entries.

Do not clear map caches. The later normal integration handles this. Temporarily stale cached map displays are accepted until that integration completes.

## Minimal SQLite shape

Keep the originally requested four-table shape. These names and fields describe the implementation to review; small bookkeeping columns may support streaming and batch completion.

| Table | Contents |
| --- | --- |
| `integration_transfer` | Repair UUID, integration UUID, creation timestamp (UTC), target attribute-table name, cutoff, preparation/application completion state, prepared upsert/delete counts, first apply-start timestamp, and warning counts. |
| `remote_ids_and_date_changed` | Repair UUID, integration key, and source change time; a seen-in-LIFT marker can support streamed comparison. |
| `addition_diff` | Repair UUID, integration key, prepared source change time, and processed marker. Covers inserts and updates. |
| `removal_diff` | Repair UUID, target row UUID, integration key, prepared target change time, and processed marker. |

All child rows belong to their repair UUID. Do not store full source payloads or create a second persistent LIFT inventory table.

## Implementation shape

A small `repair.py` provides `prepare <integration_uuid>` and `apply <repair_uuid>` commands. Use direct Oracle/PostgreSQL access and SQLite, with environment-based connection settings. Keep the integration discovery, comparison, mapping, and batch handling easy to follow. The implemented roles and setup instructions are in [README.md](../README.md).

## Measured performance paths

An optional integration-UUID entry in `oracle_keys.json` provides integer source
key component column names and a separator. Payload fetch uses numeric tuple
predicates on those saved-query output columns; without an entry it uses the
original integration-key predicate. This does not change inventory ordering.
Apply reads existing target UUIDs/change times for a whole page in one query and
pipelines its writes, checking pipeline completion before PostgreSQL commit and
SQLite progress marking. Preserve existing metadata and newer-date semantics.
Normal runs record phase timings. Read-only benchmarks and disposable local
comparison trials are documented in `BENCHMARKS.md`; they never apply repairs.
