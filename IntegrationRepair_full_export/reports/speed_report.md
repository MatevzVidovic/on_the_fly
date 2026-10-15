# Integration repair: speed improvements and storage experiments

14 October 2026 · staging · Python 3.14 · DuckDB 1.5.6 · SQLite 3.50.4

> Configuration update, 15 October: all ten EV composite keys are now configured and sample-checked. See [current key coverage](oracle_key_coverage.md). Configuration prerequisites below describe the original benchmark date; throughput estimates remain unvalidated write scenarios.

## Outcome

Keep SQLite for the current resumable repair store. The biggest verified improvements are fetching Oracle payloads by their original numeric key columns and batching PostgreSQL apply lookups. Pipelined PostgreSQL writes are implemented, but write throughput has not been measured with the read-only account.

The requested RAM-first DuckDB experiment is implemented as a local prototype and tested. Even with one final transaction commit and one final file snapshot, it did not beat SQLite in matched 10k/100k samples. Larger local batches help DuckDB more than reducing commits. No backend migration, inventory-order change, or remote data writes were performed during these experiments.

All estimates below distinguish measured read work from assumed write costs. **Only EV parcela currently has the composite-key JSON fast path configured.** Other large-table estimates are conditional on an efficient indexed payload lookup, and on a future measured PostgreSQL write rate.

## 1. What was measured and how

The live database sessions were explicitly read-only. LIFT's account was verified to have SELECT and no INSERT/UPDATE/DELETE permission. Oracle used a read-only transaction. Remote tests were bounded and sequential; expensive failing text predicates were not repeatedly retried. No shared caches were flushed.

Earlier remote trials used 100/1,000 keys, 10k/100k inventory samples, and initial/middle/late paging anchors. Those JSON reports retain scales, timestamps, result checks, hashes and access-profile information where recorded. Remote latency changed during the investigation; older and newer access profiles must not be treated as one controlled experiment.

The new storage experiment captured one bounded 100,000-key source sample and its corresponding LIFT rows, then reused that cache for all local trials. **No repeated remote acquisition was needed for the storage matrix.** The 10k subset contains 9,994 target rows; the 100k sample contains 99,910. It is not a full target-range capture: target-only cases are covered by local unit fixtures, not claimed as observed in this sample.

Every local variant received identical native-key Python batches, streamed LIFT pages, the same key/date rules and matching commit policies. Each result includes source loading, target-page ingestion, differences, final commit, file close and—where applicable—RAM snapshot creation. Data was reopened and checked after completion. Three repetitions used rotated backend order. SQLite and DuckDB had a 512 MiB cache/engine budget; DuckDB used two threads. SQLite's larger experimental cache and simplified single-run schema differ from the production store. These are bounded engine/algorithm comparisons, not full 26m-row repair executions or strict replicas of production file layout.

## 2. Apply improvements: what each change brought

| Change | Measurement | Interpretation | Status |
|---|---|---|---|
| Batch PostgreSQL existing-row lookup | 100 keys: 7.595s → 0.074s; 1,000: 43.312s → 0.219s | About 103×/198× faster for this **read phase** | Implemented |
| Pipeline PostgreSQL commands | 1,000 SELECTs: 43.312s sequential → 0.184s pipelined | Removes most sequential waits; SELECT proxy, not write throughput | Writes implemented; read-only proxy tested |
| Original Oracle key columns | First controlled 1,000-row payload probe: 0.393s; text predicate failed at 10.18s | Verified index-compatible predicate and requested keys; no completed old runtime, hence no exact speedup ratio | EV parcela configured |
| Reuse Oracle connection / different key positions | Three 1,000-row groups: 1.009s / 0.337s / 0.385s | Payload fetching is practical after the key fix; warm-up/network/position matter | Measured |
| Terminal skips and fixed run metadata | Correctness/resume tests | Preserve semantics; not credited with a measured speedup | Implemented |

The PostgreSQL lookup asks the **remote LIFT table** for existing row UUIDs and change dates before apply. It is not a comparison against SQLite. A unique index makes each server lookup cheap; it does not remove a round trip per individual query.

