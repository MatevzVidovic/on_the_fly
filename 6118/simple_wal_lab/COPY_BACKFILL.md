# Copy restored tables and calculate UTC during insert

`batched_copy_backfill.py` reads the restored original name and inserts into the
existing `_org2810` table. It does not create, truncate, rename, or change logging
on either table. Connection settings come from the same `.env` as other scripts.

```bash
# EV
.venv/bin/python batched_copy_backfill.py --table public.ev_parcela_h --source-date-column date_change --date-column date_change_utc

# KN
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_parcele_h --source-date-column datum_sys --date-column datum_sys_utc
```

Default destination is the source name plus `_org2810`, in the same schema.
Override with `--copy-target public.some_other_name` if needed.
Default batch: 500,000 rows; pause: 1 second. Override with `--batch-size 500000
--pause 1`. Only this script accepts these copy options.

All writable destination columns are explicitly mapped by name. IDs, audit fields,
geometry and other stored fields are copied unchanged. The destination UTC column
is computed as `(source_date AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'`,
even if the restored table contains an older UTC value. The source need not have
the UTC column. NULL source dates produce NULL UTC values; those rows are copied
too. Generated columns are calculated by PostgreSQL. Existing destination triggers
and constraints still run. Both tables must have a unique indexed NOT NULL `id`.
The script checks matching PostgreSQL types for copied writable columns and refuses
to silently omit source columns missing from the target.

Each INSERT...SELECT batch is one autocommitted statement. The next batch starts
after the largest ID successfully inserted. On restart, it reads the destination's
largest ID with `ORDER BY id DESC LIMIT 1`; no bisection or date filtering.
This requires the destination to be empty initially, then populated only by this
script's ascending batches. A target populated out of order or with holes is not a
valid resume state. Only one copy from this script can use a destination at once.

Stop integrations and other writers to both tables; finish restoring the source
before copying. No automatic consistency snapshot spans the complete copy. The
data recovered is exactly the restored source: later changes absent from Tuesday's
backup are not recovered by this script.

Barman checks happen before and after batches: pause at 2 GiB, resume below 1 GiB.
These don't measure actual disk free space. If the destination is unlogged, its
data still grows on disk; a crash can truncate it again. Copying here does not fix
the underlying disk-space shortage. Monitor real filesystem headroom throughout.
Keep logging-mode changes sequential and manual, with headroom for their rewrites.

Ctrl+C cancels the current batch, preserves earlier committed batches, and logs the
run in `full.sqlite` like the other scripts. Each batch prints UTC time, row count,
elapsed time and last ID. To monitor the destination in another terminal:

```bash
.venv/bin/python db_tracker.py recovery.sqlite --table public.ev_parcela_h_org2810
```

Before renaming/restoring logging, validate source and target row counts, IDs, copied
values and UTC conversion. Reaching the end of the source isn't a full validation
of an arbitrarily pre-existing target. If explicitly copied identity/serial values
use sequences, check their next values before resuming application inserts; this
script does not alter sequences. Columns with `timestamp(0)` still round seconds.
