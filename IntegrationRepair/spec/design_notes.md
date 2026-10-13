# Repair design decisions

This document records decisions and supporting evidence from the design interview. The consolidated implementation requirements are in [basic_spec.md](basic_spec.md).

## Settled

- The tool is standalone Python in IntegrationRepair.
- Repair covers KN Oracle delta integrations only. Full-sync integrations do not need repair and are excluded.
- Integration definitions come from the existing LIFT metadata, including saved SQL and ID/change-field mappings.
- The integration key is the configured source record ID, not the target row UUID or integration UUID.
- A matching integration-key/change-time pair in LIFT is considered correct. Repair does not compare the remaining payload fields.
- A run has two explicit steps: prepare the differences, then apply the prepared run.
- Full source payloads are fetched during apply. Require the prepared key/date pair to match; a changed or missing source row is skipped, logged, and reported in the final warnings. Skips are finished for this run, with no retry scheduling; a later fresh run can reconcile again.
- Missing keys and keys with an older LIFT change time belong in `addition_diff` and are upserted using FMP-equivalent behavior.
- Existing rows are updated in place. FMP normally retains their target UUID; the inspected KN integrations have no enabled mapping into `id`.
- If LIFT's change time is newer than Oracle's, log and skip the record, then warn and report the count at process end.
- Remote repair membership comes from the current integration query bounded inclusively by the run cutoff. Absence from this bounded membership permits removal, including a key whose current Oracle date is now beyond the cutoff.
- LIFT rows are filtered to the same inclusive cutoff. Target rows beyond it are outside comparison and are left alone.
- Apply saved removals directly, without an Oracle membership recheck.
- This removal is accepted because normal LIFT integration is expected to restore the newer row later and normal integration is run immediately before repair, which is expected to prevent this case in practice. See ADR 0002.
- No locking is needed. Integrations writing the target table are kept stopped throughout preparation, review, and application; the target is otherwise assumed unchanged. The rest of the system stays operational.
- The initial spec requires a SQLite run record and remote key/date, removal-difference, and addition-difference child tables. The run stores its UUID, integration UUID, and cutoff taken from the integration's current high-water mark.
- Missing key/date mappings, missing watermarks, duplicate keys, and null keys/dates fail preparation with a clear error.
- The default page size is a code constant of 10,000. Apply commits batches, records completed entries in SQLite, stops on failure, and resumes remaining work when rerun. Committed work without saved completion markers may be replayed safely.
- The normal integration's watermark and processing status are left untouched.
- No separate audit-history writes are made. Target-row metadata follows FMP's system integration path: both timestamp fields use run `maxDate` and both user fields use the NIL UUID, including on updates. `maxDate` is the first apply-start timestamp stored on the run and reused on restarts.
- Scalar NULL or missing source values are omitted from mapped payloads, matching FMP.
- After apply, resolve and refresh dependent materialized views using FMP's metadata rules and perform the point-layer `__mod` fill.
- WKT mappings reproduce FMP's PostGIS parsing, source/destination SRID handling, and MULTI conversion after running the saved Oracle integration SQL.
- Repair does not clear map caches. A later normal integration handles clearing; temporarily stale map displays are accepted until then.
- Unsupported location transformations, payload decorators, and other custom hooks stop preparation with a clear explanation, except for behavior explicitly supported or deliberately deferred by this spec.
- Integration configuration is assumed unchanged across prepare/apply. No configuration-change detection or versioning is added.
- Preserve FMP's source wall-clock timestamp representation for writes, pair comparisons, and cutoff filtering, including fractional seconds. Avoid implicit Python/PostgreSQL session-timezone conversion and follow any UTC projection in the saved SQL.

## Review state

All interview choices are settled, and the user authorized implementation. The tool implements the agreed four-table flow in five Python files, with the seven logical roles described in [README.md](../README.md). The worker/reviewer loop finished with no remaining actionable correctness or simplicity findings; 16 tests pass. Read-only PostgreSQL checks covered metadata, WKT conversion, timestamp binding, and preparation of generated write statements without execution. Oracle execution and live writes remain unverified.

## Verified backend behavior

Primary implementation references: [integration payload handler](/Users/matevzvidovic/fmp/app/_AttributeTables/Services/Facade/AttributeTableIntegration/Processing/Core/ProcessIntegrationPayloadFacadeService.php:99), [upsert manager](/Users/matevzvidovic/fmp/app/_Util/Managers/BaseModelManager.php:71), [row metadata manager](/Users/matevzvidovic/fmp/app/_AttributeTables/Managers/AttributeTableDataManager.php:43), [WKT handler](/Users/matevzvidovic/fmp/app/_AttributeTables/Services/Transformation/Location/WktLocationTransformationService.php:33), and [materialized-view resolution](/Users/matevzvidovic/fmp/app/_AttributeTables/Services/Activities/SyncMaterializedViewActivity.php:37). Earlier timestamp controls are recorded in [KN preflight](../../KN_deltas_reason/reconciliation/PREFLIGHT.md).

