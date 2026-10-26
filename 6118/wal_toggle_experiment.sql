-- Optional evidence experiment, ISOLATED CLONE ONLY. Not a migration strategy.
-- Measure EVERY step separately; SET LOGGED is expected to generate WAL.
-- Run each command in autocommit mode, not in an outer BEGIN/COMMIT block.
ALTER TABLE wal6118_bench.logging_toggle SET UNLOGGED;
UPDATE wal6118_bench.logging_toggle
SET date_change_utc =
    (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
WHERE date_change_utc IS NULL AND date_change IS NOT NULL;
ALTER TABLE wal6118_bench.logging_toggle SET LOGGED;
