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

Use `--schema another_schema` only when staging tables are not in `public`; use `--preview-limit` to change the number of displayed rows.
