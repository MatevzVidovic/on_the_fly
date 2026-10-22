-- USER-RUN WRITE SCRIPT. Run on PG_DATABASE_DATA after adding date_change_utc
-- as a date-time field through Lift. Stop the integration during the cutover.
-- This script was prepared, not executed by the audit.
BEGIN;
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF (SELECT count(*) FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'ev_pe_parc_h'
          AND column_name IN ('date_change', 'date_change_utc')
          AND data_type = 'timestamp without time zone') <> 2 THEN
        RAISE EXCEPTION 'Both date_change columns must exist and be timestamp without time zone';
    END IF;
END $$;

-- Existing rows are updated; do not INSERT new rows or subtract a fixed offset.
UPDATE public.ev_pe_parc_h
SET date_change_utc =
    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
WHERE date_change_utc IS NULL AND date_change IS NOT NULL;

-- Expect missing_utc = 0 and conversion_mismatches = 0.
SELECT
    count(*) FILTER (WHERE date_change IS NOT NULL AND date_change_utc IS NULL) AS missing_utc,
    count(*) FILTER (
        WHERE date_change IS NOT NULL
          AND date_change_utc IS DISTINCT FROM
              ((date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')
    ) AS conversion_mismatches
FROM public.ev_pe_parc_h;

-- Change to COMMIT after reviewing the checks; ROLLBACK is the preview default.
COMMIT;