# Staging to production

Copies every staging row to the same production table in UUID `id` keyset
pages.  Each production page is `INSERT ... ON CONFLICT (id) DO UPDATE`, so a
crash after commit but before its checkpoint is safe to replay.  `id`,
`created_at`, and `created_by` are immutable on a conflict; other copied
columns are updated.  This tool never deletes production rows.

Both tables must have identical copyable column names **and PostgreSQL types**,
with `id uuid NOT NULL` and a ready, valid, non-partial unique btree index on
`id`.  The run uses the shared local and
PostgreSQL writer locks, committed JSON checkpoints, and normal Ctrl-C page
semantics (first Ctrl-C stops after a page; second rolls back the active page).

```sh
.venv/bin/python src/stag_to_prod/sync_table.py ev_parc_pripis_podatki_h --dry-run

.venv/bin/python src/stag_to_prod/sync_table.py ev_parc_pripis_podatki_h \
  --apply --page-size 50000
```

Rerun an interrupted apply command to resume.  A completed ordinary command
automatically starts a new full, idempotent copy epoch on its next invocation;
use `--fresh --apply` to explicitly abandon a partial checkpoint and rescan
from the beginning.  `--truncate --apply` is the one replacement operation:
it truncates production and resets/copies under one writer lock. `--page-key
id` remains a compatibility option, but no other key is supported.

Each invocation reads staging in one `REPEATABLE READ, READ ONLY` snapshot.
The tool deliberately does not reconnect that source session: changing the
snapshot during a resumed keyset scan could skip rows behind the checkpoint.
If its staging connection fails, rerun it; periodic completed full epochs give
best-effort convergence when staging continues to change between invocations.

`--page-size N` is fixed by default. `--auto-page-size` enables the same
non-persistent core page-size search as KN staging (`--initial-page-size`,
`--max-page-size`); `--constant-page-size N` is an explicit fixed override.
