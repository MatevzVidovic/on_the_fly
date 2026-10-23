# Checklist: migrate a Lift Oracle delta integration to UTC

Use for existing **Ljubljana-local, timezone-less** change timestamps. Replace the example table/field names and source expression below.



- [ ] Add a new **date-time** field through Lift, e.g. `date_change_utc`. Keep the old field.

- [ ] In the **system DB**, set this integration's watermark to the **saved original** local watermark converted to UTC, minus three hours:

  ```sql
  ((TIMESTAMP 'saved_original_watermark' AT TIME ZONE 'Europe/Ljubljana')
      AT TIME ZONE 'UTC') - INTERVAL '3 hours'
  ```



- [ ] Add a UTC projection to the **Oracle query**, preserving the original change-time expression:

  ```sql
  FROM_TZ(CAST(source_change_expression AS TIMESTAMP), 'Europe/Ljubljana')
      AT TIME ZONE 'UTC' AS date_change_utc
  ```

- [ ] Map the new source field to the new target field. Make it the **only DATE_CHANGED** field; keep the old field's ordinary mapping.




- [ ] Backfill existing rows in the **data DB**; both columns must be `timestamp without time zone`:

  ```sql
  UPDATE schema_name.table_name
  SET date_change_utc =
      (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
  WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
  ```

- [ ] Preview through Lift: check `+00:00`

- [ ] Run delta integ.




Prefer `AT TIME ZONE 'UTC'` over bare `SYS_EXTRACT_UTC`: Lift compares against timezone-aware Oracle bounds. [Code verification](lift_behavior_verification.md).

The overlap does **not** repair older missing rows. Backfilling ambiguous autumn clock-change times may require source reconciliation.
