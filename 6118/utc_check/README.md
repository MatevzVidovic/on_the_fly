# UTC backfill audit

From this directory, run:

```bash
../simple_wal_lab/.venv/bin/python export.py
```

The script uses the PostgreSQL credentials in `../simple_wal_lab/.env`. It connects to the configured data database and reads LIFT integration metadata from the `fmp` database using the same credentials.

To use a different metadata database:

```bash
../simple_wal_lab/.venv/bin/python export.py --metadata-db DATABASE_NAME
```

Each run overwrites `report.md` in this directory. The report contains the fixed backfill list (12 EV and 20 KN tables), table sizes, UTC column and integration mapping checks, and the integration SQL for review.

All database connections enforce read-only transactions. The script does not modify the database. Inventory row counts are estimates; `Num-null` counts scan existing UTC columns and are exact at query time. Each query has a 30-second timeout; timed-out counts are marked `timeout`.
