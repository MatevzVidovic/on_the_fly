-- Staging sandbox only: the original UPDATE, adapted solely to the clone.
-- Original ev_pe_parc_utc_backfill.sql is deliberately unchanged.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '20s';
UPDATE wal6118_bench.baseline
SET date_change_utc =
    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
COMMIT;
