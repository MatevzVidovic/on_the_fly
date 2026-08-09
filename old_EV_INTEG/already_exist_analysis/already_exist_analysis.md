# Existing EV historical-table analysis

This compares the fresh Oracle estimates in `research/approx_table_sizes.csv` with the LIFT PostgreSQL table sizes and approximate row counts supplied on 2026-08-05. Row-count differences are diagnostic only: Oracle statistics and PostgreSQL `reltuples` are approximate and may have been collected at different times. They are not a substitute for exact `COUNT(*)` using the same filter.

| EV source table | Oracle research estimate | Existing LIFT historical target(s) | LIFT approx. rows | LIFT physical size | Difference / coverage | Advance analysis |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `DST_PRIPIS_PODATKI` | 1,935,694 | None found | — | — | — | Missing target; create/analyse a new historical integration. |
| `JN_DEL_STAVBE` | 11,133,941 | `ev_del_stavbe_h` | 9,941,382 | 2,490 MB | -1,192,559 / 89.29% | Existing data is materially behind the current Oracle estimate; inspect status/filter and latest `date_change`. |
| `JN_DEL_STAVBE_ENOTA` | 11,673,062 | `ev_del_stavbe_enota_h_2020_2024`; `ev_del_stavbe_enota_h_2025_danes` | 6,902,641 + 4,747,777 = 11,650,418 | 1,229 MB + 1,258 MB = 2,487 MB | -22,644 / 99.81% | Very close to the Oracle estimate; still verify the split boundary, overlap/gap, omitted `PODATKI`, and 2025+ delta configuration. |
| `JN_PARC_DEL` | 18,238,911 | `ev_parc_del_h` | 14,801,009 | 2,943 MB | -3,437,902 / 81.15% | Largest non-split shortfall; investigate before relying on the existing table. |
| `JN_PARC_ENOTA` | 90,939,157 | `ev_parc_enota_h_2020`, `_2021`, `_2022`, `_2023`, `_2024`, `_2025_danes` | 88,248,911 total | 21,542 MB total | -2,690,246 / 97.04% | Looks broadly populated, but exact annual range checks are required. |
| `JN_PARCELA` | 26,286,228 | `ev_parcela_h` | 26,018,648 | 8,169 MB | -267,580 / 98.98% | Close to the Oracle estimate; validate freshness and historical projection. |
| `JN_PE_DST` | 213,204 | `ev_pe_dst_h` | 195,225 | 47 MB | -17,979 / 91.57% | Existing POC candidate, but it is incomplete relative to research. Analyse before bootstrap/reload. |
| `JN_PE_PARC` | 193,584 | `ev_pe_parc_h`; also `ev_h_pe_parc` | 170,292; `ev_h_pe_parc` has no estimated rows | 41 MB; 16 kB | -23,292 / 87.97% for `ev_pe_parc_h` | Use `ev_pe_parc_h` as the likely real target; `ev_h_pe_parc` appears empty/placeholder and must not be used without schema verification. |
| `JN_POSEBNA_ENOTA` | 45,445 | `ev_posebna_enota_h`; related `ev_posebna_enota_pod_h` | 35,768; 84,926 | 39 MB; 22 MB | -9,677 / 78.71% for direct target | Direct target is significantly behind. `_pod_h` is a different/detail dataset, not an alternative row-count match. |
| `JN_PROSTOR` | 4,739,443 | `ev_prostor_h` | 4,550,946 | 830 MB | -188,497 / 96.02% | Close, but validate freshness and status filtering. |
| `JN_STAVBA` | 3,246,415 | `ev_stavba_h` | 2,021,174 | 648 MB | -1,225,241 / 62.26% | Material shortfall; high-priority investigation before reuse. |
| `PARC_PRIPIS_PODATKI` | 8,584,239 | None found | — | — | — | Missing target; create/analyse a new historical integration. |

## What already exists

- Apparent historical targets exist for 10 of the 12 required source tables.
- `DST_PRIPIS_PODATKI` and `PARC_PRIPIS_PODATKI` have no apparent LIFT historical target.
- The three POC targets already exist, but all have fewer approximate rows than the Oracle research statistics. They should be analysed rather than blindly treated as empty targets.

## Important observations

1. The source and LIFT numbers were measured at different times: Oracle `LAST_ANALYZED` values in `research/approx_table_sizes.csv` range from 2025 to 2026, and the supplied PostgreSQL values are approximate. Small differences may be timing/statistics; the large gaps below are still worth investigating.
2. The most concerning direct-target coverage is `ev_stavba_h` (62.26%), then `ev_posebna_enota_h` (78.71%) and `ev_parc_del_h` (81.15%).
3. `ev_h_pe_parc` is only 16 kB with no estimated rows, while `ev_pe_parc_h` contains 170,292 rows. This strongly suggests a placeholder/empty table or an abandoned integration; inspect its schema and dependencies before any write.
4. `ev_posebna_enota_pod_h` has more rows than `ev_posebna_enota_h`, so it is not a direct duplicate of the required source table. Treat it as a distinct subordinate/detail relation.
5. The `JN_PARC_ENOTA` yearly targets total 88.25 million rows against the fresh Oracle estimate of 90.94 million. This supports the intended split design, but the `2020` table is much larger than the later annual tables; verify it is truly one calendar-year partition and not a legacy catch-all range.
6. For every candidate target, run exact comparable checks before loading: `COUNT(*)`; `COUNT(DISTINCT synthetic_pk)`; min/max `valid_from`, `valid_to`, and `date_change`; count of `JN_STATUS = 'X'` where that source column exists (expected zero after filtering); and the exact source/LIFT schema and unique-key contract.