Oracle EV parcela has primary key `(PC_MID, JN_REV_NUM)`, both `NUMBER(12,0) NOT NULL`, with valid unique index `JN_PARCELA_PK_JNF_IX`. The JSON fast path splits the integration key into integer components and filters those saved-query output columns. Query joins, projections and payload checks remain in place. The old concatenated expression does not automatically benefit from the underlying pair index. Execution-plan privileges were unavailable, so index eligibility and empirical timings are verified; the chosen plan is not.

The user-interrupted old EV parcela apply spent 528.97 seconds in Oracle fetching and left **28,621 pending, zero processed**. That is an interrupted lower bound, not a completed baseline duration. The earlier user-run etaze/prostori applies took 57.324s for 3,108 and 98.01s for 4,729 upserts respectively. Those measured the old sequential path; they are not measurements of the new pipeline.

## 3. Prepare improvements and Oracle pagination

| Experiment / feature | Result | Decision |
|---|---|---|
| Candidate SQLite page joins | 1m sample: 3.032s versus current loop 2.448s | Not adopted |
| DuckDB global joins, already loaded | 1m: 0.070s; import another 1.946s | Promising query engine, not proof of complete prepare speed |
| Numeric keyset pages | Median 0.138s at 100 rows, 0.145s at 1,000, across tested anchors | Useful seek/resume prototype; not a production ordering change |
| Text keyset pages | Middle 1,000-row pages about 8.9–9.3s; initial short probe failed | Avoid computed-key seeks where original columns are available |
| Prepare resume | Commits rows/diffs with checkpoints; reuses complete source export | Saves repeated work after interruption; no isolated normal-run speed claim |
| `--only-src` | Stops before LIFT scanning/comparison | Phase isolation, not a total-work speedup |
| Skip materialized refresh | Avoids the known concurrent-refresh prerequisite failure | Accepted scope decision; not a measured base-table write acceleration |

Production inventory currently opens one ordered Oracle query and repeatedly fetches batches from that cursor. Later fetches do not rerun SQL or sort again. Do not extrapolate a fast keyset page into a faster full export: 26.5m rows / 1,000 × 0.145s is roughly **64 minutes of repeated-page latency** under that simplistic model, whereas the user measured a complete streaming Oracle export in **3:03.74** under earlier conditions. This illustration is not an apples-to-apples forecast; it explains why we have not switched uninterrupted exports to one SQL query per page.

There is also a real ordering constraint: the PostgreSQL text-key order in the sampled range differed from Python/SQLite binary ordering. Numeric pair ordering differs from concatenated-text ordering as well. Ordered range merging requires a consistent, verified ordering and checkpoint version. We therefore used order-independent batch comparisons for the matched engine experiment. Equal interval counts alone cannot prove matching keys or dates.

## 4. Matched SQLite / native DuckDB / RAM experiment

Seconds below include loading, streamed target comparisons and durable completion. These are median local times over three repetitions, with 10,000-row batches. `Page commits` means every completed 10k rows; `final commit` means a single final transaction. RAM page commits stay volatile until export.

| Strategy | 10k source rows | 100k source rows |
|---|---:|---:|
| SQLite, current loop / page commits | 0.022s | 0.233s |
| SQLite, current loop / final commit | 0.021s | 0.219s |
| SQLite, bulk SQL / final commit | 0.021s | 0.218s |
| DuckDB file, bulk / page commits | 0.070s | 0.859s |
| DuckDB file, bulk / final commit | 0.070s | 0.734s |
| DuckDB RAM, page transactions + snapshot | 0.077s | 0.910s |
| DuckDB RAM, final transaction + snapshot | 0.075s | 0.769s |

With 100,000-row batches and only the final commit:

| Strategy | 100k source rows |
|---|---:|
| SQLite current loop | 0.217s |
| SQLite bulk SQL | 0.232s |
| DuckDB file | 0.371s |
| DuckDB RAM + snapshot | 0.415s |

The RAM prototype really uses `duckdb.connect(':memory:')`, not a persistent connection with a long transaction. It writes its durable database with `COPY FROM DATABASE memory TO saved`, checkpoints it, closes it and reopens the file. Earlier versions committed pages in RAM; the additional end-only trial removes even those internal commits. CSV ingestion uses a bounded temporary staging file and its conversion/I/O cost is included. Thus this is RAM-first **database state**, not zero temporary filesystem I/O.

