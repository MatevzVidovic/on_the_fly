# Staging-to-production table synchronisation

Create `src/stag_to_prod/.env` from `.env.example` and fill in the two PostgreSQL connections. `STAG_DATABASE` and `PROD_DATABASE` default to `fmp_data_gurs`; `SYNC_SCHEMA` defaults to `public`.

The table name is supplied without a schema. The utility uses `id` as the membership key and `DATE_CHANGE` as the version field. It deletes production rows whose IDs are not in staging, inserts staging rows whose IDs are not in production, and fully updates a production row only when its `DATE_CHANGE` is older than staging's. Equal values are left alone.

If any matching production row has a newer `DATE_CHANGE` (or a non-comparable/null mismatch), the run fails before making any change. Use `--change-field another_field` when a table uses a different version column.

Preview the proposed changes (no writes):

```sh
.venv/bin/python src/stag_to_prod/sync_table.py jn_pe_parc --dry-run
```

It prints the total counts and up to five example rows for each action. Use `--preview-limit 500` for more, or `--preview-limit 0` for counts only.

Apply the changes only after reviewing the preview:

```sh
.venv/bin/python src/stag_to_prod/sync_table.py jn_pe_parc --apply
```

Use `--schema another_schema` only when the tables are not in `public`.
