# MV refresh WAL planning — 2026-10-28

Read-only production catalogue inspection; no refresh was executed. Scope: 12 EV + 19 KN repaired delta tables, plus the separately repaired huge KN table. The full-sync namenske-rabe table is excluded.

## Recount after the normal Deli integration

Oracle and LIFT each contain **2,743,194 rows**, with total gap 0 and current-watermark cutoff gap 0. This verifies count parity, not all keys or payload values. Saved in `kn_deli_after_lift_counts.json`.

## Main finding

Eight of ten dependent materialized-view definitions select `uuid_generate_v4() AS id`. A newly generated UUID changes the entire output row on each refresh. PostgreSQL concurrent refresh compares complete rows, so unchanged business data does not prevent full result churn for these views. This is an inference from the actual definitions and PostgreSQL 15.7 match/merge implementation. No definitions were changed.

The checked local FMP Temporal activity executes `REFRESH MATERIALIZED VIEW CONCURRENTLY`. A separate older facade executes plain `REFRESH MATERIALIZED VIEW`. Local code is not proof of the exact deployed worker version or refresh mode for every path. The Temporal workflow refreshes its resolved list sequentially, but separate base-table workflows can overlap.

| Materialized view | Heap + TOAST GiB | Index GiB | Total GiB | Random UUID | Estimated rows |
|---|---:|---:|---:|:---:|---:|
| `kn_nep_parcele_a` | 4.554 | 1.522 | 6.076 | yes | 5,850,213 |
| `kn_nep_parcele` | 2.168 | 0.582 | 2.750 | no | 5,830,607 |
| `kn_nep_deli_stavb_stavbe` | 1.750 | 0.270 | 2.020 | yes | 1,931,033 |
| `pp_kn_parcele_mv` | 0.000 | 1.619 | 1.619 | yes | 0 |
| `kn_nep_deli_stavb_a` | 0.931 | 0.532 | 1.463 | yes | 1,917,864 |
| `kn_nep_stavbe_parcele_a` | 1.195 | 0.239 | 1.434 | yes | 1,323,469 |
| `pp_kn_deli_stavb_mv` | 0.000 | 1.349 | 1.350 | yes | 0 |
| `kn_nep_stavbe_obrisi_a` | 0.892 | 0.415 | 1.307 | yes | 1,173,104 |
| `kn_nep_naslovi_view` | 0.088 | 0.098 | 0.187 | no | 580,263 |
| `kn_nep_katastrske_obcine_a` | 0.037 | 0.001 | 0.038 | yes | 2,698 |

The unique inventory occupies **18.24 GiB**, including indexes. The random-UUID subset occupies **15.31 GiB**. These are physical disk sizes, not measurements of WAL. Two pp MVs have zero estimated rows and near-zero heap size but large indexes: dead/index space and changed output size make proportional estimates particularly uncertain.

## Previous numerical scenarios withdrawn

The former 1–3× physical-footprint scenarios were unsupported by measured WAL for this workload and are withdrawn. They are not capacity limits. See [the expanded integration/MV map and WAL research](integration_mv_refresh_wal.md) for the full SQL, identity fixes, amplification mechanisms and Barman guidance. No replacement numerical forecast is asserted without measured deltas.

Server settings: `wal_level=replica`, `full_page_writes=on`, `wal_compression=off`, checkpoint timeout 5 minutes. Full-page images, index maintenance, geometry/TOAST content, bloat, cache and checkpoint timing affect WAL. Concurrent refresh still fully evaluates the query, but its temporary result tables do not create persistent table-data WAL; persistent delete/insert maintenance does. Plain refresh rebuilds contents and indexes instead.

The Barman slot was active with about **10.7 MiB** retained when inspected. This is an instantaneous replication-slot backlog, not total generated WAL, Barman disk usage, or a forecast. Barman can receive WAL while a long refresh is running. The repair script's between-batch Barman guard is not installed inside the normal LIFT MV refresh, and cannot pause a single REFRESH halfway.

## How to obtain a measured estimate

`pg_stat_statements` is installed but not loaded through `shared_preload_libraries`, so historical per-refresh `wal_bytes` were unavailable. No server configuration was changed.

Record `pg_current_wal_lsn()` immediately before and after one deliberate MV refresh and calculate `pg_wal_lsn_diff(after,before)`. That measures all cluster WAL generated in the interval, so avoid simultaneous repair/backfill writes and interpret other background activity as contamination. Refreshes already scheduled by the user are suitable; do not trigger extra refreshes solely for an estimate without accounting for their WAL.

Avoid launching all integration/MV workflows at once. Reducing repeat refreshes and replacing random output IDs with stable IDs are the main potential improvements, but stable IDs require checking FMP links, uniqueness and downstream references; they were not changed here.

Sources: [PostgreSQL 15.7 MV implementation](https://raw.githubusercontent.com/postgres/postgres/REL_15_7/src/backend/commands/matview.c), [REFRESH documentation](https://www.postgresql.org/docs/15/sql-refreshmaterializedview.html), [WAL settings](https://www.postgresql.org/docs/15/runtime-config-wal.html).
