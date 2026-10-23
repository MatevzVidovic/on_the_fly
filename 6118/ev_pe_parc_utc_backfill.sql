-- USER-RUN WRITE SCRIPT. Run on PG_DATABASE_DATA after adding date_change_utc
-- as a date-time field through Lift. Stop the integration during the cutover.
-- This script was prepared, not executed by the audit.
BEGIN;
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF (SELECT count(*) FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'ev_parcela_h'
          AND column_name IN ('date_change', 'date_change_utc')
          AND data_type = 'timestamp without time zone') <> 2 THEN
        RAISE EXCEPTION 'Both date_change columns must exist and be timestamp without time zone';
    END IF;
END $$;

-- Existing rows are updated; do not INSERT new rows or subtract a fixed offset.
UPDATE public.ev_parcela_h
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
FROM public.ev_parcela_h;

-- Change to COMMIT after reviewing the checks; ROLLBACK is the preview default.
COMMIT;


ROLLBACK;





SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    xact_start,
    clock_timestamp() - xact_start AS transaction_age,
    wait_event_type,
    wait_event,
    left(query, 500) AS current_or_last_query
FROM pg_stat_activity
WHERE datname = current_database()
  AND backend_type = 'client backend'
  AND pid <> pg_backend_pid()
ORDER BY xact_start NULLS LAST;



SELECT clock_timestamp() AS sampled_at,
       slot_name, slot_type, active, restart_lsn,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal
FROM pg_replication_slots
WHERE slot_name = 'barman';


SELECT archived_count, failed_count,
       last_archived_time, last_failed_time
FROM pg_stat_archiver;


SHOW archive_mode;




SHOW min_wal_size;
SHOW max_wal_size;
SHOW wal_keep_size;
SHOW checkpoint_timeout;