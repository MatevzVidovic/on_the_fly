-- One independently committed batch. This DOES generate WAL.
-- Invoke with psql variables: target_schema, target_table, last_id, batch_size.
-- Keep this separate from the unchanged original backfill SQL.
-- The caller must pause/check WAL and disk budgets between invocations.
-- Requires an indexed UUID id, stopped competing writers and autocommit mode.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '20s';

WITH picked AS MATERIALIZED (
    SELECT id
    FROM :"target_schema".:"target_table"
    WHERE (NULLIF(:'last_id', '')::uuid IS NULL
           OR id > NULLIF(:'last_id', '')::uuid)
      AND date_change_utc IS NULL AND date_change IS NOT NULL
    ORDER BY id
    LIMIT :batch_size
    FOR UPDATE
), updated AS (
    UPDATE :"target_schema".:"target_table" t
    SET date_change_utc =
        (t.date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
    FROM picked p
    WHERE t.id = p.id
    RETURNING t.id
)
SELECT jsonb_build_object(
    'rows', count(*),
    'last_id', (array_agg(id ORDER BY id DESC))[1]::text
)
FROM updated;

COMMIT;
