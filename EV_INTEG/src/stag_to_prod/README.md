# Staging-to-production table synchronisation

Create `src/stag_to_prod/.env` from `.env.example` and fill in the two PostgreSQL connections. `STAG_DATABASE`, `PROD_DATABASE`, and `SYNC_SCHEMA` default to `fmp_data_gurs` when omitted.

The table name is supplied without a schema. The utility uses the `id` column as the membership key: it deletes production rows whose IDs are not in staging, then inserts staging rows whose IDs are not in production. It deliberately does **not** update IDs present in both databases.

Preview the proposed changes (no writes):

```sh
.venv/bin/python src/stag_to_prod/sync_table.py jn_pe_parc --dry-run
```

It prints row data for up to 100 deletes and 100 inserts. Use `--preview-limit 500` for more, or `--preview-limit 0` for counts only.

Apply the changes only after reviewing the preview:

```sh
.venv/bin/python src/stag_to_prod/sync_table.py jn_pe_parc --apply
```

Use `--schema public` if the tables are in `public` rather than `fmp_data_gurs`.
