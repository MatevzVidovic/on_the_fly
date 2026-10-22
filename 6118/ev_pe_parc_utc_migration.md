# EV H Pe parc: UTC watermark cutover

Integration: `pnreos_pe_parc_ev` (`26856cbc-ae67-11f0-8b08-169cd02558fe`), target `public.ev_pe_parc_h`.

Run the write scripts with an account permitted to update the respective tables. The supplied audit account has no table-level UPDATE permission on either table, and no column-level UPDATE permission on the watermark. The scripts were not executed; even a non-executing `EXPLAIN UPDATE` was rejected for permissions.

## Process

1. Stop scheduling and wait for any running integration to finish. Confirm deployed **`APP_TIMEZONE=UTC`**: Lift reparses its timezone-less watermark using the PHP app timezone. Save the integration SQL, field mappings and **original** `last_changed_datetime`. On 2026-10-22 the schedule was `none`, status `PROCESSED`, and watermark `2026-10-12 23:59:59.999`; recheck before applying.
2. Add `date_change_utc` as a **date-time field through Lift**, so both application metadata and the physical column exist. Keep `date_change`, `valid_from`, `valid_to`, the integration ID, and the `JN_PE_PARC_PK → jn_pe_parc_pk` ID mapping.
3. Backfill existing target rows with [the PostgreSQL UPDATE script](ev_pe_parc_utc_backfill.sql), on **PG_DATABASE_DATA**. The script checks that both columns are `timestamp without time zone`. This is an UPDATE, not an INSERT:

   ```sql
   UPDATE public.ev_pe_parc_h
   SET date_change_utc =
       (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
   WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
   ```

   The script defaults to `ROLLBACK`; inspect its validation results, then use `COMMIT` to persist. Do not backfill by subtracting a fixed offset: Ljubljana is UTC+1 in winter and UTC+2 in summer. An ambiguous repeated autumn hour cannot be uniquely reconstructed from a timezone-less timestamp; reconcile those rows against the source if exact historical instants matter.
4. Add this projection to the existing Oracle query; keep the original `date_change` projection too. [Complete source query](ev_pe_parc_utc_source.sql):

   ```sql
   FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')
       AT TIME ZONE 'UTC' AS date_change_utc
   ```

5. Preview the Oracle query through Lift: the new value should carry **`+00:00`** and match the backfilled UTC value for a known row. Map source **`DATE_CHANGE_UTC`** to target **`date_change_utc`**. Make it the sole **DATE_CHANGED** mapping, clearing that flag from `DATE_CHANGE` while retaining its ordinary mapping. Explicitly save **`is_full_sync = false`** and **`use_changed_datetime_for_delta = true`**, preserving the existing ID mapping. An API save that omits these booleans defaults to full sync / disabled changed-time delta; a field save that omits the ID flag can clear it. Save all configuration before setting the watermark.
6. Convert the **saved original** watermark from Ljubljana time to UTC, then subtract a three-hour overlap. Use [the guarded watermark script](ev_pe_parc_utc_watermark.sql) on **PG_DATABASE_SYSTEM**. With the observed value, the result is **`2026-10-12 18:59:59.999`**: `23:59 local → 21:59 UTC → 18:59 UTC`. This is deliberately more overlap than simply subtracting three hours from the unconverted value. Never clear the watermark or apply the conversion twice. The script defaults to `ROLLBACK`; require `UPDATE 1`, review, then use `COMMIT`.
7. Re-read the saved configuration: exactly one DATE_CHANGED mapping (`DATE_CHANGE_UTC`), unchanged ID mapping, `is_full_sync = false`, `use_changed_datetime_for_delta = true`, the intended non-null watermark, and the original **non-null `last_sync_start`**. Start **one fresh ordinary delta run**, not a retry of an old full-sync workflow. Check logs for **“Performing delta synchronization...”**, existing row IDs, new UTC field values, and that the stored watermark advances in UTC. Resume scheduling after validation.

## Why use `AT TIME ZONE 'UTC'`?

Use it here. Bare `SYS_EXTRACT_UTC(...)` returns a timezone-less UTC timestamp, whereas `AT TIME ZONE 'UTC'` preserves timezone information. Lift's Oracle delta filter uses `TO_TIMESTAMP_TZ` bounds. Oracle interprets a timezone-less timestamp using the **Oracle session timezone** when comparing it with a timezone-aware value, and Lift does not guarantee that session timezone is UTC. Keeping the UTC timezone avoids that dependency. `FROM_TZ(SYS_EXTRACT_UTC(...), 'UTC')` is another explicit, timezone-aware option, but is longer.

Sources: [Oracle conversion/comparison rules](https://docs.oracle.com/en/database/oracle/oracle-database/19/nlspg/datetime-data-types-and-time-zone-support.html), [Oracle datetime expressions](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/Datetime-Expressions.html), [PostgreSQL AT TIME ZONE](https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-ZONECONVERT).

## What this does and does not verify

In the inspected Lift code, changing SQL or the DATE_CHANGED mapping does not itself clear the watermark or select full sync. Full sync is selected if `is_full_sync` is true, `last_sync_start` is empty, or a retried workflow carries a full-sync checkpoint. Preserve the guards above. Matching the same integration key updates the existing row and preserves its ID; use one run at a time.

The read-only database check confirmed the old column is `timestamp without time zone`, the new field does not yet exist, and the current ID/change mappings match the names above. Winter/summer conversion examples and five existing-row conversion previews were checked without writes. See [Lift source verification](lift_behavior_verification.md) for the save/run paths and their limits; local source inspection cannot certify the deployed version or substitute for checking the first run.

This cutover prevents the timezone error going forward. A recent three-hour overlap **does not repair historical gaps from earlier runs**; those require a separate reconciliation/backfill.

No database changes or integration runs were performed while preparing this procedure.
