# Huge KN payload fetch speedup

Measured read-only on 2026-10-28 for `kn_nep_ostalo_dejanske_rabe_parcel_h`, using the saved integration SQL and pending keys from run `eb6eef3a-e08f-4e0f-b105-94625718e188`. No repair writes, schema changes, or Oracle hints were executed.

## Cause and change

The query selects `SDO_UTIL.TO_WKTGEOMETRY(GEOM) AS GEOM`, which returns a CLOB. The old reader fetched LOB handles and called `LOB.read()` individually for each geometry. The reader now requests CLOB values as text with the batch through its existing output type handler. Oracle SQL, geometry conversion, numeric and date handling, and apply checkpoints are unchanged.

| Same keys and complete payloads | 100 rows | 1,000 rows |
|---|---:|---:|
| Old individual CLOB reads | 2.580s | 25.833s |
| Batched CLOB text | 0.163s | 0.999s |
| Diagnostic query without geometry output | 0.189s | 0.269s |

Old and new full payload dictionaries matched exactly at both scales, including WKT text. Removing geometry was only a diagnostic; it is not the implementation.

## Query sizes with the optimized reader

| IDs per query | 1,000 total rows | 10,000 total rows |
|---|---:|---:|
| 100 | 1.133s | 11.503s |
| 500 | 0.667s | 4.276s |
| 1,000, first pass | 0.739s | 4.631s |
| 1,000, repeated | 0.520s | 3.415s |

All query sizes returned identical payload hashes within each workload. The 10,000-row sample contained 7,135,850 WKT characters. These are sequential tests with cache effects, not randomized production-wide estimates. Keep the existing 10,000-row apply/checkpoint batches and 1,000-ID Oracle queries.

Additional 1,000-key samples at pending offsets 500,000 and 2,500,000 took 1.069s and 0.340s, respectively. Geometry sizes vary, so this does not guarantee a uniform rate over the entire table.

## Oracle indexes

Source: `NEP_OSTALO.DEJANSKE_RABE_H`. Integration key: numeric `DEJANSKA_RABA_H_ID`.

A valid unique normal index, `DEJANSKE_RABE_H_PK`, covers that single key column. Two additional valid unique composite indexes cover `(DEJANSKA_RABA_ID, POSTOPEK_ID_DO)` and `(DEJANSKA_RABA_ID, POSTOPEK_ID_OD)`. Other indexes cover the operation and related-entity foreign keys; full inventory is saved in the benchmark JSON.

The fetch binds numeric IDs directly. The account lacks SELECT on V$SESSION, so DBMS_XPLAN could not display the actual cursor plan. Index use is not asserted as proven. Fast queries without geometry and the same-query CLOB comparison show that individual CLOB reads were the dominant measured bottleneck. No new index or special key grouping is needed for this fix.

## Estimate and resuming

The old user-observed fetch took 211–283s per 10,000 rows, plus 10–14s PostgreSQL writes: roughly 31–41 hours for five million rows. Optimized fetch samples suggest roughly 3–11s per 10,000, plus the observed writes: provisionally about 2–4 hours, excluding Barman pauses, changing load, and unusually large geometries. Validate using the first resumed production batches; the write side was not benchmarked or changed.

Stop the old apply before restarting. Committed pages are saved in SQLite; an interrupted uncommitted page can be replayed by the existing apply logic. No prepare rerun is necessary:

```bash
bash run_kn_huge_utc_apply.sh
```

Regression suite: 135 passing tests, including the CLOB fetch mapping test. Benchmarks: `diagnostics/benchmark_huge_payloads.py` (old/new equality and timing) and `diagnostics/benchmark_huge_batch_sizes.py` (query sizes and distant pending samples). Both are read-only against remote databases and save reports locally.

Driver documentation: [Fetching LOBs as strings and bytes](https://python-oracledb.readthedocs.io/en/v2.5.0/user_guide/lob_data.html#fetching-lobs-as-strings-and-bytes).
