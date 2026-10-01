# Live preflight — 2026-10-01

All remote operations were read-only. No integration configuration, watermark, index or data was changed remotely.

## Verified

- Both PostgreSQL databases (`fmp`, `fmp_data_gurs`) and Oracle service `EPRO.cman.prim` are reachable using the local credentials/tunnels.
- Integration `bfe62b52-9aaf-11ef-9c54-0242ac120008` uses KN ORACLE and targets `kn_nep_deli_stavb_h`.
- Its complete source SQL selects `NEP.DELI_STAVB_H` without joins/filters. The diagnostic projection has equivalent row membership.
- Live SQL SHA256: `98d6fe66c99a12d597caf285a1e0f8897aa5e6c9d902436151023517701a53a7`.
- Key mapping: `DEL_STAVBE_H_ID` → `del_stavbe_h_id`; change mapping: `DATUM_SYS` → `datum_sys`. Both enabled.
- Oracle key is `NUMBER(28,0)` NOT NULL; change date is `DATE` NOT NULL.
- Target key is `bigint`; change date is `timestamp without time zone`; UUID is NOT NULL. Both audit columns exist.
- `kn_nep_deli_stavb_h_pk` is a unique business-key index, valid and ready. This rules out duplicate *nonnull* business keys in the currently constrained target; it does not establish historical uniqueness or prevent null keys.
- 23 matched records across 2022 summer, January 2026, July 2026 and September 2026 retain identical source/target wall-clock dates. Oracle UTC conversion differs by one winter hour/two summer hours. Set `target_timezone = Europe/Ljubljana`, not UTC.
- Target catalog estimate: 2,717,208 rows, total relation size including indexes about 1008 MB. Oracle estimate: 2,636,805 rows, stale statistics from 2025-09-08. These are not exact counts.
- Driver dependencies already installed; no installation needed.

## Watermark: distinguish storage from runtime interpretation

At 2026-10-01 13:37:25 UTC, before the user's proposed manual run:

| Field | Value |
|---|---|
| processing_status | PROCESSED |
| last_sync_start | 2026-09-26 02:50:00 |
| last_sync_end | 2026-09-26 02:50:58 |
| last_changed_datetime | 2026-09-25 14:06:59 |
| target maximum datum_sys | 2026-09-25 14:06:59 |

All three metadata date fields are timezone-less. The watermark wall value matches source/target Ljubljana wall time. This does **not** establish what timezone PHP uses on the next read.

The inspected FMP code constructs `new DateTime(last_changed_datetime)` without an explicit timezone, then includes the resolved offset in the Oracle bound. Its app config defaults to UTC, but an environment override is possible. The DB stores a Saturday `50 2 * * 6` schedule and the recorded start is 02:50; the local schedule builder leaves Temporal's timezone at its UTC default. This supports UTC worker behavior but is not independent verification of deployed runtime settings.

If the worker interprets the stored September watermark as UTC, it means 16:06:59 Ljubljana rather than the original 14:06:59: a two-hour forward shift. That is a testable hypothesis, **not a confirmed production defect**. Comparing an actual manual run's wall-clock UTC execution time with its persisted last_sync_start can provide more evidence; a generated Oracle bound or actual worker timezone would be stronger.

`watermark_timezone` stays empty. Capture and timestamp comparison work, but relative-bound labels remain UNKNOWN rather than guessing. Source/target timezone normalization is independently verified.

## Local setup changes

The user renamed Oracle credential variables while setup was being checked. Removed the added obsolete `${KN_USER}`/`${KN_PASSWORD}` aliases, which were overriding those renamed credentials with empty strings. DSN is explicitly `localhost:10522/EPRO.cman.prim`. Password values were not printed or copied.

An initial export attempt failed at Oracle connection before fetching source rows and left only an incomplete capture. It must not be used. A subsequent connection smoke test succeeded.

Production deployment commit remains UNVERIFIED. The local code is evidence about implementation, not proof of deployed version.

## Completed baseline

Capture: `captures/20261001T133732435890Z/capture.sqlite3` (635.6 MiB).

- Source: 2,736,617 rows, acquired 13:37:32–13:37:59 UTC.
- Target: 2,735,180 rows, acquired 13:37:59–13:39:06 UTC.
- Metadata before/after was identical; the integration still reported its September 26 completion.
- No null business keys, null change timestamps or duplicate business keys on either side.
- July 1 inclusive through October 1 exclusive, Ljubljana time: 46,149 timestamp-equal keys, 1,036 missing target keys, 2,916 stale target keys.
- No target-only or target-ahead keys in this report cohort. That is not a claim about all history.

See the capture's `summary.md`, `differences.csv`, `daily.csv`, and `global_anomalies.csv`.
Some discrepancies may be ordinary lag since September 26. A completed manual integration followed by
a second capture will distinguish repaired rows from remaining gaps. Neither unchanged timestamps nor
these counts establish full business-payload equality or a cause.

The only unresolved configuration is the worker's effective watermark timezone. Empty means UNKNOWN
and does not block export/comparison. The local regression suite passes after this adjustment.

## Staging verification

The `STAG_*` connection reaches a different PostgreSQL server from `PROD_*`; both are writable
primaries, but our sessions are explicitly read-only. Staging uses databases `fmp` and `fmp_data_gurs`.
The KN integration ID, exact SQL hash, key/change mappings and selected target column types match
production. Five matching key/date probes spanning winter and summer also retain Ljubljana wall time.
The same source Oracle connection and diagnostic SQL can therefore be used for this table pair.

The UI completion time `2026-10-01 13:40:58` belongs to staging **ev_parcela_h**, integration
`prnos_ev_parcela`, whose recorded start is `13:38:42`. It was not a run of `kn_nep_deli_stavb_h`.
The KN staging metadata still showed September 26 when checked. Do not treat that EV run as a
before/after test of KN or assume staging and production are identical merely because samples match.

Exports now require `--environment staging` or `--environment production`. Captures are partitioned
by environment, and new capture metadata and reports name their environment. Legacy captures remain
unchanged; this document identifies `20261001T133732435890Z` as production.

### Staging capture after a newly completed KN run

By capture time, KN staging had completed a new run: start `2026-10-01 13:48:14`,
end `13:48:39`, watermark `2026-10-01 14:53:26`. These settings were unchanged before/after
the capture. Therefore this is a **post-run** staging snapshot, not a pre-run baseline.

`captures/staging/20261001T134900129421Z/capture.sqlite3` contains 2,736,617 source rows and
2,736,508 staging rows. July–September report: 48,208 timestamp-equal keys, 16 missing target
keys, 1,856 stale target keys. No null keys/dates or duplicate keys anywhere in either inventory.
The source/target acquisitions ran 13:49:00–13:50:41 UTC.

Staging is measurably different from the earlier production snapshot. Cross-environment counts
are not a controlled before/after test, even though staging currently has fewer discrepancies.
The new run's execution timestamps further support UTC worker behavior while the source-derived
watermark retains Ljubljana wall time. Runtime-bound verification remains separate; eligibility
labels deliberately stay UNKNOWN.