At 100k rows and 10k batches, fewer commits reduced SQLite's current loop from about 0.233s to 0.219s (roughly 6%). Native DuckDB fell from about 0.859s to 0.734s (roughly 15%). Moving DuckDB's whole transaction to RAM plus one export took about 0.769s. Bigger batches reduced native DuckDB to about 0.371s and end-only RAM to about 0.415s; SQLite's loop was still about 0.217s. Commit policy is not the main bottleneck in these samples.

A direct Python-array/UNNEST loader was also tested and rejected: roughly 20.2s per 100k rows. Bulk CSV loading cut that dramatically. This shows why storage timings must include the ingestion path, not just the database join. The global already-loaded DuckDB join remains fast, but the matched streamed workload includes work that isolated join timings omit.

There is no claim that DuckDB can never win at larger scale. The tested crossover has not been demonstrated, and 100k rows fit comfortably in the chosen budget. A 26m-row RAM store, indexes, snapshot copying and potential spilling require a memory/scale test before rollout. Neither database promises zero physical I/O merely because a transaction remains uncommitted.

## 5. What happens on failure

These cases ran against disposable local files/processes:

| Case | Rows persisted |
|---|---|
| SQL failure inside one uncommitted file transaction, then rollback | None |
| SQL failure inside one uncommitted RAM transaction, then rollback/export | None |
| RAM transactions committed after completed pages; next page fails; rollback that page and export | Previous completed rows `[1,2]` |
| Reload the saved RAM snapshot and continue | `[1,2,3]` |
| Controlled remote-fetch failure at a completed-page boundary while DB transaction is healthy | Can commit previous completed rows `[1,2]` |
| Abrupt RAM process exit before export | No snapshot created |
| Abrupt file-backed exit with an earlier commit and a later uncommitted row | Earlier committed rows `[1,2]` survive |

The correct action depends on the failure. A healthy transaction after a caught fetch error can be committed at a known completed-page boundary. After a SQL error requiring rollback, committing afterwards cannot resurrect the discarded transaction. Safe RAM recovery needs complete-page transactions in memory, rollback of only the failed page, and a handler that exports the completed state. Abrupt exit/OOM/kill cannot be relied upon to run that handler. These are prototype demonstrations, not a new repair backend wired into `repair.py`.

