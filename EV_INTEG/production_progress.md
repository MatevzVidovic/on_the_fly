# EV production integration progress

Updated: 2026-09-22. This records the manual LIFT walkthrough and the latest saved production report (2026-08-17). It is not a fresh production inspection.

“Done — user confirmed” means the user explicitly said the integration is done. “Walked through — verify” means instructions were given and the user moved on; successful execution and current correctness have not been demonstrated. A request for the next table is not proof of a successful run. The two explicitly completed integrations remain done in this tracker despite older failures in the August report.

## Progress for all 12 targets

| Source | Production target | Current walkthrough status | Remaining work / evidence needed |
| --- | --- | --- | --- |
| `DST_PRIPIS_PODATKI` | `ev_dst_pripis_podatki_h` | **Done — user confirmed** | Include in final production verification. |
| `PARC_PRIPIS_PODATKI` | `ev_parc_pripis_podatki_h` | **Done — user confirmed** | Include in final production verification. |
| `JN_PE_PARC` | `ev_pe_parc_h` | Index explicitly confirmed; LIFT walked through — verify | Confirm saved SQL/settings, successful delta run, and source/target verification. Watermark mismatch existed in August. |
| `JN_PE_DST` | `ev_pe_dst_h` | Walked through — verify; a failed execution was supplied | Supplied failure used locked `GURS ORCL` account. Confirm saved `KN ORACLE` connection and a subsequent successful run; verify index, watermark and data. |
| `JN_POSEBNA_ENOTA` | `ev_posebna_enota_h` | Walked through — verify | Confirm index, connection switch, canonical SQL, watermark and successful run. |
| `JN_PROSTOR` | `ev_prostor_h` | Walked through — verify | Confirm index, connection switch, canonical SQL, watermark and successful run. |
| `JN_STAVBA` | `ev_stavba_h` | Walked through — verify | Confirm index, canonical SQL/name, successful run and data. Watermark equality passed in August; that alone does not prove complete data. |
| `JN_PARC_DEL` | `ev_parc_del_h` | Walked through — verify | Confirm index, connection switch, canonical SQL, watermark and successful run. |
| `JN_DEL_STAVBE` | `ev_del_stavbe_h` | **Current table — in progress** | Confirm index/settings; inspect current watermark and target dates before catch-up; verify after completion. See the 6.9 million explanation below. |
| `JN_PARCELA` | `ev_parcela_h` | Instructions given; treated as pending after size-order correction | Confirm whether earlier instructions were applied; otherwise index, connection switch, canonical SQL, watermark and run remain. |
| `JN_DEL_STAVBE_ENOTA` | `ev_del_stavbe_enota_h_2025_danes` | **Pending — 2025 onward only** | Measure scoped source; validate existing target; unique key/index; create integration if still absent; configure safe initial/delta behavior; run and verify. August report found no integration. |
| `JN_PARC_ENOTA` | `ev_parc_enota_h_2025_danes` | **Pending — 2025 onward only** | Measure scoped source; validate existing target; unique key/index; repair SQL and first-run metadata; run and verify. August report found invalid SQL and a null `last_sync_start`. |

After the current `JN_DEL_STAVBE`, the next non-split table is `JN_PARCELA`. Choose the order of the two enota targets from their actual 2025+ workload, not their all-years research size. Successful workflow completion should be followed by data verification; checking only the maximum date cannot prove that older rows are complete.

## Where the 6.9 million number came from

Source: [saved production report](src/check_all/reports/state_report_prod_20260817_102123_072899.md), section `ev_del_stavbe_h`. The [checker implementation](src/check_all/check.py) counts rows returned by the integration SQL with the LIFT time predicate; it does not calculate this figure from table size statistics.

| Measurement | Value | Meaning |
| --- | ---: | --- |
| Research `NUM_ROWS` | 11,133,941 | Whole Oracle table statistics, last analyzed 2026-07-24; not the delta scope. |
| Report source count | 11,049,211 | Source query population recorded by the August checker; includes integration joins/filtering. |
| Report target count | 9,940,024 | Rows recorded in the production target. |
| Source count minus target count | 1,109,187 | Net count difference; not an exact missing-key count and not transfer volume. |
| LIFT delta preview | **6,935,375** | Source rows selected from the saved watermark through the checker start. Includes rows already present that can be updated/replayed. |
| Strictly newer than watermark | 6,934,829 | Separate source count using a strict lower bound. The checker does not impose the preview's upper bound on this separate count. |

The preview used the recorded watermark `2025-05-10 09:56:01` and upper bound `2026-08-17 10:21:23.704821`. The target's maximum `date_change` was `2026-01-20 23:59:59.999000`.

Conceptually the preview applies:

```sql
date_change >= saved_last_changed_datetime
AND date_change <= checker_start_time
```

For this integration, `date_change` comes from `COALESCE(rt.CREATED, rf.CREATED)`: closing an older historical version can change its date and cause it to be selected again. The preview does not subtract keys already in PostgreSQL. Therefore millions of delta candidates can coexist with a much smaller net row-count shortfall.

