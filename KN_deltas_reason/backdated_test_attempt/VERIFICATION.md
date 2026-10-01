# Multi-table monitor verification

Date: 2026-09-23. This records implementation checks, not a conclusion about source drift.

## SQL checks

- All 40 configured diagnostic SQLs validated through the current KN Oracle login in a read-only transaction, using a zero-row outer query.
- Every result exposes text `MATCHING_KEY` and `CHANGED_AT`; the five enriched EV queries also expose their expected text audit timestamp.
- Compared every query's original FROM/JOIN/WHERE clauses with the saved integration SQL in `exploration/artifacts/20260923T084030Z/integrations.json`. All membership clauses match, apart from the intentionally added common lower-bound predicate.
- This includes the ZPS `TEREN_GEOM IS NOT NULL` predicate, EV enota's 2025 cutoff and railway `ID = '77920'` predicate.
- Zero-row validation establishes syntax, access and output shape, not whole-window runtime or key uniqueness.

## Existing observations

The original `snapshots.sqlite3` is preserved without migration. Before implementation verification it contained one completed Jira-table observation with 46,719 rows, captured at 2026-09-23 08:15 UTC.

## Acceptance results

- Ten deterministic local tests pass. They cover all comparison categories, backward timestamps, native-audit NULL transitions, fixed/empty baselines, fingerprint separation, output contracts and rollback/failure isolation.
- First complete Jira export: 46,736 rows in 5.34 seconds. SQLite row count matches the recorded count; keys are text, UTC timestamps are 30 characters, and neither required field is NULL.
- Then `python monitor.py export` completed all 40 extracts without failures, from 10:02:19 to 10:06:11 UTC (about 232 seconds). This run stored 14,491,393 rows. Six extracts had empty windows; these remain valid complete baselines.
- Experiment file: `observations_ea4f75d1c93f.sqlite3`. It contains the initial Jira acceptance observation plus the 40-extract run: 41 complete observations and 14,538,129 diagnostic records. Size after the run: 905,506,816 bytes (about 864 MiB). Future complete runs add roughly another cohort's worth of storage; the window has no upper bound.
- Jira's second observation contains 46,738 rows. Local comparison reports two NEW_KEY differences, both newer than the baseline maximum, and no other differences. Neither is an older-than-baseline candidate. This short same-day check does not establish whether late visibility occurs over subsequent days.
- SQLite `PRAGMA quick_check` returns `ok`; actual stored counts match all 41 observation counts. Native audit values were populated for all selected pripis and ceste rows; the other two audit-enriched extracts have empty windows.
- The explicit-database CLI comparison succeeds without Oracle environment variables. It emits the two Jira differences and marks the other 39 extracts as insufficient observations, not unchanged.
- All four independent reviews completed: correctness/quality and approach/simplicity, each reviewed by a medium and a small model. No blocking correctness issues or actionable unnecessary complexity were found; no repair round was needed.

The largest selected cohort is `kn_nep_ostalo_dejanske_rabe_parcel_h` with 4,978,197 rows; `ev_stavba_h` has 2,330,180 and `ev_del_stavbe_h` has 2,152,294. Narrow diagnostic projections do not imply small row counts.

No Oracle data, production integration configuration, or PostgreSQL tables were changed.
