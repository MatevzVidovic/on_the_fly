# KN to staging delta sync with deletes

Create `src/kn_to_stag_delta_with_delete/.env` from `.env.example`. The source is Oracle KN (schema `EV` in the integration SQL); the destination is PostgreSQL database `fmp_data_gurs`, schema `public` by default.

Pass a staging table name and a file containing the integration `SELECT`. The query must select all insertable destination columns, use destination-compatible aliases, include a non-null unique key, and return no duplicate keys. The key defaults to `id`; use `--id-field` for tables such as `jn_pe_parc_pk`. For every execution, the utility deletes staging keys absent from KN, then inserts KN keys absent from staging. Existing keys are not updated.

Dry-run is the default and prints counts plus up to five example rows for each action:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --dry-run
```

After review, execute the same operation with `--apply`:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --apply
```

Use `--schema another_schema` only when staging tables are not in `public`; use `--preview-limit` to change the number of displayed rows.