The 6,935,375 was a query count reported in August, not a current September estimate, a byte size, or a count of missing rows. A newer maximum date in the target does not establish that every earlier change was loaded. Do not advance the watermark simply to reduce the preview count.

## Enota sizing: what we have and what is still missing

The [research estimates](research/approx_table_sizes.csv) use `ALL_TABLES.NUM_ROWS * AVG_ROW_LEN`. They have no revision-date or status filter, and are not sized for the selected columns after omitting `PODATKI`.

| Source / target | Available measurement | Scope and limitation |
| --- | --- | --- |
| `JN_DEL_STAVBE_ENOTA` | 11,673,062 rows; 13.111 GB | Whole Oracle table statistics, all years; not the 2025+ export. This estimate is present in the current research files; the earlier conversational claim that it was unavailable was outdated. |
| `JN_PARC_ENOTA` | 90,939,157 rows; 41.415 GB | Whole Oracle table statistics, all years; not the 2025+ export. |
| `ev_del_stavbe_enota_h_2025_danes` | Approx. 4,747,777 rows; 1,258 MB | Existing LIFT target figures supplied on 2026-08-05 in the [earlier analysis](already_exist_analysis/already_exist_analysis.md). These are target storage/population, not a fresh source count or remaining transfer estimate. |
| `ev_parc_enota_h_2025_danes` | No separate figure found in the saved analysis | The analysis reports 88,248,911 rows and 21,542 MB across all parcel-enota yearly targets together. That total cannot size the 2025+ target. |

Neither enota target has a validated source count or delta preview in the saved August production report: one integration was absent and the other's SQL validation failed. There is no saved measurement here establishing current 2025+ transfer bytes or catch-up rows.

Both canonical LIFT queries already implement the intended scope:

```sql
WHERE j.JN_STATUS <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'
```

They both omit `PODATKI`. The cutoff is the version's start revision (`rf.CREATED` / `valid_from`), not its latest `date_change`. An older version changed after 2025 is not part of these targets unless its start revision is also in 2025 or later. There is no fixed end date: these are ongoing 2025-onward integrations.

- [Building-part enota canonical SQL](src/kn_to_stag_delta_with_delete/ev_del_stavbe_enota_h_2025_danes_lift.sql)
- [Parcel enota canonical SQL](src/kn_to_stag_delta_with_delete/ev_parc_enota_h_2025_danes_lift.sql)

The smaller scope and omitted column can make the work more manageable, but full-table statistics cannot tell us the resulting runtime or transfer size.

## Queries prepared for the next measurements

### Results supplied on 2026-09-22

| Source | Exact eligible source rows (2025 onward, revision joins, status filter) | Exact production target rows |
| --- | ---: | --- |
| `JN_DEL_STAVBE_ENOTA` | 4,866,018 | Pending |
| `JN_PARC_ENOTA` | 25,904,376 | Pending |

These new source counts supersede the absence of scoped counts described in the historical evidence above. They are the full eligible subset, not the remaining delta workload.

The latest supplied target-size result now confirms `database_name = fmp_data_gurs` and resolves both targets. It reports estimated rows of 4,747,853 for building-part enota and 23,049,612 for parcel enota. Their provisional net shortfalls are 118,165 and 2,854,764 rows. Exact target counts remain pending; update counts cannot be inferred from these totals. See [the 2025+ workload comparison](already_exist_analysis/enota_2025_workload.md) for storage figures, assumptions and the distinction between missing rows, updates and replayed rows. The earlier result from database `postgres` is superseded by these measurements.

1. In the PyCharm **KN Oracle** console, run the two statements in [enota_2025_source_counts.sql](research/enota_2025_source_counts.sql) individually. Each returns the exact source population using the canonical joins and filters. These read actual source rows and can take time; they are not metadata-only size queries. Export the results manually. Counts describe the entire eligible subset, not the remaining delta.
2. In **production PostgreSQL / fmp_data_gurs**, run [enota_2025_target_sizes.sql](research/enota_2025_target_sizes.sql). It returns current catalog row estimates and target storage for just the two 2025+ tables. Missing tables remain visible. Existing target storage is not a prediction of remaining transfer bytes.
3. With those results and each integration's current watermark, decide whether the existing data supports a delta catch-up or needs a scoped backfill/reconciliation. In particular, a null `last_sync_start` caused the checker to predict a full run of the integration query; setting a timestamp arbitrarily is not proof that an initial load is complete.

After manual changes/runs, the existing checker can verify a selected target. From `EV_INTEG`, for example:

```sh
.venv/bin/python src/check_all/check.py --environment prod ev_del_stavbe_h --refresh-data
```

It is read-only against the databases but can perform substantial source/target scans. No database queries or integration executions were performed while creating this progress document; the prepared measurement SQL has not been tested against the live databases.
