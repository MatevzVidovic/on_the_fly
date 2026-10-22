# Checklist: migrate a Lift Oracle delta integration to UTC

Use for existing **Ljubljana-local, timezone-less** change timestamps. Replace the example table/field names and source expression below.

- [ ] Pause scheduling; wait for running jobs to finish. Confirm `APP_TIMEZONE=UTC`.
- [ ] Save the original SQL, mappings, `last_changed_datetime`, and `last_sync_start`.
- [ ] Add a new **date-time** field through Lift, e.g. `date_change_utc`. Keep the old field.
- [ ] Backfill existing rows in the **data DB**; both columns must be `timestamp without time zone`:

  ```sql
  UPDATE schema_name.table_name
  SET date_change_utc =
      (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
  WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
  ```

- [ ] Add a UTC projection to the **Oracle query**, preserving the original change-time expression:

  ```sql
  FROM_TZ(CAST(source_change_expression AS TIMESTAMP), 'Europe/Ljubljana')
      AT TIME ZONE 'UTC' AS date_change_utc
  ```

- [ ] Preview through Lift: check `+00:00` and compare a known row with the backfill.
- [ ] Map the new source field to the new target field. Make it the **only DATE_CHANGED** field; keep the old field's ordinary mapping.
- [ ] Save explicitly with `is_full_sync=false`, `use_changed_datetime_for_delta=true`, and the **existing ID mapping unchanged**. Omitted API flags can default to full sync or clear the ID flag.
- [ ] In the **system DB**, set this integration's watermark to the **saved original** local watermark converted to UTC, minus three hours:

  ```sql
  ((TIMESTAMP 'saved_original_watermark' AT TIME ZONE 'Europe/Ljubljana')
      AT TIME ZONE 'UTC') - INTERVAL '3 hours'
  ```

  Apply once, scoped by integration ID. Never clear the watermark or `last_sync_start`.
- [ ] Re-read the saved flags, ID/date mappings, watermark, and non-null `last_sync_start`.
- [ ] Start one **fresh delta run**, not an old full-sync retry. Verify “Performing delta synchronization...”, preserved row IDs, UTC values, and watermark advancement; then resume scheduling.

Prefer `AT TIME ZONE 'UTC'` over bare `SYS_EXTRACT_UTC`: Lift compares against timezone-aware Oracle bounds. [Code verification](lift_behavior_verification.md).

The overlap does **not** repair older missing rows. Backfilling ambiguous autumn clock-change times may require source reconciliation.
