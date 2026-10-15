# EV parcela: post-apply audit — 15 October 2026

Run: `03ff3376-0110-4c42-a617-07662100d1bf`.

## Actual apply result

The user's completed apply processed 28,621 upserts in **13.181 seconds**:
Oracle payloads 4.467s; PostgreSQL lookup/upsert phases 7.507s; SQLite progress
0.089s; remaining startup/overhead about 1.118s. No removals or warnings.
These are real writes, superseding the old assumed EV parcela apply range.
The fresh prepare took 935.50s, including Oracle export 270.515s and LIFT
scan/comparison 662.608s. This single table does not establish other tables' rates.

## Stored-value audit

A separate read-only check fetched fresh Oracle payloads for **all 28,621 repaired
keys** and compared **all 19 mapped fields** with staging. Expected values were
cast by PostgreSQL to the actual table column types using `jsonb_to_recordset`;
dates were canonicalized to the tool's agreed wall-clock representation. This
checks stored values rather than Python string formatting. It does not rerun PHP.

- All 28,621 keys exist in both Oracle and staging.
- No Oracle change date differs from the prepared date in this checked cohort.
- Zero mismatches across mapped fields, including keys, numeric values, status,
  valid-from, valid-to and date-change timestamps.
- No source-NULL field has an unexpected non-NULL target value in either checked
  cohort. NULL omission on updates remains the agreed general behavior.
- Columns have the existing shared PostgreSQL types: bigint/integer for IDs and
  codes, exact numeric for areas/coordinates, text for keys/parcel/status, and
  timestamp without time zone for mapped dates. Oracle numbers arrive as strings,
  preserving precision before database casting.
- All 28,621 rows have the saved `mvidovic` actor in both user columns and the
  saved run time `2026-10-15 07:11:43.975687` in both metadata timestamp columns.
- Geometry is NULL on every repaired row. There is no enabled geometry mapping
  for this integration; its coordinates are mapped as numeric attributes.

The control cohort was a deterministic PostgreSQL SYSTEM page sample, limited to
100 rows whose creation time differs from this run. All 100 control payloads also
matched fresh Oracle values. This is a physical-page sample, not a uniform random
sample or proof about every older row. Geometry was NULL in all 100 controls too.

## Are they indistinguishable?

**Business-field representation is consistent in this audit. Metadata identifies
this repair, deliberately.** Repaired rows carry the user UUID explicitly requested
for repair and the new run timestamp. The older sampled rows have creator
`154f70e2-a1a1-11ef-9574-0242ac120008` and NULL `updated_by`. Their metadata need not
match a later UPSERT: the local FMP payload handler sets both creation and update
metadata for UPSERT, and omits source NULL fields during field mapping.

The repaired cohort contains 21,620 UUIDv1 IDs and 7,001 UUIDv4 IDs; the older
100-row sample contains UUIDv4 IDs. The repair generates UUIDv1 for new rows and
preserves existing IDs on updates, matching the current local FMP UUID-generation
choice. These version counts alone do not prove the exact insert/update split.
No claim of byte-for-byte identity with every historic importer is made.

No data/schema fixes were needed or performed during this audit. Materialized
views and caches remain deferred as agreed. The audit does not verify those views,
application events, every unmapped column or every historic row.

## Recheck remaining differences without refetching Oracle

```sh
cd /Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export
time .venv/bin/python verify_lift.py --store full-ev-parcela.sqlite 03ff3376-0110-4c42-a617-07662100d1bf
```

Expected remaining upserts/removals/warnings: zero if the target remains unchanged.
This full-table check was supplied for the user to run; it was not executed as
part of the field audit. The full repair plan remains applied and unchanged.

Raw evidence: `diagnostics/ev_parcela_value_audit.json`.
Reproduce the field audit: `.venv/bin/python diagnostics/audit_ev_parcela.py`.
Local FMP reference: `ProcessIntegrationPayloadFacadeService.php`, UPSERT metadata
and `applyFieldMapping`; normal deployment's later user stamping can differ.
