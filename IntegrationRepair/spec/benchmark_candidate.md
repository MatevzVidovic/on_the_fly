# Next repair benchmark candidate

Recommend **`kn_nep_deli_stavb_h` first**, then **`kn_nep_etaze_h`** for geometry. Deli combines a medium inventory with thousands of historical repairs, enough to observe both reconciliation preparation and application. House numbers and prostor predominantly measure preparation; stavba immediately introduces a much larger write workload.

## Historical evidence: 7 October 2026

Exact counts below are from each capture’s primary `summary.json`. Repair scope is **missing + stale at or before that capture’s watermark**; later changes and target-only keys are excluded. These are historical candidate volumes, not a newly prepared plan.

| Table (primary summary) | Source rows | Scoped missing | Scoped stale | Historical upserts | Use |
|---|---:|---:|---:|---:|---|
| [kn_nep_deli_stavb_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_deli_stavb_h/summary.json) | 2,738,125 | 120 | 7,427 | 7,547 | First scalar benchmark |
| [kn_nep_etaze_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_etaze_h/summary.json) | 2,360,318 | 24 | 3,033 | 3,057 | Next geometry benchmark |
| [kn_nep_hisne_stevilke_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_hisne_stevilke_h/summary.json) | 1,448,186 | 2 | 205 | 207 | Too few writes |
| [ev_stavba_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/ev_stavba_h/summary.json) | 3,189,514 | 377,982 | 301,178 | 679,160 | Large write workload |
| [ev_prostor_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/ev_prostor_h/summary.json) | 4,658,219 | 148 | 0 | 148 | Prepare-heavy; too few writes |

Deli’s captured watermark was `2026-10-07 10:48:25`; etaze’s was `2026-10-07 10:44:24`. Both had stable metadata and zero duplicate keys/null change dates in source and target. Deli also had 11 target-only keys; they do not contribute to this upsert-only benchmark. See the linked summaries.

## Original acquisition durations

Durations are `intervals.source_end − source_start` and the equivalent target interval from each SQLite `capture.metadata_json` record, read without scanning inventory tables. The acquisition queries export business keys and change dates, rather than all repair payload fields. These timings do **not** measure current IntegrationRepair prepare or apply.

| Capture metadata | Source acquisition seconds | Target acquisition seconds |
|---|---:|---:|
| [kn_nep_deli_stavb_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_deli_stavb_h/capture.sqlite3) | 15.987 | 22.434 |
| [kn_nep_etaze_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_etaze_h/capture.sqlite3) | 13.640 | 22.285 |
| [kn_nep_hisne_stevilke_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_hisne_stevilke_h/capture.sqlite3) | 9.034 | 12.084 |
| [ev_stavba_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/ev_stavba_h/capture.sqlite3) | 20.204 | 23.682 |
| [ev_prostor_h](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/ev_prostor_h/capture.sqlite3) | 27.385 | 46.044 |

Deli source acquisition ran `2026-10-07T08:59:39.620730+00:00`–`08:59:55.608134+00:00`; etaze ran `08:58:59.980511+00:00`–`08:59:13.620977+00:00`. Captured integration SQL is a direct `nep.DELI_STAVB_H` select with 26 mapped fields for deli; etaze has 15 mapped fields and SDO geometry conversion. The EV candidates join revision tables, so their row counts alone do not establish equivalent source query cost. Sources: each linked capture’s `before.url`, `before.mappings`, and `intervals` fields; [deli acquisition SQL](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_deli_stavb_h/source.sql), [etaze acquisition SQL](../../KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_etaze_h/source.sql).

## Current compatibility checks: 14 October 2026

Read-only live checks using the application’s `.env` reported deli integration UUID `bfe62b52-9aaf-11ef-9c54-0242ac120008`, no geometry/point sampling, and three direct dependent views (`kn_nep_deli_stavb_a`, `kn_nep_deli_stavb_stavbe`, `pp_kn_deli_stavb_mv`). Etaze UUID is `550a20ee-9d03-11ef-8c7b-0242ac120008`, with MULTIPOLYGON WKT and one direct view (`pp_kn_deli_stavb_mv`). Both had cutoff `2026-10-09 14:24:52` and unique business-key indexes. Catalog row estimates were 2,736,693 and 2,359,879 respectively; these are **estimates**, not new exact inventories. These live observations are separate from the linked historical artifacts. A fresh prepare must establish actual current repair counts before deciding whether the write volume still makes a useful benchmark.

An additional read-only check compared the historical missing-key CSV and 20 stale-pair samples against current LIFT. All **120 historical scoped missing keys remain absent**; all **20 sampled stale rows remain older than their captured Oracle counterparts**. This confirms remaining target-side work without assuming Oracle has stayed unchanged since October 7. Fresh prepare still determines the current eligible plan.

## Commands

Keep integrations writing the table stopped during the benchmark; run the normal integration beforehand as usual. From `IntegrationRepair`:

```sh
time .venv/bin/python repair.py --store kn-medium.sqlite prepare bfe62b52-9aaf-11ef-9c54-0242ac120008
# Review the printed counts and SQLite upsert_diff before applying.
time .venv/bin/python repair.py --store kn-medium.sqlite apply REPAIR_UUID
# Verify using a fresh plan after application.
time .venv/bin/python repair.py --store kn-medium.sqlite prepare bfe62b52-9aaf-11ef-9c54-0242ac120008
```

Retain the `real` time and preparation summary for each phase. No integration or repair has been executed as part of this candidate research.

## Measured user-run benchmark: 14 October 2026

Run `658cb459-9556-4f87-96cb-68b4d85c7f5f` prepared in **23.784 seconds** with cutoff `2026-10-14 13:57:49`: Oracle 2,739,514; LIFT 2,739,348; 177 inserts; 7,487 updates; expected surplus 11; zero warnings.

The apply command lasted **135.04 seconds**, committed all 7,664 entries, then failed during concurrent MV refresh because its dependent views had no unique index. Read-only verification found all 7,664 prepared key/date pairs in LIFT and a scoped target count of 2,739,525, exactly the previous count plus 177 inserts. SQLite marked every entry processed and retained the unfinished run state for completion retry.

The user rejected adding MV indexes. Repair now leaves MVs untouched, keeps point sampling completion, and can finish the same run without rewriting processed entries. Normal LIFT completion requests MV refresh separately, but the inspected FMP activity also uses `CONCURRENTLY`, so successful later refresh is not guaranteed by running an integration.

## Measurement and projection

The observed prepare rate is roughly 115,000 source rows/second; the apply command's effective rate is roughly 57 upserts/second, including payload fetching/startup and the failed refresh attempt. These are one-run observations, not guaranteed rates. A comparable scalar workload of 100,000 upserts would be about 29 minutes at that effective rate, plus prepare and any separate application maintenance.

The current implementation overlaps inventory fetching with comparisons during prepare. Apply fetches payloads and writes each batch sequentially. Geometry, row width, source joins, indexes, network latency, cache state, and load limit extrapolation. MV refresh time is no longer part of repair; point-layer sampling work still is.
