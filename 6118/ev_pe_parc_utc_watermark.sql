-- USER-RUN WRITE SCRIPT. Run on PG_DATABASE_SYSTEM after saving the new mapping,
-- with all runs stopped. Prepared, not executed by the audit.
-- Expected old value was read on 2026-10-22; re-read it before using this script.
BEGIN;
SET LOCAL lock_timeout = '5s';

UPDATE public.attribute_table_integrations i
SET last_changed_datetime =
    ((TIMESTAMP '2026-10-12 23:59:59.999' AT TIME ZONE 'Europe/Ljubljana')
      AT TIME ZONE 'UTC') - INTERVAL '3 hours'
WHERE i.id = '26856cbc-ae67-11f0-8b08-169cd02558fe'
  AND i.last_changed_datetime = TIMESTAMP '2026-10-12 23:59:59.999'
  AND i.is_full_sync = false
  AND i.use_changed_datetime_for_delta = true
  AND i.last_sync_start IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM public.attribute_field_integrations f
      JOIN public.attribute_fields a ON a.id = f.attribute_field_id
      WHERE f.attribute_table_integration_id = i.id AND f.api_id = true
        AND f.api_name = 'JN_PE_PARC_PK' AND a.name = 'jn_pe_parc_pk'
  )
  AND EXISTS (
      SELECT 1 FROM public.attribute_field_integrations f
      JOIN public.attribute_fields a ON a.id = f.attribute_field_id
      WHERE f.attribute_table_integration_id = i.id
      AND f.api_last_sync_field = true AND f.api_name = 'DATE_CHANGE_UTC'
        AND a.name = 'date_change_utc' AND a.type = 'date-time'
  )
  AND NOT EXISTS (
      SELECT 1 FROM public.attribute_field_integrations f
      WHERE f.attribute_table_integration_id = i.id
        AND f.api_last_sync_field = true AND f.api_name <> 'DATE_CHANGE_UTC'
  )
RETURNING i.id, i.last_changed_datetime, i.is_full_sync, i.use_changed_datetime_for_delta;

-- Expect UPDATE 1 and 2026-10-12 18:59:59.999.
-- UPDATE 0 means a precondition changed: inspect it; do not remove the guards.
-- Change to COMMIT after reviewing the result; ROLLBACK is the preview default.
ROLLBACK;
