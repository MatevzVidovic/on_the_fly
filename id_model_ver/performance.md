# Backfill performance diagnosis — 15 October 2026

Read-only probes on staging and KN Oracle. No backfill writes were executed during diagnosis, and the running transfer implementation was not changed.

## Reproduced bottleneck

A fixed page of 10,000 UUID-ordered staging rows after `0938aa00-28f5-4af9-a107-101123f856f1` took:

| Phase | Seconds |
| --- | ---: |
| Staging page read | 0.988 |
| Oracle fetch by scattered composite keys | 6.223 |
| Total before any staging UPDATE | **7.211** |

`benchmark_backfill.py --budget 2` failed its page read/fetch budget assertion. This reproduces the reported slow page without performing remote writes. It does not measure UPDATE or commit duration.

## Source strategy comparison

| Strategy | 1,000 rows | 10,000 rows |
| --- | ---: | ---: |
| Current `fetch_models` | 0.838s | 5.923s |
| Same function with cursor prefetch set to 1,000 | 0.494s | 5.599s |
| Sequential source sample | 0.055s | 0.500s |

Only one measurement per strategy and scale was taken, sequentially while the user's transfer may have been running. Prefetch measurements followed the current method on the same keys and may benefit from warmed caches. They do not establish a reliable buffering speedup.

The sequential sample uses the proposed 2020–2024 date/status scope and stops after N rows. It does not read the same key subset as the target-driven lookup. It tests bulk source delivery; it is not a full export benchmark, an execution-plan comparison, or a proof of target membership.

## Interpretation

Oracle lookup time accounts for most of the observed page duration. UUID ordering on staging gives Oracle a scattered selection of historical source keys. The valid composite Oracle index makes direct lookup possible but does not make millions of scattered payload reads equivalent to a sequential scan. We have not collected the executed lookup plan, so this diagnosis does not claim to prove the optimizer's access method.

A larger PostgreSQL page reduces commit/pagination overhead, but the code still executes ten 1,000-key Oracle queries per 10,000 target rows. It cannot remove this source lookup cost. The measured buffer change was small at 10,000 rows.

At approximately 7.8 seconds per 10,000 rows, 6.9 million rows project to about **90 minutes**, not 13 hours. This assumes stable throughput. It does not account for later load changes.

## Suggested next implementation

1. Stream only source identity and model-version values from Oracle into SQLite once: numeric `DST_SID`, numeric `JN_REV_NUM`, nullable `ID_MODEL_VER`.
2. Index the local pair and preserve source NULL distinctly from a missing key.
3. Keep the existing target UUID pagination and batch UPDATE path. Replace per-page remote Oracle lookups with local SQLite lookups.
4. Validate source coverage before changing any target row in a page. The old export's scope is unverified; do not silently skip keys outside a chosen cache export range. Either fail on a cache miss or explicitly look up that missing key remotely.
5. Reuse the cache across interrupted runs, retaining the committed target UUID as the resume boundary. Record cache scope/source snapshot time so a stale cache is not mistaken for fresh data.

At the 10,000-row sample's sequential throughput, reading 6.9 million source rows alone extrapolates to roughly six minutes. SQLite insertion, index construction, staging reads, UPDATEs, and commits add time. **A new end-to-end duration cannot be asserted from these samples.** The PostgreSQL write phase still needs measurement after removing remote lookups.

At the original diagnosis stage, no SQLite exporter or cache-backed transfer had been implemented. Existing committed pages remain valid; they do not need to be undone.

## Evidence

- [Baseline timings](benchmark_baseline.json)
- [Source strategy timings](benchmark_source_strategies.json)
- `IntegrationRepair_full_export/.venv/bin/python id_model_ver/benchmark_backfill.py --budget 2`
- `IntegrationRepair_full_export/.venv/bin/python id_model_ver/benchmark_source_strategies.py`

Both benchmark scripts read only a bounded sample and use read-only database sessions. Their local JSON outputs are overwritten when rerun.

## Implemented follow-up: SQLite-backed transfer

`export_models.py` now builds a completed per-table SQLite snapshot. `backfill.py` uses only that local source and staging, with no Oracle connection. No remote writes were performed to validate this code change.

A bounded live comparison using the same 10,000 target keys measured:

| Phase | Seconds |
| --- | ---: |
| Old scattered Oracle fetch | 4.286 |
| Write those 10,000 values to a temporary indexed SQLite file | 0.009 |
| New staging read and local comparison, 1,000 rows | 0.076 |
| New staging read and local comparison, 10,000 rows | **0.155** |

The new 10,000-row comparison passes the same two-second read/compare budget that the original 7.211-second path failed. The samples were run at different times and may benefit from warmed caches. They do not measure full export duration or PostgreSQL writes/commits. The sample cache was seeded with the original lookup results to keep key coverage and source values identical; it was not a full export.

Evidence: [benchmark_cached_backfill.json](benchmark_cached_backfill.json). Reproduce read-only with `IntegrationRepair_full_export/.venv/bin/python id_model_ver/benchmark_cached_backfill.py`.
