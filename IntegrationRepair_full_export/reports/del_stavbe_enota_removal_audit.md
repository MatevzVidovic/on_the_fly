# Del-stavbe-enota removal review — 15 October 2026

Prepared run: `676a2dc7-00cb-4da1-85ae-6a2a8b19d121`.
All inspection used read-only PostgreSQL/Oracle sessions and read-only SQLite access. Nothing was applied.

## Verdict

The 11,895 removals are consistent with the agreed repair rules and current integration query. Every candidate has `JN_STATUS = 'X'` in both Oracle and staging. None belongs to the integration result, whose query explicitly requires:

```sql
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'
```

These are removals from the LIFT target table, not physical deletions from Oracle. All 11,895 underlying Oracle records still exist. The reason for exclusion is status X for every candidate; this is not an incomplete source export, a cutoff/date mismatch, or the 2025 filter.

## Complete candidate checks

| Check | Result |
| --- | ---: |
| Candidates checked | 11,895 / 11,895 |
| Present in saved Oracle export | 0 |
| Present in live saved integration query result | 0 |
| Present in raw Oracle table | 11,895 |
| Raw Oracle status X | 11,895 |
| Staging status X | 11,895 |
| Staging UUID no longer present | 0 |
| Staging key changed since prepare | 0 |
| Staging change date changed since prepare | 0 |
| Staging change date beyond cutoff | 0 |
| Referencing foreign-key constraints | 0 |
| User-defined PostgreSQL table triggers | 0 |

All 661 upsert candidates also remain present in the current integration query and have the same source change dates as the prepared plan.

## Why normal integration can leave these behind

An upsert-based delta integration only processes rows returned by its query. A key excluded by the status filter produces no row to upsert and no deletion instruction for the existing target record. Such historical rows can therefore remain in staging even after a successful normal integration. The current check does not establish when each X row originally entered staging or when its source status changed.

This repair compares complete query membership and explicitly removes target-only keys. Here the entire deletion cohort is already marked X in staging too; no candidate currently has an active/non-X status on either side.

## Apply this reviewed run

With the target's normal integration still stopped and its configuration unchanged:

```sh
time .venv/bin/python repair.py --store full-ev-del-stavbe-enota.sqlite apply 676a2dc7-00cb-4da1-85ae-6a2a8b19d121
```

The tool does not refresh materialized views, as previously agreed. This audit checks current membership and target identity/date, not every application-level relationship.

Raw evidence: `diagnostics/enota_removal_audit.json`.
Reproduce the read-only check: `.venv/bin/python diagnostics/audit_enota_removals.py`.
