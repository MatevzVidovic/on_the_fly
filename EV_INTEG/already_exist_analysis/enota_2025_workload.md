# Enota 2025-onward: source vs production and expected work

Results supplied on 2026-09-22. Source counts come from the Oracle integration joins with `JN_STATUS <> 'X'` and `rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'`. Production measurements come from PostgreSQL database `fmp_data_gurs`. Source counts are exact at query execution; target row counts are catalog estimates, potentially stale. Measurements are separate snapshots.

## Row comparison

| Oracle source | Production target | Eligible source rows | Estimated existing target rows | Approx. net shortfall / provisional inserts | Target/source count ratio | Updates needed |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `JN_DEL_STAVBE_ENOTA` | `ev_del_stavbe_enota_h_2025_danes` | 4,866,018 | 4,747,853 | **118,165** | 97.57% | Unknown; requires comparison of matching rows |
| `JN_PARC_ENOTA` | `ev_parc_enota_h_2025_danes` | 25,904,376 | 23,049,612 | **2,854,764** | 88.98% | Unknown; requires comparison of matching rows |

The provisional insert figures are `source count - estimated target count`. They assume target keys are unique, every existing target key belongs to the eligible source subset, and the catalog estimates are reasonably current. Under those assumptions, the targets are short by roughly **118 thousand** and **2.85 million** rows respectively. The ratios are count ratios, not verified key coverage.

Extra/out-of-scope target rows or duplicates can hide additional missing source keys. Stale target statistics can shift the estimates in either direction. Even exact total counts would not identify matching keys or how many existing rows changed.

## Existing PostgreSQL storage

| Production target | Table including TOAST (MB) | Indexes (MB) | Total (MB) |
| --- | ---: | ---: | ---: |
| `ev_del_stavbe_enota_h_2025_danes` | 810.39 | 447.09 | 1,257.48 |
| `ev_parc_enota_h_2025_danes` | 4,522.59 | 2,416.15 | 6,938.74 |

These are current allocated target sizes, including existing indexes separately. The query divides bytes by 1024 squared (MiB, labelled MB in its output). These figures are not Oracle transfer sizes or estimates of additional storage. Both canonical integration projections omit `PODATKI`.

## What inserts and updates will actually happen?

There are three different quantities:

- **Missing rows to insert:** source keys absent from the target. The table above gives a provisional estimate only.
- **Existing rows needing an update:** matching keys whose imported values differ. Counts and storage measurements provide no estimate of this quantity. Comparing `date_change` is a useful integration check; a full content comparison is stronger.
- **Rows processed by a run:** the rows selected by LIFT's saved watermark, or all eligible source rows for an initial/full run. This can include unchanged existing rows replayed through the upsert path.

For illustration, if the loader upserts the entire eligible subset and all the assumptions above hold:

| Target | Source rows processed | Approx. inserts | Approx. existing-key matches handled by upsert |
| --- | ---: | ---: | ---: |
| `ev_del_stavbe_enota_h_2025_danes` | 4,866,018 | 118,165 | 4,747,853 |
| `ev_parc_enota_h_2025_danes` | 25,904,376 | 2,854,764 | 23,049,612 |

This is a conditional workload illustration, not a recommendation to run a full sync. Existing-key matches are not necessarily changed rows, nor proof that the loader will issue that many physical UPDATEs. A delta run can process far fewer rows, but its volume cannot be calculated without the current watermark and a source delta count. Missing rows older than that watermark will not be repaired by that delta run.

## Next measurements

1. Obtain exact production counts and check synthetic-key uniqueness using `jn_del_stavbe_enota_pk` and `jn_parcela_enota_pk` respectively. The prepared [target count SQL](../research/enota_2025_target_counts.sql) provides exact totals.
2. Compare source and target keys to measure inserts precisely; compare matching rows' `date_change` (and imported values if needed) to measure updates.
3. Inspect each LIFT integration's actual SQL, `last_changed_datetime`, `last_sync_start`, and sync mode. Count selected delta rows with those bounds before deciding between catch-up and scoped reconciliation.

The August production report found no building-part enota integration, and found invalid parcel-enota SQL plus a null `last_sync_start`. Those historical findings need a current check; the new row counts do not establish that the integration settings have since been repaired.

Sources: user-supplied query outputs, [source count SQL](../research/enota_2025_source_counts.sql), [target size SQL](../research/enota_2025_target_sizes.sql), and the [August production report](../src/check_all/reports/state_report_prod_20260817_102123_072899.md). No live database checks were run to produce this comparison.
