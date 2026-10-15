# Staging value audit: EV stavba and prostor

15 October 2026. All remote database access was read-only. SQLite repair files were opened with `mode=ro`. No business rows, metadata, schema, or repair plans were changed.

## Results

| Table | Applied run | Repaired rows checked | Mapped fields per row | Older controls | Value mismatches |
| --- | --- | ---: | ---: | ---: | ---: |
| ev_stavba_h | dd95e254-41ff-46b4-8a35-8b9fa5fd2d52 | 678,878 (all) | 29 | 100 | 0 |
| ev_prostor_h | 1635a1ce-f116-4d93-a2c7-6da4d74b94b7 | 148 (all) | 12 | 100 | 0 |

All requested keys were present in fresh Oracle payloads and staging. No source change dates differed from the dates recorded during prepare. No duplicate target matches were observed. All older controls also matched Oracle.

## What was checked

The audit streamed processed repair keys from SQLite and fetched Oracle payloads sequentially in 1,000-key batches. Every mapped field was converted to the actual PostgreSQL column type using `jsonb_to_recordset`, then compared with its stored target value. This tests exact numeric values, bigint/integer values, text keys/status, and valid-from/valid-to/date-change timestamps without relying on Python display formatting. It does not rerun PHP.

NULL source fields were checked separately for retained non-NULL target values. None were found in either repaired cohort or either control sample. No geometry mapping is enabled for these two integrations, and the checked rows had no non-NULL geometry. This audit therefore makes no claim about WKT/geometry conversion for other integrations.

The original field mapping omits source NULL values on update; the diagnostic reports such retained values separately instead of confusing that intentional behavior with a type mismatch. No such cases needed interpretation in these cohorts.

## Comparison with previous rows

The business fields have the same shared PostgreSQL types and correctly represent the Oracle values in both groups. No conversion correction is needed based on these results.

They are distinguishable by intentional metadata:

- Every repaired row has `955ee6d4-d98e-11f0-bd04-de28270b37c5` (`mvidovic`) in both `created_by` and `updated_by`, as explicitly requested.
- All repaired stavba rows have the saved timestamp `2026-10-15 07:57:49.964356` in both metadata timestamp columns. All repaired prostor rows have `2026-10-15 08:20:35.717657`.
- Older control rows have earlier metadata and other actors; many have NULL update-user metadata. This is not a business-field conversion difference. The local FMP UPSERT handler also assigns both creation and update timestamps, while its field mapper omits source NULLs.
- All repaired IDs are UUIDv1. All 100 stavba controls also have UUIDv1. The 100 prostor controls have UUIDv4. The current local FMP implementation generates UUIDv1 for new rows, so the repair follows that choice; historic UUIDv4 rows remain valid. UUID versions alone do not establish the exact number of inserted versus updated rows or prove preservation of each prior UUID.

The older controls are deterministic physical-page samples (`TABLESAMPLE SYSTEM (0.1) REPEATABLE (17)`, limited to 100 per table and excluding the repair creation timestamp). They are not uniform random samples and do not establish correctness of every older row.

## Evidence and limits

Raw evidence:

- `diagnostics/ev_stavba_h_value_audit.json`
- `diagnostics/ev_prostor_h_value_audit.json`

Reproduce:

```sh
.venv/bin/python diagnostics/audit_ev_values.py --store full-ev-stavba.sqlite dd95e254-41ff-46b4-8a35-8b9fa5fd2d52
.venv/bin/python diagnostics/audit_ev_values.py --store full-ev-prostor.sqlite 1635a1ce-f116-4d93-a2c7-6da4d74b94b7
```

This audits repaired rows and older controls against fresh Oracle query results. It does not scan for all additional differences across the whole tables; the user's separate full stavba `verify_lift.py` run already found zero remaining differences against its saved inventory. Materialized views, caches, application events, and every unmapped column are outside this value audit. EV parcela was audited separately in `ev_parcela_post_apply_audit.md`.
