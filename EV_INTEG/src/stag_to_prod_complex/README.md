# Staging-to-production table synchronisation

Create `src/stag_to_prod/.env` from `.env.example` and fill in the two PostgreSQL connections. `STAG_DATABASE` and `PROD_DATABASE` default to `fmp_data_gurs`; `SYNC_SCHEMA` defaults to `public`.

The table name is supplied without a schema. The utility uses `id` as the membership key by default and `DATE_CHANGE` as the version field. It deletes production rows whose keys are not in staging, inserts staging rows whose keys are not in production, and fully updates a production row only when its `DATE_CHANGE` is older than staging's. Equal values are left alone. Use `--id-field jn_pe_parc_pk` for tables that use a synthetic key instead of `id`.

If any matching production row has a newer `DATE_CHANGE` (or a non-comparable/null mismatch), the run fails before making any change. Use `--change-field another_field` when a table uses a different version column. Both tables must have a non-partial single-column unique index/constraint on the membership key.

Large runs are resumable. The first run freezes staging membership and change values in `src/stag_to_prod/.state/`, performs the complete conflict check, then commits set-based insert/update/delete pages. Restart the same command after an interruption; use `--restart` only to discard incomplete local state and begin again. `--page-size` defaults to 10,000 (and `--batch-size` remains a deprecated alias); `--max-pages` is useful for controlled partial runs.

The manifest also stores a digest of every copied staging column. Before an insert or update page is written, the current staging payload must exactly match that digest, even if `DATE_CHANGE` was not updated.

If preflight records a production-newer conflict, resolve the data discrepancy and run again with `--apply --restart`; a persisted conflict state is deliberately never applied.

The membership key must contain non-null, unique values in both databases. The tool holds the same session-level PostgreSQL advisory lock on both endpoints for the whole run, acquired in stable database-identity order. If both roles are the same physical database, it takes that lock once while retaining both working connections. Other writers should cooperate by taking that lock; writers that do not cooperate are not prevented, but each page checks the preflight production version and aborts rather than overwriting an unexpected change.

Preview the proposed changes (no writes):

```sh
.venv/bin/python src/stag_to_prod/sync_table.py ev_pe_parc_h --id-field jn_pe_parc_pk --dry-run
```

It prints the total counts and up to five example rows for each action. Use `--preview-limit 500` for more, or `--preview-limit 0` for counts only.

Apply the changes only after reviewing the preview:

```sh
.venv/bin/python src/stag_to_prod/sync_table.py jn_pe_parc --apply
```

Use `--schema another_schema` only when the tables are not in `public`.
