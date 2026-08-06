# KN to staging delta sync with deletes

Create `src/kn_to_stag_delta_with_delete/.env` from `.env.example`. The source is Oracle KN (schema `EV` in the integration SQL); the destination is PostgreSQL database `fmp_data_gurs`, schema `public` by default.

If KN enforces Oracle Native Network Encryption/Data Integrity, install Oracle Instant Client and set `KN_ORACLE_CLIENT_LIB_DIR` to its library directory in `.env`. This enables python-oracledb Thick mode, which KN requires for that security setting.

Pass a staging table name and a file containing the integration `SELECT`. The query must select all insertable destination columns, use destination-compatible aliases, include a non-null unique key, and return no duplicate keys. The key defaults to `id`; use `--id-field` for tables such as `jn_pe_parc_pk`. For every execution, the utility deletes staging keys absent from KN, then inserts KN keys absent from staging. Existing keys are not updated.

The destination-managed LIFT fields `id`, `created_at`, `created_by`, `updated_at`, and `updated_by` are intentionally omitted from the KN query. PostgreSQL generates `id` and timestamps/defaults on insert. By default, matching keys are compared using `DATE_CHANGE`: KN-newer rows are updated, equal rows are left unchanged, and staging-newer rows abort the complete run before any write. Use `--ignore-change-field` for integrations that should use only key membership: delete staging keys absent from KN and insert KN keys absent from staging, while leaving matching keys unchanged.

### Oracle timezone workaround

If Oracle raises `ORA-01805` when fetching `TIMESTAMP WITH TIME ZONE` values, return the timestamp values as ISO text from the integration query. Oracle still applies the `Europe/Ljubljana` time zone and daylight-saving rules; PostgreSQL casts the ISO text back to its timestamp-with-time-zone columns. For example:

```sql
TO_CHAR(FROM_TZ(CAST(rf.created AS TIMESTAMP), 'Europe/Ljubljana'),
        'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS valid_from,
TO_CHAR(FROM_TZ(CAST(rt.created AS TIMESTAMP), 'Europe/Ljubljana'),
        'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS valid_to,
TO_CHAR(FROM_TZ(CAST(COALESCE(rt.created, rf.created) AS TIMESTAMP), 'Europe/Ljubljana'),
        'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS date_change
```

The tool also parses ISO `DATE_CHANGE` text for its comparisons.

## Dry-run: compare `DATE_CHANGE`

This is the default. It deletes staging keys absent from KN, inserts absent staging keys, updates rows where KN is newer, and errors if staging is newer:

Dry-run fetches only the key and comparison field from KN (and the same two fields from staging), so it does not pull the full table payload. The displayed examples therefore contain only those fields.


```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --change-field DATE_CHANGE --dry-run


.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_dst_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_dst_pripis_podatki_h_kn.sql \
  --id-field dst_pripis_podatki_pk --change-field DATE_CHANGE --dry-run


.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_parc_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_parc_pripis_podatki_h_kn.sql \
  --id-field parc_pripis_podatki_pk --change-field DATE_CHANGE --dry-run
```

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_dst_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_dst_pripis_podatki_h_kn.sql \
  --id-field dst_pripis_podatki_pk --change-field DATE_CHANGE --resumable --apply


.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_parc_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_parc_pripis_podatki_h_kn.sql \
  --id-field parc_pripis_podatki_pk --change-field DATE_CHANGE --resumable --apply
```

## Dry-run: use only key membership

This still deletes staging keys absent from KN and inserts missing staging keys, but leaves all matching keys unchanged without comparing `DATE_CHANGE`:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --ignore-change-field --dry-run
```

After review, execute the same operation with `--apply`:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --apply
```

## Resumable apply

Add `--resumable` to use keyset pages and a locally persisted checkpoint. Each insert/update/delete page is committed independently; after a connection failure or interruption, rerun the identical command to continue from the last committed page:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --change-field DATE_CHANGE \
  --source-page-key id_pe_parc,jn_rev_num \
  --resumable --apply
```

`--source-page-key` is required for resumable runs. It is the native KN key (one or more integration-query columns) in the same order as the KN index; it controls Oracle paging only. `--id-field` remains the destination membership key. For `ev_pe_parc_h`, use `id_pe_parc,jn_rev_num`; for direct-ID tables, use their selected `*_pk` alias. The resumable run first pages KN key/date values and records every KN key in its own fingerprinted directory under `src/kn_to_stag_delta_with_delete/.state/`. It aborts before writes if it finds staging-newer values, then pages inserts/updates, and finally deletes staging keys absent from that persisted KN key index. It requires a single-column unique key on the configured staging key field and verifies that KN returns no duplicate keys before writing. Use `--page-size 1000` to tune page size and `--max-pages N` to stop cleanly for testing.

```sh
# Inspect progress without database credentials.
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --source-page-key id_pe_parc,jn_rev_num --resumable --status

# Deliberately discard only this integration's state and begin again.
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_pe_parc_h.sql \
  --id-field jn_pe_parc_pk --source-page-key id_pe_parc,jn_rev_num --resumable --restart
```

Resumable mode assumes the KN query is stable for the duration of the run. If the source query changes materially while a run is paused, use `--restart` to build a fresh key index.

Use `--schema another_schema` only when staging tables are not in `public`; use `--preview-limit` to change the number of displayed rows.
