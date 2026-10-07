# Sixteen-table staging comparison

`batch_staging.py` captures the 12 EV targets and four KN/NEP targets named in
`EV_INTEG/Agents/integrations_export.md`. It **only connects to staging** and KN
Oracle. Every remote transaction is read-only; it does not run integrations.

From this directory:

```sh
../.venv/bin/python batch_staging.py target --folder captures/staging_batch/20261007
../.venv/bin/python batch_staging.py source --folder captures/staging_batch/20261007
../.venv/bin/python batch_staging.py report --folder captures/staging_batch/20261007
```

Run these sequentially. Add `--tables <target-name> ...` to select tables.
Credentials come from this directory's `.env`, using `STAG_*` and `KN_ORACLE_*`.
Use a new folder for a new observation. Completed tables are skipped on retries;
failed tables keep a partial SQLite file and are not reported as complete.

To compare freshly exported staging against an unchanged earlier Oracle snapshot,
run `target` into a **new** folder, then:

```sh
../.venv/bin/python batch_staging.py reuse-source --folder captures/staging_batch/NEW \
  --baseline captures/staging_batch/20261007 --tables <target-name> ...
../.venv/bin/python batch_staging.py report --folder captures/staging_batch/NEW \
  --tables <target-name> ...
```

This copies the old narrow Oracle inventory locally, opens the baseline read-only,
checks that SQL/mappings are unchanged, and retains the original source snapshot
times. It is a comparison against that earlier source snapshot, not a fresh Oracle
comparison; newly added/changed/deleted Oracle rows are outside its evidence.

Each table gets a SQLite file with full narrow source and target inventories:
business key, change timestamp, and target UUID/creation/update fields. The source
query wraps the exact live integration SQL, retaining joins, status exclusions
and year cutoffs. The projection only returns key/date fields. These exports still
scan millions of rows and can consume tens of GB locally.

`summary.json`, `missing.csv`, and `missing_days.csv` describe exact missing keys.
An old target counterpart is retained, so it is classified as stale, not missing.
Missing keys newer than the saved watermark are separated from older gaps.
Source and target snapshots are independent; recent changes between snapshots
can produce temporary differences.

`inferred_windows.csv` and `missing_window_candidates.csv` test a narrower
hypothesis: do older missing keys fit intervals between a historical watermark
interpreted in Ljubljana and the same wall time interpreted in UTC?
Historical watermark candidates come from target write-cohort maximum change
dates. They are **not historical query logs**. FMP can overwrite `created_at` on
UPSERT, and later changes can alter cohort maxima. Actual skipped intervals also
depend on the next run's selected cutoff and worker timezone. In the checked local
FMP SQL-delta code, `last_changed_datetime` replaces the sync-start cutoff when
changed-date delta is enabled and the watermark exists; it is not a minimum of
the two. Coverage is supporting evidence, not proof of the cause.

Target/source matching controls support interpreting target naive change dates
as Ljubljana wall time. This does not verify the deployed worker's timezone.
No repair, deletion, watermark update, or production query is performed.
