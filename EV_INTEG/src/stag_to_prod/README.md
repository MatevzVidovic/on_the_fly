# Resumable simple staging-to-production copy

This is the simple alternative to `src/stag_to_prod_complex`: it does not
compare IDs or change timestamps. On its first `--apply`, it truncates the
production table once, then copies every staging row in committed keyset pages.
Production is therefore partial until the last page completes.

Create `.env` from `.env.example`. The default schema is `public`; `id` is the
default unique page key. The page key must have a valid single-column unique
B-tree index in both databases and cannot be NULL in staging.

```sh
.venv/bin/python src/stag_to_prod/sync_table.py ev_parc_pripis_podatki_h --dry-run

.venv/bin/python src/stag_to_prod/sync_table.py ev_parc_pripis_podatki_h \
  --apply --page-size 50000
```

If interrupted, rerun the exact same `--apply` command. It resumes from local
state in `.state/`; replaying a committed but uncheckpointed page is safe.

Use `--page-key another_key` for a table that does not use `id`. Use
`--restart` only to intentionally discard local state, truncate production, and
start the copy from zero.

Run while staging writes to the copied table are paused. This simple tool does
not freeze or detect source changes while pages are being copied.
