# KN to staging delta sync with deletes

Create `src/kn_to_stag_delta_with_delete/.env` from `.env.example`. The source is Oracle KN (schema `EV` in the integration SQL); the destination is PostgreSQL database `fmp_data_gurs`, schema `public` by default.

If KN enforces Oracle Native Network Encryption/Data Integrity, install Oracle Instant Client and set `KN_ORACLE_CLIENT_LIB_DIR` to its library directory in `.env`. This enables python-oracledb Thick mode, which KN requires for that security setting.

Pass a staging table name and a file containing the integration `SELECT`. The query must select all insertable destination columns, use destination-compatible aliases, include a non-null unique membership key, and return no duplicate keys. `--id-field` is required and must name a source/staging field such as `jn_pe_parc_pk`; it cannot be LIFT's generated `id`. For every execution, the utility deletes staging keys absent from KN, then inserts KN keys absent from staging; matching keys are compared and may be updated unless `--ignore-change-field` is used.

## Incremental insert/update-only (`--only-new`)

The normal mode is a complete reconciliation: it scans KN membership and deletes staging rows absent from KN. `--only-new` is the cheaper incremental alternative. It fetches only KN rows whose source watermark is at or after the persisted high-water timestamp, inserts missing keys, updates KN-newer matching rows, and **never deletes** staging rows.

`--only-new --apply` requires `--resumable` and `--source-page-key`; `date_change` must be selected as a native Oracle `TIMESTAMP`. The loader freezes the changed source window, reads each selected row once in watermark/page-key order, persists its selected payload in local SQLite, then applies those local rows to PostgreSQL in resumable batches. This avoids rerunning the arbitrary Oracle integration query with a large `OR` predicate per batch. The page key breaks timestamp ties; no loader-only columns are added to integration SQL and no separate full-window count query runs. KN is trusted to provide non-null, unique membership IDs and `(watermark, source-page-key...)` tuples.

The local `source_keys.sqlite3` file temporarily needs roughly the size of the changed payload plus SQLite overhead; ensure that free disk is available. It is deleted when the next completed window opens. An older active `--only-new` checkpoint must be discarded once with `--restart`; its completed high-water mark is retained.

For a KN composite primary key, keep the destination's synthetic concatenated `*_pk` as `--id-field`, but also select the raw KN key columns under normal aliases and pass those aliases to `--source-page-key` in the exact KN index order. Those extra aliases are local cursor/order and checkpoint values only; they are never inserted into PostgreSQL. Direct-ID integrations keep using their `*_pk` alias for both options.

On the first run, the completed watermark is the literal `MAX(date_change)` already in staging; an empty table imports all source rows. Every later window starts two hours before its completed watermark, safely replaying equal timestamps and the DST repeated hour. At the start of each invocation the loader freezes the greatest source `(watermark, native key...)` tuple and will not read past it. The completed watermark advances only after that window completes. `--restart` discards an incomplete window but retains the completed watermark.

Example (there are no deletes in this mode):

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_dst_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_dst_pripis_podatki_h_kn.sql \
  --id-field dst_pripis_podatki_pk \
  --source-page-key dst_pripis_podatki_pk \
  --change-field DATE_CHANGE \
  --only-new --resumable --apply --auto-page-size

.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_parc_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_parc_pripis_podatki_h_kn.sql \
  --id-field parc_pripis_podatki_pk \
  --source-page-key parc_pripis_podatki_pk \
  --change-field DATE_CHANGE \
  --only-new --resumable --apply --auto-page-size
```

Use a periodic normal full reconciliation as well: `--only-new` cannot discover KN deletions, source corrections with an unchanged/backdated `DATE_CHANGE`, or data outside its watermark contract.

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
  --id-field dst_pripis_podatki_pk \
  --source-page-key dst_pripis_podatki_pk \
  --change-field DATE_CHANGE \
  --ignore-not-null-constraint \
  --resumable --apply --page-size 20000 --auto-page-size

.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_parc_pripis_podatki_h \
  --integration-sql ./src/kn_to_stag_delta_with_delete/ev_parc_pripis_podatki_h_kn.sql \
  --id-field parc_pripis_podatki_pk \
  --source-page-key parc_pripis_podatki_pk \
  --change-field DATE_CHANGE \
  --ignore-not-null-constraint \
  --resumable --apply --page-size 20000 --auto-page-size
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
  --resumable --apply --auto-page-size
```

`--source-page-key` is required for resumable runs. It is one or more normal stored integration columns in the same order as an all-ascending KN index; it controls Oracle paging only. `--id-field` remains the destination membership key. For `ev_pe_parc_h`, use `id_pe_parc,jn_rev_num`; for the two direct-ID examples, use their selected `*_pripis_podatki_pk` field.

Before writing, resumable mode validates that both the KN membership ID and the complete native page tuple are non-null and unique. The staging membership column normally requires a non-partial unique index and a `NOT NULL` constraint. The unique index is the standard data contract and lookup index: it is required unless the exceptional `--ignore-unique-constraint` operator override is supplied. If existing staging values are known non-null but the column metadata is still nullable, use `--ignore-not-null-constraint` for a normal full reconciliation. The two overrides are independent; neither bypasses the other check. `--only-new` never needs the staging `NOT NULL` check, but still requires uniqueness by default. The loader stores typed ID/page-key values and (when enabled) `DATE_CHANGE` in a fingerprinted local state directory. After inserts and updates, it fully re-scans KN and verifies that the same IDs, page tuples, and change values are still present before it starts deleting staging-only rows. A changed source leaves the run in a terminal `source_changed` state; use `--restart` to begin again. The default initial page size and cap are both `50000`; use `--page-size N` to choose a smaller/larger starting size and `--page-size-cap N` to enforce a maximum for every resumable page, including learned auto sizes. Use `--max-pages N` to stop cleanly for testing.

Add `--auto-page-size` to make size-relevant Oracle page-read failures (fetch/query timeout, array/resource, or memory pressure) retry the same checkpoint cursor at one-third of the previous size. Connection, SSH-tunnel, network, and lost-contact failures keep the same size and use ordinary transient retry. The learned size is saved in `src/kn_to_stag_delta_with_delete/.auto_page_sizes/`, keyed by the table and integration query, and is reused by future matching auto-sized runs, including after `--restart`. You may add the flag to an already-checkpointed run without discarding its progress. The loader prints separate preflight/apply/verify/delete page numbers, page size, throughput, and phase elapsed time. Once preflight establishes the source total, apply and verify also print a simple ETA. As a conservative protection against sustained slowdown, it safely pauses after checkpointing when three full pages are each at least twice as slow per row as the earlier median; rerun the identical command to continue after investigating.

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

Resumable mode requires the KN query to remain stable from preflight through the final staging delete, including pauses and resumes. The final verification detects changes before deletion but is not an Oracle SCN/flashback snapshot; if KN may change during the run, use `--restart` to build a fresh key index. Each active invocation holds a PostgreSQL advisory lock for the target table. Other staging writers must honor that lock (or the table must otherwise be quiescent); advisory locks cannot stop unrelated writers that ignore them, and they are released between `--max-pages` runs or after a crash. Keep staging writers quiescent for the complete logical run when resuming. `DATE_CHANGE` must change whenever imported payload data changes, because it is the source-version value verified by the loader.

Use `--schema another_schema` only when staging tables are not in `public`; use `--preview-limit` to change the number of displayed rows.
