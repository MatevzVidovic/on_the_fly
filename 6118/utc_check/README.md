# UTC backfill audit

For recovery `_org2810` tables (writes a separate `report_org2810.md`):

```bash
../simple_wal_lab/.venv/bin/python export.py --table-suffix _org2810
```

This includes logging mode, estimated rows, sizes and UTC field checks. LIFT
metadata is matched to the original unsuffixed table names. It does not mean LIFT
is currently reading the renamed tables. Add `--any-null` or `--num-nulls` if needed;
those options read table data. `--output PATH` overrides the destination.

From this directory, run:

```bash
../simple_wal_lab/.venv/bin/python export.py
```

To include exact NULL counts for existing UTC columns:

```bash
../simple_wal_lab/.venv/bin/python export.py --num-nulls
```

To add an `Any-null` column showing `True` when the UTC column contains at least one NULL:

```bash
../simple_wal_lab/.venv/bin/python export.py --any-null
```

This check stops at the first NULL found, but may scan the whole table if none exist. Missing UTC columns show `—`.

You can combine `--num-nulls --any-null` to include both columns; the existence result is then derived from the count. Without either flag, the script does not scan table rows.

The script uses the PostgreSQL credentials in `../simple_wal_lab/.env`. It connects to the configured data database and reads LIFT integration metadata from the `fmp` database using the same credentials.

To use a different metadata database:

```bash
../simple_wal_lab/.venv/bin/python export.py --metadata-db DATABASE_NAME
```

Each run overwrites `report.md` in this directory. The report contains the fixed backfill list (12 EV and 20 KN tables), table sizes, UTC column and integration mapping checks, and the integration SQL for review.

All database connections enforce read-only transactions. The script does not modify the database. Inventory row counts are estimates. With `--num-nulls`, `Num-null` counts scan existing UTC columns and are exact at query time. Each query has a 30-second timeout; timed-out counts are marked `timeout`.

The report also includes stored watermarks, last sync start/end, and processing status. It checks whether the watermark date is yesterday (Europe/Ljubljana); the giant table and full-sync integrations are exempt. This date check does not prove the historical reload is complete.