- `ProcessIntegrationPayloadFacadeService::handle()` uses the configured target key for UPSERT. It supplies both `created_at` and `updated_at` from the integration run's `maxDate`, including on updates.
- `applyFieldMapping()` normally omits null or missing remote values. Copying those values as SQL NULL would behave differently.
- `BaseModelManager::upsert()` looks up an existing row by the mapped key, updates it by its target UUID, or generates a UUID v1 for a missing row unless the mapped payload supplies `id`.
- `AttributeTableDataManager::save()` overwrites both audit-user fields with the current FMP user identity. System CLI integrations use the NIL UUID; user-triggered integrations can use their initiating user's UUID. Repair uses the NIL identity.
- Geometry transformations, save decorators, and application events may add behavior beyond direct database writes. The spec supports WKT, point sampling fill, and direct materialized-view refresh; unknown behavior fails preparation and cache clearing is deferred.
- `ignore_audit=true` prevents separate audit database history writes; it does not suppress target-row metadata or other application event listeners.
- Normal completion also fills point-map sampling metadata (`__mod`), refreshes dependent materialized views, and clears map caches. A Python tool bypasses these completion listeners unless it explicitly reproduces their effects.
- WKT geometry handling has two stages: the saved Oracle SQL produces geometry text, then FMP's WKT handler builds a PostGIS expression using `ST_GeomFromText`, `ST_Transform`, and `ST_Multi` for MULTI targets. Running the saved Oracle SQL covers the first stage only.
- The repository's nginx template configures `proxy_cache_valid 200 204 30d`, and the GeoServer WMS cache key includes `style_json_updated_at`. The backend cache-clear listener bumps that layer timestamp and sends a SyncServer action to connected clients. These are verified source defaults; deployed expiry settings and upstream overrides were not inspected.
- A normal integration's completion listener invokes table-layer cache clearing. The next normal integration can therefore invalidate old cached tiles; its timing is not established by this design interview.
- FMP's Oracle fetch path passes timestamp strings through to PostgreSQL. For `timestamp without time zone`, the timestamp's wall-clock fields are retained and the offset is discarded. Python should explicitly reproduce that stored representation rather than let an aware datetime be converted through a PostgreSQL session timezone.
- Earlier matched KN source/target controls and audited source payloads corroborate wall-clock storage. Some saved integration SQL explicitly projects dates in UTC, so a blanket assumption that all mapped timestamps are Ljubljana time would be incorrect; the saved SQL's output representation matters.

## Read-only test database findings (2026-10-13)

- Metadata was inspected with `PG_DATABASE_SYSTEM=fmp` using the provided read-only access.
- All 23 inspected `kn_%` target integrations use the KN ORACLE connection and have one enabled key mapping; 22 have one enabled change-time mapping. `kn_nep_sifranti` has no change-time mapping and no stored high-water mark.
- Each inspected KN target has one configured integration, and none has an enabled mapping into target `id`. This does not independently establish whether any manually created rows exist.
- Sixteen enabled location mappings use WKT, with source and target SRID 3794. Target shapes include POINT, POLYGON, MULTIPOLYGON, and MULTILINESTRING.
- No per-table `payload_decorators` value was found for these KN tables. Global decorator/event config files were empty; the spec defines the supported boundary if unsupported behavior is encountered later.
- The three inspected target tables (`kn_nep_deli_stavb_h`, `kn_nep_etaze_h`, `kn_nep_hisne_stevilke_h`) have unique business-key indexes and UUID primary keys. UUID, `created_at`, and `created_by` require explicit values; they have no database defaults. Their `datum_sys` fields are nullable timestamps without time zone.
- Catalog estimates put each of these tables above one million rows. Inventory reads and payload application should therefore be streamed and bounded in memory.
- All inspected KN integrations have `is_full_sync=false`; `kn_nep_sifranti` still lacks the key/date/watermark shape required by this repair.
- Current KN metadata contains configured create/update/delete events that refresh dependent materialized tables. Examples include `kn_nep_hisne_stevilke_h` feeding `kn_nep_naslovi_view` and `kn_nep_etaze_h` feeding `pp_kn_deli_stavb_mv`. Direct Python writes would not invoke these configured PHP events.
- Active `sql_related_table` source subscriptions confirm dependent materialized targets independently of the per-record event settings. Normal integration completion has a separate refresh listener for these subscriptions.
- No configured KN `default_first_result` relationship fills, integration `after_sync_events`, or `prevent_materialized_view_refresh` flags were found in the current test metadata.