Primary references: [DuckDB transactions](https://duckdb.org/docs/current/sql/statements/transactions), [copying an in-memory database](https://duckdb.org/docs/stable/guides/snippets/copy_in-memory_database_to_file). Actual installed-engine tests are retained in `benchmarks/recovery-tests.json`.

## 6. How long should the large tables take?

**We have measured read improvements, not the new remote write throughput.** Therefore a precise new total would be invented. The following is a budgeting range with explicit assumptions:

- Prepare reference: 15–19 seconds per million source rows, based on completed user runs of the current full-export workflow. It is not a new measurement on every table or under the changed read-only access profile. The 26.5m EV parcela preparation actually took **7:44.62**; readonly inventory samples later ran under different conditions, so this reference may be optimistic for a later run.
- Oracle payloads: 0.4–3.7 seconds per 1,000 rows, spanning observed indexed EV parcela trials; other tables' joins/row width may differ.
- PostgreSQL lookup: 0.087–0.219 seconds per 1,000, from measured read probes.
- **Unmeasured write budget:** 1–5 milliseconds per row for pipelined writes, plus 0.3–1ms per row for local mapping/progress. These are scenario inputs, not benchmarks or a guaranteed envelope.
- Combined apply model: **1.787–9.919 seconds per 1,000 upserts**, about **101–560 rows/sec**. Deletions, point maintenance, caches/MVs and unknown hooks are excluded. No DuckDB or numeric-inventory speedup is credited.

| Table | Upserts | Prepare reference | Improved apply scenario | Combined scenario |
|---|---:|---:|---:|---:|
| `ev_parc_enota_h_2025_danes` | 847,269 | 6.5–8.2 min | 25.2–140.1 min | 31.7–148.3 min |
| `ev_stavba_h` | 679,160 | 0.8–1.0 min | 20.2–112.3 min | 21.0–113.3 min |
| `ev_parc_del_h` | 647,361 | 4.2–5.3 min | 19.3–107.0 min | 23.5–112.4 min |
| `ev_parc_pripis_podatki_h` | 170,570 | 2.2–2.8 min | 5.1–28.2 min | 7.3–31.0 min |
| `ev_parcela_h` | 28,621 | 6.6–8.4 min | 0.9–4.7 min | 7.5–13.1 min |

EV parcela uses its prepared 28,621 entries. Other repair counts and source sizes are historical October 7 captures; fresh preparation determines actual remaining work. The old approximately 12-hour whole-batch projection used Deli's old 57-upserts/sec rate and was never a measured EV batch. These conditional scenarios do not prove a specific batch-wide speedup.

### Fast-path readiness matters

| Table | Current prerequisite |
|---|---|
| `ev_parc_enota_h_2025_danes` | Needs revision output column + mapping |
| `ev_stavba_h` | Needs mapping + payload check |
| `ev_parc_del_h` | Needs mapping + payload check |
| `ev_parc_pripis_podatki_h` | Direct numeric key; payload unmeasured |
| `ev_parcela_h` | Configured; write speed unmeasured |

Read-only metadata/constraint checks confirmed the composite primary keys for JN_PARC_ENOTA, JN_STAVBA and JN_PARC_DEL. JN_PARC_ENOTA's saved SELECT does **not expose JN_REV_NUM separately**, so a simple outer tuple predicate cannot yet be added only through the current JSON mapping. JN_STAVBA and JN_PARC_DEL expose both components but have no configured entry/payload sample in this implementation. PARC_PRIPIS_PODATKI uses direct numeric ID under the alias PARC_PRIPIS_PODATKI_PK; it does not need composite splitting, though its wide payload cost remains unmeasured. EV parcela is the only currently configured composite fast path. The optimistic apply model is not applicable to an unconfigured slow computed-string lookup.

## 7. Recommendation and next validation

1. Keep the current SQLite backend, page checkpoints and the already implemented PostgreSQL batching/pipeline.
2. Use the configured numeric Oracle payload fetch for EV parcela. Verify/add other mappings individually; expose missing key columns explicitly rather than building a general SQL rewriter.
3. Keep numeric inventory paging and RAM/DuckDB storage as experiments. Do not switch the ordering of an existing partial run.
4. When write access is intentionally restored, use one real moderate apply with existing phase timings to replace the assumed PostgreSQL write budget. That is the missing measurement needed for reliable large-table scheduling.

No staging business rows were changed in these benchmarks. SQLite fixtures and DuckDB files were disposable local data; the cached bounded fixture is ignored by Git. Current correctness tests cover insertion, update, removal, ahead warnings, cutoff handling, unsorted input, durable reopening, transaction failure and reload.

## 8. Reproduce and trace every number

```sh
cd /Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export
# Reuse the saved sample: no remote database reads.
.venv/bin/python storage_trials.py --sizes 10000 100000 --repeats 3 --ingestion csv
.venv/bin/python storage_trials.py --sizes 100000 --batch-size 100000 --repeats 3 --ingestion csv
# --capture explicitly refreshes the bounded read-only sample; avoid unnecessary repeats.
.venv/bin/python -m pytest tests -q
```

- `benchmarks/*-storage.json`: rotated repeated trials; `storage_summary.json` and `storage_trials.csv`: grouped medians and raw phases.
- `benchmarks/ram-end-commit.json`: one final RAM commit/export at two scales and two batch sizes.
- `benchmarks/recovery-tests.json`: caught SQL/fetch errors, RAM reload and abrupt-exit results.
- `benchmarks/payload-position-sample.json`: three indexed 1,000-row payload groups on one connection.
- `benchmarks/large-table-key-readiness.json`: read-only primary-key/projection checks.
- `benchmarks/*-lookups.json`, `*-payloads.json`, `*-pagination.json`, `*-inventories.json`, `*-compare.json`: earlier read-only trials.
- `benchmarks/trials.csv`, `scale_summary.json`, `session_notes.json`, `timings.jsonl`: earlier aggregates, history and normal-run phase timings.
- `reports/runtime_model.json`: exact counts and formulas behind the conditional forecast table.

The short visual companion is [speed_report.html](speed_report.html). It has a write-cost slider; changing assumptions does not turn them into measured throughput.
