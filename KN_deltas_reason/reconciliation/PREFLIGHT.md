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
